"""Hanbit Mock HR API — watsonx Orchestrate Module 1 실습용 Mock 서버.

실행:
    pip install -r requirements.txt
    MOCK_API_KEY=wxo-lab-2026 uvicorn app:app --host 0.0.0.0 --port 8080

엔드포인트는 ../mock_hr_api.yaml 스펙과 같습니다. /health 는 인증 없이 열려 있습니다.
데이터는 메모리에만 저장되며 서버를 재시작하면 employees.json 상태로 돌아갑니다.
"""
import copy
import itertools
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

API_KEY = os.environ.get("MOCK_API_KEY", "wxo-lab-2026")
YEAR = int(os.environ.get("MOCK_YEAR", "2026"))
DATA_FILE = Path(__file__).with_name("employees.json")

_seed = json.loads(DATA_FILE.read_text(encoding="utf-8"))
EMPLOYEES = {e["employeeId"]: copy.deepcopy(e) for e in _seed}
REQUESTS: list[dict] = []
_seq = itertools.count(1)

app = FastAPI(title="Hanbit Mock HR API", version="1.0.0")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiError)
async def _api_error(_, exc: ApiError):
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message})


def require_key(x_api_key: Optional[str] = Header(default=None)):
    if x_api_key != API_KEY:
        raise ApiError(401, "UNAUTHORIZED", "X-API-Key 헤더가 없거나 올바르지 않습니다.")


def find(employee_id: str) -> dict:
    emp = EMPLOYEES.get(employee_id.strip().upper())
    if not emp:
        raise ApiError(404, "EMPLOYEE_NOT_FOUND", f"사번 {employee_id}에 해당하는 직원이 없습니다.")
    return emp


@app.get("/health")
def health():
    return {"status": "ok", "employees": len(EMPLOYEES), "requests": len(REQUESTS)}


@app.get("/employees/{employeeId}/leave-balance", dependencies=[Depends(require_key)])
def get_leave_balance(employeeId: str):
    e = find(employeeId)
    return {"employeeId": e["employeeId"], "name": e["name"], "year": YEAR, **e["leave"]}


@app.get("/employees/{employeeId}", dependencies=[Depends(require_key)])
def get_employee_profile(employeeId: str):
    e = find(employeeId)
    return {k: e[k] for k in ("employeeId", "name", "department", "position", "hireDate")}


class LeaveRequest(BaseModel):
    startDate: date
    endDate: date
    type: Literal["annual", "half_am", "half_pm"]
    reason: Optional[str] = None


def business_days(start: date, end: date) -> int:
    n, d = 0, start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


@app.post("/employees/{employeeId}/leave-requests", status_code=201, dependencies=[Depends(require_key)])
def create_leave_request(employeeId: str, body: LeaveRequest):
    e = find(employeeId)
    if body.endDate < body.startDate:
        raise ApiError(400, "INVALID_DATE", "종료일이 시작일보다 빠릅니다.")
    if body.type == "annual":
        days = float(business_days(body.startDate, body.endDate))
        if days == 0:
            raise ApiError(400, "INVALID_DATE", "선택한 기간에 영업일이 없습니다.")
    else:
        if body.startDate != body.endDate:
            raise ApiError(400, "INVALID_DATE", "반차는 하루만 신청할 수 있습니다.")
        days = 0.5
    if days > e["leave"]["remaining"]:
        raise ApiError(400, "INSUFFICIENT_BALANCE",
                       f"잔여 연차 {e['leave']['remaining']}일보다 많은 {days}일을 신청했습니다.")
    req = {
        "requestId": f"LR-{YEAR}-{next(_seq):04d}",
        "employeeId": e["employeeId"],
        "status": "PENDING_APPROVAL",
        "days": days,
        "remainingAfter": e["leave"]["remaining"] - days,
        **body.model_dump(mode="json"),
    }
    REQUESTS.append(req)
    return {k: req[k] for k in ("requestId", "status", "days", "remainingAfter")}


@app.post("/admin/reset")
def reset(x_api_key: Optional[str] = Header(default=None)):
    """강사용: 데이터 초기화."""
    require_key(x_api_key)
    EMPLOYEES.clear()
    EMPLOYEES.update({e["employeeId"]: copy.deepcopy(e) for e in _seed})
    REQUESTS.clear()
    return {"status": "reset"}
