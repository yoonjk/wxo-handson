"""Service Request 테이블 접근과 SQLAlchemy transaction을 캡슐화합니다."""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.service_request import ServiceRequest
from app.models.service_request_event import ServiceRequestEvent
from app.schemas.service_request_event import NotificationPublishRequest


class ServiceRequestRepository:
    @staticmethod
    def _notify_event_server(event_id: int) -> None:
        """Wake the SSE relay after commit; outbox polling remains the retry path."""
        settings = get_settings()
        base_url = settings.itsm_event_mcp_internal_url.rstrip("/")
        token = settings.itsm_event_mcp_bearer_token
        if not token or token.startswith("replace-"):
            return
        try:
            # This is a best-effort wake-up after the durable outbox commit. The relay
            # still reads event content from FastAPI, so a failed push cannot lose SRs.
            httpx.post(
                f"{base_url}/internal/event-notify",
                json={"event_id": event_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=1.0,
            ).raise_for_status()
        except httpx.HTTPError:
            # SSE's periodic outbox check recovers when the event server is unavailable.
            pass

    @staticmethod
    def create(db: Session, request: ServiceRequest) -> ServiceRequest:
        try:
            db.add(request)
            db.flush()
            event = ServiceRequestRepository._add_event(db, request, "service_request.created")
            db.commit()
            db.refresh(request)
            ServiceRequestRepository._notify_event_server(event.id)
            return request
        except Exception:
            # 실패한 transaction을 rollback해야 session을 안전하게 재사용할 수 있습니다.
            db.rollback()
            raise

    @staticmethod
    def get_by_id(db: Session, request_id: int) -> ServiceRequest | None:
        return db.get(ServiceRequest, request_id)

    @staticmethod
    def list(
        db: Session,
        status: str | None,
        severity: str | None,
        service_name: str | None,
        limit: int,
    ) -> list[ServiceRequest]:
        query = select(ServiceRequest).order_by(ServiceRequest.id.desc()).limit(limit)
        if status:
            query = query.where(ServiceRequest.status == status)
        if severity:
            query = query.where(ServiceRequest.severity == severity)
        if service_name:
            query = query.where(ServiceRequest.service_name == service_name)
        return list(db.scalars(query).all())

    @staticmethod
    def save(
        db: Session, request: ServiceRequest, event_type: str = "service_request.updated"
    ) -> ServiceRequest:
        try:
            db.add(request)
            db.flush()
            event = ServiceRequestRepository._add_event(db, request, event_type)
            db.commit()
            db.refresh(request)
            ServiceRequestRepository._notify_event_server(event.id)
            return request
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _add_event(db: Session, request: ServiceRequest, event_type: str) -> ServiceRequestEvent:
        """업무 row와 이벤트 row를 동일 transaction에 넣습니다."""
        event = ServiceRequestEvent(
            ticket_key=request.ticket_key,
            event_type=event_type,
            payload={
                "ticket_key": request.ticket_key,
                "title": request.title,
                "service_name": request.service_name,
                "environment": request.environment,
                "severity": request.severity,
                "status": request.status,
                "requester": request.requester,
                "assignee": request.assignee,
                "assignee_employee_no": request.assignee_employee_no,
                "recipient_employee_no": request.assignee_employee_no,
                "updated_at": request.updated_at.isoformat() if request.updated_at else None,
            },
        )
        db.add(event)
        db.flush()
        return event


    @staticmethod
    def create_notification(db: Session, request: NotificationPublishRequest) -> ServiceRequestEvent:
        """공지 메시지를 기존 MySQL outbox에 저장한 뒤 SSE relay를 깨웁니다."""
        try:
            payload = {
                "notification_kind": "message",
                "recipient_scope": request.target_type,
                "recipient_group": request.target_group,
                "recipient_employee_no": request.employee_no,
                "recipient_employee_nos": request.employee_nos,
                "request_id": request.request_id,
                "title": request.title,
                "message": request.message,
                "links": [link.model_dump(mode="json") for link in request.links],
                "recipient_count_at_publish": request.recipient_count,
            }
            event = ServiceRequestEvent(
                ticket_key="NOTICE",
                event_type="notification.created",
                payload=payload,
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            ServiceRequestRepository._notify_event_server(event.id)
            return event
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def events_after(
        db: Session, after_event_id: int, limit: int, ticket_key: str | None = None
    ) -> list[ServiceRequestEvent]:
        query = (
            select(ServiceRequestEvent)
            .where(ServiceRequestEvent.id > after_event_id)
            .order_by(ServiceRequestEvent.id.asc())
            .limit(limit)
        )
        if ticket_key:
            query = query.where(ServiceRequestEvent.ticket_key == ticket_key)
        return list(db.scalars(query).all())
