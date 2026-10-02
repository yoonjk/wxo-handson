"""Pure recipient matching helpers for user, group, and broadcast events."""

from __future__ import annotations

from collections.abc import Mapping, Set
from typing import Any


def configured_recipients(
    target_type: str,
    target_group: str | None,
    employee_no: str | None,
    user_tokens: Mapping[str, str],
    user_groups: Mapping[str, Set[str]],
) -> list[str]:
    """Return registered users for a target and reject empty/unknown scopes."""
    if target_type == "all":
        recipients = [employee for employee, token in user_tokens.items() if token]
        if not recipients:
            raise ValueError("등록된 Bob 사용자가 없습니다.")
        return recipients
    if target_type == "user":
        if not employee_no or employee_no not in user_tokens or not user_tokens[employee_no]:
            raise ValueError("employee_no가 ITSM_EVENT_USER_TOKENS_JSON에 등록되어 있지 않습니다.")
        return [employee_no]
    if target_type == "group":
        recipients = [
            employee
            for employee, token in user_tokens.items()
            if token and target_group in user_groups.get(employee, set())
        ]
        if not recipients:
            raise ValueError("target_group에 속한 등록 Bob 사용자가 없습니다.")
        return recipients
    raise ValueError("target_type은 all, group, user 중 하나여야 합니다.")


def matches_recipient(
    event: Mapping[str, Any],
    employee_no: str,
    user_tokens: Mapping[str, str],
    user_groups: Mapping[str, Set[str]],
) -> bool:
    """Check a durable outbox event against one token-authenticated Bob user."""
    payload = event.get("payload") or {}
    event_type = event.get("event_type", "")
    if event_type.startswith("service_request."):
        return payload.get("recipient_employee_no") == employee_no
    if event_type != "notification.created":
        return False
    scope = payload.get("recipient_scope")
    if scope == "all":
        return employee_no in user_tokens and bool(user_tokens[employee_no])
    if scope == "user":
        return (
            payload.get("recipient_employee_no") == employee_no
            or employee_no in (payload.get("recipient_employee_nos") or [])
        )
    if scope == "group":
        return payload.get("recipient_group") in user_groups.get(employee_no, set())
    return False
