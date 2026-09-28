from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate


class ProductRepository:
    """물품 카탈로그 조회를 담당하는 DB 접근 계층입니다."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self) -> list[Product]:
        statement = (
            select(Product)
            .where(Product.active.is_(True))
            .order_by(Product.sku)
        )
        return list(self.db.scalars(statement).all())

    def get_active_by_sku(self, sku: str) -> Product | None:
        statement = select(Product).where(
            Product.sku == sku.upper(),
            Product.active.is_(True),
        )
        return self.db.scalar(statement)

    def get_by_sku(self, sku: str) -> Product | None:
        """활성 여부와 관계없이 SKU 중복 여부를 확인합니다."""
        statement = select(Product).where(Product.sku == sku.upper())
        return self.db.scalar(statement)

    def create(self, data: ProductCreate) -> Product:
        """새 물품을 저장하고 DB가 생성한 값을 포함해 반환합니다."""
        product = Product(**data.model_dump())
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product
