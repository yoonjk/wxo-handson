# lab03/server.py
import os

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("guardrails-mcp")


@mcp.tool()
def mcp_guardrails_tool(text: str) -> str:
    """입력 텍스트를 받아 MCP 서버 연결을 확인합니다."""
    return f"입력 확인 완료: {len(text)}자"


if __name__ == "__main__":
    # 컨테이너 또는 호스팅 환경에서 외부 요청을 받도록 전체 인터페이스에 바인딩합니다.
    host = os.getenv("GUARDRAILS_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    # MCP SDK 코드에서는 transport 이름을 하이픈으로 표기합니다.
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
    )