"""MySQL engine, 세션 factory, 요청별 세션 의존성을 제공합니다."""

from collections.abc import Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# URL.create가 password 특수문자를 안전하게 인코딩합니다.
database_url = URL.create(
    drivername="mysql+pymysql",
    username=settings.db_username,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    database=settings.db_name,
    query={"charset": "utf8mb4"},
)

engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """요청마다 DB session을 열고 응답 후 반드시 닫습니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

