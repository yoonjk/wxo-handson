"""watsonx Orchestrate A2A 0.3.0 JSON-RPC client."""

from __future__ import annotations

import os
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

load_dotenv()


class WXOClientError(RuntimeError):
    """설정, 인증 또는 A2A 요청 실패를 상위 MCP tool에 전달합니다."""


class WXOClient:
    """IAM token을 안전하게 보관하고 A2A discovery/message 요청을 보냅니다."""

    def __init__(self) -> None:
        self.discovery_url = os.getenv("WXO_A2A_DISCOVERY_URL", "").strip()
        self.agent_url = os.getenv("WXO_A2A_AGENT_URL", "").strip()
        self.agent_name = os.getenv("WXO_AGENT_NAME", "").strip()
        self.direct_token = os.getenv("WXO_A2A_BEARER_TOKEN", "").strip()
        self.iam_api_key = os.getenv("WXO_IAM_API_KEY", "").strip()
        self.iam_token_url = os.getenv(
            "WXO_IAM_TOKEN_URL", "https://iam.cloud.ibm.com/identity/token"
        ).strip()
        self.timeout = float(os.getenv("WXO_HTTP_TIMEOUT", "60"))
        self._cached_token = ""
        self._token_expires_at = 0.0

    def _access_token(self) -> str:
        """직접 제공된 Bearer token 또는 IBM IAM API key로 발급한 token을 반환합니다."""
        if self.direct_token:
            # .env에는 'Bearer ' 없이 token만 저장하도록 안내합니다.
            return self.direct_token.removeprefix("Bearer ").strip()

        if not self.iam_api_key:
            raise WXOClientError(
                "WXO_A2A_BEARER_TOKEN 또는 WXO_IAM_API_KEY를 .env에 설정하세요."
            )

        # 만료 60초 전 token을 갱신해 요청 도중 만료될 가능성을 줄입니다.
        if self._cached_token and time.time() < self._token_expires_at - 60:
            return self._cached_token

        form = {
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": self.iam_api_key,
        }
        try:
            response = httpx.post(
                self.iam_token_url,
                data=form,
                headers={"Accept": "application/json"},
                timeout=20.0,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # URL이나 request header에 credential을 넣지 않으며 응답 본문도 로그에 남기지 않습니다.
            raise WXOClientError("IBM IAM token 발급에 실패했습니다.") from exc

        token = payload.get("access_token")
        if not token:
            raise WXOClientError("IBM IAM 응답에 access_token이 없습니다.")
        self._cached_token = token
        self._token_expires_at = time.time() + int(payload.get("expires_in", 3600))
        return token

    def _json_rpc(self, url: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """A2A JSON-RPC 요청을 보내고 protocol/HTTP 오류를 안전한 메시지로 변환합니다."""
        request_id = str(uuid.uuid4())
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        try:
            response = httpx.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self._access_token()}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
                follow_redirects=False,
            )
            response.raise_for_status()
            envelope = response.json()
        except WXOClientError:
            raise
        except httpx.HTTPStatusError as exc:
            raise WXOClientError(
                f"watsonx Orchestrate가 HTTP {exc.response.status_code}을 반환했습니다. "
                "A2A endpoint와 agent 환경 URL을 확인하세요."
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise WXOClientError("watsonx Orchestrate A2A endpoint 호출에 실패했습니다.") from exc

        rpc_error = envelope.get("error")
        if rpc_error:
            code = rpc_error.get("code", "unknown")
            message = rpc_error.get("message", "JSON-RPC error")
            raise WXOClientError(f"A2A JSON-RPC 오류 {code}: {message}")
        if "result" not in envelope:
            raise WXOClientError("A2A JSON-RPC 응답에 result가 없습니다.")
        return envelope["result"]

    def list_agents(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Orchestrate의 `agents/get` discovery endpoint에서 agent cards를 가져옵니다."""
        if not self.discovery_url:
            raise WXOClientError("WXO_A2A_DISCOVERY_URL을 .env에 설정하세요.")
        result = self._json_rpc(
            self.discovery_url,
            "agents/get",
            {"limit": max(1, min(limit, 100)), "offset": max(0, offset)},
        )
        cards = result.get("agentCards", [])
        if not isinstance(cards, list):
            raise WXOClientError("agents/get 응답의 agentCards 형식이 올바르지 않습니다.")
        return cards

    def _resolve_agent_url(self) -> str:
        """직접 지정한 endpoint를 우선하고, 없으면 이름과 일치하는 agent card를 찾습니다."""
        if self.agent_url:
            return self.agent_url
        if not self.agent_name:
            raise WXOClientError("WXO_A2A_AGENT_URL 또는 WXO_AGENT_NAME을 설정하세요.")
        cards = self.list_agents()
        matches = [card for card in cards if card.get("name") == self.agent_name]
        if not matches:
            names = ", ".join(str(card.get("name", "")) for card in cards)
            raise WXOClientError(
                f"WXO_AGENT_NAME과 일치하는 agent가 없습니다. 발견된 이름: {names or '(없음)'}"
            )
        if len(matches) > 1:
            raise WXOClientError("같은 이름의 agent card가 여러 개입니다. WXO_A2A_AGENT_URL을 직접 지정하세요.")
        url = matches[0].get("url")
        if not url:
            raise WXOClientError("선택한 Orchestrate agent card에 url이 없습니다.")
        return url

    def send_message(
        self,
        message: str,
        context_id: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """JSON-RPC `message/send`로 사용자 메시지를 WXO agent에 전달합니다."""
        cleaned_message = message.strip()
        if not cleaned_message:
            raise WXOClientError("message는 비어 있을 수 없습니다.")

        a2a_message: dict[str, Any] = {
            "messageId": str(uuid.uuid4()),
            "role": "user",
            "parts": [{"kind": "text", "text": cleaned_message}],
        }
        # 이전 응답의 contextId를 보내면 같은 대화 흐름을 이어갑니다.
        if context_id:
            a2a_message["contextId"] = context_id
        # Orchestrate가 input-required로 반환했을 때 해당 task에 대한 답변임을 표시합니다.
        if task_id:
            a2a_message["taskId"] = task_id

        result = self._json_rpc(
            self._resolve_agent_url(),
            "message/send",
            {"message": a2a_message},
        )
        return self._summarize_result(result)

    @staticmethod
    def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
        """A2A Task/Message에서 agent 답변을 찾아 MCP client에 읽기 쉽게 돌려줍니다."""
        texts: list[str] = []

        def collect_parts(parts: Any) -> None:
            if not isinstance(parts, list):
                return
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])

        # Task 응답은 artifacts, history, status.message 중 한 곳에 답을 포함할 수 있습니다.
        artifacts = result.get("artifacts", [])
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if isinstance(artifact, dict):
                    collect_parts(artifact.get("parts"))

        history = result.get("history", [])
        if isinstance(history, list):
            for entry in history:
                if isinstance(entry, dict) and entry.get("role") == "agent":
                    collect_parts(entry.get("parts"))

        status = result.get("status") or {}
        if isinstance(status, dict) and isinstance(status.get("message"), dict):
            collect_parts(status["message"].get("parts"))
        if result.get("kind") == "message":
            collect_parts(result.get("parts"))

        # 같은 텍스트가 history와 artifact 양쪽에 있으면 한 번만 표시합니다.
        unique_texts = list(dict.fromkeys(text.strip() for text in texts if text.strip()))
        return {
            "task_id": result.get("id"),
            "context_id": result.get("contextId"),
            "state": status.get("state") if isinstance(status, dict) else None,
            "text": "\n\n".join(unique_texts),
            "raw_result": result,
        }

