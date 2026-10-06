"""MySQL 데이터 액세스 계층.

watsonx Orchestrate toolkit의 여러 worker thread에서 함께 사용되므로,
커넥션은 호출마다 풀에서 빌리고 반환합니다. 전역에는 thread-safe 초기화된
커넥션 풀만 보관하며, 요청별 데이터나 커넥션은 전역에 보관하지 않습니다.
"""

import os
import threading
from contextlib import contextmanager
from typing import Iterator, List, Optional

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

try:
    from ibm_watsonx_orchestrate.run import connections as orchestrate_connections
    _HAS_ORCHESTRATE_CONNECTIONS = True
except ImportError:
    _HAS_ORCHESTRATE_CONNECTIONS = False

# toolkit import 시 --app-id mysql_hr_demo 로 연결을 연결해야 합니다.
MYSQL_APP_ID = "mysql_hr_demo"
_POOL: Optional[MySQLConnectionPool] = None
_POOL_INIT_LOCK = threading.Lock()


def _get_mysql_config() -> dict:
    """Orchestrate key-value connection 또는 로컬 환경 변수에서 접속정보를 읽습니다."""
    if _HAS_ORCHESTRATE_CONNECTIONS:
        try:
            creds = orchestrate_connections.key_value(MYSQL_APP_ID)
            return {
                "host": creds["MYSQL_HOST"],
                "port": int(creds.get("MYSQL_PORT", 3306)),
                "user": creds["MYSQL_USER"],
                "password": creds.get("MYSQL_PASSWORD", ""),
                "database": creds.get("MYSQL_DATABASE", "demo"),
            }
        except Exception:
            # 로컬 실행 또는 연결 미설정 때 환경 변수 설정을 사용합니다.
            pass

    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        # 제공된 schema.sql에서 생성하는 DB명은 demo입니다.
        "database": os.getenv("MYSQL_DATABASE", "demo"),
    }


def _get_pool() -> MySQLConnectionPool:
    """동시 첫 요청에서도 하나의 연결 풀만 생성합니다."""
    global _POOL
    if _POOL is None:
        with _POOL_INIT_LOCK:
            if _POOL is None:
                _POOL = MySQLConnectionPool(
                    pool_name="hr_vacation_pool",
                    pool_size=5,
                    charset="utf8mb4",
                    collation="utf8mb4_unicode_ci",
                    use_unicode=True,
                    **_get_mysql_config(),
                )
    return _POOL


@contextmanager
def get_connection() -> Iterator["mysql.connector.MySQLConnection"]:
    """풀에서 연결을 빌려 사용하고, 예외 시 미완료 트랜잭션을 롤백합니다."""
    conn = _get_pool().get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_employee(employee_id: str) -> Optional[dict]:
    """사번으로 직원 1건을 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT employee_id, name, department, manager_id, "
                "annual_leave_days, used_leave_days FROM employees WHERE employee_id = %s",
                (employee_id,),
            )
            return cur.fetchone()
        finally:
            cur.close()


def fetch_team_member_ids(employee_id: str) -> List[str]:
    """해당 직원과 매니저가 동일한 동료 사번 목록(본인 제외)을 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT manager_id FROM employees WHERE employee_id = %s", (employee_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                return []
            manager_id = row[0]
            cur.execute(
                "SELECT employee_id FROM employees WHERE manager_id = %s AND employee_id != %s",
                (manager_id, employee_id),
            )
            return [r[0] for r in cur.fetchall()]
        finally:
            cur.close()


def fetch_overlapping_approved_requests(start_date: str, end_date: str) -> List[dict]:
    """지정 기간과 겹치는 승인 휴가 신청을 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT request_id, employee_id, start_date, end_date, status, reason "
                "FROM vacation_requests "
                "WHERE status = 'Approved' AND start_date <= %s AND end_date >= %s",
                (end_date, start_date),
            )
            rows = cur.fetchall()
            for row in rows:
                row["start_date"] = str(row["start_date"])
                row["end_date"] = str(row["end_date"])
            return rows
        finally:
            cur.close()


def register_vacation_request(
    employee_id: str, start_date: str, end_date: str, reason: str, requested_days: int
) -> dict:
    """요청 ID 발급, 잔여 연차 재검증, 신청 저장, 연차 차감을 하나의 작업으로 처리합니다.

    MySQL named lock은 여러 toolkit worker와 여러 서버 인스턴스 사이에서
    동시에 같은 요청 번호를 발급하지 않도록 직렬화합니다. 직원 row 잠금으로
    연차 잔여량도 저장 직전에 다시 검증합니다.
    """
    lock_name = "hr_vacation_demo_request_id"
    with get_connection() as conn:
        lock_cur = conn.cursor()
        try:
            lock_cur.execute("SELECT GET_LOCK(%s, 10)", (lock_name,))
            lock_row = lock_cur.fetchone()
            if not lock_row or lock_row[0] != 1:
                raise RuntimeError("휴가 신청 처리를 위한 DB 잠금을 얻지 못했습니다.")

            conn.start_transaction()
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    "SELECT annual_leave_days, used_leave_days FROM employees "
                    "WHERE employee_id = %s FOR UPDATE",
                    (employee_id,),
                )
                employee = cur.fetchone()
                if not employee:
                    raise ValueError(f"직원 ID '{employee_id}'를 찾을 수 없습니다.")

                remaining = employee["annual_leave_days"] - employee["used_leave_days"]
                if requested_days > remaining:
                    raise ValueError(
                        f"잔여 연차({remaining}일)가 신청 일수({requested_days}일)보다 부족하여 신청할 수 없습니다."
                    )

                cur.execute(
                    "SELECT request_id FROM vacation_requests "
                    "ORDER BY CAST(SUBSTRING(request_id, 3) AS UNSIGNED) DESC LIMIT 1"
                )
                last_row = cur.fetchone()
                if not last_row:
                    request_id = "V-1001"
                else:
                    last_sequence = int(last_row["request_id"].split("-")[1])
                    request_id = f"V-{last_sequence + 1}"

                cur.execute(
                    "INSERT INTO vacation_requests "
                    "(request_id, employee_id, start_date, end_date, status, reason) "
                    "VALUES (%s, %s, %s, %s, 'Pending', %s)",
                    (request_id, employee_id, start_date, end_date, reason),
                )
                cur.execute(
                    "UPDATE employees SET used_leave_days = used_leave_days + %s "
                    "WHERE employee_id = %s",
                    (requested_days, employee_id),
                )
                conn.commit()
                return {"request_id": request_id, "remaining_leave_days_after": remaining - requested_days}
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
        finally:
            try:
                lock_cur.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
            finally:
                lock_cur.close()


def fetch_team_requests(manager_id: str, include_past: bool = False) -> List[dict]:
    """매니저 팀원의 휴가 신청을 기간 오름차순으로 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            query = (
                "SELECT vr.request_id, vr.employee_id, e.name AS employee_name, "
                "vr.start_date, vr.end_date, vr.status, vr.reason "
                "FROM vacation_requests vr JOIN employees e ON vr.employee_id = e.employee_id "
                "WHERE e.manager_id = %s "
            )
            if not include_past:
                query += "AND vr.end_date >= CURDATE() "
            query += "ORDER BY vr.start_date ASC"
            cur.execute(query, (manager_id,))
            rows = cur.fetchall()
            for row in rows:
                row["start_date"] = str(row["start_date"])
                row["end_date"] = str(row["end_date"])
            return rows
        finally:
            cur.close()


def fetch_request_by_id(request_id: str) -> Optional[dict]:
    """신청 번호로 휴가 신청 한 건을 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT request_id, employee_id, start_date, end_date, status, reason "
                "FROM vacation_requests WHERE request_id = %s",
                (request_id,),
            )
            row = cur.fetchone()
            if row:
                row["start_date"] = str(row["start_date"])
                row["end_date"] = str(row["end_date"])
            return row
        finally:
            cur.close()


def fetch_requests_by_employee(employee_id: str) -> List[dict]:
    """직원의 휴가 신청 내역을 최신순으로 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT request_id, employee_id, start_date, end_date, status, reason "
                "FROM vacation_requests WHERE employee_id = %s "
                "ORDER BY CAST(SUBSTRING(request_id, 3) AS UNSIGNED) DESC",
                (employee_id,),
            )
            rows = cur.fetchall()
            for row in rows:
                row["start_date"] = str(row["start_date"])
                row["end_date"] = str(row["end_date"])
            return rows
        finally:
            cur.close()
