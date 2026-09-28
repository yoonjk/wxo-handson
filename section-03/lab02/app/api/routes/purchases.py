from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.documentation import (
    CONFLICT,
    CREATE_EXAMPLES,
    NOT_FOUND,
    REQUEST_ID_DESCRIPTION,
    SERVER_ERROR,
    STATUS_EXAMPLES,
    result_examples,
    validation_response,
)
from app.db.connection import get_db
from app.repositories.purchase_repository import PurchaseRepository
from app.schemas.purchase import (
    PurchaseRequestCreate,
    PurchaseRequestResponse,
    PurchaseStatusUpdate,
)
from app.services.purchase_service import (
    InvalidStatusTransitionError,
    PurchaseNotFoundError,
    PurchaseService,
)

router = APIRouter(
    prefix="/api/purchase-requests",
    tags=["Purchase requests"],
)


def get_service(db: Session = Depends(get_db)) -> PurchaseService:
    """Build the business service using the request-scoped database session."""
    return PurchaseService(PurchaseRepository(db))


@router.post(
    "",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_purchase_request",
    summary="구매 요청 생성",
    description=(
        "구매 요청을 MySQL의 purchase_requests 테이블에 저장하고 생성된 레코드를 반환합니다. "
        "새 요청의 상태는 서버에서 PENDING으로 지정하며 id와 생성/수정 시각은 저장 후 DB에서 받습니다.\n\n"
        "요청 본문에는 구매 유형, 요청자, 양수 금액을 전달합니다. reason은 선택 항목입니다. "
        "현재 API는 인증·인가를 수행하지 않으며 requester 문자열을 요청 본문에서 받습니다.\n\n"
        "같은 POST를 다시 보내면 별도의 구매 요청이 새로 생성됩니다. 멱등성 키나 중복 방지 처리가 없으므로 "
        "응답이 불명확한 경우 곧바로 재호출하지 말고 생성 여부를 확인하세요."
    ),
    responses={
        201: {
            "description": "구매 요청이 생성되었습니다. 생성된 id와 PENDING 상태를 반환합니다.",
            "content": result_examples("PENDING"),
        },
        422: validation_response(
            ["body", "total_amount"], "Input should be greater than 0", "greater_than"
        ),
        500: SERVER_ERROR,
    },
)
def create_purchase_request(
    body: Annotated[
        PurchaseRequestCreate,
        Body(
            description="새 구매 요청 필드입니다. 금액은 0보다 커야 하고 사유는 생략할 수 있습니다.",
            openapi_examples=CREATE_EXAMPLES,
        ),
    ],
    service: PurchaseService = Depends(get_service),
) -> PurchaseRequestResponse:
    """Persist a new request; repeated calls create separate rows."""
    return service.create(body)


@router.get(
    "/{request_id}",
    response_model=PurchaseRequestResponse,
    operation_id="get_purchase_request",
    summary="구매 요청 단건 조회",
    description=(
        "경로의 request_id와 일치하는 구매 요청 한 건을 조회합니다. id는 POST 생성 응답에서 받은 정수입니다. "
        "존재하는 요청이면 현재 상태와 처리 결과를 포함한 레코드를 반환하고, 없으면 404를 반환합니다.\n\n"
        "요청 본문은 없습니다. 호출은 데이터를 변경하지 않습니다."
    ),
    responses={
        200: {
            "description": "요청이 존재하면 구매 요청 레코드를 반환합니다.",
            "content": result_examples("PENDING", "APPROVED", "REJECTED"),
        },
        404: NOT_FOUND,
        422: validation_response(
            ["path", "request_id"], "Input should be a valid integer", "int_parsing"
        ),
        500: SERVER_ERROR,
    },
)
def get_purchase_request(
    request_id: Annotated[int, Path(description=REQUEST_ID_DESCRIPTION, examples=[1])],
    service: PurchaseService = Depends(get_service),
) -> PurchaseRequestResponse:
    """Return the stored purchase request or HTTP 404."""
    try:
        return service.get(request_id)
    except PurchaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/{request_id}/status",
    response_model=PurchaseRequestResponse,
    operation_id="update_purchase_status",
    summary="구매 요청 승인 또는 반려",
    description=(
        "PENDING 상태인 구매 요청에 승인 또는 반려 결과를 저장합니다. status는 APPROVED 또는 REJECTED이며 "
        "approver_role은 필수 업무 기록 필드입니다. comment는 선택 사항입니다.\n\n"
        "정상 처리 후 갱신된 요청을 반환합니다. 이미 같은 최종 상태인 요청에 같은 결과를 보내면 현재 레코드를 그대로 반환합니다. "
        "이 경우 새 comment나 approver_role은 저장되지 않습니다. 이미 APPROVED인 요청을 REJECTED로 바꾸거나 그 반대의 "
        "전이는 409를 반환합니다. 없는 id는 404입니다.\n\n"
        "이 API는 approver_role을 이용해 호출자의 권한을 인증하거나 검사하지 않습니다. 호출자 권한 검증은 별도로 구성해야 합니다."
    ),
    responses={
        200: {
            "description": "상태가 갱신되었거나 동일한 현재 상태가 반환되었습니다.",
            "content": result_examples("APPROVED", "REJECTED"),
        },
        404: NOT_FOUND,
        409: CONFLICT,
        422: validation_response(
            ["body", "approver_role"], "Field required", "missing"
        ),
        500: SERVER_ERROR,
    },
)
def update_purchase_status(
    request_id: Annotated[int, Path(description=REQUEST_ID_DESCRIPTION, examples=[1])],
    body: Annotated[
        PurchaseStatusUpdate,
        Body(
            description="저장할 최종 처리 결과입니다. status와 approver_role은 필수입니다.",
            openapi_examples=STATUS_EXAMPLES,
        ),
    ],
    service: PurchaseService = Depends(get_service),
) -> PurchaseRequestResponse:
    """Apply an approval result while enforcing the service's state transition."""
    try:
        return service.update_status(request_id, body)
    except PurchaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
