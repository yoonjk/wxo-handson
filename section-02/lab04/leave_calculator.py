from ibm_watsonx_orchestrate.agent_builder.tools import tool

@tool
def cal_leave_days(join_date: str, current_date: str) -> dict:
    """
    입사일과 현재 날짜를 기준으로 사용 가능한 연차 일수를 계산합니다.

    :param join_date: 입사일 (YYYY-MM-DD)
    :param current_date: 기준일 (YYYY-MM-DD)
    :returns: 근속연차와 사용 가능 연차 일수
    """
    from datetime import datetime
    fmt = "%Y-%m-%d"
    years = (datetime.strptime(current_date, fmt) - datetime.strptime(join_date, fmt)).days // 365
    days = min(15 + max(0, years - 1), 25)
    return {"years_of_service": years, "available_leave_days": days}