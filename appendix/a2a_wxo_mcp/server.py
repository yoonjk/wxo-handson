"""Bearer-protected Streamable HTTP MCP -> watsonx Orchestrate A2A gateway."""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uvicorn

from a2a_client.wxo_client import WXOClient, WXOClientError

# Resolve .env relative to project root, not a potentially unexpected working dir.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
MCP_TOKEN = os.getenv("WXO_MCP_BEARER_TOKEN", "")
if not MCP_TOKEN or MCP_TOKEN.startswith("replace-"):
    raise RuntimeError("WXO_MCP_BEARER_TOKEN에 강력한 임의 토큰을 설정해야 합니다.")
client = WXOClient()
mcp = MCPServer(
    "A2A WXO MCP Server",
    instructions=("먼저 list_wxo_agents로 허용된 Agent 목록을 확인하세요. "
                  "send_message_to_wxo 호출에는 Agent Card의 정확한 agent_name과 업무 요청 message를 입력하세요."),
)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/health" and request.method == "GET":
            return await call_next(request)
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, f"Bearer {MCP_TOKEN}"):
            return JSONResponse({"detail": "유효한 MCP Bearer Token이 필요합니다."}, status_code=401)
        return await call_next(request)


@mcp.tool()
def list_wxo_agents(limit: int = 100, offset: int = 0) -> dict:
    """허용된 WXO SaaS Live Agent 이름, 설명, URL, skills를 반환합니다."""
    try:
        cards = client.list_agents(limit=limit, offset=offset)
        return {"agents": [{
            "name": c.get("name"), "description": c.get("description"),
            "url": c.get("url") or c.get("endpoint"),
            "protocolVersion": c.get("protocolVersion"),
            "skills": c.get("skills", []),
        } for c in cards]}
    except WXOClientError as exc:
        return {"error": str(exc)}


@mcp.tool()
def send_message_to_wxo(agent_name: str, message: str, context_id: str = "", task_id: str = "") -> dict:
    """정확한 Agent 이름을 지정해 A2A message/send를 호출합니다.

    쓰기/변경 요청은 사용자가 확인한 뒤 전송합니다.
    input-required 상태에서는 해당 Agent의 context_id 및 task_id를 유지하여 후속 메시지를 전송합니다.
    Agent 사이에 context_id 또는 task_id를 혼용하지 마세요.
    """
    try:
        return client.send_message(agent_name=agent_name, message=message,
                                   context_id=context_id or None, task_id=task_id or None)
    except WXOClientError as exc:
        return {"error": str(exc), "agent_name": agent_name}


def main() -> None:
    host = os.getenv("WXO_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("WXO_MCP_PORT", "8050"))
    extra_hosts = [h.strip() for h in os.getenv("WXO_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=os.getenv("WXO_MCP_DNS_REBINDING_PROTECTION", "true").lower() == "true",
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *extra_hosts],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*",
                         *[f"http://{h}" for h in extra_hosts], *[f"https://{h}" for h in extra_hosts]],
    )
    app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True,
                                  host=host, transport_security=security)
    app.add_middleware(BearerTokenMiddleware)
    app.add_route("/health", lambda request: JSONResponse({"status": "ok", "service": "a2a-wxo-mcp"}), methods=["GET"])
    print(f"[a2a-wxo-mcp] listen={host}:{port}, allowed_agents={sorted(client.allowed_agents)}", flush=True)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
