import asyncio
import time
import httpx

from app.config import get_settings

IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"

# 프로세스 메모리에 IAM token과 만료시간을 보관합니다.
# 이는 Bob 사용자의 access token을 저장하는 것이 아니라,
# MCP Gateway 자체가 Orchestrate API를 호출하기 위한 service credential cache입니다.
_token: str | None = None
_expires_at: float = 0.0
_lock = asyncio.Lock()


async def get_iam_token() -> str:
    """IBM Cloud API Key로 IAM access token을 발급/재사용합니다."""

    global _token, _expires_at

    now = time.time()
    if _token and now < _expires_at - 60:
        return _token

    async with _lock:
        now = time.time()
        if _token and now < _expires_at - 60:
            return _token

        settings = get_settings()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                IAM_TOKEN_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={
                    "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                    "apikey": settings.wxo_api_key,
                },
            )
            response.raise_for_status()
            body = response.json()

        _token = body["access_token"]

        # IAM 응답의 expiration은 epoch seconds입니다.
        # 혹시 없을 경우 expires_in을 이용해 계산합니다.
        expiration = body.get("expiration")
        if expiration:
            _expires_at = float(expiration)
        else:
            _expires_at = now + float(body.get("expires_in", 3600*24))

        return _token
