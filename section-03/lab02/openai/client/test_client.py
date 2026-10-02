"""A2A 테스트 클라이언트 (Orchestrate 없이 에이전트 단독 테스트용).

사용 예:
  python -m client.test_client --url http://localhost:8020 "hi"
  python -m client.test_client --url http://localhost:10000 "고객별 총 주문 금액 상위 3명"
  python -m client.test_client --url http://localhost:10000 --stream "상품 목록 보여줘"
"""
import argparse
import warnings
import asyncio
import os
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest, SendStreamingMessageRequest

load_dotenv()
warnings.filterwarnings("ignore", category=DeprecationWarning)  # A2AClient(legacy) 경고 숨김


def _texts(parts) -> list[str]:
    return [p["text"] for p in parts or [] if p.get("kind") == "text"]


def extract_texts(result: dict) -> list[str]:
    """A2A 응답/이벤트 종류별로 에이전트가 보낸 텍스트만 추출합니다 (사용자 입력 history 제외)."""
    kind = result.get("kind")
    if kind == "message":
        return _texts(result.get("parts"))
    if kind == "task":
        out = [t for a in result.get("artifacts", []) for t in _texts(a.get("parts"))]
        return out or _texts(result.get("status", {}).get("message", {}).get("parts"))
    if kind == "status-update":
        state = result.get("status", {}).get("state")
        return [f"({state}) {t}" for t in _texts(result.get("status", {}).get("message", {}).get("parts"))]
    if kind == "artifact-update":
        return _texts(result.get("artifact", {}).get("parts"))
    return []


async def main(url: str, text: str, stream: bool, verbose: bool) -> None:
    token = os.getenv("A2A_AUTH_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async with httpx.AsyncClient(timeout=180, headers=headers) as http:
        card = await A2ACardResolver(httpx_client=http, base_url=url).get_agent_card()
        print(f"[Agent Card] {card.name} v{card.version} (protocol {card.protocol_version})")
        print(f"  skills: {[s.name for s in card.skills]}\n")

        client = A2AClient(httpx_client=http, agent_card=card)
        params = MessageSendParams(
            message={
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "messageId": uuid4().hex,
            }
        )

        if stream:
            req = SendStreamingMessageRequest(id=str(uuid4()), params=params)
            async for chunk in client.send_message_streaming(req):
                data = chunk.model_dump(mode="json", exclude_none=True)
                if verbose:
                    print(chunk.model_dump_json(exclude_none=True, indent=2))
                for t in extract_texts(data.get("result", {})):
                    print(f"[stream] {t}")
        else:
            req = SendMessageRequest(id=str(uuid4()), params=params)
            resp = await client.send_message(req)
            data = resp.model_dump(mode="json", exclude_none=True)
            if verbose:
                print(resp.model_dump_json(exclude_none=True, indent=2))
            print("[응답]")
            print("\n".join(extract_texts(data.get("result", {}))) or data)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("text", nargs="?", default="hello")
    p.add_argument("--url", default="http://nexweb.ddnsgeek.com/hello")
    p.add_argument("--stream", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true", help="원본 JSON 출력")
    a = p.parse_args()
    asyncio.run(main(a.url, a.text, a.stream, a.verbose))

