"""MCP tools/call 요청을 watsonx Orchestrate A2A message/send로 전달합니다."""

import hmac
import os

from dotenv import load_dotenv
from mcp.server import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uvicorn

from a2a_client.wxo_client import WXOClient, WXOClientError

load_dotenv()

MCP_TOKEN = os.getenv("WXO_MCP_BEARER_TOKEN", "replace-with-a-third-long-random-token")
client = WXOClient()
mcp = MCPServer(
    "A2A WXO MCP Server",
    instructions=(
        "watsonx Orchestrate agent에 보낼 메시지를 A2A 0.3.0으로 전달합니다. "
        "send_message_to_wxo의 message에는 실행할 자연어 업무 요청을 입력하세요."
    ),
)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Gateway에서 오는 MCP HTTP 호출의 별도 token을 검증합니다."""

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        supplied = request.headers.get("authorization", "")
        if MCP_TOKEN.startswith("replace-") or not hmac.compare_digest(
            supplied, f"Bearer {MCP_TOKEN}"
        ):
            return JSONResponse({"detail": "유효한 WXO MCP Bearer token이 필요합니다."}, status_code=401)
        return await call_next(request)


@mcp.tool()
def list_wxo_agents(limit: int = 100, offset: int = 0) -> dict:
    """Orchestrate A2A discovery에서 이름, 설명, endpoint, skill을 조회합니다."""
    try:
        cards = client.list_agents(limit=limit, offset=offset)
        # Agent Card 전체를 공개하지 않고 호출 선택에 필요한 필드만 반환합니다.
        return {
            "agents": [
                {
                    "name": card.get("name"),
                    "description": card.get("description"),
                    "url": card.get("url"),
                    "protocolVersion": card.get("protocolVersion"),
                    "preferredTransport": card.get("preferredTransport"),
                    "skills": card.get("skills", []),
                }
                for card in cards
            ]
        }
    except WXOClientError as exc:
        return {"error": str(exc)}


@mcp.tool()
def send_message_to_wxo(message: str, context_id: str = "", task_id: str = "") -> dict:
    """메시지를 Orchestrate agent에 전달하고 답변과 후속 대화 ID를 반환합니다.

    쓰기 요청은 Orchestrate agent 지침에 따라 사용자 확인을 받은 뒤 보내세요.
    input-required 응답이면 agent가 요청한 추가 정보를 담아 같은 context_id와 task_id로 다시 호출하세요.
    """
    try:
        return client.send_message(
            message=message,
            context_id=context_id or None,
            task_id=task_id or None,
        )
    except WXOClientError as exc:
        return {"error": str(exc)}


def main() -> None:
    """MCP SDK v2 Streamable HTTP endpoint를 실행합니다."""
    app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True)
    app.add_middleware(BearerTokenMiddleware)
    app.add_route("/health", lambda request: JSONResponse({"status": "ok", "service": "a2a-wxo-mcp"}))
    uvicorn.run(
        app,
        host=os.getenv("WXO_MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("WXO_MCP_PORT", "8031")),
    )


if __name__ == "__main__":
    main()

