from datetime import datetime

from sqlalchemy.orm import Session

from app.models.purchase_request import PurchaseRequest
from app.schemas.purchase import PurchaseRequestCreate, PurchaseStatusUpdate


class PurchaseRepository:
    """SQL 실행과 트랜잭션 처리를 담당하는 DB 접근 계층입니다."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, request_id: int) -> PurchaseRequest | None:
        return self.db.get(PurchaseRequest, request_id)

    def create(self, data: PurchaseRequestCreate) -> PurchaseRequest:
        purchase = PurchaseRequest(**data.model_dump(), status="PENDING")
        self.db.add(purchase)
        self.db.commit()
        self.db.refresh(purchase)
        return purchase

    def update_status(
        self, purchase: PurchaseRequest, data: PurchaseStatusUpdate
    ) -> PurchaseRequest:
        purchase.status = data.status.value
        purchase.approver_role = data.approver_role
        purchase.approval_comment = data.comment
        purchase.approved_at = datetime.now() if data.status.value == "APPROVED" else None
        self.db.commit()
        self.db.refresh(purchase)
        return purchase

    def list_all(self) -> list[PurchaseRequest]:
        """구매 승인 요청 전체 목록을 조회합니다."""

        return (
            self.db.query(PurchaseRequest)
            .order_by(PurchaseRequest.id.desc())
            .all()
        )

    