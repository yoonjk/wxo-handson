"""전체/그룹/개인 공지의 outbox 저장과 실제 SSE 수신 범위를 확인합니다.

이 스크립트는 테스트 메시지를 MySQL outbox에 기록하고, .env에 설정한 각 Bob
사용자의 개별 토큰으로 SSE를 구독해 지정 대상만 메시지를 받는지 검증합니다.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def read_env_with_legacy(new_name: str, legacy_name: str, default: str = "") -> str:
    """Prefer the renamed setting while accepting existing SR_EVENT_* .env keys."""
    return os.getenv(new_name, os.getenv(legacy_name, default))


def wait_for_message(
    employee_no: str,
    token: str,
    base_url: str,
    event_id: int,
    expected_title: str,
    expected_links: list[dict[str, str]],
    timeout_seconds: float,
) -> bool:
    """개별 사용자 SSE로 특정 테스트 메시지가 도착하는지 확인합니다."""
    url = f"{base_url.rstrip('/')}/events"
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    params = {"after_event_id": max(0, event_id - 1)}
    timeout = httpx.Timeout(connect=4.0, read=timeout_seconds, write=4.0, pool=4.0)
    try:
        with httpx.stream("GET", url, headers=headers, params=params, timeout=timeout) as response:
            response.raise_for_status()
            data_lines: list[str] = []
            deadline = time.monotonic() + timeout_seconds
            for line in response.iter_lines():
                if time.monotonic() >= deadline:
                    break
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif line == "":
                    if data_lines:
                        try:
                            event = json.loads("\n".join(data_lines))
                        except json.JSONDecodeError:
                            event = {}
                        if (
                            str(event.get("event_id")) == str(event_id)
                            and event.get("title") == expected_title
                            and event.get("links", []) == expected_links
                        ):
                            print(f"[received] employee_no={employee_no} event_id={event_id}")
                            return True
                    data_lines.clear()
    except httpx.ReadTimeout:
        pass
    except httpx.HTTPError as exc:
        print(f"[sse_error] employee_no={employee_no} detail={exc}")
    print(f"[not_received] employee_no={employee_no}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="전체/그룹/개별 Bob 공지 SSE 테스트")
    parser.add_argument("--target", required=True, choices=("all", "group", "user"))
    parser.add_argument("--group", help="group 대상일 때 그룹명")
    parser.add_argument("--employee-no", help="user 대상일 때 employee_no")
    parser.add_argument("--timeout", type=float, default=8.0, help="사용자별 SSE 대기 초 (기본 8초)")
    args = parser.parse_args()

    token_map_json = read_env_with_legacy(
        "ITSM_EVENT_USER_TOKENS_JSON", "SR_EVENT_USER_TOKENS_JSON", "{}"
    )
    groups_json = read_env_with_legacy(
        "ITSM_EVENT_USER_GROUPS_JSON", "SR_EVENT_USER_GROUPS_JSON", "{}"
    )
    try:
        tokens = json.loads(token_map_json)
        groups = json.loads(groups_json)
    except json.JSONDecodeError as exc:
        print(f"ITSM_EVENT_*_JSON 설정 형식이 올바르지 않습니다: {exc}", file=sys.stderr)
        return 2
    if not isinstance(tokens, dict) or not isinstance(groups, dict):
        print("ITSM_EVENT_*_JSON 설정은 JSON object여야 합니다.", file=sys.stderr)
        return 2
    if any(
        not isinstance(employee_no, str)
        or not employee_no.strip()
        or not isinstance(token, str)
        or not token.strip()
        for employee_no, token in tokens.items()
    ):
        print("ITSM_EVENT_USER_TOKENS_JSON은 비어 있지 않은 employee_no/token 문자열만 포함해야 합니다.", file=sys.stderr)
        return 2
    if any(
        not isinstance(employee_no, str)
        or not isinstance(user_groups, list)
        or any(not isinstance(group, str) or not group.strip() for group in user_groups)
        for employee_no, user_groups in groups.items()
    ):
        print("ITSM_EVENT_USER_GROUPS_JSON은 employee_no별 group 문자열 배열이어야 합니다.", file=sys.stderr)
        return 2
    if not tokens:
        print("ITSM_EVENT_USER_TOKENS_JSON에 Bob 사용자를 등록하세요.", file=sys.stderr)
        return 2

    if args.target == "all":
        expected = set(tokens)
        target_group = employee_no = None
    elif args.target == "group":
        if not args.group:
            print("--target group에는 --group이 필요합니다.", file=sys.stderr)
            return 2
        expected = {
            employee_no
            for employee_no, user_groups in groups.items()
            if args.group in user_groups and employee_no in tokens
        }
        target_group, employee_no = args.group, None
    else:
        if not args.employee_no:
            print("--target user에는 --employee-no가 필요합니다.", file=sys.stderr)
            return 2
        if args.employee_no not in tokens:
            print("employee_no가 ITSM_EVENT_USER_TOKENS_JSON에 없습니다.", file=sys.stderr)
            return 2
        expected = {args.employee_no}
        target_group, employee_no = None, args.employee_no

    if not expected:
        print("선택한 대상에 속한 등록 Bob 사용자가 없습니다.", file=sys.stderr)
        return 2

    base_url = read_env_with_legacy(
        "ITSM_EVENT_MCP_INTERNAL_URL", "SR_EVENT_MCP_INTERNAL_URL", "http://127.0.0.1:8032"
    ).rstrip("/")
    api_base_url = os.getenv("ITSM_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    api_token = os.getenv("ITSM_API_TOKEN", "")
    if not api_token or api_token.startswith("replace-"):
        print("ITSM_API_TOKEN을 .env에 설정하세요.", file=sys.stderr)
        return 2

    title = f"Notification target test {uuid.uuid4().hex[:8]}"
    links = [
        {"title": "Test runbook", "url": f"https://example.com/runbooks/{uuid.uuid4().hex}"},
        {"title": "Release notes", "url": f"https://example.com/releases/{uuid.uuid4().hex}"},
    ]
    body = {
        "target_type": args.target,
        "target_group": target_group,
        "employee_no": employee_no,
        "title": title,
        "message": f"SSE scope test: {args.target}",
        "links": links,
    }
    try:
        response = httpx.post(
            f"{api_base_url}/service-request-events/notifications",
            json=body,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=10.0,
        )
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPError as exc:
        print(f"공지 발행 실패: {exc}", file=sys.stderr)
        if getattr(exc, "response", None) is not None:
            print(exc.response.text, file=sys.stderr)
        return 1

    event_id = int(result["event_id"])
    print(
        f"[published] event_id={event_id} target={args.target} "
        f"expected_recipients={len(expected)} title={title}"
    )
    print("각 설정된 Bob 사용자에게 일회성 SSE 연결을 열어 수신 대상을 확인합니다.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tokens), 64)) as pool:
        futures = {
            pool.submit(
                wait_for_message,
                employee_no,
                token,
                base_url,
                event_id,
                title,
                links,
                args.timeout,
            ): employee_no
            for employee_no, token in tokens.items()
        }
        results = {employee_no: future.result() for future, employee_no in futures.items()}

    received = {employee_no for employee_no, got_message in results.items() if got_message}
    missing = expected - received
    unexpected = received - expected
    print(f"[summary] expected={sorted(expected)} received={sorted(received)}")
    if missing or unexpected:
        print(f"[scope_mismatch] missing={sorted(missing)} unexpected={sorted(unexpected)}")
        return 1
    print("[success] 대상 범위가 일치합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
