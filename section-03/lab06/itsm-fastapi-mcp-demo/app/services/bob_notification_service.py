"""공지 대상 계산과 정규화 테이블/outbox 기록을 한 transaction으로 처리합니다."""

from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bob_notification import (
    BobGroup,
    BobUser,
    BobUserGroup,
    Notification,
    NotificationReceipt,
    NotificationTarget,
)
from app.models.service_request_event import ServiceRequestEvent
from app.repositories.service_request_repository import ServiceRequestRepository
from app.schemas.service_request_event import NotificationLink


def resolve_active_recipients(db: Session, request) -> list[str]:
    """전송 시점의 활성 사용자/그룹 매핑을 기반으로 받는 사람을 고정합니다."""
    if request.target_type == "all":
        recipients = list(
            db.scalars(select(BobUser.employee_no).where(BobUser.status == "active")).all()
        )
    elif request.target_type == "group":
        if not request.target_group or not db.get(BobGroup, request.target_group):
            raise HTTPException(status_code=422, detail="등록된 그룹을 선택하세요.")
        recipients = list(
            db.scalars(
                select(BobUser.employee_no)
                .join(BobUserGroup, BobUserGroup.employee_no == BobUser.employee_no)
                .where(
                    BobUser.status == "active",
                    BobUserGroup.group_name == request.target_group,
                )
            ).all()
        )
    else:
        recipients = list(dict.fromkeys(
            getattr(request, "employee_nos", None)
            or ([request.employee_no] if getattr(request, "employee_no", None) else [])
        ))
        if not recipients:
            raise HTTPException(status_code=422, detail="수신자를 한 명 이상 선택하세요.")
        known = set(
            db.scalars(
                select(BobUser.employee_no).where(
                    BobUser.status == "active", BobUser.employee_no.in_(recipients)
                )
            ).all()
        )
        if known != set(recipients):
            raise HTTPException(status_code=422, detail="미등록 또는 비활성 사용자가 포함되어 있습니다.")
    if not recipients:
        raise HTTPException(status_code=422, detail="활성 수신자가 없습니다.")
    return sorted(set(recipients))


def persist_notification(db: Session, request, created_by: str) -> dict:
    """공지, 대상, receipt, SSE outbox를 원자적으로 기록합니다."""
    recipients = resolve_active_recipients(db, request)
    links = [NotificationLink.model_validate(link) for link in request.links]
    notification_id = str(uuid4())
    if request.target_type == "all":
        targets = [("all", None)]
    elif request.target_type == "group":
        targets = [("group", request.target_group)]
    else:
        targets = [("employee", employee_no) for employee_no in recipients]

    notification = Notification(
        notification_id=notification_id,
        request_id=request.request_id,
        message=request.message,
        link_url=str(links[0].url) if links else None,
        created_by=created_by,
    )
    target_rows = [
        NotificationTarget(
            target_id=str(uuid4()),
            notification_id=notification_id,
            target_type=target_type,
            target_value=target_value,
        )
        for target_type, target_value in targets
    ]
    receipts = [
        NotificationReceipt(notification_id=notification_id, employee_no=employee_no)
        for employee_no in recipients
    ]
    event = ServiceRequestEvent(
        ticket_key="NOTICE",
        event_type="notification.created",
        payload={
            "notification_kind": "message",
            "notification_id": notification_id,
            "recipient_scope": request.target_type,
            "recipient_group": request.target_group,
            "recipient_employee_nos": recipients,
            "request_id": request.request_id,
            "title": request.title,
            "message": request.message,
            "links": [link.model_dump(mode="json") for link in links],
            "recipient_count_at_publish": len(recipients),
        },
    )
    try:
        db.add(notification)
        db.add_all(target_rows)
        db.add_all(receipts)
        db.add(event)
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise
    ServiceRequestRepository._notify_event_server(event.id)
    return {
        "event_id": event.id,
        "notification_id": notification_id,
        "event_type": event.event_type,
        "target_type": request.target_type,
        "title": request.title,
        "recipient_count": len(recipients),
        "created_at": event.created_at,
    }
