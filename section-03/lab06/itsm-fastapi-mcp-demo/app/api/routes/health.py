"""프로세스 및 MySQL readiness endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.models.service_request import ServiceRequest

router = APIRouter(tags=["Health"])


@router.get("/health", summary="ITSM API 상태 확인", description="애플리케이션 프로세스 상태를 반환합니다.")
def health():
    return {"status": "ok", "service": "itsm-api", "time": datetime.now(timezone.utc).isoformat()}


@router.get(
    "/health/db",
    summary="MySQL 연결 상태와 저장 건수 확인",
    description="MySQL에 SELECT 1 및 itsm_service_requests 건수 조회를 실행합니다.",
)
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        count = db.scalar(select(func.count()).select_from(ServiceRequest))
        return {
            "status": "ok",
            "database": "mysql",
            "table": ServiceRequest.__tablename__,
            "service_request_count": count,
        }
    except SQLAlchemyError as exc:
        # Driver exception의 문자열에는 접속 정보가 있을 수 있어 그대로 노출하지 않습니다.
        raise HTTPException(status_code=503, detail="MySQL 연결 또는 테이블 조회에 실패했습니다.") from exc
