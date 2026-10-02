"""새 SR을 등록해 transactional outbox와 Bob 팝업 경로를 점검합니다.

실제 IDE 팝업은 Bob 안에서 실행 중인 bob_notifier 확장이 표시합니다.
이 스크립트는 SR 등록 및 outbox 발행까지 자동 확인하고, 사용자에게 Bob 팝업 확인을 안내합니다.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    # --help remains usable before project requirements are installed.
    def load_dotenv() -> None:
        return None

load_dotenv()

BASE_URL = os.getenv("ITSM_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("ITSM_API_TOKEN", "")


def request_json(path: str, method: str = "GET", payload: dict | None = None):
    """ITSM API 인증 헤더를 붙여 JSON 요청을 보냅니다."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ITSM API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ITSM API에 연결할 수 없습니다: {exc.reason}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="테스트 SR을 등록하고 Bob 알림용 outbox 이벤트가 발행됐는지 확인합니다."
    )
    parser.add_argument("--title", default="Bob 팝업 E2E 테스트 SR")
    parser.add_argument(
        "--description",
        default="test_bob_popup.py가 IBM Bob Notification 팝업 확인용으로 만든 데모 SR입니다.",
    )
    parser.add_argument("--service", default="bob-notification-demo")
    parser.add_argument("--environment", default="development")
    parser.add_argument("--severity", choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], default="HIGH")
    parser.add_argument("--requester", default="bob-popup-e2e-test")
    parser.add_argument(
        "--assignee-employee-no",
        default="EMP1001",
        help="알림 대상 Bob 사용자의 employee_no (.env token map key와 일치해야 함)",
    )
    parser.add_argument("--event-timeout", type=int, default=15, help="outbox 확인 대기 시간(초)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not TOKEN:
        print("ITSM_API_TOKEN을 프로젝트 .env에 설정하세요.", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    title = f"{args.title} {stamp}"
    payload = {
        "title": title,
        "description": args.description,
        "service_name": args.service,
        "environment": args.environment,
        "severity": args.severity,
        "requester": args.requester,
        "assignee": None,
        "assignee_employee_no": args.assignee_employee_no,
    }

    try:
        created = request_json("/service-requests", method="POST", payload=payload)
        ticket_key = created["ticket_key"]
        print(
            f"[1/3] SR 등록 완료: {ticket_key} / {created['status']} / "
            f"담당 employee_no={created.get('assignee_employee_no')}"
        )

        query = urllib.parse.urlencode({"ticket_key": ticket_key, "limit": 20})
        deadline = time.monotonic() + max(1, min(args.event_timeout, 120))
        event = None
        while time.monotonic() < deadline:
            events = request_json(f"/service-request-events?{query}")
            event = next(
                (
                    item for item in events
                    if item.get("event_type") == "service_request.created"
                    and item.get("payload", {}).get("recipient_employee_no") == args.assignee_employee_no
                ),
                None,
            )
            if event:
                break
            time.sleep(0.5)

        if not event:
            raise RuntimeError(
                f"{ticket_key}는 생성됐지만 outbox의 service_request.created 이벤트를 찾지 못했습니다."
            )

        print(f"[2/3] MySQL outbox 발행 확인: event_id={event['id']} / {event['event_type']}")
        print(f"[2/3] 대상 Bob 사용자 확인: {event['payload']['recipient_employee_no']}")
        print("[3/3] 해당 employee_no로 연결된 Bob IDE에서 ‘새 운영 SR’ 팝업을 확인하세요.")
        print("      Bob 확장의 ITSM SR Notifier Output 채널에서 [notification] 로그도 확인할 수 있습니다.")
        print(f"확인용 SR: {ticket_key} — {created['title']}")
        return 0
    except (OSError, RuntimeError, KeyError, ValueError) as exc:
        print(f"테스트 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
