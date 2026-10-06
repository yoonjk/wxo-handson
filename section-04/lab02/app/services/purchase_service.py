from app.models.purchase_request import PurchaseRequest
from app.repositories.product_repository import ProductRepository
from app.repositories.purchase_repository import PurchaseRepository
from app.schemas.purchase import PurchaseRequestCreate, PurchaseStatusUpdate


class PurchaseNotFoundError(Exception):
    pass


class InvalidStatusTransitionError(Exception):
    pass


class InvalidPurchaseProductError(ValueError):
    """구매 요청에 포함된 SKU가 활성 상품 목록에 없을 때 발생합니다."""


class PurchaseService:
    """상품 유효성 검사와 승인 상태 전이 같은 업무 규칙을 담당합니다."""

    def __init__(
        self,
        repository: PurchaseRepository,
        product_repository: ProductRepository,
    ) -> None:
        self.repository = repository
        self.product_repository = product_repository

    def get(self, request_id: int) -> PurchaseRequest:
        purchase = self.repository.get_by_id(request_id)
        if purchase is None:
            raise PurchaseNotFoundError(f"구매 요청 {request_id}을(를) 찾을 수 없습니다.")
        return purchase

    def _validate_product(self, data: PurchaseRequestCreate) -> None:
        """purchase_type의 SKU가 활성 상품 카탈로그에 등록되어 있는지 확인합니다."""
        # 현재 요청 스키마는 상품 코드를 purchase_type 필드로 전달합니다.
        sku = data.purchase_type.strip().upper()
        if not sku:
            raise InvalidPurchaseProductError("구매 요청에 상품 SKU를 입력해야 합니다.")

        # 활성 상품만 허용하므로 비활성 또는 미등록 SKU는 None으로 반환됩니다.
        product = self.product_repository.get_active_by_sku(sku)
        if product is None:
            raise InvalidPurchaseProductError(
                f"SKU '{sku}'는 활성 상품 목록에 없습니다."
            )

    def create(self, data: PurchaseRequestCreate) -> PurchaseRequest:
        # 저장 전에 모든 요청 상품을 검증해 미등록/비활성 상품 구매를 차단합니다.
        self._validate_product(data)
        return self.repository.create(data)

    def update_status(
        self, request_id: int, data: PurchaseStatusUpdate
    ) -> PurchaseRequest:
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
