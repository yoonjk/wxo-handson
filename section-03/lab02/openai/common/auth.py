"""간단한 Bearer 토큰 인증 미들웨어.

- A2A_AUTH_TOKEN 이 비어 있으면 인증을 하지 않습니다.
- Agent Card(/.well-known/...) 는 누구나 조회할 수 있도록 인증에서 제외합니다.
- watsonx Orchestrate 의 external agent 설정(auth_scheme: BEARER_TOKEN)의 token 과 같은 값을 사용하세요.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str = ""):
        super().__init__(app)
        self.token = token.strip()

    async def dispatch(self, request: Request, call_next):
        if not self.token or request.url.path.startswith("/.well-known/"):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {self.token}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)
