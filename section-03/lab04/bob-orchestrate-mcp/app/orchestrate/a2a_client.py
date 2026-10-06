from typing import Any
import uuid
import httpx

from app.auth import get_iam_token
from app.config import get_settings
from app.orchestrate.common import extract_text


def _rpc(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """A2A JSON-RPC 2.0 request envelope을 생성합니다."""
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params,
    }


def _find_interaction_url(value: Any) -> str | None:
    """agents/get 응답에서 agent-specific interaction URL을 탐색합니다.

    IBM API의 응답 필드가 환경/버전에 따라 확장될 수 있으므로
    URL처럼 보이는 interaction 관련 값을 재귀적으로 찾습니다.
    찾지 못하면 임의 URL을 만들어 호출하지 않고 명시적으로 오류를 냅니다.
    """

    if isinstance(value, dict):
        # 우선 의미가 명확한 키를 검사합니다.
        for key in (
            "interactionEndpoint",
            "interaction_endpoint",
            "interactionUrl",
            "interaction_url",
            "url",
        ):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                # 단순 agent-card URL보다 interaction 문맥의 URL을 우선합니다.
                if "interaction" in key.lower() or "/a2a" in candidate.lower():
                    return candidate

        for key, nested in value.items():
            if "interaction" in key.lower():
                found = _find_interaction_url(nested)
                if found:
                    return found

        for nested in value.values():
            found = _find_interaction_url(nested)
            if found:
                return found

    elif isinstance(value, list):
        for item in value:
            found = _find_interaction_url(item)
            if found:
                return found

    return None


async def discover_agent(agent_id: str | None = None) -> dict[str, Any]:
    """공통 A2A discovery endpoint의 agents/get을 호출합니다."""

    settings = get_settings()
    target_agent_id = agent_id or settings.wxo_agent_id
    token = await get_iam_token()

    url = f"{settings.instance_base_url}/v1/orchestrate/A2A"

    # IBM A2A discovery의 agent 지정 파라미터는 배포 버전에 따라
    # 문서/OpenAPI에서 확인해야 할 수 있습니다. 여기서는 agentId를 사용하고,
    # 서버가 다른 이름을 요구할 경우 이 한 곳만 수정하면 됩니다.
    payload = _rpc(
        "agents/get",
        {
            "agentId": target_agent_id,
        },
    )

    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()


async def send_a2a_message(
    message: str,
    agent_id: str | None = None,
    interaction_url: str | None = None,
) -> dict[str, Any]:
    """Agent-specific A2A interaction endpoint로 message/send를 호출합니다.

    interaction_url이 주어지지 않으면 먼저 agents/get discovery를 수행합니다.
    """

    settings = get_settings()
    target_agent_id = agent_id or settings.wxo_agent_id
    token = await get_iam_token()

    discovery: dict[str, Any] | None = None

    if not interaction_url:
        discovery = await discover_agent(target_agent_id)
        interaction_url = _find_interaction_url(discovery)

    if not interaction_url:
        raise RuntimeError(
            "A2A agents/get 응답에서 agent interaction endpoint를 찾지 못했습니다. "
            "실제 discovery JSON을 확인한 뒤 interaction URL 필드명을 "
            "app/orchestrate/a2a_client.py의 _find_interaction_url()에 반영하세요."
        )

    payload = _rpc(
        "message/send",
        {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": message,
                    }
                ],
            }
        },
    )

    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        response = await client.post(
            interaction_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        body = response.json()

    return {
        "mode": "a2a",
        "agent_id": target_agent_id,
        "interaction_url": interaction_url,
        "text": extract_text(body),
        "response": body,
        "discovery": discovery,
    }
