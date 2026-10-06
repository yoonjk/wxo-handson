from typing import Literal

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.orchestrate.a2a_client import discover_agent, send_a2a_message
from app.orchestrate.chat_client import send_chat_message

settings = get_settings()

# Bob에서 표시될 MCP Server 이름입니다.
mcp = FastMCP(
    "watsonx-orchestrate-gateway",
    host=settings.mcp_host,
    port=settings.mcp_port,
)


@mcp.tool()
async def ask_orchestrate_agent(
    message: str,
    mode: Literal["chat", "a2a"] | None = None,
    agent_id: str | None = None,
) -> dict:
    """watsonx Orchestrate Agent에게 자연어 요청을 전달합니다.

    Args:
        message:
            Agent에게 전달할 사용자 요청.
            예: "구매요청 PR-1001의 승인 상태를 알려줘."

        mode:
            "chat"은 /chat/completions API를 사용합니다.
            "a2a"는 agents/get으로 Agent를 발견한 뒤 A2A message/send를 사용합니다.
            생략하면 DEFAULT_CALL_MODE 환경설정을 사용합니다.

        agent_id:
            특정 Agent ID를 지정할 때 사용합니다.
            생략하면 WXO_AGENT_ID를 사용합니다.

    Returns:
        Agent의 text 응답과 원본 API response.
    """

    call_mode = mode or settings.default_call_mode

    if call_mode == "chat":
        return await send_chat_message(message, agent_id)

    if call_mode == "a2a":
        return await send_a2a_message(message, agent_id)

    raise ValueError("mode는 'chat' 또는 'a2a'여야 합니다.")


@mcp.tool()
async def ask_purchase_agent(
    message: str,
) -> dict:
    """구매 업무를 담당하는 기본 watsonx Orchestrate Agent에게 요청합니다.

    Bob이 구매 요청 조회, 승인 상태, 승인자, 구매 정책 관련 요청을 받았을 때
    이 Tool을 선택하도록 업무 의미를 명확히 기술합니다.
    """

    return await send_chat_message(message)


@mcp.tool()
async def discover_orchestrate_agent(
    agent_id: str | None = None,
) -> dict:
    """watsonx Orchestrate A2A agents/get을 이용해 Agent 정보를 조회합니다."""

    return await discover_agent(agent_id)


if __name__ == "__main__":
    # Streamable HTTP를 사용하면 Bob IDE에서 원격 MCP Server로 연결할 수 있습니다.
    # FastMCP의 기본 endpoint는 SDK 버전에 따라 /mcp 로 노출됩니다.
    mcp.run(transport="streamable-http")
