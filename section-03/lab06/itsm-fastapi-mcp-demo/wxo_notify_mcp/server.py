"""watsonx Orchestrate(SaaS) 전용 Bob 공지 발송 + SR 조회·발행 MCP 서버 (독립 실행형).

- itsm_event_mcp(server.py)나 app 패키지를 import하지 않습니다. 이 파일 하나와 자체 .env만으로 동작하므로
  itsm_event_mcp와 다른 서버/컨테이너에 배포할 수 있습니다.
- 외부 연결은 ITSM FastAPI(HTTP) 하나뿐입니다. FastAPI가 outbox에 기록하고 itsm_event_mcp에 알리면,
  Bob Notifier는 기존 /events SSE로 그대로 수신합니다.
- 도구는 네 개만 노출합니다: send_notification(공지 발송), get_service_request(SR 상세 조회, 읽기 전용),
  list_service_requests(SR 목록 요약 조회, 읽기 전용),
  create_service_request(SR 발행. 담당자 사번이 있으면 FastAPI가 Bob 알림 이벤트를 자동 기록).
  ITSM FastAPI를 외부에 공개하지 않고 이 서버만 공개하며, 인증은 wxO 전용 Bearer token으로 분리합니다.

필요 패키지: mcp(Python SDK 2.2+), httpx, pydantic, python-dotenv, uvicorn, starlette
"""

import asyncio
import hashlib
import re
import hmac
import json
import logging
import os
import time
from typing import Annotated, Literal

import httpx
import uvicorn
from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

load_dotenv()
logger = logging.getLogger("wxo_notify_mcp")
logging.basicConfig(level=logging.INFO)

# 이 서버 전용 설정. itsm_event_mcp와 다른 호스트라면 FastAPI 주소를 네트워크 주소로 지정합니다.
API_BASE = os.getenv("WXO_NOTIFY_ITSM_API_BASE_URL", "http://127.0.0.1:8030").rstrip("/")
API_TOKEN = os.getenv("WXO_NOTIFY_ITSM_API_TOKEN", "replace-with-itsm-api-token")
API_TIMEOUT = float(os.getenv("WXO_NOTIFY_ITSM_API_TIMEOUT", "10"))
WXO_TOKEN = os.getenv("WXO_NOTIFY_MCP_BEARER_TOKEN", "replace-with-a-wxo-notify-token")
DEDUP_WINDOW_SECONDS = max(60, int(os.getenv("WXO_NOTIFY_DEDUP_WINDOW_SECONDS", "600")))


# ---------------------------------------------------------------------------
# FastAPI /service-request-events/notifications 요청 스키마 (자체 정의)
# server.py의 PublishMessageRequest와 같은 계약입니다. 최종 검증은 FastAPI가 합니다.
# ---------------------------------------------------------------------------
class NotificationLink(BaseModel):
    """공지 첨부 링크. FastAPI app/schemas/service_request_event.py의 NotificationLink와 같은 계약입니다."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120, description="링크 표시 이름")
    url: str = Field(min_length=1, max_length=2048, description="자료 URL (http/https)")


class PublishMessageRequest(BaseModel):
    target_type: Literal["all", "group", "user"]
    request_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=200)
    target_group: str | None = Field(default=None, max_length=64)
    employee_no: str | None = Field(default=None, max_length=32)
    employee_nos: list[str] | None = Field(default=None, min_length=1, max_length=100)
    links: list[NotificationLink] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_type == "group" and not self.target_group:
            raise ValueError("group 발행에는 target_group이 필요합니다.")
        if self.target_type != "group" and self.target_group is not None:
            raise ValueError("target_group은 group 발행에만 지정하세요.")
        if self.target_type == "user" and not self.employee_no and not self.employee_nos:
            raise ValueError("user 발행에는 employee_nos가 필요합니다.")
        if self.target_type != "user" and (self.employee_no is not None or self.employee_nos is not None):
            raise ValueError("employee_nos는 user 발행에만 지정하세요.")
        if self.employee_nos and len(set(self.employee_nos)) != len(self.employee_nos):
            raise ValueError("employee_nos 중복 값은 허용하지 않습니다.")
        for link in self.links:
            if not link.url.startswith(("http://", "https://")):
                raise ValueError(f"링크 URL은 http(s)여야 합니다: {link.url}")
        return self


async def _publish_notification(payload: PublishMessageRequest) -> dict:
    """FastAPI가 DB 그룹/계정 기준으로 대상을 계산하고 outbox에 기록합니다."""
    body = payload.model_dump(mode="json", exclude_none=True)
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{API_BASE}/service-request-events/notifications",
                json=body,
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            return {"error": "notification_publish_failed", "status": response.status_code, "detail": detail}
        return response.json()
    except httpx.HTTPError as exc:
        logger.exception("notification publish failed: scope=%s", payload.target_type)
        return {"error": "notification_publish_failed", "detail": f"ITSM API 연결 실패: {exc!s}"}


def _derive_request_id(
    target_type: str, target_group: str | None, employee_nos: list[str], title: str, message: str
) -> str:
    """같은 내용을 짧은 시간 안에 재시도하면 같은 request_id가 나오도록 만듭니다(FastAPI 중복 제거용)."""
    bucket = int(time.time() // DEDUP_WINDOW_SECONDS)
    raw = json.dumps(
        [target_type, target_group, sorted(employee_nos), title.strip(), message.strip(), bucket],
        ensure_ascii=False,
    )
    return "wxo-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


SR_KEY_PATTERN = re.compile(r"^SR-[0-9]{1,12}$")


async def _fetch_service_request(ticket_key: str) -> dict:
    """FastAPI GET /service-requests/{ticket_key} (읽기 전용). 형식을 먼저 검증해 경로 조작을 막습니다."""
    if not SR_KEY_PATTERN.fullmatch(ticket_key):
        return {"error": "invalid_ticket_key", "detail": "SR 번호 형식은 SR-숫자입니다. 예: SR-123"}
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(
                f"{API_BASE}/service-requests/{ticket_key}",
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )
    except httpx.HTTPError as exc:
        logger.exception("service request lookup failed: %s", ticket_key)
        return {"error": "service_request_lookup_failed", "detail": f"ITSM API 연결 실패: {exc!s}"}
    if response.status_code == 404:
        return {"error": "service_request_not_found", "ticket_key": ticket_key, "detail": "해당 SR이 없습니다."}
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        return {"error": "service_request_lookup_failed", "status": response.status_code, "detail": detail}
    return response.json()


LIST_MAX_LIMIT = max(1, int(os.getenv("WXO_NOTIFY_LIST_MAX_LIMIT", "20")))
# 목록에는 요약 필드만 돌려줘 agent 컨텍스트를 아낍니다. 상세(설명, 작업 기록)는 get_service_request로 봅니다.
LIST_SUMMARY_FIELDS = (
    "ticket_key", "title", "status", "severity", "service_name", "environment",
    "requester", "assignee", "assignee_employee_no", "created_at", "updated_at",
)


def _summarize_sr(item) -> dict:
    if not isinstance(item, dict):
        return {"value": item}
    summary = {k: item[k] for k in LIST_SUMMARY_FIELDS if k in item}
    return summary or item  # 알려진 필드가 하나도 없으면 원본을 그대로 둡니다(스키마가 다른 경우 대비)


async def _list_service_requests(
    status: str | None, severity: str | None, service_name: str | None, limit: int
) -> dict:
    """FastAPI GET /service-requests (읽기 전용). 필터와 limit만 전달합니다."""
    limit = max(1, min(limit, LIST_MAX_LIMIT))
    params: dict[str, str | int] = {"limit": limit}
    if status:
        params["status"] = status
    if severity:
        params["severity"] = severity
    if service_name:
        params["service_name"] = service_name
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(
                f"{API_BASE}/service-requests",
                params=params,
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )
    except httpx.HTTPError as exc:
        logger.exception("service request list failed")
        return {"error": "service_request_list_failed", "detail": f"ITSM API 연결 실패: {exc!s}"}
    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:500]
        return {"error": "service_request_list_failed", "status": response.status_code, "detail": detail}
    data = response.json()
    # 응답이 배열이거나 {"items": [...]} 형태 모두 처리합니다.
    if isinstance(data, dict):
        rows = data.get("items", data.get("results", data.get("data")))
        total = data.get("total", data.get("count"))
    else:
        rows, total = data, None
    if not isinstance(rows, list):
        return {"error": "service_request_list_failed", "detail": "예상하지 못한 응답 형식입니다."}
    items = [_summarize_sr(r) for r in rows[:limit]]
    result = {"count": len(items), "limit": limit, "filters": {k: v for k, v in params.items() if k != "limit"},
              "items": items}
    if total is not None:
        result["total"] = total
    if len(rows) > limit:
        result["truncated"] = True
    return result


class ServiceRequestCreateBody(BaseModel):
    """FastAPI ServiceRequestCreate와 같은 계약(자체 정의). 최종 검증은 FastAPI가 합니다."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    service_name: str = Field(min_length=2, max_length=120)
    environment: str = Field(default="production", min_length=2, max_length=32)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    requester: str = Field(min_length=2, max_length=120)
    assignee: str | None = Field(default=None, max_length=120)
    assignee_employee_no: str = Field(min_length=2, max_length=32)


# FastAPI의 SR 생성 API에는 중복 방지가 없으므로 이 서버에서 같은 내용의 재발행을 막습니다.
# 프로세스 메모리 기준이라 서버 재시작이나 다중 worker에서는 공유되지 않습니다(단일 프로세스 운영 전제).
_recent_creates: dict[str, tuple[float, dict]] = {}
_create_lock = asyncio.Lock()


def _create_fingerprint(body: ServiceRequestCreateBody) -> str:
    raw = json.dumps(body.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _create_service_request(body: ServiceRequestCreateBody) -> dict:
    """FastAPI POST /service-requests. 전송 오류는 생성 여부가 불확실하므로 자동 재시도하지 않습니다."""
    fingerprint = _create_fingerprint(body)
    async with _create_lock:
        now = time.time()
        for key in [k for k, (ts, _) in _recent_creates.items() if now - ts > DEDUP_WINDOW_SECONDS]:
            del _recent_creates[key]
        if fingerprint in _recent_creates:
            previous = dict(_recent_creates[fingerprint][1])
            previous["duplicate"] = True
            previous["detail"] = "같은 내용의 SR이 방금 발행되어 새로 만들지 않았습니다."
            return previous
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await client.post(
                    f"{API_BASE}/service-requests",
                    json=body.model_dump(mode="json", exclude_none=True),
                    headers={"Authorization": f"Bearer {API_TOKEN}"},
                )
        except httpx.HTTPError as exc:
            logger.exception("service request create failed: service=%s", body.service_name)
            return {
                "error": "service_request_create_uncertain",
                "detail": f"ITSM API 연결 실패({exc!s}). SR이 생성되었는지 알 수 없으므로 같은 요청을 다시 보내지 말고 담당자에게 확인을 요청하세요.",
            }
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            return {"error": "service_request_create_failed", "status": response.status_code, "detail": detail}
        created = response.json()
        created["bob_notification"] = {
            "recipient_employee_no": body.assignee_employee_no,
            "note": "담당자 사번으로 SR 생성 이벤트가 기록되었습니다. Bob Notifier에 접속 중이면 알림이 표시됩니다.",
        }
        _recent_creates[fingerprint] = (now, created)
        return created


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """/health를 제외한 모든 요청에 wxO 전용 token을 요구합니다."""

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        supplied = request.headers.get("authorization", "")
        if WXO_TOKEN.startswith("replace-") or not hmac.compare_digest(supplied, f"Bearer {WXO_TOKEN}"):
            return JSONResponse({"detail": "유효한 wxO notify MCP Bearer token이 필요합니다."}, status_code=401)
        return await call_next(request)


mcp = MCPServer(
    "Bob Notifier for watsonx Orchestrate",
    instructions=(
        "IBM Bob 사용자(전체, 그룹, 개별 사번)에게 공지를 발송하고, SR을 조회·발행합니다. "
        "전체 공지는 confirm_all=true, SR 발행은 confirmed=true를 사용자 확인 후에만 사용합니다."
    ),
)


@mcp.tool()
async def send_notification(
    target_type: Annotated[
        Literal["all", "group", "user"],
        Field(description="수신 범위. all=전체, group=그룹, user=특정 사번"),
    ],
    title: Annotated[str, Field(description="공지 제목 (1~200자)")],
    message: Annotated[str, Field(description="공지 본문 (1~200자)")],
    target_group: Annotated[
        str | None, Field(description="target_type=group일 때 그룹 이름. 그 외에는 비워 둡니다.")
    ] = None,
    employee_nos: Annotated[
        list[str] | None,
        Field(description="target_type=user일 때 수신자 사번 목록(1~100명). 그 외에는 비워 둡니다."),
    ] = None,
    links: Annotated[
        list[NotificationLink] | None, Field(description="선택: 공지에 첨부할 자료 링크(최대 10개)")
    ] = None,
    confirm_all: Annotated[
        bool, Field(description="target_type=all일 때 사용자가 전체 발송을 명시적으로 확인했으면 true")
    ] = False,
) -> dict:
    """IBM Bob 사용자에게 공지를 발송합니다. Bob Notifier(VSCode/Bob)에 알림으로 표시됩니다."""
    if target_type == "all" and not confirm_all:
        return {
            "error": "confirmation_required",
            "detail": "전체 공지는 사용자에게 확인을 받은 뒤 confirm_all=true로 다시 호출하세요.",
        }

    nos = [n.strip() for n in (employee_nos or []) if n and n.strip()]
    request_id = _derive_request_id(target_type, target_group, nos, title, message)
    try:
        payload = PublishMessageRequest(
            target_type=target_type,
            request_id=request_id,
            title=title,
            message=message,
            target_group=target_group or None,
            employee_no=nos[0] if len(nos) == 1 else None,
            employee_nos=nos if len(nos) > 1 else None,
            links=links or [],
        )
    except Exception as exc:  # pydantic ValidationError 포함
        return {"error": "invalid_request", "detail": str(exc)}

    result = await _publish_notification(payload)
    logger.info(
        "publisher=wxo request_id=%s scope=%s group=%s recipients=%s result=%s",
        request_id, target_type, target_group, nos or None,
        result.get("error") or result.get("event_id"),
    )
    if "error" not in result:
        result.setdefault("request_id", request_id)
    return result


@mcp.tool()
async def get_service_request(
    ticket_key: Annotated[
        str, Field(description="조회할 SR 번호. 형식: SR-숫자 (예: SR-123). Bob Notifier 알림에 표시된 번호를 그대로 사용")
    ],
) -> dict:
    """SR 번호로 SR 상세(상태, 담당자, 심각도, 작업 기록)를 조회합니다. 읽기 전용이며 SR을 변경하지 않습니다."""
    key = ticket_key.strip().upper()
    result = await _fetch_service_request(key)
    logger.info("publisher=wxo lookup=%s result=%s", key, result.get("error") or result.get("status"))
    return result


@mcp.tool()
async def list_service_requests(
    status: Annotated[str | None, Field(description="상태 필터(선택). ITSM에서 쓰는 상태 값 그대로", max_length=32)] = None,
    severity: Annotated[
        Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None, Field(description="심각도 필터(선택)")
    ] = None,
    service_name: Annotated[str | None, Field(description="서비스 이름 필터(선택)", max_length=120)] = None,
    limit: Annotated[int, Field(description="가져올 최대 건수 (1~20, 기본 10)", ge=1, le=100)] = 10,
) -> dict:
    """SR 목록을 요약(번호, 제목, 상태, 심각도, 담당자 등)으로 조회합니다. 읽기 전용이며 SR을 변경하지 않습니다.
    상세 내용과 작업 기록은 목록의 SR 번호로 get_service_request를 호출해 확인하세요."""
    result = await _list_service_requests(
        (status or "").strip() or None, severity, (service_name or "").strip() or None, limit
    )
    logger.info(
        "publisher=wxo list_sr filters=%s/%s/%s result=%s",
        status, severity, service_name, result.get("error") or result.get("count"),
    )
    return result


@mcp.tool()
async def create_service_request(
    title: Annotated[str, Field(description="SR 제목 (3~200자)")],
    description: Annotated[str, Field(description="증상, 영향, 재현 절차, 기대 결과 (3자 이상)")],
    service_name: Annotated[str, Field(description="대상 애플리케이션/서비스 이름 (2~120자)")],
    requester: Annotated[str, Field(description="요청자 이름 (2~120자)")],
    assignee_employee_no: Annotated[
        str,
        Field(description="Bob 알림을 받을 담당자 사번(2~32자). 추측하지 말고 사용자에게 확인한 값만 넣습니다."),
    ],
    assignee: Annotated[str | None, Field(description="담당자 이름(표시용, 선택)")] = None,
    environment: Annotated[str, Field(description="환경. 기본 production")] = "production",
    severity: Annotated[
        Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"], Field(description="심각도. 기본 MEDIUM")
    ] = "MEDIUM",
    confirmed: Annotated[
        bool, Field(description="사용자가 SR 내용(제목, 담당자 등)을 확인하고 등록에 동의했으면 true")
    ] = False,
) -> dict:
    """SR을 발행(등록)합니다. 담당자 사번으로 Bob Notifier 알림 이벤트가 자동 기록됩니다."""
    if not confirmed:
        return {
            "error": "confirmation_required",
            "detail": "SR 내용을 사용자에게 보여 주고 동의를 받은 뒤 confirmed=true로 다시 호출하세요.",
        }
    try:
        body = ServiceRequestCreateBody(
            title=title.strip(),
            description=description.strip(),
            service_name=service_name.strip(),
            requester=requester.strip(),
            assignee_employee_no=assignee_employee_no.strip(),
            assignee=(assignee or "").strip() or None,
            environment=environment.strip() or "production",
            severity=severity,
        )
    except Exception as exc:  # pydantic ValidationError 포함
        return {"error": "invalid_request", "detail": str(exc)}
    result = await _create_service_request(body)
    logger.info(
        "publisher=wxo create_sr service=%s assignee=%s severity=%s result=%s",
        body.service_name, body.assignee_employee_no, body.severity,
        result.get("error") or result.get("ticket_key"),
    )
    return result


async def health(request):
    """프로세스 상태와 FastAPI 도달 여부를 함께 보여 줍니다(분리 배포 시 네트워크 점검용)."""
    api_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{API_BASE}/health")
            api_ok = r.status_code < 500
    except httpx.HTTPError:
        api_ok = False
    return JSONResponse(
        {"status": "ok", "service": "wxo-bob-notify-mcp", "itsm_api": API_BASE, "itsm_api_reachable": api_ok}
    )


def main():
    host = os.getenv("WXO_NOTIFY_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("WXO_NOTIFY_MCP_PORT", "8041"))

    # 리버스 프록시가 원래 Host(notify.example.com)를 전달하므로 허용 목록에 넣어야 421이 나지 않습니다.
    # HTTPS 443 요청은 Host에 포트가 없으므로 "도메인"과 "도메인:*"를 함께 넣으세요.
    extra_hosts = [h.strip() for h in os.getenv("WXO_NOTIFY_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=os.getenv(
            "WXO_NOTIFY_MCP_DNS_REBINDING_PROTECTION", "true"
        ).lower() == "true",
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *extra_hosts],
        allowed_origins=[
            "http://127.0.0.1:*", "http://localhost:*",
            *[f"https://{h}" for h in extra_hosts],
        ],
    )
    if API_TOKEN.startswith("replace-"):
        logger.warning("WXO_NOTIFY_ITSM_API_TOKEN이 설정되지 않았습니다. 발송이 실패합니다.")
    print(
        f"[wxo_notify_mcp] listen={host}:{port} itsm_api={API_BASE} "
        f"dns_rebinding_protection={transport_security.enable_dns_rebinding_protection} "
        f"allowed_hosts={transport_security.allowed_hosts}",
        flush=True,
    )
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        host=host,
        transport_security=transport_security,
    )
    app.add_middleware(BearerTokenMiddleware)
    app.add_route("/health", health, methods=["GET"])
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()