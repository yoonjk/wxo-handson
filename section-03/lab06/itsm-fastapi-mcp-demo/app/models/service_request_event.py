"""ITSM 업무 및 일반 알림 이벤트를 저장하는 transactional outbox 모델."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceRequestEvent(Base):
    """업무 변경과 같은 transaction 안에 기록되는 이벤트 로그."""

    __tablename__ = "itsm_event_outbox"

    # Python int maps to the signed MySQL BIGINT event cursor.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_key: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
