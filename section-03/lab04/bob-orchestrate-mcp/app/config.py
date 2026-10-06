from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 환경설정.

    실제 credential은 소스에 하드코딩하지 않고 환경변수에서 읽습니다.
    """

    wxo_base_url: str
    wxo_instance_id: str
    wxo_agent_id: str
    wxo_api_key: str

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8030
    default_call_mode: str = "a2a"
    http_timeout: float = 90.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def instance_base_url(self) -> str:
        """Orchestrate instance URL을 일관되게 생성합니다."""
        return (
            f"{self.wxo_base_url.rstrip('/')}"
            f"/instances/{self.wxo_instance_id}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
