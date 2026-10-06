"""ITSM event 조회와 대상별 사용자 알림 API schema."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator


class ServiceRequestEventView(BaseModel):
    id: int
    ticket_key: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_model(cls, event):
        return cls(
            id=event.id,
            ticket_key=event.ticket_key,
            event_type=event.event_type,
            payload=event.payload,
            created_at=event.created_at,
        )


class NotificationLink(BaseModel):
    """메시지에 연결할 자료의 표시 이름과 웹 URL."""

    title: str = Field(min_length=1, max_length=120)
    url: AnyHttpUrl


class NotificationPublishRequest(BaseModel):
    """MCP에서 전달하는 수신 대상 지정 공지 요청."""

    target_type: Literal["all", "group", "user"] = Field(
        description="all: 등록된 Bob 사용자 전체, group: 지정 group, user: 지정 employee_no"
    )
    request_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=200)
    target_group: str | None = Field(default=None, max_length=64)
    employee_no: str | None = Field(default=None, max_length=32)
    employee_nos: list[str] | None = Field(default=None, min_length=1, max_length=100)
    links: list[NotificationLink] = Field(default_factory=list, max_length=10)
    recipient_count: int = Field(default=0, ge=0, exclude=True)

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_type == "group" and not self.target_group:
            raise ValueError("target_type이 group이면 target_group이 필요합니다.")
        if self.target_type == "user" and not self.employee_no and not self.employee_nos:
            raise ValueError("target_type이 user이면 employee_no가 필요합니다.")
        if self.target_type == "user" and self.employee_no and self.employee_nos:
            raise ValueError("employee_no와 employee_nos 중 하나만 지정하세요.")
        if self.target_type != "group" and self.target_group is not None:
            raise ValueError("target_group은 target_type이 group일 때만 지정할 수 있습니다.")
        if self.target_type != "user" and (self.employee_no is not None or self.employee_nos is not None):
            raise ValueError("employee_no(s)는 target_type이 user일 때만 지정할 수 있습니다.")
        if self.employee_nos and len(set(self.employee_nos)) != len(self.employee_nos):
            raise ValueError("employee_nos 중복 값은 허용하지 않습니다.")
        return self


class NotificationPublishResponse(BaseModel):
    event_id: int
    event_type: str
    target_type: Literal["all", "group", "user"]
    title: str
    recipient_count: int
    created_at: datetime
