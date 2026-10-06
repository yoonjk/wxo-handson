"""Bob 사용자·토큰·그룹 및 공지 전송/수신 상태를 저장하는 모델."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BobUser(Base):
    """Bob 사용자 계정과 알림 관리자 역할."""

    __tablename__ = "bob_user"

    employee_no: Mapped[str] = mapped_column(String(32), primary_key=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BobUserToken(Base):
    """사용자별 Bearer token의 해시만 보관합니다. 원문 token은 발급 응답에서 한 번만 노출합니다."""

    __tablename__ = "bob_user_token"

    token_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    employee_no: Mapped[str] = mapped_column(
        ForeignKey("bob_user.employee_no", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BobGroup(Base):
    """Bob 알림 대상 그룹."""

    __tablename__ = "bob_group"

    group_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BobUserGroup(Base):
    """사용자와 그룹의 다대다 매핑."""

    __tablename__ = "bob_user_group"

    employee_no: Mapped[str] = mapped_column(
        ForeignKey("bob_user.employee_no", ondelete="CASCADE"), primary_key=True
    )
    group_name: Mapped[str] = mapped_column(
        ForeignKey("bob_group.group_name", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Notification(Base):
    """전송된 공지 본문과 작성자를 보존합니다."""

    __tablename__ = "notification"

    notification_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(String(200), nullable=False)
    link_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_by: Mapped[str] = mapped_column(
        ForeignKey("bob_user.employee_no"), nullable=False, index=True
    )


class NotificationTarget(Base):
    """공지 전송 당시 선택된 전체/그룹/개인 대상을 기록합니다."""

    __tablename__ = "notification_target"

    target_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    notification_id: Mapped[str] = mapped_column(
        ForeignKey("notification.notification_id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_value: Mapped[str | None] = mapped_column(String(64), nullable=True)


class NotificationReceipt(Base):
    """사용자별 전달 및 읽음 시각."""

    __tablename__ = "notification_receipt"

    notification_id: Mapped[str] = mapped_column(
        ForeignKey("notification.notification_id", ondelete="CASCADE"), primary_key=True
    )
    employee_no: Mapped[str] = mapped_column(
        ForeignKey("bob_user.employee_no", ondelete="CASCADE"), primary_key=True
    )
    delivered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
