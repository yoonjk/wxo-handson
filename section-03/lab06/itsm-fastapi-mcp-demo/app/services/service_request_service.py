"""SR 유효성, 상태 전이와 저장소 호출을 조합합니다."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.service_request import ServiceRequest
from app.repositories.service_request_repository import ServiceRequestRepository
from app.schemas.service_request import (
    ServiceRequestCreate,
    ServiceRequestStatus,
    Severity,
    StatusUpdate,
    WorklogCreate,
)

# 데모 업무 규칙: 배포 전에는 IN_PROGRESS, 배포 성공 후 RESOLVED, 관찰 후 CLOSED입니다.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"IN_PROGRESS"},
    "IN_PROGRESS": {"RESOLVED"},
    "RESOLVED": {"IN_PROGRESS", "CLOSED"},
    "CLOSED": set(),
}


class ServiceRequestService:
    def __init__(self, repository: type[ServiceRequestRepository] = ServiceRequestRepository):
        self.repository = repository

    def create(self, db: Session, payload: ServiceRequestCreate) -> ServiceRequest:
        request = ServiceRequest(**payload.model_dump(), status="NEW", worklog="")
        return self.repository.create(db, request)

    def list(
        self,
        db: Session,
        status: ServiceRequestStatus | None,
        severity: Severity | None,
        service_name: str | None,
        limit: int,
    ) -> list[ServiceRequest]:
        return self.repository.list(db, status, severity, service_name, limit)

    def get(self, db: Session, ticket_key: str) -> ServiceRequest:
        if not ticket_key.startswith("SR-") or not ticket_key[3:].isdigit():
            raise HTTPException(status_code=404, detail="Service Request를 찾을 수 없습니다.")
        request = self.repository.get_by_id(db, int(ticket_key[3:]))
        if request is None:
            raise HTTPException(status_code=404, detail="Service Request를 찾을 수 없습니다.")
        return request

    def update_status(self, db: Session, ticket_key: str, payload: StatusUpdate) -> ServiceRequest:
        request = self.get(db, ticket_key)
        allowed = ALLOWED_TRANSITIONS[request.status]
        if payload.status not in allowed:
            raise HTTPException(
                status_code=409,
                detail=f"{request.status}에서 {payload.status}(으)로 변경할 수 없습니다. 허용 상태: {sorted(allowed)}",
            )
        previous_status = request.status
        request.status = payload.status
        return self.repository.save(
            db, request, f"service_request.status_changed.{previous_status.lower()}_to_{payload.status.lower()}"
        )

    def add_worklog(self, db: Session, ticket_key: str, payload: WorklogCreate) -> ServiceRequest:
        request = self.get(db, ticket_key)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"[{stamp}] {payload.author}: {payload.note}"
        request.worklog = f"{request.worklog}\n{entry}".strip()
        return self.repository.save(db, request, "service_request.worklog_added")


service_request_service = ServiceRequestService()
