"""Outbox 이벤트를 별도 MCP event consumer가 cursor 기반으로 읽는 API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_demo_token
from app.db.connection import get_db
from app.models.bob_notification import BobUser
from app.repositories.service_request_repository import ServiceRequestRepository
from app.services.bob_notification_service import persist_notification
from app.schemas.bob_notification_admin import BobNotificationCreate
from app.schemas.service_request_event import (
    NotificationPublishRequest,
    NotificationPublishResponse,
    ServiceRequestEventView,
)

router = APIRouter(
    prefix="/service-request-events",
    tags=["Service Request Events"],
    dependencies=[Depends(require_demo_token)],
)
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[ServiceRequestEventView], summary="SR 변경 이벤트 조회")
def list_events(
    db: DbSession,
    after_event_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    ticket_key: str | None = Query(default=None, min_length=3, max_length=16),
):
    events = ServiceRequestRepository.events_after(db, after_event_id, limit, ticket_key)
    return [ServiceRequestEventView.from_model(event) for event in events]


@router.post("/notifications", response_model=NotificationPublishResponse, status_code=201, summary="사용자 알림 발행")
def publish_notification(request: NotificationPublishRequest, db: DbSession):
    """전체/그룹/개인 대상으로 공지를 outbox에 내구성 있게 기록합니다."""
    # The internal MCP publisher uses the SYSTEM actor. User-facing sends instead
    # pass the current Bob token through the admin router and record that employee.
    if not db.get(BobUser, "SYSTEM"):
        db.add(BobUser(employee_no="SYSTEM", is_admin=False, status="inactive"))
        db.flush()
    payload = BobNotificationCreate(
        target_type=request.target_type,
        target_group=request.target_group,
        employee_nos=request.employee_nos or ([request.employee_no] if request.employee_no else None),
        request_id=request.request_id,
        title=request.title,
        message=request.message,
        links=[link.model_dump(mode="json") for link in request.links],
    )
    result = persist_notification(db, payload, "SYSTEM")
    return NotificationPublishResponse(
        event_id=result["event_id"],
        event_type=result["event_type"],
        target_type=request.target_type,
        title=request.title,
        recipient_count=result["recipient_count"],
        created_at=result["created_at"],
    )
