"""Service Request API 요청 및 응답 schema."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ServiceRequestStatus = Literal["NEW", "IN_PROGRESS", "RESOLVED", "CLOSED"]


class ServiceRequestCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200, description="유지보수 요청 제목")
    description: str = Field(min_length=3, description="증상, 영향, 재현 절차와 기대 결과")
    service_name: str = Field(min_length=2, max_length=120, description="대상 애플리케이션/서비스")
    environment: str = Field(default="production", min_length=2, max_length=32)
    severity: Severity = Field(default="MEDIUM")
    requester: str = Field(min_length=2, max_length=120)
    assignee: str | None = Field(default=None, max_length=120)
    assignee_employee_no: str | None = Field(
        default=None,
        min_length=2,
        max_length=32,
        description="Bob 팝업 수신 대상 직원 번호. Event MCP 사용자 identity와 매칭됩니다.",
    )


class StatusUpdate(BaseModel):
    status: ServiceRequestStatus


class WorklogCreate(BaseModel):
    note: str = Field(min_length=2, max_length=2000)
    author: str = Field(min_length=2, max_length=120)


class ServiceRequestView(BaseModel):
    ticket_key: str
    title: str
    description: str
    service_name: str
    environment: str
    severity: Severity
    status: ServiceRequestStatus
    requester: str
    assignee: str | None
    assignee_employee_no: str | None
    worklog: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, request):
        """SQLAlchemy ORM row를 안정된 API 응답 schema로 변환합니다."""
        return cls(
            ticket_key=request.ticket_key,
            title=request.title,
            description=request.description,
            service_name=request.service_name,
            environment=request.environment,
            severity=request.severity,
            status=request.status,
            requester=request.requester,
            assignee=request.assignee,
            assignee_employee_no=request.assignee_employee_no,
            worklog=request.worklog,
            created_at=request.created_at,
            updated_at=request.updated_at,
        )
