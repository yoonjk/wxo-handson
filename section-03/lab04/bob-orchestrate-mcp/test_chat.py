"""
test_chat.py

IBM watsonx Orchestrate Chat Completions API 테스트 프로그램

기능
------------------------------------------------------------
1. .env에서 watsonx Orchestrate Agent ID 조회
2. 사용자가 Console에서 질문 입력
3. IBM Cloud IAM Access Token 발급
4. watsonx Orchestrate Chat Completions API 호출
5. Agent의 최종 응답 출력

설계 원칙
------------------------------------------------------------
- 사용자 질문을 코드에 hardcoding하지 않습니다.
- 사용자 질문을 .env에도 저장하지 않습니다.
- 실행 시 input()으로 질문을 입력받습니다.
- Agent ID는 .env의 WXO_AGENT_ID에서 읽습니다.
- IAM Access Token은 로그에 출력하지 않습니다.
- HTTP 오류 발생 시 서버 응답을 출력합니다.
"""

import asyncio
import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from app.auth import get_iam_token
from app.config import get_settings


# ============================================================
# Environment
# ============================================================

# 프로젝트 루트의 .env 파일을 로딩합니다.
load_dotenv()


# ============================================================
# Console Utility
# ============================================================

def print_title(title: str) -> None:
    """테스트 단계별 로그를 구분하기 위한 제목 출력 함수입니다."""

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
# Chat Response Text 추출
# ============================================================

def extract_chat_answer(
    response_body: dict[str, Any]
) -> str:
    """
    watsonx Orchestrate Chat Completions 응답에서
    Agent의 최종 text를 추출합니다.

    기본적으로 OpenAI 호환 Chat Completions 형태인

        choices[0].message.content

    를 우선 처리합니다.

    content가 문자열이면 그대로 반환합니다.

    content가 배열 형태인 경우에는 text 값을 찾아서
    하나의 문자열로 결합합니다.
    """

    choices = response_body.get(
        "choices",
        []
    )

    if not isinstance(choices, list) or not choices:

        return ""

    first_choice = choices[0]

    if not isinstance(first_choice, dict):

        return ""

    message = first_choice.get(
        "message",
        {}
    )

    if not isinstance(message, dict):

        return ""

    content = message.get(
        "content"
    )

    # --------------------------------------------------------
    # Case 1
    #
    # 일반적인 응답:
    #
    # "content": "구매 승인 요청 목록입니다."
    # --------------------------------------------------------

    if isinstance(content, str):

        return content.strip()

    # --------------------------------------------------------
    # Case 2
    #
    # content가 배열인 경우
    #
    # "content": [
    #     {
    #         "type": "text",
    #         "text": "..."
    #     }
    # ]
    # --------------------------------------------------------

    if isinstance(content, list):

        texts: list[str] = []

        for item in content:

            if not isinstance(item, dict):
                continue

            text = item.get("text")

            if isinstance(text, str):

                text = text.strip()

                if text:
                    texts.append(text)

        return "\n".join(texts)

    return ""


# ============================================================
# Chat Completions 호출
# ============================================================

async def send_chat_message(
    client: httpx.AsyncClient,
    chat_url: str,
    token: str,
    message: str
) -> dict[str, Any]:
    """
    watsonx Orchestrate Chat Completions API에
    사용자 메시지를 전달합니다.

    message는 코드에 고정하지 않습니다.

    main()에서 사용자가 input()으로 입력한 값을
    그대로 전달받습니다.
    """

    request_body = {
        "stream": False,

        "messages": [
            {
                "role": "user",

                # ★ 사용자가 입력한 메시지
                "content": message
            }
        ]
    }

    # --------------------------------------------------------
    # Request 정보 출력
    # --------------------------------------------------------

    print_title(
        "CHAT COMPLETIONS ENDPOINT"
    )

    print(
        chat_url
    )

    print_title(
        "CHAT COMPLETIONS REQUEST"
    )

    print_json(
        request_body
    )

    # --------------------------------------------------------
    # API 호출
    # --------------------------------------------------------

    response = await client.post(
        chat_url,
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
        "Chat HTTP Status:",
        response.status_code
    )

    # --------------------------------------------------------
    # Response JSON 처리
    # --------------------------------------------------------

    try:

        response_body = response.json()

    except Exception:

        print_title(
            "CHAT RAW RESPONSE"
        )

        print(
            response.text
        )

        response.raise_for_status()

        raise

    print_title(
        "CHAT COMPLETIONS RESPONSE"
    )

    print_json(
        response_body
    )

    # --------------------------------------------------------
    # HTTP 오류 확인
    #
    # 오류 body를 먼저 출력한 뒤 HTTPStatusError를 발생시킵니다.
    # --------------------------------------------------------

    if response.is_error:

        response.raise_for_status()

    return response_body


# ============================================================
# Main
# ============================================================

async def main() -> None:

    print_title(
        "IBM watsonx Orchestrate Chat API Test"
    )

    # --------------------------------------------------------
    # 공통 watsonx Orchestrate 설정을 가져옵니다.
    #
    # settings.instance_base_url 예:
    #
    # https://api.<region>.watson-orchestrate.cloud.ibm.com
    # /instances/<instance-id>
    # --------------------------------------------------------

    settings = get_settings()

    # ========================================================
    # 1. Agent ID
    # ========================================================
    #
    # Agent ID는 코드에 hardcoding하지 않습니다.
    #
    # .env:
    #
    # WXO_AGENT_ID=<agent-id>
    #
    # 기본값을 사용하지 않습니다.
    # 설정되지 않았으면 즉시 오류를 발생시킵니다.
    # ========================================================

    agent_id = os.getenv(
        "WXO_AGENT_ID"
    )

    if not agent_id:

        raise RuntimeError(
            "WXO_AGENT_ID 환경변수가 "
            "설정되어 있지 않습니다."
        )

    agent_id = agent_id.strip()

    if not agent_id:

        raise RuntimeError(
            "WXO_AGENT_ID 값이 비어 있습니다."
        )

    # ========================================================
    # 2. 사용자 질문 입력
    # ========================================================
    #
    # 질문을 다음과 같이 코드에 넣지 않습니다.
    #
    # message = "구매승인요청 목록을 조회해줘."
    #
    # .env에도 A2A_TEST_MESSAGE 같은 형태로 넣지 않습니다.
    #
    # 프로그램 실행 시 사용자가 직접 입력합니다.
    # ========================================================

    print_title(
        "CHAT MESSAGE INPUT"
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
        "Agent ID:",
        agent_id
    )

    # ========================================================
    # 3. IBM Cloud IAM Access Token
    # ========================================================

    print()
    print(
        "[1/3] IBM Cloud IAM Access Token 발급"
    )

    token = await get_iam_token()

    print(
        "      IAM Access Token 발급 성공"
    )

    # 보안을 위해 IAM Access Token 자체는 출력하지 않습니다.

    # ========================================================
    # 4. Chat Completions URL 생성
    # ========================================================
    #
    # 최종 URL:
    #
    # {instance_base_url}
    # /v1/orchestrate/{agent_id}/chat/completions
    #
    # ========================================================

    chat_url = (
        f"{settings.instance_base_url}"
        f"/v1/orchestrate/"
        f"{agent_id}"
        f"/chat/completions"
    )

    print()
    print(
        "[2/3] watsonx Orchestrate "
        "Chat Completions 호출 준비"
    )

    print()
    print(
        "Chat URL:"
    )

    print(
        chat_url
    )

    # ========================================================
    # 5. HTTP Timeout
    # ========================================================

    timeout = getattr(
        settings,
        "http_timeout",
        90
    )

    # ========================================================
    # 6. Chat API 호출
    # ========================================================

    async with httpx.AsyncClient(
        timeout=float(timeout)
    ) as client:

        print()
        print(
            "[3/3] Chat message 전송"
        )

        print()
        print(
            "User Message:",
            user_message
        )

        response_body = await send_chat_message(
            client=client,
            chat_url=chat_url,
            token=token,

            # ★ Console 입력값을 그대로 전달합니다.
            message=user_message
        )

    # ========================================================
    # 7. Agent 최종 답변 추출
    # ========================================================

    answer = extract_chat_answer(
        response_body
    )

    print_title(
        "AGENT ANSWER"
    )

    if not answer:

        print(
            "Chat 응답에서 Agent의 "
            "text 응답을 찾지 못했습니다."
        )

        # 응답 형식이 예상과 다를 경우
        # 이미 위의 CHAT COMPLETIONS RESPONSE에
        # 전체 JSON이 출력되어 있으므로 분석할 수 있습니다.
        return

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
