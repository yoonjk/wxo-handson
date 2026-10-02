# test_chat_debug.py
#
# watsonx Orchestrate /chat/completions API Debug Test
#
# 기존 app/orchestrate/chat_client.py를 사용하지 않습니다.
# 따라서 기존 코드의 raise_for_status() 영향을 받지 않습니다.

import asyncio
import json

import httpx

from app.auth import get_iam_token
from app.config import get_settings


async def main():

    settings = get_settings()

    print("=" * 80)
    print("watsonx Orchestrate Chat API - DEBUG")
    print("=" * 80)

    # ---------------------------------------------------------
    # 1. 환경설정 확인
    # ---------------------------------------------------------

    print()
    print("[1] Configuration")

    print("Instance Base URL:")
    print(settings.instance_base_url)

    print()
    print("Agent ID:")
    print(settings.wxo_agent_id)

    # ---------------------------------------------------------
    # 2. IAM Token
    # ---------------------------------------------------------

    print()
    print("[2] IBM Cloud IAM Token")

    token = await get_iam_token()

    print("IAM token acquired successfully.")
    print("Token is NOT displayed.")

    # ---------------------------------------------------------
    # 3. Chat API URL
    # ---------------------------------------------------------

    url = (
        f"{settings.instance_base_url}"
        f"/v1/orchestrate/"
        f"{settings.wxo_agent_id}"
        f"/chat/completions"
    )

    print()
    print("[3] Request URL")
    print(url)

    # ---------------------------------------------------------
    # 4. Request Body
    # ---------------------------------------------------------

    payload = {
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": "구매요청 목록을 조회해줘."
            }
        ]
    }

    print()
    print("[4] Request Body")

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        )
    )

    # ---------------------------------------------------------
    # 5. HTTP 호출
    #
    # 중요:
    # 여기서는 raise_for_status()를 먼저 호출하지 않습니다.
    #
    # 서버가 400을 반환하더라도 response body를 먼저 확인합니다.
    # ---------------------------------------------------------

    print()
    print("[5] Sending request...")

    async with httpx.AsyncClient(
        timeout=90.0
    ) as client:

        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            json=payload
        )

    # ---------------------------------------------------------
    # 6. HTTP Status
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("HTTP RESPONSE")
    print("=" * 80)

    print()
    print("Status Code:")
    print(response.status_code)

    # ---------------------------------------------------------
    # 7. Response Headers
    # ---------------------------------------------------------

    print()
    print("Response Headers:")

    for name, value in response.headers.items():

        # 불필요하게 긴 일부 header는 제외해도 됩니다.
        print(f"{name}: {value}")

    # ---------------------------------------------------------
    # 8. RAW Response
    #
    # 가장 중요합니다.
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("RAW RESPONSE BODY")
    print("=" * 80)

    print()
    print(response.text)

    # ---------------------------------------------------------
    # 9. JSON Response
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("JSON RESPONSE BODY")
    print("=" * 80)

    try:

        body = response.json()

        print(
            json.dumps(
                body,
                ensure_ascii=False,
                indent=2
            )
        )

    except Exception as exc:

        print()
        print("Response is not JSON.")
        print("JSON parsing error:")
        print(exc)

    # ---------------------------------------------------------
    # 10. 최종 결과
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)

    if 200 <= response.status_code < 300:

        print()
        print("SUCCESS")

    else:

        print()
        print(
            f"FAILED - HTTP {response.status_code}"
        )

        print()
        print(
            "위 RAW RESPONSE BODY를 확인하세요."
        )


if __name__ == "__main__":

    asyncio.run(main())
