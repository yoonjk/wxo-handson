import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401
from app.api.routes.health import router as health_router
from app.api.routes.products import router as product_router
from app.api.routes.purchases import router as purchase_router
from app.api.routes.a2a import router as a2a_router
from app.core.config import get_settings
from app.db.connection import Base, engine

settings = get_settings()

# Nginx 외부 경로 설정
# 로컬 실행 시 ROOT_PATH=""로 설정할 수 있습니다.
root_path = os.getenv("ROOT_PATH", "/purchase")

# watsonx Orchestrate가 호출할 절대 URL
public_api_url = os.getenv(
    "PUBLIC_API_URL",
    "http://nexweb.ddnsgeek.com/purchase",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    애플리케이션 시작 시 필요한 초기화 작업을 수행합니다.

    AUTO_CREATE_TABLES=true인 경우에만 SQLAlchemy 모델 기준으로
    테이블을 자동 생성합니다. 운영 환경에서는 별도 SQL 마이그레이션을
    사용하는 것을 권장합니다.
    """
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    summary="구매 요청 생성·조회 및 Workflow 승인 결과 저장",
    description=(
        "watsonx Orchestrate가 결정한 구매 승인/반려 결과를 MySQL에 저장하는 purchase app입니다. "
        "HTTP 처리, 업무 규칙, DB 처리, 연결 관리를 각각 routes, services, repositories, db 모듈로 분리합니다.\n\n"
        "**호출 순서:** POST /api/purchase-requests로 생성 → 응답 id 보관 → Workflow에서 결정 → "
        "PATCH /api/purchase-requests/{request_id}/status로 결과 저장 → GET으로 현재 상태 확인.\n\n"
        "현재 상태는 PENDING / APPROVED / REJECTED입니다. 이 앱에는 견적·품목 조회·발주·결제 API가 없습니다. "
        "purchase_type은 활성 상품 카탈로그의 SKU인지 확인합니다. requester와 approver_role 문자열은 인증/역할 검사를 의미하지 않습니다. "
        "현재 실습 앱에는 애플리케이션 인증이 없습니다.\n\n"
        "구매 총액은 Decimal이며 응답 JSON에서는 문자열로 반환됩니다. 날짜·시각에는 timezone 정보가 없습니다. "
        "오류는 FastAPI 형식을 사용하며 404/409는 detail 문자열, 입력 검증 422는 detail 배열입니다. "
        "처리되지 않은 DB 오류에는 JSON 오류 변환 핸들러가 없습니다."
    ),
    root_path=root_path,
    servers=[
        {
            "url": public_api_url,
            "description": "HTTPS API through Nginx",
        }
    ],
    lifespan=lifespan,
)

# 공통 상태 확인 API
app.include_router(health_router)

# 구매 물품 목록 및 SKU별 단가 조회 API
app.include_router(product_router)

# 구매 요청 생성, 조회, 승인/반려 API
app.include_router(purchase_router)

# A2A(Agent-to-Agent) API
app.include_router(a2a_router)