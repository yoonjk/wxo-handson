"""
공용 MySQL 커넥션 유틸리티
==========================

"DB 접속 정보 조회 + 커넥션 풀 관리" 로직만 이 모듈에 모아둡니다.
SQL 쿼리 자체는 여기에 두지 않습니다 — 각 프로젝트의 데이터 액세스 모듈
(예: banking_db.py, db.py)에서 이 모듈의 get_connection()만 가져다 쓰고,
실제 쿼리/비즈니스 로직은 각자 파일에 둡니다.

app_id 별로 커넥션 풀을 캐싱하므로, 여러 데이터 액세스 모듈이 서로 다른
watsonx Orchestrate 커넥션(app-id)을 사용하더라도 이 모듈 하나를 공유해서
쓸 수 있습니다.

접속 정보 우선순위 (app_id 기준):
    1. watsonx Orchestrate의 key_value 커넥션
    2. 환경 변수 (ADK가 없거나 커넥션이 아직 없는 경우의 로컬 개발 폴백)
"""

import os
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

try:
    # watsonx Orchestrate ADK가 설치된 환경(실제 배포 환경)에서만 사용 가능
    from ibm_watsonx_orchestrate.run import connections as orchestrate_connections
    _HAS_ORCHESTRATE_CONNECTIONS = True
except ImportError:
    _HAS_ORCHESTRATE_CONNECTIONS = False

# app_id -> MySQLConnectionPool. 여러 스레드에서 동시에 풀을 생성하지
# 않도록 _POOLS_LOCK으로 보호합니다.
_POOLS: dict[str, MySQLConnectionPool] = {}
_POOLS_LOCK = threading.Lock()


def _get_mysql_config(app_id: str, defaults: Optional[dict] = None) -> dict:
    """
    지정된 app_id에 대한 접속 정보를 가져옵니다.

    :param app_id: watsonx Orchestrate 커넥션의 app-id
                    (예: "mysql_bank_demo", "mysql_hr_demo")
    :param defaults: key_value 커넥션/환경 변수 어느 쪽에도 값이 없을 때
                      사용할 기본값 딕셔너리
                      (host, port, user, password, database 중 일부만 넣어도 됨)
    """
    defaults = defaults or {}

    if _HAS_ORCHESTRATE_CONNECTIONS:
        try:
            creds = orchestrate_connections.key_value(app_id)
            return {
                "host": creds["MYSQL_HOST"],
                "port": int(creds.get("MYSQL_PORT", defaults.get("port", 3306))),
                "user": creds["MYSQL_USER"],
                "password": creds.get("MYSQL_PASSWORD", defaults.get("password", "")),
                "database": creds.get("MYSQL_DATABASE", defaults.get("database", "")),
            }
        except Exception:
            # 커넥션이 아직 설정되지 않았거나 로컬 실행 중이면 환경 변수로 폴백
            pass

    return {
        "host": os.getenv("MYSQL_HOST", defaults.get("host", "localhost")),
        "port": int(os.getenv("MYSQL_PORT", str(defaults.get("port", 3306)))),
        "user": os.getenv("MYSQL_USER", defaults.get("user", "root")),
        "password": os.getenv("MYSQL_PASSWORD", defaults.get("password", "")),
        "database": os.getenv("MYSQL_DATABASE", defaults.get("database", "")),
    }


def get_pool(
    app_id: str,
    pool_name: Optional[str] = None,
    pool_size: int = 5,
    defaults: Optional[dict] = None,
) -> MySQLConnectionPool:
    """
    app_id에 해당하는 커넥션 풀을 반환합니다. 이미 생성되어 있으면 캐시된
    풀을 재사용하고, 없으면 새로 만듭니다 (프로세스 생명주기 동안 1회만 생성).
    """
    pool_name = pool_name or app_id
    with _POOLS_LOCK:
        pool = _POOLS.get(pool_name)
        if pool is None:
            cfg = _get_mysql_config(app_id, defaults)
            pool = MySQLConnectionPool(
                pool_name=pool_name,
                pool_size=pool_size,
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
                use_unicode=True,
                **cfg,
            )
            _POOLS[pool_name] = pool
        return pool


@contextmanager
def get_connection(
    app_id: str,
    pool_name: Optional[str] = None,
    pool_size: int = 5,
    defaults: Optional[dict] = None,
) -> Iterator["mysql.connector.MySQLConnection"]:
    """
    풀에서 커넥션 하나를 빌려주는 컨텍스트 매니저.
    사용 예:

        with get_connection("mysql_bank_demo", defaults={"database": "demo"}) as conn:
            cur = conn.cursor()
            ...
    """
    conn = get_pool(app_id, pool_name, pool_size, defaults).get_connection()
    try:
        yield conn
    finally:
        conn.close()