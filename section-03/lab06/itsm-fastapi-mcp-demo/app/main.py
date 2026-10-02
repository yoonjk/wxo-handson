"""ITSM FastAPI 애플리케이션 진입점."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from app.api.routes import bob_notification_admin, health, service_request_events, service_requests
from app.core.config import get_settings
from app.db.base import Base
from app.db.connection import SessionLocal, engine
from app.models import ServiceRequest  # noqa: F401 - metadata에 ORM 모델 등록
from app.models import bob_notification  # noqa: F401 - 새 Bob/공지 테이블 metadata 등록
from app.services.bob_user_bootstrap import seed_bob_users_from_environment

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """데모/개발 환경에서만 테이블을 자동 생성합니다."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seeded = seed_bob_users_from_environment(db)
    if seeded:
        print(f"[bob_user_bootstrap] imported {seeded} user(s); token hashes stored in MySQL")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A2A WXO / MCP Gateway 시나리오를 위한 MySQL 기반 ITSM Service Request API",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(service_requests.router)
app.include_router(service_request_events.router)
app.include_router(bob_notification_admin.router)


if __name__ == "__main__":
    # python -m app.main starts FastAPI using APP_HOST / APP_PORT from .env.
    uvicorn.run(app, host=settings.app_host, port=settings.app_port)
