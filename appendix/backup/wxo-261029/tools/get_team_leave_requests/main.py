"""
HR 휴가 관리 데모 - 로컬 테스트용 CLI
=======================================

watsonx Orchestrate에 등록하기 전에, 세 가지 기능이 의도대로
동작하는지 터미널에서 바로 확인할 수 있는 스크립트입니다.

실행:
    python main.py
"""

import json

from tools import apply_leave, check_leave_conflict, get_leave_balance, list_leave_requests


def pretty(title: str, data: dict) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    # 1) 휴가 잔여일 조회
    pretty("① 휴가 잔여일 조회 (E001)", get_leave_balance("E001"))

    # 2) 휴가 conflict 조회
    #    - E002(같은 팀 동료)가 2026-09-15~17에 승인된 휴가가 있음 -> 충돌 발생 예상
    pretty(
        "② 휴가 Conflict 조회 (E001, 2026-09-16 ~ 2026-09-18)",
        check_leave_conflict("E001", "2026-09-16", "2026-09-18"),
    )

    # 3) 휴가 신청 - 충돌이 없는 기간으로 신청
    pretty(
        "③ 휴가 신청 (E003, 2026-11-02 ~ 2026-11-04)",
        apply_leave("E003", "2026-11-02", "2026-11-04", reason="개인 사유"),
    )

    # 신청 후 잔여일 재조회로 차감 확인
    pretty("④ 신청 후 잔여일 재조회 (E003)", get_leave_balance("E003"))

    # 신청이 실제로 DB에 반영됐는지 신청 내역 조회로 재확인
    pretty("④-1 신청 내역 조회로 반영 여부 확인 (E003)", list_leave_requests("E003"))

    # 존재하지 않는 직원 / 잘못된 날짜 등 에러 케이스도 확인
    pretty("⑤ 존재하지 않는 직원 조회 (E999)", get_leave_balance("E999"))
    pretty(
        "⑥ 잔여 연차 초과 신청 (E002, 30일)",
        apply_leave("E002", "2026-12-01", "2026-12-31", reason="장기 휴가"),
    )


if __name__ == "__main__":
    main()