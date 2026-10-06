"""
test_a2a.py

IBM watsonx Orchestrate A2A 0.3.0 최종 테스트 프로그램

기능
------------------------------------------------------------
1. IBM Cloud IAM Access Token 발급
2. watsonx Orchestrate A2A Agent Discovery
3. WXO_AGENT_NAME으로 호출 대상 Agent 선택
4. 사용자가 Console에서 질문 입력
5. A2A message/send 호출
6. Agent의 최종 응답만 출력

설계 원칙
------------------------------------------------------------
- 질문(Message)을 코드에 hardcoding하지 않습니다.
- Agent 이름도 코드에 hardcoding하지 않습니다.
- Agent 이름은 .env의 WXO_AGENT_NAME에서 읽습니다.
- Target Agent를 찾지 못하면 다른 Agent로 fallback하지 않습니다.
- IAM Access Token은 로그에 출력하지 않습니다.
- A2A Task 응답에서는 artifacts를 우선 사용합니다.
- artifacts가 없으면 Message 또는 history의 agent 응답을 사용합니다.
- history의 user message는 최종 AGENT ANSWER에서 제외합니다.
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
# Environment
# ============================================================

# 프로젝트 루트의 .env 파일을 읽습니다.
load_dotenv()


# ============================================================
# Console Utility
# ============================================================

def print_title(title: str) -> None:
    """단계별 로그를 구분하기 위한 제목 출력 함수입니다."""

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_json(data: Any) -> None:
    """JSON을 한글이 깨지지 않도록 보기 좋게 출력합니다."""

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        )
    )


# ============================================================
# A2A Text Part 처리
# ============================================================

def extract_text_from_parts(
    parts: list[dict[str, Any]]
) -> list[str]:
    """
    A2A의 parts 배열에서 kind=text인 항목만 추출합니다.

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


def remove_duplicates(
    texts: list[str]
) -> list[str]:
    """
    artifacts와 history 등에 같은 응답이 중복될 수 있으므로
    입력 순서를 유지하면서 중복 문자열을 제거합니다.
    """

    result: list[str] = []

    for text in texts:

        if text not in result:
            result.append(text)

    return result


# ============================================================
# Agent 최종 응답 추출
# ============================================================

def extract_agent_answer(
    response_body: dict[str, Any]
) -> list[str]:
    """
    A2A response에서 Agent의 최종 답변만 추출합니다.

    우선순위
    ----------------------------------------------------------
    1. result.artifacts[].parts[]
    2. result.role == "agent"인 Message
    3. result.history[] 중 role == "agent"

    history에 포함된 role=user 메시지는 반환하지 않습니다.
    """

    result = response_body.get(
        "result",
        {}
    )

    if not isinstance(result, dict):
        return []

    # ========================================================
    # 1. Task Artifact
    # ========================================================

    artifacts = result.get(
        "artifacts",
        []
    )

    artifact_texts: list[str] = []

    if isinstance(artifacts, list):

        for artifact in artifacts:

            if not isinstance(artifact, dict):
                continue

            parts = artifact.get(
                "parts",
                []
            )

            if not isinstance(parts, list):
                continue

            artifact_texts.extend(
                extract_text_from_parts(parts)
            )

    # Artifact가 존재하면 최종 결과로 사용합니다.
    if artifact_texts:

        return remove_duplicates(
            artifact_texts
        )

    # ========================================================
    # 2. A2A Message
    # ========================================================
    #
    # 일부 Agent는 Task가 아니라 Message를 직접 반환할 수 있습니다.
    #
    # {
    #     "result": {
    #         "role": "agent",
    #         "parts": [...]
    #     }
    # }
    # ========================================================

    if result.get("role") == "agent":

        parts = result.get(
            "parts",
            []
        )

        if isinstance(parts, list):

            texts = extract_text_from_parts(
                parts
            )

            if texts:

                return remove_duplicates(
                    texts
                )

    # ========================================================
    # 3. Task History
    # ========================================================

    history = result.get(
        "history",
        []
    )

    history_texts: list[str] = []

    if isinstance(history, list):

        for message in history:

            if not isinstance(message, dict):
                continue

            # 사용자 입력은 최종 응답에서 제외합니다.
            if message.get("role") != "agent":
                continue

            parts = message.get(
                "parts",
                []
            )

            if not isinstance(parts, list):
                continue

            history_texts.extend(
                extract_text_from_parts(parts)
            )

    return remove_duplicates(
        history_texts
    )


# ============================================================
# A2A Agent Discovery
# ============================================================

async def discover_agents(
    client: httpx.AsyncClient,
    discovery_url: str,
    token: str
) -> list[dict[str, Any]]:
    """
    watsonx Orchestrate A2A Gateway의 agents/get을 호출하여
    사용 가능한 Agent Card 목록을 가져옵니다.
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

    print_json(
        request_body
    )

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
    # 오류가 발생하더라도 IBM 서버의 응답을 확인할 수 있도록
    # response body를 먼저 파싱합니다.
    # --------------------------------------------------------

    try:

        response_body = response.json()

    except Exception:

        print_title(
            "A2A agents/get RAW RESPONSE"
        )

        print(
            response.text
        )

        response.raise_for_status()

        raise

    print_title(
        "A2A agents/get RESPONSE"
    )

    print_json(
        response_body
    )

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

    # 실제 watsonx Orchestrate 응답 구조:
    #
    # result.agentCards
    #
    agent_cards = result.get(
        "agentCards",
        []
    )

    if not isinstance(agent_cards, list):

        raise RuntimeError(
            "agents/get 응답의 "
            "result.agentCards가 list 형식이 아닙니다."
        )

    return agent_cards


# ============================================================
# Discovery Agent 출력
# ============================================================

def print_discovered_agents(
    agent_cards: list[dict[str, Any]]
) -> None:
    """
    Discovery에서 반환된 Agent Card 정보를 출력합니다.
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

        # Collaborator / Skill 정보 출력
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
    WXO_AGENT_NAME과 정확히 일치하는 Agent를 선택합니다.

    Target Agent가 존재하지 않으면 다른 Agent로
    fallback하지 않고 오류를 발생시킵니다.
    """

    target_agent_name = (
        target_agent_name.strip()
    )

    print_title(
        "A2A TARGET AGENT"
    )

    print(
        "Requested Agent :",
        f"[{target_agent_name}]"
    )

    for card in agent_cards:

        discovered_name = str(
            card.get(
                "name",
                ""
            )
        ).strip()

        print(
            "Discovered Agent:",
            f"[{discovered_name}]"
        )

        if (
            discovered_name
            == target_agent_name
        ):

            return card

    # --------------------------------------------------------
    # 여기까지 왔다면 원하는 Agent가 없는 것입니다.
    # 절대로 다른 Agent를 선택하지 않습니다.
    # --------------------------------------------------------

    available_agents = [
        card.get("name")
        for card in agent_cards
    ]

    raise RuntimeError(
        "\n요청한 A2A Agent를 찾을 수 없습니다."
        f"\nRequested : [{target_agent_name}]"
        f"\nAvailable : {available_agents}"
    )


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
    선택한 watsonx Orchestrate A2A Agent에
    사용자의 메시지를 전달합니다.

    message는 코드에 고정하지 않고 main()에서 사용자가
    입력한 값을 그대로 전달받습니다.
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

                        # ★ 사용자가 입력한 질문
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

    print(
        agent_url
    )

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

    try:

        response_body = response.json()

    except Exception:

        print_title(
            "A2A message/send RAW RESPONSE"
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

    # HTTP 오류 확인
    if response.is_error:

        response.raise_for_status()

    # JSON-RPC 오류 확인
    if "error" in response_body:

        raise RuntimeError(
            "A2A message/send JSON-RPC 오류:\n"
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
        "IBM watsonx Orchestrate A2A 0.3.0 Test"
    )

    settings = get_settings()

    # ========================================================
    # 1. Target Agent 이름
    # ========================================================
    #
    # 코드에 Agent 이름을 hardcoding하지 않습니다.
    #
    # 반드시 .env에 다음과 같이 설정합니다.
    #
    # WXO_AGENT_NAME=<호출할 Agent 이름>
    #
    # ========================================================

    target_agent_name = os.getenv(
        "WXO_AGENT_NAME"
    )

    if not target_agent_name:

        raise RuntimeError(
            "WXO_AGENT_NAME 환경변수가 설정되어 있지 않습니다."
        )

    target_agent_name = (
        target_agent_name.strip()
    )

    if not target_agent_name:

        raise RuntimeError(
            "WXO_AGENT_NAME 값이 비어 있습니다."
        )

    # ========================================================
    # 2. 사용자 질문 입력
    # ========================================================
    #
    # 질문을 코드나 .env에 hardcoding하지 않습니다.
    #
    # 실행할 때 Console에서 입력합니다.
    #
    # ========================================================

    print_title(
        "A2A MESSAGE INPUT"
    )

    user_message = input(
        "질문을 입력하세요: "
    ).strip()

    if not user_message:

        raise RuntimeError(
            "질문이 입력되지 않았습니다."
        )

    print()
    print(
        "Target Agent:",
        target_agent_name
    )

    # ========================================================
    # 3. IAM Access Token 발급
    # ========================================================

    print()
    print(
        "[1/5] IBM Cloud IAM Access Token 발급"
    )

    token = await get_iam_token()

    print(
        "      IAM Access Token 발급 성공"
    )

    # IAM Access Token은 보안을 위해 출력하지 않습니다.

    # ========================================================
    # 4. A2A Discovery URL 생성
    # ========================================================

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

    # ========================================================
    # HTTP Timeout
    # ========================================================

    timeout = getattr(
        settings,
        "http_timeout",
        90
    )

    async with httpx.AsyncClient(
        timeout=float(timeout)
    ) as client:

        # ====================================================
        # 5. A2A Agent Discovery
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
        # 6. Target Agent 선택
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

        selected_name = selected_agent.get(
            "name"
        )

        selected_url = selected_agent.get(
            "url"
        )

        if not selected_url:

            raise RuntimeError(
                f"A2A Agent [{selected_name}]에 "
                "URL이 없습니다."
            )

        # ====================================================
        # Agent 선택 최종 검증
        # ====================================================

        if (
            str(selected_name).strip()
            != target_agent_name
        ):

            raise RuntimeError(
                "잘못된 A2A Agent가 선택되었습니다."
                f"\nRequested : [{target_agent_name}]"
                f"\nSelected  : [{selected_name}]"
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
        # 7. A2A message/send
        # ====================================================

        print()
        print(
            "[5/5] A2A message/send"
        )

        print()
        print(
            "User Message:",
            user_message
        )

        # ★ Console에서 입력받은 값을 그대로 전달합니다.
        response_body = await send_a2a_message(
            client=client,
            agent_url=selected_url,
            token=token,
            message=user_message
        )

    # ========================================================
    # 8. Agent 최종 답변 추출
    # ========================================================

    answers = extract_agent_answer(
        response_body
    )

    print_title(
        "AGENT ANSWER"
    )

    if not answers:

        print(
            "Agent의 text 응답을 찾지 못했습니다."
        )

        return

    for answer in answers:

        print(
            answer
        )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    # ========================================================
    # HTTP 오류
    # ========================================================

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

    # ========================================================
    # Network 오류
    # ========================================================

    except httpx.RequestError as exc:

        print_title(
            "NETWORK ERROR"
        )

        print(
            str(exc)
        )

        raise

    # ========================================================
    # 기타 오류
    # ========================================================

    except Exception as exc:

        print_title(
            "ERROR"
        )

        print(
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        raise
