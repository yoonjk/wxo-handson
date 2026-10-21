"""watsonx Orchestrate SaaS A2A 0.3.0 client with explicit agent routing."""
from __future__ import annotations

import os
import time
import threading
import uuid
from typing import Any
from urllib.parse import urlparse

import requests


class WXOClientError(RuntimeError):
    """Safe, actionable A2A client error."""


class WXOClient:
    def __init__(self) -> None:
        self.discovery_url = os.getenv("WXO_A2A_DISCOVERY_URL", "").strip()
        self.agent_url = os.getenv("WXO_A2A_AGENT_URL", "").strip()
        self.agent_name = os.getenv("WXO_AGENT_NAME", "").strip()
        self.allowed_agents = frozenset(
            name.strip() for name in os.getenv("WXO_ALLOWED_AGENTS", "").split(",") if name.strip()
        )
        self.timeout = float(os.getenv("WXO_A2A_TIMEOUT", "90"))
        # IAM API key -> short-lived access token. No static token required.
        self.api_key = (os.getenv("WXO_IAM_API_KEY") or os.getenv("WXO_IBM_CLOUD_API_KEY") or "").strip()
        self.token = (os.getenv("WXO_A2A_BEARER_TOKEN") or "").strip()
        self.iam_url = os.getenv("WXO_IAM_TOKEN_URL", "https://iam.cloud.ibm.com/identity/token").strip()
        self._token_expires_at = float("inf") if self.token else 0.0
        self._token_lock = threading.Lock()
        if not self.api_key and not self.token:
            raise WXOClientError("WXO_API_KEY (권장) 또는 WXO_A2A_BEARER_TOKEN을 설정하세요.")
        self._validate_url(self.iam_url)
        self.session = requests.Session()
        if not self.discovery_url and not self.agent_url:
            raise WXOClientError("WXO_A2A_DISCOVERY_URL 또는 WXO_A2A_AGENT_URL을 설정하세요.")
        if not self.allowed_agents:
            raise WXOClientError("WXO_ALLOWED_AGENTS를 설정하세요. 빈 Allowlist는 허용하지 않습니다.")
        self._validate_url(self.discovery_url or self.agent_url)
        if self.agent_url:
            self._validate_url(self.agent_url)

    @staticmethod
    def _validate_url(url: str) -> None:
        p = urlparse(url)
        if p.scheme != "https" or not p.hostname or p.username or p.password:
            raise WXOClientError("A2A URL은 사용자 정보가 없는 HTTPS URL이어야 합니다.")
        # User-supplied URLs are allowed only when explicitly configured, not via tool input.

    def _get_token(self, force_refresh: bool = False) -> str:
        # Static token fallback for external token management.
        if not self.api_key:
            return self.token
        with self._token_lock:
            if not force_refresh and self.token and time.monotonic() < self._token_expires_at - 120:
                return self.token
            try:
                response = self.session.post(
                    self.iam_url,
                    data={
                        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                        "apikey": self.api_key,
                    },
                    headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30,
                    allow_redirects=False,
                )
                response.raise_for_status()
                payload = response.json()
                token = payload.get("access_token") or payload.get("token")
                if not token or not isinstance(token, str):
                    raise WXOClientError("IBM IAM 응답에 access_token이 없습니다.")
                expires_in = int(payload.get("expires_in", 3600))
                self.token = token
                self._token_expires_at = time.monotonic() + max(1, expires_in)
                return token
            except (requests.RequestException, ValueError) as exc:
                raise WXOClientError(f"IBM IAM 토큰 발급 실패: {type(exc).__name__} (API Key 및 IAM 접근 확인)") from exc

    def _rpc(self, url: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params}
        try:
            for attempt in range(2):
                headers["Authorization"] = f"Bearer {self._get_token(force_refresh=(attempt == 1))}"
                response = self.session.post(
                    url, json=payload, headers=headers, timeout=self.timeout,
                    allow_redirects=False,
                )
                # Refresh only when the credential is managed through an IAM API key.
                if response.status_code != 401 or not self.api_key or attempt == 1:
                    break
        except requests.RequestException as exc:
            raise WXOClientError(f"A2A 연결 실패 ({type(exc).__name__})") from exc
        if response.status_code >= 300:
            raise WXOClientError(f"A2A {method} HTTP {response.status_code} (URL 또는 인증/권한 확인)")
        try:
            data = response.json()
        except ValueError as exc:
            raise WXOClientError(f"A2A {method} 응답이 JSON이 아닙니다.") from exc
        if not isinstance(data, dict):
            raise WXOClientError("A2A 응답 형식이 올바르지 않습니다.")
        if "error" in data:
            err = data["error"]
            raise WXOClientError(f"A2A {method} JSON-RPC 오류: {err}")
        if "result" not in data:
            raise WXOClientError("A2A 응답에 result가 없습니다.")
        return data

    def _get_agent_page(self, limit: int, offset: int) -> list[dict[str, Any]]:
        if not self.discovery_url:
            raise WXOClientError("Agent 검색을 위해 WXO_A2A_DISCOVERY_URL이 필요합니다.")
        payload = self._rpc(self.discovery_url, "agents/get", {"limit": limit, "offset": offset})
        result = payload["result"]
        if not isinstance(result, dict):
            raise WXOClientError("agents/get result가 객체가 아닙니다.")
        cards = result.get("agentCards", result.get("agents", []))
        if not isinstance(cards, list):
            raise WXOClientError("agents/get 응답에 유효한 Agent 목록이 없습니다.")
        return [c for c in cards if isinstance(c, dict)]

    def list_agents(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        if not (1 <= limit <= 1000) or offset < 0:
            raise WXOClientError("limit(1..1000), offset(0 이상) 값을 확인하세요.")
        return [c for c in self._get_agent_page(limit, offset)
                if c.get("name") in self.allowed_agents]

    def _select_agent(self, name: str) -> dict[str, Any]:
        if name not in self.allowed_agents:
            raise WXOClientError(f"허용되지 않은 Agent: {name!r}")
        offset = 0
        while offset < 10000:
            page = self._get_agent_page(limit=100, offset=offset)
            matches = [c for c in page if c.get("name") == name]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise WXOClientError(f"Agent 이름이 중복됩니다: {name}")
            if len(page) < 100:
                break
            offset += 100
        raise WXOClientError(f"Discovery에서 Agent를 찾지 못했습니다: {name}. Live 배포 및 정확한 이름을 확인하세요.")

    def send_message(
        self, message: str, context_id: str | None = None, task_id: str | None = None,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        name = (agent_name or self.agent_name).strip() if (agent_name or self.agent_name) else ""
        if not name:
            raise WXOClientError("agent_name을 지정하세요 (또는 WXO_AGENT_NAME 설정).")
        if name not in self.allowed_agents:
            raise WXOClientError(f"허용되지 않은 Agent: {name!r}")
        if not message or not message.strip():
            raise WXOClientError("message는 필수입니다.")
        if self.agent_url:
            if not self.agent_name or name != self.agent_name:
                raise WXOClientError("직접 Agent URL 모드에서는 WXO_AGENT_NAME과 동일한 Agent만 허용합니다.")
            endpoint = self.agent_url
        else:
            card = self._select_agent(name)
            endpoint = card.get("url") or card.get("endpoint")
            if not isinstance(endpoint, str):
                raise WXOClientError(f"Agent Card에 endpoint URL이 없습니다: {name}")
            self._validate_url(endpoint)
            # Enforce same origin as discovery, to avoid exfiltrating bearer token to an arbitrary endpoint.
            discovery_origin = urlparse(self.discovery_url)
            target_origin = urlparse(endpoint)
            if (discovery_origin.scheme, discovery_origin.netloc) != (target_origin.scheme, target_origin.netloc):
                raise WXOClientError("Agent URL이 Discovery URL과 다른 origin입니다. 신뢰할 수 있는 URL인지 확인하세요.")
        msg: dict[str, Any] = {
            "messageId": str(uuid.uuid4()), "role": "user", "parts": [{"kind": "text", "text": message}],
        }
        if context_id:
            msg["contextId"] = context_id
        if task_id:
            msg["taskId"] = task_id
        result = self._rpc(endpoint, "message/send", {"message": msg})["result"]
        if not isinstance(result, dict):
            raise WXOClientError("message/send result가 객체가 아닙니다.")
        return {"agent_name": name, "result": result,
                "context_id": result.get("contextId") or result.get("context_id") or context_id,
                "task_id": result.get("id") if result.get("kind") == "task" else task_id}
