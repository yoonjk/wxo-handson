from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수에서 애플리케이션 설정을 읽습니다."""

    app_name: str = "Purchase Approval API"
    app_version: str = "1.0.0"
    # DB 접속 정보에는 기본값을 두지 않습니다. 하나라도 누락되면
    # 애플리케이션 시작 단계에서 ValidationError가 발생하여 잘못된 DB로
    # 연결되는 상황을 방지합니다.
    db_host: str
    db_port: int
    db_user: str
    db_password: SecretStr
    db_name: str
    db_echo: bool = False
    auto_create_tables: bool = False

    # watsonx Orchestrate가 호출할 절대 URL입니다.
    # 예: http://nexweb.ddnsgeek.com/purchase
    public_api_url: str = "http://nexweb.ddnsgeek.com/purchase"
    a2a_bearer_token: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
