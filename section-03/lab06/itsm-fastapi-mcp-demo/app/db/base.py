"""ORM model들이 상속할 SQLAlchemy declarative base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """테이블 metadata를 모아 schema 생성에 사용합니다."""

