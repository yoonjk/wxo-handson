"""기존 JSON 환경설정을 새 DB 사용자 모델로 한 번만 옮깁니다."""

import hashlib
import json
import os
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bob_notification import BobGroup, BobUser, BobUserGroup, BobUserToken


def seed_bob_users_from_environment(db: Session) -> int:
    """빈 사용자 테이블에만 레거시 token/group 설정을 초기 데이터로 가져옵니다.

    token 원문은 bootstrap 입력으로만 읽습니다. DB에는 SHA-256 hash와 화면에
    표시할 마지막 네 자리만 저장하며, DB가 한 번 채워진 뒤에는 환경설정을
    다시 동기화하지 않아 관리자 화면 변경이 재시작 후에도 유지됩니다.
    """
    existing = db.scalar(
        select(func.count()).select_from(BobUser).where(BobUser.employee_no != "SYSTEM")
    ) or 0
    if existing:
        if not db.get(BobUser, "SYSTEM"):
            db.add(BobUser(employee_no="SYSTEM", is_admin=False, status="inactive"))
            db.commit()
        return 0
    raw_tokens = os.getenv(
        "ITSM_EVENT_USER_TOKENS_JSON",
        os.getenv("SR_EVENT_USER_TOKENS_JSON", "{}"),
    )
    raw_groups = os.getenv(
        "ITSM_EVENT_USER_GROUPS_JSON",
        os.getenv("SR_EVENT_USER_GROUPS_JSON", "{}"),
    )
    raw_admins = os.getenv("ITSM_EVENT_ADMIN_EMPLOYEE_NOS_JSON", "[]")
    tokens = json.loads(raw_tokens)
    groups = json.loads(raw_groups)
    admins = json.loads(raw_admins)
    if not isinstance(tokens, dict) or not isinstance(groups, dict):
        raise RuntimeError("Bob bootstrap token/group 설정은 JSON object여야 합니다.")
    if not isinstance(admins, list):
        raise RuntimeError("ITSM_EVENT_ADMIN_EMPLOYEE_NOS_JSON은 JSON array여야 합니다.")
    admins.extend(os.getenv("ITSM_EVENT_ADMIN_EMPLOYEES", "").split(","))
    admin_set = {value.strip() for value in admins if isinstance(value, str) and value.strip()}

    memberships: dict[str, list[str]] = {}
    group_names: set[str] = set()
    for employee_no, token in tokens.items():
        if not isinstance(employee_no, str) or not employee_no.strip() or not isinstance(token, str) or not token:
            raise RuntimeError("Bob 사용자 bootstrap 값은 employee_no와 token 문자열이어야 합니다.")
        employee_no = employee_no.strip()
        user_groups = groups.get(employee_no, [])
        if not isinstance(user_groups, list) or any(not isinstance(name, str) or not name.strip() for name in user_groups):
            raise RuntimeError(f"{employee_no}의 group 값은 문자열 배열이어야 합니다.")
        normalized_groups = sorted({name.strip() for name in user_groups})
        memberships[employee_no] = normalized_groups
        group_names.update(normalized_groups)
        db.add(BobUser(
            employee_no=employee_no,
            is_admin=employee_no in admin_set,
            status="active",
        ))
        db.add(BobUserToken(
            token_id=str(uuid4()),
            employee_no=employee_no,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            token_last_four=token[-4:],
        ))
    for group_name in sorted(group_names):
        db.add(BobGroup(group_name=group_name))
    db.flush()
    for employee_no, user_groups in memberships.items():
        db.add_all(
            BobUserGroup(employee_no=employee_no, group_name=group_name)
            for group_name in user_groups
        )
    # Internal MCP notifications have no Bob end-user identity. This inactive
    # sentinel satisfies the ERD's created_by foreign key without granting login.
    if not db.get(BobUser, "SYSTEM"):
        db.add(BobUser(employee_no="SYSTEM", is_admin=False, status="inactive"))
    db.commit()
    return len(memberships)
