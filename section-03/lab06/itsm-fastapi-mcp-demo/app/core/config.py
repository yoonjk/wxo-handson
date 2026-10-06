"""환경변수와 프로젝트 루트의 .env 파일에서 애플리케이션 설정을 읽습니다."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 서비스 실행 위치가 달라도 프로젝트 루트의 .env를 읽도록 절대 경로를 구성합니다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """DB 접속 정보와 서비스 인증값을 검증해 보관합니다."""

    # 실제 환경변수가 .env보다 우선합니다. .env의 알 수 없는 키는 무시합니다.
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "demo"
    db_username: str = "nexweb"
    db_password: str = ""
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    itsm_api_token: str = "replace-with-a-long-random-demo-token"
    itsm_event_mcp_internal_url: str = Field(
        default="http://127.0.0.1:8032",
        validation_alias=AliasChoices("ITSM_EVENT_MCP_INTERNAL_URL", "SR_EVENT_MCP_INTERNAL_URL"),
    )
    itsm_event_mcp_bearer_token: str = Field(
        default="replace-with-an-event-mcp-token",
        validation_alias=AliasChoices("ITSM_EVENT_MCP_BEARER_TOKEN", "SR_EVENT_MCP_BEARER_TOKEN"),
    )
    app_name: str = "Demo ITSM API"
    app_version: str = "1.0.0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스 안에서 동일 설정 인스턴스를 재사용합니다."""
    return Settings()
