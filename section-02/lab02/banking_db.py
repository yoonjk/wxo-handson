"""
MySQL 데이터 액세스 계층 (뱅킹 데모)
====================================

banking_tools.py 에서 사용하는 모든 SQL 쿼리를 이 파일에 모아둡니다.
tools.py 쪽에는 비즈니스 로직(입력 검증, JSON 응답 포맷 등)만 남기고,
실제 DB 접근은 전부 여기서 처리합니다.

DB 접속 정보 조회 / 커넥션 풀 관리는 mysql_connection.py로 분리되어
있습니다 (다른 프로젝트, 예: db.py의 HR 데모와도 공유해서 재사용 가능).
이 파일은 오직 "뱅킹 도메인 SQL 쿼리"만 담당합니다.

먼저 schema.sql로 테이블과 시드 데이터를 생성해 두어야 합니다:
    mysql -u nexweb -p -h nexweb.ddnsgeek.com -P 13306 demo < schema.sql

필요 환경 변수 (로컬 개발 폴백용 — watsonx Orchestrate 커넥션이 없을 때):
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
    (기본값은 아래 _DEFAULTS 참고)
"""

from decimal import Decimal
from typing import List, Optional

import mysql_connection

# orchestrate connections add -a mysql_bank_demo 로 등록한 app-id와 반드시 동일해야 합니다.
MYSQL_APP_ID = "mysql_bank_demo"

# 풀 이름은 app_id와 별개로 둬서, 같은 app_id를 다른 용도의 풀 크기로
# 여러 곳에서 쓰고 싶을 때도 충돌하지 않도록 합니다.
_POOL_NAME = "banking_demo_pool"

# key_value 커넥션/환경 변수 어디에도 값이 없을 때 사용할 기본값
_DEFAULTS = {
    "host": "nexweb.ddnsgeek.com",
    "port": 13306,
    "database": "demo",
}


def get_connection():
    """이 프로젝트(mysql_bank_demo) 전용 커넥션을 빌려주는 컨텍스트 매니저."""
    return mysql_connection.get_connection(
        MYSQL_APP_ID, pool_name=_POOL_NAME, defaults=_DEFAULTS
    )


# ---------------------------------------------------------------------------
# 커스텀 예외 — tools.py에서 잡아서 사용자 친화적인 JSON 오류로 변환합니다.
# ---------------------------------------------------------------------------

class AccountNotFoundError(Exception):
    """존재하지 않는 account_id를 참조했을 때 발생합니다."""


class InsufficientFundsError(Exception):
    """이체 시 출금 계좌의 가용 잔액이 부족할 때 발생합니다."""


# ---------------------------------------------------------------------------
# 고객 / 계좌 조회
# ---------------------------------------------------------------------------

def fetch_account_ids(identifier: str) -> List[str]:
    """사용자명 또는 고객번호로 연결된 모든 account_id를 조회합니다.

    한 identifier가 여러 계좌(체크/저축 등)에 연결되어 있을 수 있으므로
    리스트를 반환합니다. 매칭되는 계좌가 없으면 빈 리스트를 반환합니다.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT account_id FROM customers WHERE identifier = %s ORDER BY account_id",
            (identifier,),
        )
        rows = cur.fetchall()
        cur.close()
        return [row[0] for row in rows]


def fetch_accounts_with_balance(identifier: str) -> List[dict]:
    """
    사용자명/고객번호에 연결된 모든 계좌를 잔액과 함께 조회합니다.
    (계좌 목록 화면 - "사용자 → 전체 계좌 목록(잔액 포함)" 용도)

    매칭되는 계좌가 없으면 빈 리스트를 반환합니다.
    """
    account_ids = fetch_account_ids(identifier)
    if not account_ids:
        return []

    placeholders = ", ".join(["%s"] * len(account_ids))
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT account_id, currency, available_balance, ledger_balance "
            f"FROM accounts WHERE account_id IN ({placeholders}) "
            "ORDER BY account_id",
            tuple(account_ids),
        )
        rows = cur.fetchall()
        cur.close()

    return [
        {
            "account_id": r["account_id"],
            "currency": r["currency"],
            "available": str(r["available_balance"]),
            "ledger": str(r["ledger_balance"]),
        }
        for r in rows
    ]


def account_exists(account_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM accounts WHERE account_id = %s", (account_id,))
        found = cur.fetchone() is not None
        cur.close()
        return found


def fetch_account_balance(account_id: str) -> Optional[dict]:
    """계좌의 통화, 가용잔액, 원장잔액을 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT currency, available_balance, ledger_balance "
            "FROM accounts WHERE account_id = %s",
            (account_id,),
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return {
            "currency": row["currency"],
            "available": str(row["available_balance"]),
            "ledger": str(row["ledger_balance"]),
        }


def fetch_account_detail(account_id: str) -> Optional[dict]:
    """
    계좌 상세 화면용 조회 - 잔액에 더해 등록된 연락처(email/phone)까지 포함합니다.
    (계좌 목록에서 계좌를 "선택"했을 때 보여줄 상세 정보)
    """
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT account_id, currency, available_balance, ledger_balance, email, phone "
            "FROM accounts WHERE account_id = %s",
            (account_id,),
        )
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return {
            "account_id": row["account_id"],
            "currency": row["currency"],
            "available": str(row["available_balance"]),
            "ledger": str(row["ledger_balance"]),
            "email": row["email"],
            "phone": row["phone"],
        }


def fetch_available_balance(account_id: str) -> Optional[Decimal]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT available_balance FROM accounts WHERE account_id = %s",
            (account_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None


def update_contact_details(account_id: str, email: Optional[str], phone: Optional[str]) -> bool:
    """계좌의 이메일/전화번호를 갱신합니다. 계좌가 없으면 False를 반환합니다."""
    if not account_exists(account_id):
        return False

    sets, params = [], []
    if email:
        sets.append("email = %s")
        params.append(email)
    if phone:
        sets.append("phone = %s")
        params.append(phone)
    if not sets:
        return True

    params.append(account_id)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE accounts SET {', '.join(sets)} WHERE account_id = %s",
            tuple(params),
        )
        conn.commit()
        cur.close()
    return True


# ---------------------------------------------------------------------------
# 거래 내역
# ---------------------------------------------------------------------------

def fetch_transactions(
    account_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
) -> Optional[List[dict]]:
    """
    거래 내역을 조회합니다. 계좌가 존재하지 않으면 None을 반환하고,
    거래가 없으면 빈 리스트를 반환합니다.
    """
    if not account_exists(account_id):
        return None

    query = (
        "SELECT txn_id AS id, txn_date AS date, txn_type AS type, "
        "amount, description AS `desc` "
        "FROM transactions WHERE account_id = %s"
    )
    params: list = [account_id]
    if start_date:
        query += " AND txn_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND txn_date <= %s"
        params.append(end_date)
    query += " ORDER BY txn_date DESC LIMIT %s"
    params.append(limit)

    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        cur.close()

    for r in rows:
        r["date"] = str(r["date"])
        r["amount"] = str(r["amount"])
    return rows


# ---------------------------------------------------------------------------
# 지점 코드
# ---------------------------------------------------------------------------

def fetch_branch_code(branch_query: str) -> Optional[str]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT branch_code FROM branches WHERE branch_query = %s",
            (branch_query.strip().lower(),),
        )
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None


# ---------------------------------------------------------------------------
# 계좌 이체
# ---------------------------------------------------------------------------

def transfer_funds(
    transaction_id: str,
    from_account: str,
    to_account: str,
    amount: Decimal,
    currency: str,
    reference: Optional[str],
) -> None:
    """
    from_account -> to_account 로 amount 만큼 원자적으로 이체합니다.

    다음을 모두 "하나의 DB 트랜잭션" 안에서 처리합니다 (전부 성공하거나 전부 롤백):
      1. 두 계좌 행을 잠근 뒤(FOR UPDATE) 잔액 확인
      2. accounts.available_balance / ledger_balance 갱신
      3. transactions 테이블에 debit(출금 계좌)/credit(입금 계좌) 행을 각각 추가
         → 이체도 "거래내역 조회"(list_recent_transactions 등)에 나타나게 하기 위함
      4. transfers 테이블에 이체 이력(감사/이체 조회용) 기록

    :raises AccountNotFoundError: 두 계좌 중 하나라도 존재하지 않는 경우
    :raises InsufficientFundsError: 출금 계좌의 가용 잔액이 부족한 경우
    """
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            conn.start_transaction()

            cur.execute(
                "SELECT available_balance FROM accounts WHERE account_id = %s FOR UPDATE",
                (from_account,),
            )
            from_row = cur.fetchone()
            if from_row is None:
                raise AccountNotFoundError(from_account)
            if from_row[0] < amount:
                raise InsufficientFundsError(from_account)

            cur.execute(
                "SELECT 1 FROM accounts WHERE account_id = %s FOR UPDATE",
                (to_account,),
            )
            if cur.fetchone() is None:
                raise AccountNotFoundError(to_account)

            cur.execute(
                "UPDATE accounts SET available_balance = available_balance - %s, "
                "ledger_balance = ledger_balance - %s WHERE account_id = %s",
                (amount, amount, from_account),
            )
            cur.execute(
                "UPDATE accounts SET available_balance = available_balance + %s, "
                "ledger_balance = ledger_balance + %s WHERE account_id = %s",
                (amount, amount, to_account),
            )

            # transactions 테이블에도 남겨서 "거래내역 조회"에 이체가 보이게 함.
            # txn_id가 PK이므로 debit/credit 각각 다른 id를 사용.
            desc_out = f"Transfer to {to_account}" + (f" ({reference})" if reference else "")
            desc_in = f"Transfer from {from_account}" + (f" ({reference})" if reference else "")
            cur.execute(
                "INSERT INTO transactions (txn_id, account_id, txn_date, txn_type, amount, description) "
                "VALUES (%s, %s, CURDATE(), 'debit', %s, %s)",
                (f"{transaction_id}D", from_account, -amount, desc_out),
            )
            cur.execute(
                "INSERT INTO transactions (txn_id, account_id, txn_date, txn_type, amount, description) "
                "VALUES (%s, %s, CURDATE(), 'credit', %s, %s)",
                (f"{transaction_id}C", to_account, amount, desc_in),
            )

            # transfers 테이블에 이체 이력(감사/이체 조회용) 기록
            cur.execute(
                "INSERT INTO transfers "
                "(transaction_id, from_account, to_account, amount, currency, status, reference) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (transaction_id, from_account, to_account, str(amount), currency, "initiated", reference or ""),
            )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def fetch_transfer_history(account_id: str, limit: int = 20) -> Optional[List[dict]]:
    """
    해당 계좌가 관련된(보낸/받은) 이체 내역을 최신순으로 조회합니다.
    (계좌 상세 화면에서 "이체 조회"를 선택했을 때 사용)

    계좌가 존재하지 않으면 None, 이체 내역이 없으면 빈 리스트를 반환합니다.
    각 건에는 해당 account_id 기준 "outgoing"/"incoming" 방향을 표시합니다.
    """
    if not account_exists(account_id):
        return None

    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT transaction_id, from_account, to_account, amount, currency, "
            "status, reference, created_at "
            "FROM transfers WHERE from_account = %s OR to_account = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (account_id, account_id, limit),
        )
        rows = cur.fetchall()
        cur.close()

    for r in rows:
        r["amount"] = str(r["amount"])
        r["created_at"] = str(r["created_at"])
        r["direction"] = "outgoing" if r["from_account"] == account_id else "incoming"
    return rows