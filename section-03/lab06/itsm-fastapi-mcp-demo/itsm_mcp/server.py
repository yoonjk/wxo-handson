"""FastAPI REST API를 SR 중심 MCP 도구로 노출하는 원격 서버."""

import hmac
import os

import httpx
import uvicorn
from dotenv import load_dotenv
from mcp.server import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

load_dotenv()

API_BASE = os.getenv("ITSM_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("ITSM_API_TOKEN", "replace-with-a-long-random-demo-token")
MCP_TOKEN = os.getenv("ITSM_MCP_BEARER_TOKEN", "replace-with-a-different-long-random-token")


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """MCP HTTP 요청에서 공유 데모 Bearer token을 검증합니다."""

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        supplied = request.headers.get("authorization", "")
        if MCP_TOKEN.startswith("replace-") or not hmac.compare_digest(supplied, f"Bearer {MCP_TOKEN}"):
            return JSONResponse({"detail": "유효한 데모 Bearer token이 필요합니다."}, status_code=401)
        return await call_next(request)


def _call_api(method: str, path: str, **kwargs):
    """MCP 도구가 인증을 붙여 내부 REST API를 호출합니다."""
    try:
        response = httpx.request(
            method,
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=10.0,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return {"error": exc.response.status_code, "detail": exc.response.text}
    except httpx.HTTPError as exc:
        return {"error": "service_unavailable", "detail": str(exc)}


mcp = MCPServer("Demo ITSM Service Request MCP Server", instructions="운영 유지보수 Service Request를 조회하고 승인된 작업을 기록합니다.")


@mcp.tool()
def list_service_requests(status: str = "", severity: str = "", service_name: str = "", limit: int = 20) -> dict:
    """SR 목록 조회. status: NEW/IN_PROGRESS/RESOLVED/CLOSED."""
    params = {"limit": max(1, min(limit, 100))}
    if status:
        params["status"] = status
    if severity:
        params["severity"] = severity
    if service_name:
        params["service_name"] = service_name
    return {"service_requests": _call_api("GET", "/service-requests", params=params)}


@mcp.tool()
def get_service_request(ticket_key: str) -> dict:
    """SR-000001 형식의 Service Request 상세 조회."""
    return _call_api("GET", f"/service-requests/{ticket_key}")


@mcp.tool()
def create_service_request(
    title: str,
    description: str,
    service_name: str,
    environment: str,
    severity: str,
    requester: str,
    assignee: str = "",
    assignee_employee_no: str = "",
) -> dict:
    """SR 생성. 실행 전 사용자 승인을 받고, 중복 SR을 먼저 조회하세요."""
    payload = {
        "title": title,
        "description": description,
        "service_name": service_name,
        "environment": environment,
        "severity": severity,
        "requester": requester,
        "assignee": assignee or None,
        "assignee_employee_no": assignee_employee_no or None,
    }
    return _call_api("POST", "/service-requests", json=payload)


@mcp.tool()
def update_service_request_status(ticket_key: str, status: str) -> dict:
    """승인된 SR 상태 변경. NEW→IN_PROGRESS→RESOLVED→CLOSED 순서를 따릅니다."""
    return _call_api("PATCH", f"/service-requests/{ticket_key}/status", json={"status": status})


@mcp.tool()
def add_worklog(ticket_key: str, note: str, author: str) -> dict:
    """승인된 작업 결과, 빌드 번호, Quality Gate 및 배포 버전을 SR에 기록합니다."""
    return _call_api("POST", f"/service-requests/{ticket_key}/worklog", json={"note": note, "author": author})


def main():
    """MCP SDK v2 ASGI 앱을 Uvicorn으로 실행합니다."""
    host = os.getenv("ITSM_MCP_HOST", "0.0.0.0")
    port = int(os.getenv("ITSM_MCP_PORT", "8030"))
    app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True)
    app.add_middleware(BearerTokenMiddleware)
    app.add_route("/health", lambda request: JSONResponse({"status": "ok", "service": "itsm-sr-mcp"}))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
