from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate


class ProductNotFoundError(Exception):
    """요청한 SKU가 활성 물품 카탈로그에 없을 때 발생합니다."""


class ProductAlreadyExistsError(Exception):
    """등록하려는 SKU가 이미 물품 카탈로그에 있을 때 발생합니다."""


class ProductService:
    """물품 목록과 SKU별 단가 조회 업무를 담당합니다."""

    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    def list_products(self) -> list[Product]:
        return self.repository.list_active()

    def create_product(self, data: ProductCreate) -> Product:
        """SKU를 정규화하고 중복을 확인한 뒤 물품을 등록합니다."""
        normalized_sku = data.sku.strip().upper()
        if self.repository.get_by_sku(normalized_sku) is not None:
            raise ProductAlreadyExistsError(
                f"SKU '{normalized_sku}'는 이미 등록된 물품입니다."
            )

        normalized_data = ProductCreate(
            sku=normalized_sku,
            name=data.name.strip(),
            unit_price=data.unit_price,
            description=data.description.strip() if data.description else None,
            active=data.active,
        )
        return self.repository.create(normalized_data)

    def get_product(self, sku: str) -> Product:
        normalized_sku = sku.strip().upper()
        product = self.repository.get_active_by_sku(normalized_sku)
        if product is None:
            raise ProductNotFoundError(
                f"SKU '{normalized_sku}'에 해당하는 구매 물품을 찾을 수 없습니다."
            )
        return product
