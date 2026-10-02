from collections.abc import Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속하는 기본 클래스입니다."""


settings = get_settings()
# URL.create()를 사용하면 비밀번호에 !, @, / 같은 문자가 포함되어도
# 수동 URL 인코딩 없이 안전하게 SQLAlchemy 연결 URL을 만들 수 있습니다.
database_url = URL.create(
    drivername="mysql+pymysql",
    username=settings.db_user,
    password=settings.db_password.get_secret_value(),
    host=settings.db_host,
    port=settings.db_port,
    database=settings.db_name,
    query={"charset": "utf8mb4"},
)
engine = create_engine(
    database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """요청마다 DB 세션을 만들고 응답 후 안전하게 닫습니다."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
