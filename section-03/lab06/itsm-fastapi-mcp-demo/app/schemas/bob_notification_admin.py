"""관리자 UI의 Bob 사용자·그룹 관리 요청/응답 schema."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


EMPLOYEE_NO_PATTERN = r"^[A-Za-z0-9._-]+$"


class BobUserCreate(BaseModel):
    employee_no: str = Field(min_length=1, max_length=32, pattern=EMPLOYEE_NO_PATTERN)
    group_names: list[str] = Field(default_factory=list, max_length=100)
    is_admin: bool = False

    @field_validator("group_names")
    @classmethod
    def unique_groups(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ValueError("그룹 이름은 비어 있거나 중복될 수 없습니다.")
        return cleaned


class BobUserUpdate(BaseModel):
    group_names: list[str] = Field(default_factory=list, max_length=100)
    is_admin: bool = False
    status: Literal["active", "inactive"] = "active"

    @field_validator("group_names")
    @classmethod
    def unique_groups(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ValueError("그룹 이름은 비어 있거나 중복될 수 없습니다.")
        return cleaned


class BobGroupCreate(BaseModel):
    group_name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9._-]*$")
    description: str | None = Field(default=None, max_length=255)


class BobNotificationCreate(BaseModel):
    target_type: Literal["all", "group", "user"]
    target_group: str | None = Field(default=None, max_length=64)
    employee_nos: list[str] | None = Field(default=None, min_length=1, max_length=100)
    request_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=200)
    links: list[dict[str, str]] = Field(default_factory=list, max_length=10)


class BobIdentity(BaseModel):
    employee_no: str
    is_admin: bool
    status: Literal["active"]
    group_names: list[str]


class NotificationReadRequest(BaseModel):
    notification_ids: list[str] = Field(min_length=1, max_length=100)
