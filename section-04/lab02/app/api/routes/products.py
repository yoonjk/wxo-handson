from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductResponse
from app.services.product_service import (
    ProductAlreadyExistsError,
    ProductNotFoundError,
    ProductService,
)

router = APIRouter(prefix="/api/products", tags=["Products"])


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(ProductRepository(db))


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_product",
    summary="구매 물품 등록",
    description=(
        "구매 요청에 사용할 물품을 SKU, 물품명, 단가와 함께 등록합니다. "
        "SKU는 대문자로 정규화되며 이미 등록된 SKU는 다시 등록할 수 없습니다."
    ),
    responses={409: {"description": "이미 등록된 SKU입니다."}},
)
def create_product(
    data: ProductCreate,
    service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    try:
        return service.create_product(data)
    except ProductAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "",
    response_model=list[ProductResponse],
    operation_id="list_products",
    summary="구매 가능한 물품 목록 조회",
    description=(
        "구매 요청에 사용할 수 있는 활성 물품 목록을 SKU, 물품명, 단가와 함께 반환합니다. "
        "For each 노드에서 items의 sku와 비교할 때 사용할 수 있습니다."
    ),
)
def list_products(
    service: ProductService = Depends(get_product_service),
) -> list[ProductResponse]:
    return service.list_products()


@router.get(
    "/{sku}",
    response_model=ProductResponse,
    operation_id="get_product_by_sku",
    summary="SKU로 물품 및 단가 조회",
    description=(
        "지정한 SKU의 활성 물품을 조회하고 1개 기준 단가(unit_price)를 반환합니다. "
        "SKU는 대소문자를 구분하지 않으며 서버에서 대문자로 정규화합니다."
    ),
    responses={404: {"description": "해당 SKU의 활성 물품이 없습니다."}},
)
def get_product_by_sku(
    sku: str = Path(
        description="조회할 물품 SKU",
        min_length=1,
        max_length=50,
        examples=["NOTEBOOK", "MONITOR", "KEYBOARD"],
    ),
    service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    try:
        return service.get_product(sku)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
