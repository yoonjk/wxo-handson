"""ITSM Service Request ORM 모델."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServiceRequest(Base):
    """운영 유지보수 SR, 상태와 처리 이력을 저장합니다."""

    __tablename__ = "itsm_service_requests"

    # Python int maps to the signed MySQL BIGINT primary key.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    service_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="NEW", index=True)
    requester: Mapped[str] = mapped_column(String(120), nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assignee_employee_no: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    worklog: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def ticket_key(self) -> str:
        """사람이 읽을 수 있는 SR 번호를 반환합니다."""
        return f"SR-{self.id:06d}"
