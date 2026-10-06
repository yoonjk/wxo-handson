"""관리자 API token을 잃어버렸을 때 기존 관리자 token을 DB에서 복구합니다.

일반 발급 API는 관리자 token이 필요하므로, 이 복구 도구는 서버의
프로젝트 .env에 설정된 DB에 직접 접속합니다. employee_no가 이미 활성
관리자여야 하며, 해당 계정의 기존 활성 token은 모두 폐기한 뒤 새 token
하나를 저장합니다. DB에는 원문이 아닌 SHA-256 hash만 저장합니다.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import secrets
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

# Import after loading the project's DB settings.
from app.db.connection import SessionLocal  # noqa: E402
from app.models.bob_notification import BobUser, BobUserToken  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="기존 활성 Bob 관리자의 token을 DB에서 안전하게 재발급합니다."
    )
    parser.add_argument("employee_no", help="기존 관리자 employee number")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="기존 활성 token 폐기 확인을 생략",
    )
    args = parser.parse_args()
    employee_no = args.employee_no.strip()
    if not employee_no:
        print("employee_no를 입력하세요.", file=sys.stderr)
        return 2

    if not args.yes:
        print(
            f"{employee_no}의 기존 활성 token을 모두 폐기하고 새 token을 발급합니다."
        )
        answer = getpass.getpass("계속하려면 YES를 입력하세요: ")
        if answer != "YES":
            print("취소했습니다.")
            return 0

    db = SessionLocal()
    try:
        user = db.get(BobUser, employee_no)
        if user is None:
            print(f"등록된 Bob 사용자가 없습니다: {employee_no}", file=sys.stderr)
            return 1
        if not user.is_admin:
            print(
                f"{employee_no}는 관리자 계정이 아닙니다. DB 변경 없이 종료합니다.",
                file=sys.stderr,
            )
            return 1
        if user.status != "active":
            print(
                f"{employee_no}는 비활성 사용자입니다. DB 변경 없이 종료합니다.",
                file=sys.stderr,
            )
            return 1

        now = datetime.utcnow()
        active_tokens = db.scalars(
            select(BobUserToken).where(
                BobUserToken.employee_no == employee_no,
                BobUserToken.revoked_at.is_(None),
            )
        ).all()
        for old_token in active_tokens:
            old_token.revoked_at = now

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        db.add(
            BobUserToken(
                token_id=str(uuid4()),
                employee_no=employee_no,
                token_hash=token_hash,
                token_last_four=token[-4:],
            )
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        print(f"DB token 복구 실패: {exc.__class__.__name__}", file=sys.stderr)
        print("프로젝트 .env의 DB 접속 설정과 DB 상태를 확인하세요.", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"복구 완료: employee_no={employee_no}")
    print(f"표시용 값: ••••{token[-4:]}")
    print("원문 token은 아래에 한 번만 표시됩니다. 안전한 곳에 복사하세요.")
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
