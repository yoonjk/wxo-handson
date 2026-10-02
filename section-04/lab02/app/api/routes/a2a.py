"""구매 승인 애플리케이션용 Google A2A 엔드포인트입니다.

이 모듈은 업무 로직을 직접 구현하지 않고 A2A 어댑터 역할만 수행합니다.
A2A JSON-RPC 요청을 기존 PurchaseService 호출로 변환하므로 REST API와
A2A가 동일한 업무 규칙, SQLAlchemy 세션, MySQL 트랜잭션을 공유합니다.

지원 기능
---------
* 구매 요청 생성
* 구매 요청 단건 조회
* 구매 요청 전체 목록 조회
* 구매 요청 승인 또는 반려
* 메모리 기반 A2A Task 조회 및 취소

main.py에서 이 라우터를 ``/purchase`` prefix로 등록하는 것을 전제로 합니다.
외부에서 접근하는 최종 주소는 다음과 같습니다.

* POST http://nexweb.ddnsgeek.com/purchase/a2a
* GET  http://nexweb.ddnsgeek.com/purchase/.well-known/agent-card.json
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.connection import get_db
from app.repositories.product_repository import ProductRepository
from app.repositories.purchase_repository import PurchaseRepository
from app.schemas.purchase import (
    ApprovalStatus,
    PurchaseRequestCreate,
    PurchaseStatusUpdate,
)
from app.services.purchase_service import (
    InvalidStatusTransitionError,
    PurchaseNotFoundError,
    PurchaseService,
)


router = APIRouter(tags=["A2A"])
settings = get_settings()

# 실습을 위해 단순한 프로세스 메모리 딕셔너리를 사용합니다.
# 애플리케이션이 재시작되면 Task가 사라지므로 운영환경에서는 Redis와 같은
# 공유 저장소에 Task를 저장해야 합니다.
TASKS: dict[str, dict[str, Any]] = {}


def now() -> str:
    """A2A Task 응답에 사용할 RFC 3339 형식의 UTC 시각을 반환합니다."""

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def agent_card() -> dict[str, Any]:
    """A2A 클라이언트에 제공할 Agent Card를 생성합니다.

    ``PUBLIC_API_URL``에는 A2A 엔드포인트 자체가 아니라 외부에서 접근할
    수 있는 애플리케이션 기본 URL을 설정해야 합니다.
    기본 Nginx prefix를 사용하는 경우 값은 다음과 같습니다.
    ``http://nexweb.ddnsgeek.com/purchase``
    """

    public_base_url = settings.public_api_url.rstrip("/")

    return {
        "name": "Purchase Approval A2A Agent",
        "description": "Creates purchase requests and records approval results in MySQL.",
        "url": f"{public_base_url}/a2a",
        "version": settings.app_version,
        "protocolVersion": "0.3.0",
        "preferredTransport": "JSONRPC",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text", "application/json"],
        "defaultOutputModes": ["text", "application/json"],
        "skills": [
            {
                "id": "purchase-approval",
                "name": "Purchase approval",
                "description": (
                    "Creates purchase requests, lists requests, and saves "
                    "APPROVED/REJECTED results."
                ),
                "tags": ["purchase", "approval", "mysql"],
                "examples": [
                    "노트북 구매 요청을 생성해줘",
                    "구매 승인 요청 목록을 조회해줘",
                    "구매 요청 1번을 IT_MANAGER 권한으로 승인해줘",
                ],
                "inputModes": ["text", "application/json"],
                "outputModes": ["text", "application/json"],
            }
        ],
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
        "security": [{"bearerAuth": []}],
    }


def rpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    """성공한 JSON-RPC 2.0 응답을 생성합니다."""

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    """JSON-RPC 2.0 업무 오류 응답을 생성합니다."""

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def text_message(text: str, role: str) -> dict[str, Any]:
    """A2A Task history에 사용할 메시지를 생성합니다.

    A2A Task 모델에서는 ``kind: message``가 필요합니다. 이 값을 생략하면
    HTTP 응답이 200이어도 Orchestrate의 등록 또는 호출이 실패할 수 있습니다.
    """

    return {
        "kind": "message",
        "messageId": str(uuid.uuid4()),
        "role": role,
        "parts": [{"kind": "text", "text": text}],
    }


def extract_input_data(params: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """A2A 메시지에서 구조화된 데이터와 텍스트를 추출합니다.

    지원하는 입력 예시는 다음과 같습니다.

    * data part: ``{"action": "list_requests"}``
    * JSON text: ``{"request_id": 3}``
    * 자연어: ``구매 승인 요청 목록을 조회해줘``

    자연어는 별도로 보관합니다. 그래야 목록 요청을 구매 요청의
    ``reason``으로 잘못 처리하여 ``total_amount`` 누락 오류가 발생하지 않습니다.
    """

    message = params.get("message") or {}
    if not isinstance(message, dict):
        return {}, ""

    values: dict[str, Any] = {}
    text_values: list[str] = []

    for part in message.get("parts", []):
        if not isinstance(part, dict):
            continue

        if part.get("kind") == "data" and isinstance(part.get("data"), dict):
            values.update(part["data"])

        if part.get("kind") == "text" and isinstance(part.get("text"), str):
            text_values.append(part["text"])

    request_text = "\n".join(text_values).strip()

    # text part 안에 data part 대신 JSON 객체가 전달될 수도 있습니다.
    if request_text:
        try:
            parsed = json.loads(request_text)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict):
            values.update(parsed)

    return values, request_text


def extract_request_id(request_text: str) -> int | None:
    """자연어 문장에서 구매 요청 ID를 추출합니다.

    예를 들어 다음 표현을 모두 지원합니다.

    * ``구매 요청 3번을 조회해줘``
    * ``구매 요청 번호 3 조회``
    * ``purchase request 3 조회``
    """

    patterns = (
        r"(?:구매\s*)?(?:승인\s*)?(?:요청|건)\s*(?:번호\s*)?(\d+)\s*번?",
        r"(?:purchase\s+request|request)\s*#?\s*(\d+)\b",
    )

    for pattern in patterns:
        match = re.search(pattern, request_text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def serialise_purchase(purchase: Any) -> dict[str, Any]:
    """SQLAlchemy 모델을 JSON으로 반환할 수 있는 artifact 데이터로 변환합니다."""

    values = {
        column.name: getattr(purchase, column.name)
        for column in purchase.__table__.columns
    }

    for key, value in values.items():
        if isinstance(value, datetime):
            values[key] = value.isoformat()
        elif isinstance(value, Decimal):
            values[key] = str(value)

    return values


def task_status_message(text: str) -> dict[str, Any]:
    """Task status에 넣을 최종 응답 메시지를 생성합니다.

    history에만 응답 문장을 넣으면 일부 A2A 클라이언트가 대화 화면에
    표시할 텍스트를 찾지 못할 수 있습니다. 따라서 완료 상태의 Task에는
    동일한 최종 응답을 ``status.message``에도 넣습니다.
    """

    return text_message(text, "agent")


def make_list_message(request_text: str, purchases: list[Any]) -> dict[str, Any]:
    """목록 조회처럼 즉시 완료되는 작업의 직접 Message 응답을 생성합니다.

    watsonx Orchestrate 일부 화면에서는 Task의 artifact를 대화 메시지로
    변환하지 못할 수 있습니다. 목록 조회는 동기 작업이므로 최종 텍스트와
    구조화된 목록 데이터를 하나의 Message에 함께 넣어 반환합니다.
    """

    items = [serialise_purchase(purchase) for purchase in purchases]
    response_text = f"구매 승인 요청 목록 조회 결과입니다. 총 {len(items)}건입니다."

    return {
        "kind": "message",
        "messageId": str(uuid.uuid4()),
        "role": "agent",
        "parts": [
            {"kind": "text", "text": response_text},
            {
                "kind": "data",
                "data": {"count": len(items), "items": items},
            },
        ],
    }


def make_purchase_message(purchase: Any) -> dict[str, Any]:
    """단건 조회·생성·승인 결과를 직접 Message로 반환합니다."""

    purchase_data = serialise_purchase(purchase)
    response_text = f"구매 요청 {purchase.id}번의 현재 상태는 {purchase.status}입니다."

    return {
        "kind": "message",
        "messageId": str(uuid.uuid4()),
        "role": "agent",
        "parts": [
            {"kind": "text", "text": response_text},
            {"kind": "data", "data": purchase_data},
        ],
    }


def make_task(request_text: str, purchase: Any) -> dict[str, Any]:
    """구매 요청 한 건에 대한 완료 상태의 A2A Task를 생성합니다."""

    response_text = f"구매 요청 {purchase.id}번의 현재 상태는 {purchase.status}입니다."

    task = {
        "kind": "task",
        "id": str(uuid.uuid4()),
        "contextId": str(uuid.uuid4()),
        "status": {
            "state": "completed",
            "message": task_status_message(response_text),
            "timestamp": now(),
        },
        "history": [
            text_message(request_text, "user"),
            task_status_message(response_text),
        ],
        "artifacts": [
            {
                "artifactId": str(uuid.uuid4()),
                "name": "purchase-request",
                "parts": [
                    {
                        "kind": "data",
                        "data": serialise_purchase(purchase),
                    }
                ],
            }
        ],
    }

    TASKS[task["id"]] = task
    return task


def is_list_request(values: dict[str, Any], request_text: str) -> bool:
    """구조화된 목록 요청과 자연어 목록 요청을 판별합니다."""

    # 특정 request_id가 있으면 목록이 아니라 단건 조회 또는 상태 변경입니다.
    if values.get("request_id") is not None:
        return False

    action = str(values.get("action", "")).strip().lower()
    if action in {"list_requests", "list_purchases", "get_requests"}:
        return True

    normalized = request_text.lower()
    return any(keyword in normalized for keyword in ("목록", "전체", "모든", "list", "show all"))


def verify_bearer_token(authorization: str | None) -> None:
    """Authorization 헤더를 ``A2A_BEARER_TOKEN``과 비교하여 검증합니다.

    현재 실습용 Connection에는 고정 Bearer Token 비교 방식이 적합합니다.
    운영환경에서는 issuer, audience, 만료시간, scope를 포함하는
    Keycloak/OIDC JWT 검증 방식으로 교체해야 합니다.
    """

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is required")

    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator:
        raise HTTPException(status_code=401, detail="Bearer token is required")

    token = token.strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token is empty")

    expected = settings.a2a_bearer_token.get_secret_value()
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="Invalid Bearer token")


@router.get("/.well-known/agent-card.json", include_in_schema=False)
@router.get("/.well-known/agent.json", include_in_schema=False)
@router.get("/agent-card", include_in_schema=False)
def get_agent_card() -> dict[str, Any]:
    """GET 요청으로 Agent Card를 반환합니다."""

    return agent_card()


@router.post("/a2a", include_in_schema=False)
async def a2a_rpc(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    """A2A JSON-RPC 요청을 처리하고 PurchaseService에 업무를 위임합니다."""

    verify_bearer_token(authorization)
    body = await request.json()
    request_id = body.get("id") if isinstance(body, dict) else None

    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        return JSONResponse(
            rpc_error(request_id, -32600, "jsonrpc must be 2.0")
        )

    params = body.get("params") or {}
    if not isinstance(params, dict):
        return JSONResponse(rpc_error(request_id, -32602, "params must be an object"))

    method = body.get("method")
    service = PurchaseService(
        repository=PurchaseRepository(db),
        product_repository=ProductRepository(db),
    )

    try:
        if method in {"message/send", "tasks/send"}:
            values, request_text = extract_input_data(params)

            # Orchestrate가 자연어로 단건 조회를 전달하는 경우에도
            # request_id를 추출하여 목록 조회와 구분합니다.
            if values.get("request_id") is None and request_text:
                request_number = extract_request_id(request_text)
                if request_number is not None:
                    values["request_id"] = request_number

            if is_list_request(values, request_text):
                purchases = service.list_all()
                return JSONResponse(
                    rpc_result(
                        request_id,
                        make_list_message(
                            request_text or json.dumps(values, ensure_ascii=False),
                            purchases,
                        ),
                    )
                )

            request_number = values.get("request_id")
            approval = values.get("approval") or values.get("status")

            if request_number is not None and approval:
                purchase = service.update_status(
                    int(request_number),
                    PurchaseStatusUpdate(
                        status=ApprovalStatus(str(approval).upper()),
                        comment=values.get("approval_comment") or values.get("comment"),
                        approver_role=values.get("approver_role", "A2A_AGENT"),
                    ),
                )
            elif request_number is not None:
                purchase = service.get(int(request_number))
            else:
                if "total_amount" not in values:
                    return JSONResponse(
                        rpc_error(
                            request_id,
                            -32602,
                            "total_amount is required when creating a purchase request",
                        )
                    )
                if not values.get("purchase_type"):
                    return JSONResponse(
                        rpc_error(
                            request_id,
                            -32602,
                            "purchase_type (product SKU) is required when creating a purchase request",
                        )
                    )

                purchase = service.create(
                    PurchaseRequestCreate(
                        purchase_type=values["purchase_type"],
                        requester=values.get("requester", "A2A_USER"),
                        total_amount=values["total_amount"],
                        reason=values.get("reason"),
                    )
                )

            return JSONResponse(
                rpc_result(request_id, make_purchase_message(purchase))
            )

        if method in {"tasks/get", "task/get"}:
            task = TASKS.get(params.get("id") or params.get("taskId"))
            if task is None:
                return JSONResponse(
                    rpc_error(request_id, -32001, "Task not found")
                )
            return JSONResponse(rpc_result(request_id, task))

        if method in {"tasks/cancel", "task/cancel"}:
            task = TASKS.get(params.get("id") or params.get("taskId"))
            if task is None:
                return JSONResponse(
                    rpc_error(request_id, -32001, "Task not found")
                )

            task["status"] = {"state": "canceled", "timestamp": now()}
            return JSONResponse(rpc_result(request_id, task))

        return JSONResponse(
            rpc_error(request_id, -32601, f"Method not found: {method}")
        )

    except (KeyError, ValueError, TypeError) as exc:
        return JSONResponse(rpc_error(request_id, -32602, str(exc)))
    except PurchaseNotFoundError as exc:
        return JSONResponse(rpc_error(request_id, -32004, str(exc)))
    except InvalidStatusTransitionError as exc:
        return JSONResponse(rpc_error(request_id, -32009, str(exc)))
