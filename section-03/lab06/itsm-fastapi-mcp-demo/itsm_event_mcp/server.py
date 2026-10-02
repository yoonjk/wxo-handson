"""MySQL outbox를 읽고 Bob 사용자에게 공지를 전달하는 MCP 서버."""

import asyncio
import hmac
import json
import logging
import os
import time
from pydantic import BaseModel, Field, model_validator
from typing import Literal

import httpx
import uvicorn
from dotenv import load_dotenv
from mcp.server import MCPServer

from app.schemas.service_request_event import NotificationLink
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response, StreamingResponse

load_dotenv()
logger = logging.getLogger("notification_mcp")

API_BASE = os.getenv("ITSM_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.getenv("ITSM_API_TOKEN", "replace-with-a-long-random-demo-token")
MCP_TOKEN = os.getenv(
    "ITSM_EVENT_MCP_BEARER_TOKEN",
    os.getenv("SR_EVENT_MCP_BEARER_TOKEN", "replace-with-an-event-mcp-token"),
)
# User identity, roles, tokens, and groups are stored in FastAPI's MySQL tables.

# FastAPI posts a committed outbox event ID here to wake waiting SSE sessions.
# Periodic reads remain enabled as a recovery path if this best-effort push fails.
_notification_condition = asyncio.Condition()
_notification_version = 0


class EventNotification(BaseModel):
    """Minimal internal push message; event contents remain in the durable API outbox."""

    event_id: int = Field(ge=1)


def _identity_for_token(authorization: str) -> dict | None:
    """FastAPI에서 token hash, 계정 상태, 관리자 권한을 확인합니다."""
    try:
        response = httpx.get(
            f"{API_BASE}/service-request-events/identity",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
        if response.status_code != 200:
            return None
        identity = response.json()
        return identity if identity.get("employee_no") and identity.get("status") == "active" else None
    except (httpx.HTTPError, ValueError):
        logger.exception("Bob identity lookup failed")
        return None


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """SSE는 직원별 token, MCP transport는 서버용 token으로 각각 인증합니다."""

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        supplied = request.headers.get("authorization", "")
        if request.url.path == "/events" or request.url.path.startswith(("/admin/", "/receipts/")):
            # employee_no를 query parameter로 받지 않습니다. FastAPI는 DB의 token hash를
            # 확인하고, 요청자 신원과 역할을 반환합니다.
            identity = await asyncio.to_thread(_identity_for_token, supplied)
            if identity is None:
                return JSONResponse({"detail": "등록되었고 활성 상태인 Bob 사용자 token이 필요합니다."}, status_code=401)
            request.state.employee_no = identity["employee_no"]
            request.state.bob_identity = identity
            if request.url.path.startswith("/admin/") and not identity.get("is_admin"):
                return JSONResponse({"detail": "알림 관리자 권한이 필요합니다."}, status_code=403)
            return await call_next(request)
        if MCP_TOKEN.startswith("replace-") or not hmac.compare_digest(supplied, f"Bearer {MCP_TOKEN}"):
            return JSONResponse({"detail": "유효한 event MCP Bearer token이 필요합니다."}, status_code=401)
        return await call_next(request)


def _matches_recipient(event: dict, identity: dict) -> bool:
    """SSE 사용자 identity와 저장된 공지 target을 기준으로 수신 여부를 판단합니다."""
    employee_no = identity["employee_no"]
    payload = event.get("payload") or {}
    if event.get("event_type", "").startswith("service_request."):
        return payload.get("recipient_employee_no") == employee_no
    if event.get("event_type") != "notification.created":
        return False
    recipients = payload.get("recipient_employee_nos")
    if recipients is not None:
        return employee_no in recipients
    scope = payload.get("recipient_scope")
    if scope == "all":
        return True
    if scope == "user":
        return payload.get("recipient_employee_no") == employee_no
    if scope == "group":
        return payload.get("recipient_group") in set(identity.get("group_names") or [])
    return False

def _read_events(after_event_id: int, limit: int) -> list[dict]:
    """FastAPI event API에서 cursor 이후 이벤트를 읽습니다."""
    response = httpx.get(
        f"{API_BASE}/service-request-events",
        params={"after_event_id": after_event_id, "limit": limit},
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


mcp = MCPServer(
    "IBM Bob Notification MCP Server",
    instructions=(
        "MySQL transactional outbox를 통해 전체, group, 개별 사용자를 대상으로 "
        "알림을 발행하고 각 Bob 사용자의 인증된 SSE stream으로 전달합니다."
    ),
)


class PublishMessageRequest(BaseModel):
    """HTTP publisher request accepted by the authenticated internal API."""

    target_type: Literal["all", "group", "user"]
    request_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=200)
    target_group: str | None = Field(default=None, max_length=64)
    employee_no: str | None = Field(default=None, max_length=32)
    employee_nos: list[str] | None = Field(default=None, min_length=1, max_length=100)
    links: list[NotificationLink] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_type == "group" and not self.target_group:
            raise ValueError("group 발행에는 target_group이 필요합니다.")
        if self.target_type != "group" and self.target_group is not None:
            raise ValueError("target_group은 group 발행에만 지정하세요.")
        if self.target_type == "user" and not self.employee_no and not self.employee_nos:
            raise ValueError("user 발행에는 employee_no가 필요합니다.")
        if self.target_type == "user" and self.employee_no and self.employee_nos:
            raise ValueError("employee_no와 employee_nos 중 하나만 지정하세요.")
        if self.target_type != "user" and (self.employee_no is not None or self.employee_nos is not None):
            raise ValueError("employee_no(s)는 user 발행에만 지정하세요.")
        if self.employee_nos and len(set(self.employee_nos)) != len(self.employee_nos):
            raise ValueError("employee_nos 중복 값은 허용하지 않습니다.")
        return self


def _publish_notification(payload: PublishMessageRequest) -> dict:
    """FastAPI가 DB 그룹/계정 기준으로 대상을 계산하고 outbox에 기록합니다."""
    body = payload.model_dump(mode="json")
    try:
        response = httpx.post(
            f"{API_BASE}/service-request-events/notifications",
            json=body,
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=10.0,
        )
        response.raise_for_status()
        result = response.json()
        logger.info(
            "notification published: event_id=%s scope=%s recipients=%s",
            result.get("event_id"), payload.target_type, result.get("recipient_count"),
        )
        return result
    except httpx.HTTPError as exc:
        logger.exception("notification publish failed: scope=%s", payload.target_type)
        return {"error": "notification_publish_failed", "detail": str(exc)}


@mcp.tool()
def send_notification(
    target_type: Literal["all", "group", "user"],
    title: str,
    message: str,
    target_group: str | None = None,
    employee_no: str | None = None,
    links: list[NotificationLink] | None = None,
) -> dict:
    """공지와 선택 자료 링크를 발행합니다. target_type은 all, group, user입니다."""
    try:
        payload = PublishMessageRequest(
            target_type=target_type,
            title=title,
            message=message,
            target_group=target_group,
            employee_no=employee_no,
            links=links or [],
        )
    except Exception as exc:
        return {"error": "invalid_request", "detail": str(exc)}
    return _publish_notification(payload)


@mcp.tool()
def watch_service_request_events(after_event_id: int = 0, wait_seconds: int = 20, limit: int = 50) -> dict:
    """새 SR 이벤트를 기다립니다. 다음 호출에는 반환된 next_event_id를 after_event_id로 전달하세요."""
    cursor = max(0, after_event_id)
    deadline = time.monotonic() + max(0, min(wait_seconds, 25))
    bounded_limit = max(1, min(limit, 100))
    try:
        while True:
            events = _read_events(cursor, bounded_limit)
            if events:
                return {
                    "events": events,
                    "next_event_id": events[-1]["id"],
                    "has_more": len(events) == bounded_limit,
                }
            if time.monotonic() >= deadline:
                return {"events": [], "next_event_id": cursor, "has_more": False, "timed_out": True}
            time.sleep(1.0)
    except httpx.HTTPError as exc:
        return {"error": "itsm_api_unavailable", "detail": str(exc), "next_event_id": cursor}


def main():
    """Event MCP 서버를 별도 포트로 실행합니다."""
    app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True)
    app.add_middleware(BearerTokenMiddleware)
    app.add_route("/health", lambda request: JSONResponse({"status": "ok", "service": "ibm-bob-notification-mcp"}))

    async def receive_event_notification(request):
        """Receive a post-commit wake-up from ITSM FastAPI."""
        global _notification_version
        try:
            payload = EventNotification.model_validate(await request.json())
        except Exception:
            return JSONResponse({"detail": "event_id가 포함된 JSON이 필요합니다."}, status_code=422)
        async with _notification_condition:
            _notification_version = max(_notification_version + 1, payload.event_id)
            _notification_condition.notify_all()
        logger.info("outbox wake-up accepted: event_id=%s", payload.event_id)
        return JSONResponse({"accepted": True, "event_id": payload.event_id})

    async def sse_event_feed(request):
        """담당자 employee_no와 일치하는 이벤트만 Bob에 전송합니다."""
        try:
            resume_id = request.headers.get(
                "last-event-id", request.query_params.get("after_event_id", "0")
            )
            cursor = max(0, int(resume_id))
        except ValueError:
            return JSONResponse({"detail": "after_event_id는 0 이상의 정수여야 합니다."}, status_code=400)
        start_cursor = cursor
        identity = request.state.bob_identity
        employee_no = identity["employee_no"]
        seen_version = _notification_version
        logger.info("SSE client connected: employee_no=%s after_event_id=%s", employee_no, cursor)

        async def generate():
            cursor = start_cursor
            last_seen_version = seen_version
            last_heartbeat = time.monotonic()
            while not await request.is_disconnected():
                try:
                    events = await asyncio.to_thread(_read_events, cursor, 100)
                except httpx.HTTPError as exc:
                    logger.exception("outbox read failed: employee_no=%s cursor=%s", employee_no, cursor)
                    yield "event: relay_error\ndata: " + json.dumps({"detail": str(exc)}) + "\n\n"
                    await asyncio.sleep(3)
                    continue
                if events:
                    matching = [
                        event for event in events
                        if _matches_recipient(event, identity)
                    ]
                    logger.info(
                        "outbox batch read: employee_no=%s cursor_before=%s count=%s id_range=%s..%s matching=%s",
                        employee_no,
                        cursor,
                        len(events),
                        events[0]["id"],
                        events[-1]["id"],
                        [event["id"] for event in matching],
                    )
                for event in events:
                    cursor = event["id"]
                    # cursor는 전체 이벤트에서 전진시키고, 인증 사용자 담당 SR만 보냅니다.
                    if not _matches_recipient(event, identity):
                        continue
                    payload = event["payload"]
                    if event["event_type"] == "notification.created":
                        notification = {
                            # SSE event IDs and JSON payloads use decimal strings so JS clients
                            # do not round BIGINT values above Number.MAX_SAFE_INTEGER.
                            "event_id": str(cursor),
                            "event_type": event["event_type"],
                            "ticket_key": "NOTICE",
                            "notification_id": payload.get("notification_id"),
                            "request_id": payload.get("request_id"),
                            "title": payload["title"],
                            "message": payload["message"],
                            "links": payload.get("links", []),
                            "service_name": "notification",
                            "severity": "INFO",
                            "status": "NEW",
                            "created_at": event["created_at"],
                            "detail_tool": None,
                        }
                    else:
                        # 기존 SR 알림 payload는 업무 데이터의 요약만 전달합니다.
                        notification = {
                            "event_id": str(cursor),
                            "event_type": event["event_type"],
                            "ticket_key": event["ticket_key"],
                            "title": payload["title"],
                            "service_name": payload["service_name"],
                            "severity": payload["severity"],
                            "status": payload["status"],
                            "created_at": event["created_at"],
                            "detail_tool": "get_service_request",
                        }
                    logger.info(
                        "SSE event sent: employee_no=%s event_id=%s ticket_key=%s event_type=%s",
                        employee_no,
                        cursor,
                        event["ticket_key"],
                        event["event_type"],
                    )
                    yield f"id: {cursor}\nevent: service_request\ndata: {json.dumps(notification, ensure_ascii=False)}\n\n"
                if time.monotonic() - last_heartbeat >= 15:
                    yield ": keep-alive\n\n"
                    last_heartbeat = time.monotonic()
                # Wake immediately on FastAPI's POST. Timeout makes the committed
                # outbox the source of truth if a push was missed or the relay restarted.
                try:
                    async with _notification_condition:
                        await asyncio.wait_for(
                            _notification_condition.wait_for(
                                lambda: _notification_version > last_seen_version
                            ),
                            timeout=5,
                        )
                        last_seen_version = _notification_version
                except asyncio.TimeoutError:
                    pass

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def proxy_admin_api(request, method: str, resource: str):
        """Bob 사용자의 token을 FastAPI로 전달해 권한을 재검증하게 합니다."""
        body = None
        if method in {"POST", "PUT", "PATCH"}:
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"detail": "JSON request body가 필요합니다."}, status_code=400)
        url = f"{API_BASE}/service-request-events/admin/{resource}"
        headers = {"Authorization": request.headers.get("authorization", "")}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            upstream = await asyncio.to_thread(
                httpx.request, method, url, json=body, headers=headers, timeout=10.0
            )
        except httpx.HTTPError as exc:
            logger.exception("FastAPI admin proxy failed: method=%s resource=%s", method, resource)
            return JSONResponse({"detail": "FastAPI 관리 API에 연결할 수 없습니다."}, status_code=502)
        if not upstream.content:
            return Response(status_code=upstream.status_code)
        try:
            data = upstream.json()
        except ValueError:
            data = {"detail": upstream.text[:1000]}
        return JSONResponse(data, status_code=upstream.status_code)

    async def publish_message(request):
        """사용자 token과 관리자 권한을 FastAPI에서 재확인한 뒤 공지를 발행합니다."""
        return await proxy_admin_api(request, "POST", "messages")

    async def admin_targets(request):
        return await proxy_admin_api(request, "GET", "targets")

    async def mark_receipts_read(request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"detail": "JSON request body가 필요합니다."}, status_code=400)
        try:
            upstream = await asyncio.to_thread(
                httpx.post,
                f"{API_BASE}/service-request-events/receipts/read",
                json=body,
                headers={"Authorization": request.headers.get("authorization", "")},
                timeout=10.0,
            )
        except httpx.HTTPError:
            logger.exception("FastAPI receipt update failed")
            return JSONResponse({"detail": "읽음 상태를 저장하지 못했습니다."}, status_code=502)
        try:
            data = upstream.json()
        except ValueError:
            data = {"detail": upstream.text[:1000]}
        return JSONResponse(data, status_code=upstream.status_code)

    async def admin_users(request):
        return await proxy_admin_api(request, "GET", "users")

    async def create_admin_user(request):
        return await proxy_admin_api(request, "POST", "users")

    async def update_admin_user(request):
        employee_no = request.path_params["employee_no"]
        return await proxy_admin_api(request, "PUT", f"users/{employee_no}")

    async def rotate_admin_user_token(request):
        employee_no = request.path_params["employee_no"]
        return await proxy_admin_api(request, "POST", f"users/{employee_no}/token")

    async def deactivate_admin_user(request):
        employee_no = request.path_params["employee_no"]
        return await proxy_admin_api(request, "DELETE", f"users/{employee_no}")

    async def admin_groups(request):
        return await proxy_admin_api(request, "GET", "groups")

    async def create_admin_group(request):
        return await proxy_admin_api(request, "POST", "groups")

    async def delete_admin_group(request):
        group_name = request.path_params["group_name"]
        return await proxy_admin_api(request, "DELETE", f"groups/{group_name}")

    async def add_admin_group_member(request):
        group_name = request.path_params["group_name"]
        employee_no = request.path_params["employee_no"]
        return await proxy_admin_api(request, "PUT", f"groups/{group_name}/members/{employee_no}")

    async def remove_admin_group_member(request):
        group_name = request.path_params["group_name"]
        employee_no = request.path_params["employee_no"]
        return await proxy_admin_api(request, "DELETE", f"groups/{group_name}/members/{employee_no}")

    app.add_route("/events", sse_event_feed, methods=["GET"])
    app.add_route("/receipts/read", mark_receipts_read, methods=["POST"])
    app.add_route("/admin/targets", admin_targets, methods=["GET"])
    app.add_route("/admin/users", admin_users, methods=["GET"])
    app.add_route("/admin/users", create_admin_user, methods=["POST"])
    app.add_route("/admin/users/{employee_no}", update_admin_user, methods=["PUT"])
    app.add_route("/admin/users/{employee_no}", deactivate_admin_user, methods=["DELETE"])
    app.add_route("/admin/users/{employee_no}/token", rotate_admin_user_token, methods=["POST"])
    app.add_route("/admin/groups", admin_groups, methods=["GET"])
    app.add_route("/admin/groups", create_admin_group, methods=["POST"])
    app.add_route("/admin/groups/{group_name}", delete_admin_group, methods=["DELETE"])
    app.add_route("/admin/groups/{group_name}/members/{employee_no}", add_admin_group_member, methods=["PUT"])
    app.add_route("/admin/groups/{group_name}/members/{employee_no}", remove_admin_group_member, methods=["DELETE"])
    app.add_route("/admin/messages", publish_message, methods=["POST"])
    app.add_route("/internal/event-notify", receive_event_notification, methods=["POST"])
    uvicorn.run(
        app,
        host=os.getenv("ITSM_EVENT_MCP_HOST", os.getenv("SR_EVENT_MCP_HOST", "0.0.0.0")),
        port=int(os.getenv("ITSM_EVENT_MCP_PORT", os.getenv("SR_EVENT_MCP_PORT", "8032"))),
    )


if __name__ == "__main__":
    main()
