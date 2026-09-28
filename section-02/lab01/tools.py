"""
watsonx Orchestrate HR 데모 - 휴가 관리 툴 (MySQL 연동 버전)
==============================================================

IBM watsonx Orchestrate ADK의 Python 툴 규격을 따르는 세 가지 기능이며,
데이터는 db.py를 통해 실제 MySQL 테이블(employees, vacation_requests)에서
조회/저장합니다.

사전 준비
---------
1. MySQL에 schema.sql 실행 (테이블 + 시드 데이터 생성)
       mysql -u root -p < schema.sql
2. 접속 정보를 환경 변수로 설정 (없으면 기본값: localhost/root/빈 비밀번호)
       export MYSQL_HOST=localhost
       export MYSQL_USER=root
       export MYSQL_PASSWORD=your_password
       export MYSQL_DATABASE=hr_vacation_demo
3. 드라이버 설치
       pip install -r requirements.txt

watsonx Orchestrate에 등록하기
--------------------------------
    orchestrate tools import -k python -f tools.py

(오프라인/메모리 기반 데모가 필요하면 tools_mock.py를 대신 사용하세요.)
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

try:
    from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
    from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
except ImportError:  # ADK 미설치 환경에서도 함수 자체는 동작하도록 폴백 처리
    class ToolPermission:
        READ_ONLY = "read_only"
        READ_WRITE = "read_write"

    class ConnectionType:
        KEY_VALUE = "key_value"

    def tool(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator

import db

# 캘린더 등 폼 위젯 기능은 실제 watsonx Orchestrate ADK가 있어야 렌더링됩니다.
# 로컬/오프라인 환경에서는 폼 대신 요약 딕셔너리를 반환하도록 폴백 처리합니다.
try:
    from ibm_watsonx_orchestrate.run.widgets.forms import (
        FormWidget,
        TextInput,
        TextArea,
        DatePicker,
        ToolEvent,
    )
    from ibm_watsonx_orchestrate.run.tool_result import (
        ToolResult,
        TextContent,
        Annotations,
        Role,
    )
    _HAS_FORM_WIDGETS = True
except ImportError:
    _HAS_FORM_WIDGETS = False

# db.py의 MYSQL_APP_ID(orchestrate connections add -a mysql_hr_demo)와 동일해야 합니다.
_MYSQL_CREDENTIALS = [{"app_id": db.MYSQL_APP_ID, "type": ConnectionType.KEY_VALUE}]


# ---------------------------------------------------------------------------
# 내부 유틸리티 함수
# ---------------------------------------------------------------------------
def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _dates_overlap(start_a: date, end_a: date, start_b: date, end_b: date) -> bool:
    return start_a <= end_b and start_b <= end_a


def _business_days(start: date, end: date) -> int:
    """토/일을 제외한 근무일 수를 계산합니다 (시작일, 종료일 포함)."""
    days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # 0=월 ... 4=금
            days += 1
        current = current.fromordinal(current.toordinal() + 1)
    return days


def _suggest_alternative_dates(
    employee_id: str,
    req_start: date,
    req_end: date,
    max_suggestions: int = 3,
    search_window_days: int = 30,
) -> List[dict]:
    """
    충돌이 발생했을 때, 동일한 일수(달력 기준)의 비어있는 기간을 뒤쪽 날짜부터
    순서대로 탐색해 최대 max_suggestions개까지 제안합니다.
    (본인 승인 휴가 및 같은 팀 동료의 승인 휴가와 겹치지 않는 기간만 제안합니다.)
    """
    duration_days = (req_end - req_start).days + 1
    suggestions: List[dict] = []

    for offset in range(1, search_window_days + 1):
        candidate_start = req_start + timedelta(days=offset)
        candidate_end = candidate_start + timedelta(days=duration_days - 1)

        candidate_result = _check_leave_conflict_impl(
            employee_id,
            candidate_start.strftime("%Y-%m-%d"),
            candidate_end.strftime("%Y-%m-%d"),
        )
        if candidate_result.get("has_conflict"):
            continue

        suggestions.append(
            {
                "start_date": candidate_start.strftime("%Y-%m-%d"),
                "end_date": candidate_end.strftime("%Y-%m-%d"),
            }
        )
        if len(suggestions) >= max_suggestions:
            break

    return suggestions


# ---------------------------------------------------------------------------
# 1. 휴가 잔여일 조회
# ---------------------------------------------------------------------------
@tool(permission=ToolPermission.READ_ONLY, expected_credentials=_MYSQL_CREDENTIALS)
def get_leave_balance(employee_id: str) -> dict:
    """
    MySQL의 employees 테이블에서 직원의 연차 잔여일수를 조회합니다.

    Args:
        employee_id: 조회할 직원의 사번 (예: "E001")

    Returns:
        직원 이름, 총 연차, 사용 연차, 잔여 연차를 담은 딕셔너리.
        직원을 찾을 수 없으면 error 필드를 반환합니다.
    """
    emp = db.fetch_employee(employee_id)
    if not emp:
        return {"error": f"직원 ID '{employee_id}'를 찾을 수 없습니다."}

    total = emp["annual_leave_days"]
    used = emp["used_leave_days"]

    return {
        "employee_id": employee_id,
        "name": emp["name"],
        "department": emp["department"],
        "total_leave_days": total,
        "used_leave_days": used,
        "remaining_leave_days": total - used,
    }


# ---------------------------------------------------------------------------
# 2. 휴가 conflict(충돌) 조회
# ---------------------------------------------------------------------------
def _check_leave_conflict_impl(employee_id: str, start_date: str, end_date: str) -> dict:
    """
    check_leave_conflict의 실제 로직. @tool 데코레이터가 붙지 않은 순수 함수로,
    apply_leave 등 다른 함수 내부에서 안전하게 재사용하기 위해 분리했습니다.

    (주의) @tool로 감싼 함수를 다른 함수 안에서 직접 호출하면, watsonx
    Orchestrate ADK가 반환값을 내부 ToolResult 객체로 감쌀 수 있어
    `.get(...)` 같은 dict 메서드 호출이 AttributeError로 실패할 수
    있습니다. 그래서 반드시 이 내부 함수를 호출해야 합니다.
    """
    emp = db.fetch_employee(employee_id)
    if not emp:
        return {"error": f"직원 ID '{employee_id}'를 찾을 수 없습니다."}

    try:
        req_start = _parse_date(start_date)
        req_end = _parse_date(end_date)
    except ValueError:
        return {"error": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."}

    if req_end < req_start:
        return {"error": "종료일이 시작일보다 빠를 수 없습니다."}

    team_ids = set(db.fetch_team_member_ids(employee_id))
    overlapping = db.fetch_overlapping_approved_requests(start_date, end_date)

    conflicts = []
    for r in overlapping:
        r_start = _parse_date(r["start_date"])
        r_end = _parse_date(r["end_date"])
        if not _dates_overlap(req_start, req_end, r_start, r_end):
            continue  # SQL은 대략적인 범위만 좁혀주므로 한 번 더 정확히 확인

        if r["employee_id"] == employee_id:
            conflicts.append(
                {
                    "type": "self",
                    "request_id": r["request_id"],
                    "start_date": r["start_date"],
                    "end_date": r["end_date"],
                    "message": "이미 본인 명의로 승인된 휴가와 기간이 겹칩니다.",
                }
            )
        elif r["employee_id"] in team_ids:
            colleague = db.fetch_employee(r["employee_id"])
            colleague_name = colleague["name"] if colleague else r["employee_id"]
            conflicts.append(
                {
                    "type": "team",
                    "employee_id": r["employee_id"],
                    "employee_name": colleague_name,
                    "start_date": r["start_date"],
                    "end_date": r["end_date"],
                    "message": f"같은 팀 동료 {colleague_name}님의 휴가와 기간이 겹칩니다.",
                }
            )

    return {
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "has_conflict": len(conflicts) > 0,
        "conflicts": conflicts,
        "suggested_alternatives": (
            _suggest_alternative_dates(employee_id, req_start, req_end)
            if conflicts
            else []
        ),
    }


@tool(permission=ToolPermission.READ_ONLY, expected_credentials=_MYSQL_CREDENTIALS)
def check_leave_conflict(employee_id: str, start_date: str, end_date: str) -> dict:
    """
    요청한 휴가 기간이 (a) 본인의 기존 승인된 휴가, 또는 (b) 같은 매니저를 둔
    팀 동료의 승인된 휴가와 겹치는지 MySQL 데이터를 기준으로 확인합니다.

    Args:
        employee_id: 휴가를 확인하려는 직원의 사번
        start_date: 휴가 시작일 (YYYY-MM-DD)
        end_date: 휴가 종료일 (YYYY-MM-DD)

    Returns:
        has_conflict 여부와 충돌 상세 목록을 담은 딕셔너리.
        충돌이 있는 경우 suggested_alternatives에 동일한 기간(일수)으로
        비어있는 대체 날짜 후보(최대 3개)를 함께 반환합니다.
    """
    return _check_leave_conflict_impl(employee_id, start_date, end_date)


# ---------------------------------------------------------------------------
# 4. 휴가 신청 내역 조회 (내 신청 건의 상태 확인용)
# ---------------------------------------------------------------------------
@tool(permission=ToolPermission.READ_ONLY, expected_credentials=_MYSQL_CREDENTIALS)
def list_leave_requests(employee_id: str) -> dict:
    """
    특정 직원이 신청한 모든 휴가 내역(Pending/Approved/Rejected 포함)을
    최신 순으로 조회합니다. "내가 신청한 휴가가 실제로 반영됐는지",
    "지금 상태가 어떤지" 확인할 때 사용합니다.

    Args:
        employee_id: 조회할 직원의 사번

    Returns:
        해당 직원의 휴가 신청 목록(requests)을 담은 딕셔너리.
        신청 내역이 없으면 빈 리스트를 반환합니다.
    """
    emp = db.fetch_employee(employee_id)
    if not emp:
        return {"error": f"직원 ID '{employee_id}'를 찾을 수 없습니다."}

    requests = db.fetch_requests_by_employee(employee_id)

    return {
        "employee_id": employee_id,
        "employee_name": emp["name"],
        "request_count": len(requests),
        "requests": requests,
    }


# ---------------------------------------------------------------------------
# 5. 휴가 승인현황 조회
# ---------------------------------------------------------------------------
@tool(permission=ToolPermission.READ_ONLY, expected_credentials=_MYSQL_CREDENTIALS)
def get_approval_status(request_id: str = "", employee_id: str = "") -> dict:
    """
    휴가 신청 건의 승인현황(Pending/Approved/Rejected)을 조회합니다.

    request_id를 알고 있으면 그 건 하나만 정확히 조회하고,
    request_id를 모르면 employee_id로 해당 직원의 모든 신청 건과
    각각의 승인현황을 조회합니다. 둘 다 비어 있으면 오류를 반환합니다.

    Args:
        request_id: 조회할 특정 휴가 신청 번호 (예: "V-1005"). 선택 사항.
        employee_id: request_id를 모를 때 대신 조회할 직원 사번. 선택 사항.

    Returns:
        단건 조회 시 해당 신청 건의 상태, 다건 조회 시 신청 목록과 각각의
        상태를 담은 딕셔너리.
    """
    if request_id:
        req = db.fetch_request_by_id(request_id)
        if not req:
            return {"error": f"신청 번호 '{request_id}'를 찾을 수 없습니다."}
        emp = db.fetch_employee(req["employee_id"])
        return {
            "request_id": req["request_id"],
            "employee_id": req["employee_id"],
            "employee_name": emp["name"] if emp else req["employee_id"],
            "start_date": req["start_date"],
            "end_date": req["end_date"],
            "status": req["status"],
            "reason": req["reason"],
        }

    if employee_id:
        emp = db.fetch_employee(employee_id)
        if not emp:
            return {"error": f"직원 ID '{employee_id}'를 찾을 수 없습니다."}
        requests = db.fetch_requests_by_employee(employee_id)
        return {
            "employee_id": employee_id,
            "employee_name": emp["name"],
            "request_count": len(requests),
            "requests": [
                {
                    "request_id": r["request_id"],
                    "start_date": r["start_date"],
                    "end_date": r["end_date"],
                    "status": r["status"],
                    "reason": r["reason"],
                }
                for r in requests
            ],
        }

    return {"error": "request_id 또는 employee_id 중 하나는 반드시 입력해야 합니다."}


# ---------------------------------------------------------------------------
# 6. 팀원 전체 휴가 신청 목록 조회 (매니저용)
# ---------------------------------------------------------------------------
@tool(permission=ToolPermission.READ_ONLY, expected_credentials=_MYSQL_CREDENTIALS)
def get_team_leave_requests(manager_id: str, include_past: bool = False) -> dict:
    """
    특정 매니저(팀장) 밑에 있는 모든 팀원의 휴가 신청 내역을 한 번에
    조회합니다. "우리 팀 휴가 일정 보여줘", "팀원들 휴가 신청 현황
    알려줘" 같은 요청에 사용합니다.

    기본적으로 종료일이 오늘보다 이전인(이미 끝난) 휴가는 결과에서
    제외됩니다 — 앞으로의 팀 휴가 일정을 보여주는 용도이기 때문입니다.
    지나간 휴가까지 포함해서 보고 싶으면 include_past=True로 호출하세요.

    Args:
        manager_id: 팀원들의 매니저(팀장)에 해당하는 사번
        include_past: True로 주면 종료일이 지난 휴가도 함께 포함합니다.
            기본값은 False (지난 휴가 제외).

    Returns:
        매니저 정보와, 해당 매니저를 둔 팀원들의 휴가 신청 목록
        (직원명, 기간, 상태, 사유 포함, 시작일 순 정렬)을 담은 딕셔너리.
        해당 매니저 밑에 팀원이 없거나 신청 내역이 없으면 빈 리스트를
        반환합니다. manager_id 자체가 존재하지 않는 사번이면 오류를
        반환합니다.
    """
    manager = db.fetch_employee(manager_id)
    if not manager:
        return {"error": f"직원 ID '{manager_id}'를 찾을 수 없습니다."}

    requests = db.fetch_team_requests(manager_id, include_past=include_past)

    return {
        "manager_id": manager_id,
        "manager_name": manager["name"],
        "request_count": len(requests),
        "requests": requests,
    }


# ---------------------------------------------------------------------------
# 7. 휴가 신청
# ---------------------------------------------------------------------------
@tool(permission=ToolPermission.READ_WRITE, expected_credentials=_MYSQL_CREDENTIALS)
def apply_leave(
    employee_id: str,
    start_date: str,
    end_date: str,
    reason: str = "",
    confirm_despite_conflict: bool = False,
) -> dict:
    """
    휴가를 신청합니다. 잔여 연차와 팀 내 일정 충돌을 먼저 확인합니다.

    - 충돌이 없으면: 바로 Pending 상태로 신청을 접수합니다.
    - 충돌이 있고 confirm_despite_conflict가 False(기본값)이면: 신청을
      DB에 저장하지 않고, 충돌 내용과 대체 날짜 후보(suggested_alternatives)만
      반환합니다 (requires_confirmation=True). 이 경우 에이전트는 사용자에게
      "그대로 진행할지, 대체 날짜 중 하나를 쓸지" 반드시 먼저 물어봐야 하며,
      사용자 확인 없이 임의로 confirm_despite_conflict=True로 재호출해서는
      안 됩니다.
    - 사용자가 "그래도 이 날짜로 신청할게요"처럼 명시적으로 동의하면, 같은
      start_date/end_date로 confirm_despite_conflict=True를 주어 다시
      호출해야 실제로 신청이 접수됩니다.
    - 사용자가 대체 날짜 중 하나를 선택하면, 그 날짜로 confirm_despite_conflict
      없이(False로) 다시 호출하면 됩니다 (보통 그 날짜엔 충돌이 없습니다).

    Args:
        employee_id: 휴가를 신청하는 직원의 사번
        start_date: 휴가 시작일 (YYYY-MM-DD)
        end_date: 휴가 종료일 (YYYY-MM-DD)
        reason: 휴가 사유 (선택 사항)
        confirm_despite_conflict: 충돌이 있어도 이 날짜 그대로 신청을
            강행할지 여부. 사용자가 명시적으로 동의한 경우에만 True로 호출.

    Returns:
        신청이 실제로 접수됐는지(success), 확인이 필요한 상태인지
        (requires_confirmation), 충돌 내용과 대체 날짜 후보 등을 담은 딕셔너리.
    """
    emp = db.fetch_employee(employee_id)
    if not emp:
        return {"error": f"직원 ID '{employee_id}'를 찾을 수 없습니다."}

    try:
        req_start = _parse_date(start_date)
        req_end = _parse_date(end_date)
    except ValueError:
        return {"error": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."}

    if req_end < req_start:
        return {"error": "종료일이 시작일보다 빠를 수 없습니다."}

    requested_days = _business_days(req_start, req_end)
    remaining = emp["annual_leave_days"] - emp["used_leave_days"]

    if requested_days > remaining:
        return {
            "success": False,
            "error": (
                f"잔여 연차({remaining}일)가 신청 일수({requested_days}일)보다 "
                "부족하여 신청할 수 없습니다."
            ),
        }

    conflict_result = _check_leave_conflict_impl(employee_id, start_date, end_date)
    conflicts = conflict_result.get("conflicts", [])
    suggested_alternatives = conflict_result.get("suggested_alternatives", [])

    if conflicts and not confirm_despite_conflict:
        return {
            "success": False,
            "requires_confirmation": True,
            "message": (
                "요청하신 기간에 일정 충돌이 있습니다. 아래 conflicts를 "
                "사용자에게 안내하고, suggested_alternatives 중 하나를 쓸지 "
                "또는 이 날짜 그대로 신청을 강행할지 물어보세요. 사용자가 "
                "그대로 진행하기를 원하면 동일한 날짜로 "
                "confirm_despite_conflict=true를 주어 이 함수를 다시 "
                "호출해야 신청이 접수됩니다."
            ),
            "employee_id": employee_id,
            "employee_name": emp["name"],
            "start_date": start_date,
            "end_date": end_date,
            "requested_days": requested_days,
            "conflicts": conflicts,
            "suggested_alternatives": suggested_alternatives,
        }

    new_request_id = db.next_request_id()
    db.insert_vacation_request(new_request_id, employee_id, start_date, end_date, reason)
    db.update_used_leave_days(employee_id, requested_days)

    return {
        "success": True,
        "request_id": new_request_id,
        "employee_id": employee_id,
        "employee_name": emp["name"],
        "start_date": start_date,
        "end_date": end_date,
        "requested_days": requested_days,
        "remaining_leave_days_after": remaining - requested_days,
        "status": "Pending",
        "has_conflict_warning": len(conflicts) > 0,
        "conflicts": conflicts,
        "suggested_alternatives": suggested_alternatives,
    }


# ---------------------------------------------------------------------------
# 8. 휴가 신청 폼 (캘린더로 날짜 선택)
# ---------------------------------------------------------------------------
@tool(permission=ToolPermission.READ_ONLY)
def show_leave_request_form(employee_id: str):
    """
    캘린더에서 시작일/종료일을 직접 선택할 수 있는 휴가 신청 폼을 화면에
    보여줍니다. 사용자가 폼을 채우고 제출하면 apply_leave가 자동으로
    호출되어 신청이 접수됩니다.

    "휴가 신청할 때 달력으로 선택하고 싶다", "휴가 신청 폼 보여줘",
    "휴가 신청하고 싶어요" 같은 요청에는 날짜를 텍스트로 직접 되묻지 말고
    이 툴을 먼저 호출해 폼을 띄우는 것을 권장합니다.

    Args:
        employee_id: 휴가를 신청할 직원의 사번

    Returns:
        캘린더 날짜 선택기(DatePicker)가 포함된 휴가 신청 폼(위젯).
        ADK 폼 위젯을 렌더링할 수 없는 환경(로컬 오프라인 테스트 등)에서는
        폼 구성 내용을 요약한 일반 딕셔너리를 대신 반환합니다.
    """
    if not _HAS_FORM_WIDGETS:
        return {
            "note": (
                "이 환경에서는 캘린더 폼 위젯을 렌더링할 수 없어 폼 구성 "
                "내용만 반환합니다. watsonx Orchestrate에 실제 배포하면 "
                "캘린더 선택 UI가 표시됩니다."
            ),
            "employee_id": employee_id,
            "form_fields": ["start_date (date picker)", "end_date (date picker)", "reason (text)"],
            "on_submit_calls": "apply_leave",
        }

    form = FormWidget(
        title="휴가 신청서",
        description="휴가 시작일과 종료일을 캘린더에서 선택하고 사유를 입력해주세요.",
        submit_text="신청하기",
        inputs=[
            TextInput(
                name="employee_id",
                title="사번",
                default_value=employee_id,
                required=True,
            ),
            DatePicker(name="start_date", title="시작일", required=True),
            DatePicker(name="end_date", title="종료일", required=True),
            TextArea(
                name="reason",
                title="사유",
                placeholder="예: 개인 사정",
                required=False,
            ),
        ],
        on_event=[
            ToolEvent(
                tool="apply_leave",
                parameters={
                    "employee_id": "",
                    "start_date": "",
                    "end_date": "",
                    "reason": "",
                },
                map_input_to="submit",
            )
        ],
    )

    return ToolResult(
        content=[
            TextContent(
                text="아래 폼에서 휴가 기간을 캘린더로 선택해주세요.",
                annotations=Annotations(audience=[Role.USER]),
            )
        ],
        widget=form,
    )