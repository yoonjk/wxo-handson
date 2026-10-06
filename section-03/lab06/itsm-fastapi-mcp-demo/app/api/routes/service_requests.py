"""Service Request REST endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_demo_token
from app.db.connection import get_db
from app.schemas.service_request import (
    ServiceRequestCreate,
    ServiceRequestStatus,
    ServiceRequestView,
    Severity,
    StatusUpdate,
    WorklogCreate,
)
from app.services.service_request_service import service_request_service

router = APIRouter(prefix="/service-requests", tags=["Service Requests"], dependencies=[Depends(require_demo_token)])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=ServiceRequestView, status_code=201, summary="SR 등록")
def create_service_request(payload: ServiceRequestCreate, db: DbSession):
    return ServiceRequestView.from_model(service_request_service.create(db, payload))


@router.get("", response_model=list[ServiceRequestView], summary="SR 목록 조회")
def list_service_requests(
    db: DbSession,
    status: ServiceRequestStatus | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    service_name: str | None = Query(default=None, min_length=2, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
):
    rows = service_request_service.list(db, status, severity, service_name, limit)
    return [ServiceRequestView.from_model(row) for row in rows]


@router.get("/{ticket_key}", response_model=ServiceRequestView, summary="SR 상세 조회")
def get_service_request(ticket_key: str, db: DbSession):
    return ServiceRequestView.from_model(service_request_service.get(db, ticket_key))


@router.patch("/{ticket_key}/status", response_model=ServiceRequestView, summary="SR 상태 변경")
def update_status(ticket_key: str, payload: StatusUpdate, db: DbSession):
    return ServiceRequestView.from_model(service_request_service.update_status(db, ticket_key, payload))


@router.post("/{ticket_key}/worklog", response_model=ServiceRequestView, summary="SR 작업 기록 추가")
def add_worklog(ticket_key: str, payload: WorklogCreate, db: DbSession):
    return ServiceRequestView.from_model(service_request_service.add_worklog(db, ticket_key, payload))
