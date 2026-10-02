from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    """물품 등록 API의 요청 모델입니다."""

    sku: str = Field(
        min_length=1,
        max_length=50,
        description="물품을 식별하는 SKU. 서버에서 대문자로 정규화합니다.",
        examples=["MOUSE"],
    )
    name: str = Field(
        min_length=1,
        max_length=100,
        description="물품명",
        examples=["마우스"],
    )
    unit_price: Decimal = Field(
        gt=0,
        description="물품 1개의 단가",
        examples=[50000],
    )
    description: str | None = Field(default=None, description="물품 설명")
    active: bool = Field(default=True, description="등록 즉시 구매 가능한 물품인지 여부")


class ProductResponse(BaseModel):
    """물품 조회 API의 응답 모델입니다."""

    model_config = ConfigDict(from_attributes=True)

    sku: str = Field(description="물품을 식별하는 대문자 SKU", examples=["NOTEBOOK"])
    name: str = Field(description="물품명", examples=["노트북"])
    unit_price: Decimal = Field(description="물품 1개의 단가", examples=[1200000])
    description: str | None = Field(default=None, description="물품 설명")
    active: bool = Field(description="현재 구매 가능한 물품인지 여부", examples=[True])
