"""
test_a2a.py

IBM watsonx Orchestrate A2A 0.3.0 최종 테스트 프로그램

처리 순서
------------------------------------------------------------
1. IBM Cloud IAM Access Token 발급
2. watsonx Orchestrate A2A agents/get 호출
3. Live 환경에 노출된 Agent Card 조회
4. WXO_AGENT_NAME과 정확하게 일치하는 Agent 선택
5. 선택된 Agent의 A2A URL로 message/send 호출
6. A2A 응답에서 "Agent의 최종 답변"만 추출

검증된 환경
------------------------------------------------------------
A2A Protocol : 0.3.0
Transport    : JSON-RPC

중요
------------------------------------------------------------
- 원하는 Agent를 찾지 못하면 다른 Agent로 fallback하지 않습니다.
- AskOrchestrate가 자동 선택되는 것을 방지합니다.
- IAM Access Token은 로그에 출력하지 않습니다.
- Task 응답에서는 artifacts를 우선 사용합니다.
- artifacts가 없으면 history의 role=agent 응답을 사용합니다.
- history의 role=user는 최종 답변에서 제외합니다.
"""

import asyncio
import json
import os
import uuid
from typing import Any

import httpx
from dotenv import load_dotenv

from app.auth import get_iam_token
from app.config import get_settings


# ============================================================
# .env 로딩
# ============================================================

load_dotenv()


# ============================================================
# Console Utility
# ============================================================

def print_title(title: str) -> None:
    """
    테스트 결과를 단계별로 쉽게 확인하기 위한
    Console Title 출력 함수입니다.
    """

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_json(data: Any) -> None:
    """
    JSON 데이터를 한글이 깨지지 않도록 출력합니다.
    """

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        )
    )


# ============================================================
# Text Part 추출
# ============================================================

def extract_text_from_parts(
    parts: list[dict[str, Any]]
) -> list[str]:
    """
    A2A parts 배열에서 text part만 추출합니다.

    예:

    "parts": [
        {
            "kind": "text",
            "text": "구매 승인 요청 목록 조회 결과입니다."
        }
    ]
    """

    texts: list[str] = []

    for part in parts:

        if not isinstance(part, dict):
            continue

        if (
            part.get("kind") == "text"
            and isinstance(part.get("text"), str)
        ):
            text = part["text"].strip()

            if text:
                texts.append(text)

    return texts


# ============================================================
# 최종 Agent Answer 추출
# ============================================================

def extract_agent_answer(
    response_body: dict[str, Any]
) -> list[str]:
    """
    watsonx Orchestrate A2A 응답에서
    Agent의 최종 답변만 추출합니다.

    우선순위
    ----------------------------------------------------------
    1. result.artifacts[].parts[]
    2. result.role == "agent" 인 Message
    3. result.history[] 중 role == "agent"

    기존 방식처럼 전체 JSON을 재귀 탐색하지 않습니다.

    이유:
    Task의 history에는 user message도 포함되므로 전체를
    재귀 탐색하면 다음처럼 출력될 수 있습니다.

        구매승인요청 목록을 조회해줘.
        구매 승인 요청 목록 조회 결과입니다. 총 5건입니다.

    최종 MCP 응답에서는 Agent의 답변만 필요하므로
    user message는 제외합니다.
    """

    result = response_body.get("result", {})

    if not isinstance(result, dict):
        return []

    # --------------------------------------------------------
    # 1. Artifact 우선
    #
    # watsonx Orchestrate Task 완료 응답에서는
    # conversation_result artifact에 최종 결과가
    # 들어오는 것을 실제 테스트에서 확인했습니다.
    # --------------------------------------------------------

    artifacts = result.get("artifacts", [])

    artifact_texts: list[str] = []

    if isinstance(artifacts, list):

        for artifact in artifacts:

            if not isinstance(artifact, dict):
                continue

            parts = artifact.get("parts", [])

            if isinstance(parts, list):

                artifact_texts.extend(
                    extract_text_from_parts(parts)
                )

    if artifact_texts:
        return remove_duplicates(artifact_texts)

    # --------------------------------------------------------
    # 2. Message 응답
    #
    # A2A가 Task가 아니라 바로 Message를 반환하는 경우:
    #
    # {
    #     "result": {
    #         "role": "agent",
    #         "parts": [...]
    #     }
    # }
    # --------------------------------------------------------

    if result.get("role") == "agent":

        parts = result.get("parts", [])

        if isinstance(parts, list):

            texts = extract_text_from_parts(parts)

            if texts:
                return remove_duplicates(texts)

    # --------------------------------------------------------
    # 3. Task History에서 Agent 메시지만 추출
    # --------------------------------------------------------

    history = result.get("history", [])

    history_texts: list[str] = []

    if isinstance(history, list):

        for message in history:

            if not isinstance(message, dict):
                continue

            # user message는 제외합니다.
            if message.get("role") != "agent":
                continue

            parts = message.get("parts", [])

            if isinstance(parts, list):

                history_texts.extend(
                    extract_text_from_parts(parts)
                )

    return remove_duplicates(history_texts)


# ============================================================
# 중복 제거
# ============================================================

def remove_duplicates(
    texts: list[str]
) -> list[str]:
    """
    동일한 text가 artifact/history에 중복될 수 있으므로
    입력 순서를 유지하면서 중복을 제거합니다.
    """

    result: list[str] = []

    for text in texts:

        if text not in result:
            result.append(text)

    return result


# ============================================================
# A2A Agent Discovery
# ============================================================

async def discover_agents(
    client: httpx.AsyncClient,
    discovery_url: str,
    token: str
) -> list[dict[str, Any]]:
    """
    watsonx Orchestrate A2A Gateway의
    agents/get JSON-RPC method를 호출합니다.

    반환값:
        Live 환경에서 발견된 Agent Card 목록
    """

    request_body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "agents/get",
        "params": {
            "limit": 100,
            "offset": 0
        }
    }

    print_title(
        "A2A agents/get REQUEST"
    )

    print_json(request_body)

    response = await client.post(
        discovery_url,
        headers={
            "Authorization":
                f"Bearer {token}",

            "Content-Type":
                "application/json",

            "Accept":
                "application/json"
        },
        json=request_body
    )

    print()
    print(
        "agents/get HTTP Status:",
        response.status_code
    )

    # --------------------------------------------------------
    # HTTP Error라도 IBM 서버가 반환한 body를 먼저
    # 확인할 수 있도록 JSON parsing을 먼저 수행합니다.
    # --------------------------------------------------------

    try:

        response_body = response.json()

    except Exception:

        print_title(
            "A2A agents/get RAW RESPONSE"
        )

        print(response.text)

        response.raise_for_status()

        raise

    print_title(
        "A2A agents/get RESPONSE"
    )

    print_json(response_body)

    # HTTP 오류 확인
    if response.is_error:
        response.raise_for_status()

    # JSON-RPC 오류 확인
    if "error" in response_body:

        raise RuntimeError(
            "A2A agents/get JSON-RPC 오류:\n"
            + json.dumps(
                response_body["error"],
                ensure_ascii=False,
                indent=2
            )
        )

    result = response_body.get(
        "result",
        {}
    )

    agent_cards = result.get(
        "agentCards",
        []
    )

    if not isinstance(agent_cards, list):

        raise RuntimeError(
            "agents/get 응답의 "
            "result.agentCards가 "
            "list 형식이 아닙니다."
        )

    return agent_cards


# ============================================================
# Discovery 결과 출력
# ============================================================

def print_discovered_agents(
    agent_cards: list[dict[str, Any]]
) -> None:
    """
    Discovery에서 발견한 A2A Agent 정보를 출력합니다.
    """

    print_title(
        "DISCOVERED A2A AGENTS"
    )

    if not agent_cards:

        print(
            "발견된 A2A Agent가 없습니다."
        )

        return

    for index, card in enumerate(
        agent_cards,
        start=1
    ):

        capabilities = card.get(
            "capabilities",
            {}
        )

        skills = card.get(
            "skills",
            []
        )

        print()
        print(
            f"[Agent {index}]"
        )

        print(
            "Name              :",
            card.get("name")
        )

        print(
            "Protocol Version  :",
            card.get("protocolVersion")
        )

        print(
            "Transport         :",
            card.get("preferredTransport")
        )

        print(
            "URL               :",
            card.get("url")
        )

        print(
            "Version           :",
            card.get("version")
        )

        print(
            "Streaming         :",
            capabilities.get("streaming")
        )

        print(
            "Skills            :",
            len(skills)
        )

        # ----------------------------------------------------
        # Collaborator가 A2A skill로 노출되었는지 확인
        # ----------------------------------------------------

        for skill in skills:

            print(
                "  └─ Skill:",
                skill.get("name"),
                f"(id={skill.get('id')})"
            )


# ============================================================
# Target Agent 선택
# ============================================================

def select_agent(
    agent_cards: list[dict[str, Any]],
    target_agent_name: str
) -> dict[str, Any]:
    """
    Agent 이름을 정확하게 비교하여
    호출 대상 A2A Agent를 선택합니다.

    매우 중요:
    ----------------------------------------------------------
    Target Agent를 찾지 못했다고 해서
    AskOrchestrate 같은 다른 Agent로 fallback하지 않습니다.

    잘못된 Agent를 호출하는 것보다
    즉시 실패시키는 것이 안전합니다.
    """

    target_agent_name = (
        target_agent_name.strip()
    )

    print_title(
        "A2A TARGET AGENT"
    )

    print(
        f"Requested Agent : "
        f"[{target_agent_name}]"
    )

    selected_agent = None

    for card in agent_cards:

        discovered_name = str(
            card.get(
                "name",
                ""
            )
        ).strip()

        print(
            f"Discovered Agent: "
            f"[{discovered_name}]"
        )

        if (
            discovered_name
            == target_agent_name
        ):

            selected_agent = card
            break

    # --------------------------------------------------------
    # Target을 찾지 못하면 즉시 오류
    # --------------------------------------------------------

    if selected_agent is None:

        available_agents = [
            card.get("name")
            for card in agent_cards
        ]

        raise RuntimeError(
            "\n요청한 A2A Agent를 "
            "찾을 수 없습니다."
            f"\nRequested : "
            f"[{target_agent_name}]"
            f"\nAvailable : "
            f"{available_agents}"
        )

    return selected_agent


# ============================================================
# A2A message/send
# ============================================================

async def send_a2a_message(
    client: httpx.AsyncClient,
    agent_url: str,
    token: str,
    message: str
) -> dict[str, Any]:
    """
    선택된 Agent Card의 URL에
    A2A message/send JSON-RPC 요청을 전송합니다.
    """

    request_body = {

        "jsonrpc": "2.0",

        "id":
            str(uuid.uuid4()),

        "method":
            "message/send",

        "params": {

            "message": {

                "messageId":
                    str(uuid.uuid4()),

                "role":
                    "user",

                "parts": [
                    {
                        "kind":
                            "text",

                        "text":
                            message
                    }
                ]
            }
        }
    }

    print_title(
        "A2A AGENT ENDPOINT"
    )

    print(agent_url)

    print_title(
        "A2A message/send REQUEST"
    )

    print_json(
        request_body
    )

    response = await client.post(
        agent_url,
        headers={

            "Authorization":
                f"Bearer {token}",

            "Content-Type":
                "application/json",

            "Accept":
                "application/json"
        },
        json=request_body
    )

    print()

    print(
        "message/send HTTP Status:",
        response.status_code
    )

    # --------------------------------------------------------
    # Response JSON
    # --------------------------------------------------------

    try:

        response_body = response.json()

    except Exception:

        print_title(
            "A2A message/send "
            "RAW RESPONSE"
        )

        print(
            response.text
        )

        response.raise_for_status()

        raise

    print_title(
        "A2A message/send RESPONSE"
    )

    print_json(
        response_body
    )

    # HTTP 오류
    if response.is_error:

        response.raise_for_status()

    # JSON-RPC 오류
    if "error" in response_body:

        raise RuntimeError(
            "A2A message/send "
            "JSON-RPC 오류:\n"
            + json.dumps(
                response_body["error"],
                ensure_ascii=False,
                indent=2
            )
        )

    return response_body


# ============================================================
# Main
# ============================================================

async def main() -> None:

    print_title(
        "IBM watsonx Orchestrate "
        "A2A 0.3.0 Test"
    )

    settings = get_settings()

    # --------------------------------------------------------
    # Target Agent
    # --------------------------------------------------------

    target_agent_name = os.getenv(
        "WXO_AGENT_NAME",
        "purchase Approval Orchestrator"
    ).strip()

    # --------------------------------------------------------
    # Test Message
    # --------------------------------------------------------

    test_message = os.getenv(
        "A2A_TEST_MESSAGE",
        "구매승인요청 번호 3번 조회해줘."
    ).strip()

    print()
    print("Environment:")

    print(
        "WXO_AGENT_NAME =",
        repr(target_agent_name)
    )

    print(
        "A2A_TEST_MESSAGE =",
        repr(test_message)
    )

    # --------------------------------------------------------
    # 1. IAM Token
    # --------------------------------------------------------

    print()

    print(
        "[1/5] IBM Cloud IAM "
        "Access Token 발급"
    )

    token = await get_iam_token()

    print(
        "      IAM Access Token "
        "발급 성공"
    )

    # Token 자체는 출력하지 않습니다.

    # --------------------------------------------------------
    # 2. Discovery URL
    # --------------------------------------------------------

    discovery_url = (
        f"{settings.instance_base_url}"
        f"/v1/orchestrate/A2A"
    )

    print()

    print(
        "[2/5] watsonx Orchestrate "
        "A2A Agent Discovery"
    )

    print()
    print(
        "A2A Discovery URL"
    )

    print(
        discovery_url
    )

    timeout = getattr(
        settings,
        "http_timeout",
        90
    )

    # --------------------------------------------------------
    # HTTP Client
    # --------------------------------------------------------

    async with httpx.AsyncClient(
        timeout=float(timeout)
    ) as client:

        # ====================================================
        # 3. Agent Discovery
        # ====================================================

        agent_cards = await discover_agents(
            client=client,
            discovery_url=discovery_url,
            token=token
        )

        print()

        print(
            "[3/5] Agent Card 분석"
        )

        print_discovered_agents(
            agent_cards
        )

        # ====================================================
        # 4. Target Agent 선택
        # ====================================================

        print()

        print(
            "[4/5] A2A Agent 선택"
        )

        selected_agent = select_agent(
            agent_cards=agent_cards,
            target_agent_name=target_agent_name
        )

        print_title(
            "SELECTED AGENT CARD"
        )

        print_json(
            selected_agent
        )

        selected_name = (
            selected_agent.get("name")
        )

        selected_url = (
            selected_agent.get("url")
        )

        if not selected_url:

            raise RuntimeError(
                f"A2A Agent "
                f"[{selected_name}]에 "
                "URL이 없습니다."
            )

        # ----------------------------------------------------
        # Safety Check
        #
        # message/send 직전에 Target을 다시 검증합니다.
        # ----------------------------------------------------

        if (
            str(selected_name).strip()
            != target_agent_name
        ):

            raise RuntimeError(
                "잘못된 A2A Agent가 "
                "선택되었습니다."
                f"\nRequested : "
                f"[{target_agent_name}]"
                f"\nSelected  : "
                f"[{selected_name}]"
            )

        print()
        print(
            "Target verification: OK"
        )

        print(
            "Selected Agent :",
            selected_name
        )

        print(
            "Selected URL   :",
            selected_url
        )

        # ====================================================
        # 5. A2A message/send
        # ====================================================

        print()

        print(
            "[5/5] A2A message/send"
        )

        print()

        print(
            f"User Message: "
            f"{test_message}"
        )

        response_body = (
            await send_a2a_message(
                client=client,
                agent_url=selected_url,
                token=token,
                message=test_message
            )
        )

    # ========================================================
    # Agent Answer 추출
    # ========================================================

    answers = extract_agent_answer(
        response_body
    )

    print_title(
        "AGENT ANSWER"
    )

    if not answers:

        print(
            "Agent의 text 응답을 "
            "찾지 못했습니다."
        )

        return

    for answer in answers:

        print(answer)


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    # --------------------------------------------------------
    # HTTP Status Error
    # --------------------------------------------------------

    except httpx.HTTPStatusError as exc:

        print_title(
            "HTTP ERROR"
        )

        print(
            "Status :",
            exc.response.status_code
        )

        print(
            "URL    :",
            exc.request.url
        )

        print()
        print(
            "Response:"
        )

        try:

            print_json(
                exc.response.json()
            )

        except Exception:

            print(
                exc.response.text
            )

        raise

    # --------------------------------------------------------
    # Network Error
    # --------------------------------------------------------

    except httpx.RequestError as exc:

        print_title(
            "NETWORK ERROR"
        )

        print(
            str(exc)
        )

        raise

    # --------------------------------------------------------
    # 기타 오류
    # --------------------------------------------------------

    except Exception as exc:

        print_title(
            "ERROR"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        raise
