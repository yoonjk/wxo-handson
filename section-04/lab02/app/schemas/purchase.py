"""Request and response models shown in the generated OpenAPI document."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(str, Enum):
    """Allowed final approval results. New requests begin in PENDING."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PurchaseRequestCreate(BaseModel):
    """Fields required to register a new purchase request."""

    purchase_type: str = Field(
        min_length=1,
        max_length=50,
        description="상품 카탈로그에 등록된 SKU입니다. 1~50자이며 서버는 활성 상태의 SKU만 구매 요청에 허용합니다.",
        examples=["NOTEBOOK"],
    )
    requester: str = Field(
        min_length=1,
        max_length=100,
        description="요청자를 식별하는 업무용 문자열입니다. 1~100자이며 애플리케이션이 로그인 사용자를 확인하지는 않습니다.",
        examples=["hong.gildong"],
    )
    total_amount: Decimal = Field(
        gt=0,
        description="구매 총액입니다. 0보다 커야 합니다. DB에는 소수점 둘째 자리까지 저장됩니다.",
        examples=["1500000.00"],
    )
    reason: str | None = Field(
        default=None,
        description="구매 사유입니다. 선택 입력이며 생략하거나 null로 보낼 수 있습니다.",
        examples=["개발용 노트북 구매"],
    )


class PurchaseStatusUpdate(BaseModel):
    """Approval result to apply to a PENDING request."""

    status: ApprovalStatus = Field(
        description="저장할 최종 결과입니다. APPROVED(승인) 또는 REJECTED(반려)만 허용됩니다."
    )
    comment: str | None = Field(
        default=None,
        max_length=2000,
        description="승인/반려 의견입니다. 선택 항목이며 최대 2,000자입니다. DB 필드명은 approval_comment입니다.",
        examples=["예산 확인 완료"],
    )
    approver_role: str = Field(
        min_length=1,
        max_length=100,
        description=(
            "결과를 기록한 역할 이름입니다. 1~100자 필수 입력입니다. 업무 기록용 값이며 "
            "인증 또는 권한 검사를 수행하지 않습니다."
        ),
        examples=["IT_MANAGER"],
    )


class PurchaseRequestResponse(BaseModel):
    """Persisted purchase request returned by create, get, and update operations."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="DB가 자동 생성한 구매 요청의 정수 식별자입니다.", examples=[1])
    purchase_type: str = Field(description="활성 상품 카탈로그에 등록된 SKU입니다.", examples=["NOTEBOOK"])
    requester: str = Field(description="요청을 등록한 사용자 식별 문자열입니다.", examples=["hong.gildong"])
    total_amount: Decimal = Field(description="구매 총액입니다. JSON 응답에서 문자열로 직렬화될 수 있습니다.", examples=["1500000.00"])
    reason: str | None = Field(description="구매 사유입니다. 입력하지 않으면 null입니다.", examples=["개발용 노트북 구매", None])
    status: str = Field(description="요청 상태입니다. 생성 시 PENDING, 처리 후 APPROVED 또는 REJECTED입니다.", examples=["PENDING"])
    approver_role: str | None = Field(description="승인/반려 처리 시 함께 저장한 역할 문자열입니다. 처리 전에는 null입니다.", examples=[None, "IT_MANAGER"])
    approval_comment: str | None = Field(description="승인/반려 처리 시 입력한 의견입니다. 입력하지 않으면 null입니다.", examples=[None, "예산 확인 완료"])
    approved_at: datetime | None = Field(description="APPROVED로 변경된 시각입니다. 반려 또는 처리 전에는 null입니다.", examples=[None, "2026-09-18T09:05:00"])
    created_at: datetime = Field(description="DB에 요청이 처음 저장된 시각입니다.", examples=["2026-09-18T09:00:00"])
    updated_at: datetime = Field(description="요청이 마지막으로 저장된 시각입니다. DB 시간대 설정을 따릅니다.", examples=["2026-09-18T09:05:00"])


CREATE_EXAMPLE = {
    "purchase_type": "NOTEBOOK",
    "requester": "hong.gildong",
    "total_amount": "1500000.00",
    "reason": "개발용 노트북 구매",
}
RESPONSE_EXAMPLE = {
    "id": 1,
    "purchase_type": "NOTEBOOK",
    "requester": "hong.gildong",
    "total_amount": "1500000.00",
    "reason": "개발용 노트북 구매",
    "status": "PENDING",
    "approver_role": None,
    "approval_comment": None,
    "approved_at": None,
    "created_at": "2026-09-18T09:00:00",
    "updated_at": "2026-09-18T09:00:00",
}
