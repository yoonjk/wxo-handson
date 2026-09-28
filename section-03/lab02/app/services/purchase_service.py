from app.models.purchase_request import PurchaseRequest
from app.repositories.purchase_repository import PurchaseRepository
from app.schemas.purchase import PurchaseRequestCreate, PurchaseStatusUpdate


class PurchaseNotFoundError(Exception):
    pass


class InvalidStatusTransitionError(Exception):
    pass


class PurchaseService:
    """승인 상태 전이 같은 업무 규칙을 담당합니다."""

    def __init__(self, repository: PurchaseRepository) -> None:
        self.repository = repository

    def get(self, request_id: int) -> PurchaseRequest:
        purchase = self.repository.get_by_id(request_id)
        if purchase is None:
            raise PurchaseNotFoundError(f"구매 요청 {request_id}을(를) 찾을 수 없습니다.")
        return purchase

    def create(self, data: PurchaseRequestCreate) -> PurchaseRequest:
        return self.repository.create(data)

    def update_status(self, request_id: int, data: PurchaseStatusUpdate) -> PurchaseRequest:
        purchase = self.get(request_id)

        # Orchestrate의 재시도에도 같은 결과를 반환하도록 동일 상태 갱신은 허용합니다.
        if purchase.status == data.status.value:
            return purchase
        if purchase.status != "PENDING":
            raise InvalidStatusTransitionError(
                f"{purchase.status} 상태의 요청은 {data.status.value}(으)로 변경할 수 없습니다."
            )
        return self.repository.update_status(purchase, data)

    def list_all(self) -> list[PurchaseRequest]:
        """구매 승인 요청 전체 목록을 Repository에 위임합니다."""

        return self.repository.list_all()