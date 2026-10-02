"""FastAPI REST endpoint용 Bearer token 검증."""

import hmac

from fastapi import Header, HTTPException

from app.core.config import get_settings


def require_demo_token(authorization: str | None = Header(default=None)) -> None:
    """MCP adapter가 보낸 token을 상수 시간 비교로 검증합니다."""
    expected = get_settings().itsm_api_token
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if expected.startswith("replace-") or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="유효한 데모 Bearer token이 필요합니다.")

