"""
MySQL 데이터 액세스 계층
==========================

환경 변수로 접속 정보를 받아 커넥션 풀을 유지하고,
HR 휴가 데모(tools.py)에 필요한 쿼리 함수를 제공합니다.

필요 환경 변수 (기본값은 로컬 개발 기준):
    MYSQL_HOST      기본값 "localhost"
    MYSQL_PORT      기본값 3306
    MYSQL_USER      기본값 "root"
    MYSQL_PASSWORD  기본값 ""
    MYSQL_DATABASE  기본값 "hr_vacation_demo"

먼저 schema.sql로 테이블과 시드 데이터를 생성해 두어야 합니다:
    mysql -u root -p < schema.sql
"""

import os
from contextlib import contextmanager
from typing import Iterator, List, Optional

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

try:
    # watsonx Orchestrate ADK가 설치된 환경(실제 배포 환경)에서만 사용 가능
    from ibm_watsonx_orchestrate.run import connections as orchestrate_connections
    _HAS_ORCHESTRATE_CONNECTIONS = True
except ImportError:
    _HAS_ORCHESTRATE_CONNECTIONS = False

# orchestrate connections add -a mysql_hr_demo 로 등록한 app-id와 반드시 동일해야 합니다.
MYSQL_APP_ID = "mysql_hr_demo"

_POOL: Optional[MySQLConnectionPool] = None


def _get_mysql_config() -> dict:
    """
    접속 정보를 가져오는 우선순위:
      1. watsonx Orchestrate의 key_value 커넥션 (MYSQL_APP_ID)
      2. 로컬 개발용 환경 변수 (ADK가 없거나 커넥션이 아직 없는 경우)
    """
    if _HAS_ORCHESTRATE_CONNECTIONS:
        try:
            creds = orchestrate_connections.key_value(MYSQL_APP_ID)
            return {
                "host": creds["MYSQL_HOST"],
                "port": int(creds.get("MYSQL_PORT", 3306)),
                "user": creds["MYSQL_USER"],
                "password": creds.get("MYSQL_PASSWORD", ""),
                "database": creds.get("MYSQL_DATABASE", "hr_vacation_demo"),
            }
        except Exception:
            # 커넥션이 아직 설정되지 않았거나 로컬 실행 중이면 환경 변수로 폴백
            pass

    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "hr_vacation_demo"),
    }


def _get_pool() -> MySQLConnectionPool:
    global _POOL
    if _POOL is None:
        cfg = _get_mysql_config()
        _POOL = MySQLConnectionPool(
            pool_name="hr_vacation_pool",
            pool_size=5,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            use_unicode=True,
            **cfg,
        )
    return _POOL


@contextmanager
def get_connection() -> Iterator["mysql.connector.MySQLConnection"]:
    conn = _get_pool().get_connection()
    try:
        yield conn
    finally:
        conn.close()


def fetch_employee(employee_id: str) -> Optional[dict]:
    """사번으로 직원 1건을 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT employee_id, name, department, manager_id, "
            "annual_leave_days, used_leave_days "
            "FROM employees WHERE employee_id = %s",
            (employee_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row


def fetch_team_member_ids(employee_id: str) -> List[str]:
    """해당 직원과 매니저가 동일한 동료 사번 목록 (본인 제외)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT manager_id FROM employees WHERE employee_id = %s",
            (employee_id,),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            cur.close()
            return []
        manager_id = row[0]

        cur.execute(
            "SELECT employee_id FROM employees "
            "WHERE manager_id = %s AND employee_id != %s",
            (manager_id, employee_id),
        )
        ids = [r[0] for r in cur.fetchall()]
        cur.close()
        return ids


def fetch_overlapping_approved_requests(start_date: str, end_date: str) -> List[dict]:
    """지정 기간과 겹치는 '승인된(Approved)' 휴가 신청을 모두 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT request_id, employee_id, start_date, end_date, status, reason "
            "FROM vacation_requests "
            "WHERE status = 'Approved' AND start_date <= %s AND end_date >= %s",
            (end_date, start_date),
        )
        rows = cur.fetchall()
        cur.close()
        # DATE 컬럼은 datetime.date로 반환되므로 문자열(YYYY-MM-DD)로 통일
        for r in rows:
            r["start_date"] = str(r["start_date"])
            r["end_date"] = str(r["end_date"])
        return rows


def insert_vacation_request(
    request_id: str, employee_id: str, start_date: str, end_date: str, reason: str
) -> None:
    """새 휴가 신청 건을 Pending 상태로 저장합니다."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO vacation_requests "
            "(request_id, employee_id, start_date, end_date, status, reason) "
            "VALUES (%s, %s, %s, %s, 'Pending', %s)",
            (request_id, employee_id, start_date, end_date, reason),
        )
        conn.commit()
        cur.close()


def update_used_leave_days(employee_id: str, additional_days: int) -> None:
    """신청 일수만큼 사용 연차를 누적합니다."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE employees SET used_leave_days = used_leave_days + %s "
            "WHERE employee_id = %s",
            (additional_days, employee_id),
        )
        conn.commit()
        cur.close()


def fetch_team_requests(manager_id: str, include_past: bool = False) -> List[dict]:
    """
    해당 매니저 밑에 있는 모든 팀원의 휴가 신청 내역을 조회합니다.
    (직원 자신이 매니저인지 여부는 확인하지 않고, manager_id로 바로 조회합니다.)

    include_past가 False(기본값)이면 종료일(end_date)이 오늘(서버 기준
    CURDATE())보다 이전인 신청 건은 결과에서 제외합니다 - 이미 지나간
    휴가는 "팀 휴가 일정"에서 보여줄 필요가 없기 때문입니다.
    """
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        query = (
            "SELECT vr.request_id, vr.employee_id, e.name AS employee_name, "
            "vr.start_date, vr.end_date, vr.status, vr.reason "
            "FROM vacation_requests vr "
            "JOIN employees e ON vr.employee_id = e.employee_id "
            "WHERE e.manager_id = %s "
        )
        if not include_past:
            query += "AND vr.end_date >= CURDATE() "
        query += "ORDER BY vr.start_date ASC"

        cur.execute(query, (manager_id,))
        rows = cur.fetchall()
        cur.close()
        for r in rows:
            r["start_date"] = str(r["start_date"])
            r["end_date"] = str(r["end_date"])
        return rows


def fetch_request_by_id(request_id: str) -> Optional[dict]:
    """request_id로 특정 휴가 신청 건 하나를 조회합니다 (승인현황 확인용)."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT request_id, employee_id, start_date, end_date, status, reason "
            "FROM vacation_requests WHERE request_id = %s",
            (request_id,),
        )
        row = cur.fetchone()
        cur.close()
        if row:
            row["start_date"] = str(row["start_date"])
            row["end_date"] = str(row["end_date"])
        return row


def fetch_requests_by_employee(employee_id: str) -> List[dict]:
    """해당 직원이 신청한 모든 휴가 내역을 최신순으로 조회합니다."""
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT request_id, employee_id, start_date, end_date, status, reason "
            "FROM vacation_requests "
            "WHERE employee_id = %s "
            "ORDER BY CAST(SUBSTRING(request_id, 3) AS UNSIGNED) DESC",
            (employee_id,),
        )
        rows = cur.fetchall()
        cur.close()
        for r in rows:
            r["start_date"] = str(r["start_date"])
            r["end_date"] = str(r["end_date"])
        return rows


def next_request_id() -> str:
    """기존 request_id 중 최대값 다음 번호(V-1003, V-1004, ...)를 생성합니다."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT request_id FROM vacation_requests "
            "ORDER BY CAST(SUBSTRING(request_id, 3) AS UNSIGNED) DESC LIMIT 1"
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return "V-1001"
        last_seq = int(row[0].split("-")[1])
        return f"V-{last_seq + 1}"