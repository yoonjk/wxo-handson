from typing import Any
import httpx

from app.auth import get_iam_token
from app.config import get_settings
from app.orchestrate.common import extract_text


async def send_chat_message(
    message: str,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Orchestrate Agent의 OpenAI-compatible chat/completions API를 호출합니다."""

    settings = get_settings()
    target_agent_id = agent_id or settings.wxo_agent_id
    token = await get_iam_token()

    url = (
        f"{settings.instance_base_url}"
        f"/v1/orchestrate/{target_agent_id}/chat/completions"
    )

    payload = {
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": message,
            }
        ],
    }

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
        body = response.json()

    return {
        "mode": "chat",
        "agent_id": target_agent_id,
        "text": extract_text(body),
        "response": body,
    }
