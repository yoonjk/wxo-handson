"""API를 통해 MySQL에 SR을 저장하고 재조회하는 스모크 테스트."""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("ITSM_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("ITSM_API_TOKEN", "")


def request_json(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    """공유 API token을 붙여 FastAPI endpoint를 호출합니다."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 요청 실패 ({exc.code}): {detail}") from exc


def main() -> int:
    """DB readiness 확인 후 새 행을 생성하고 동일 행을 다시 읽습니다."""
    if not TOKEN:
        print("ITSM_API_TOKEN을 .env에 설정하세요.", file=sys.stderr)
        return 2

    try:
        health = request_json("/health/db")
        print(f"MySQL 연결 확인: {health}")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        created = request_json(
            "/service-requests",
            method="POST",
            payload={
                "title": f"DB persistence smoke test {stamp}",
                "service_name": "smoke-test-service",
                "environment": "development",
                "description": "smoke_test_api.py가 MySQL 저장 및 재조회 확인을 위해 만든 데모 SR입니다.",
                "severity": "LOW",
                "requester": "smoke-test",
                "assignee": None,
            },
        )
        key = created["ticket_key"]
        loaded = request_json(f"/service-requests/{key}")

        if loaded["ticket_key"] != key or loaded["title"] != created["title"]:
            raise RuntimeError("생성한 SR과 재조회 결과가 일치하지 않습니다.")

        print(f"MySQL 기록 및 재조회 성공: {key} / {loaded['status']}")
        print("이 smoke test SR은 itsm_service_requests 테이블에 남습니다.")
        return 0
    except (OSError, RuntimeError, KeyError, ValueError) as exc:
        print(f"검증 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
