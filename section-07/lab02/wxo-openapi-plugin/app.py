"""watsonx Orchestrate OpenAPI plug-in 실습 서버 (Python 3.10+)."""
import os
import re
from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, StrictBool

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
BLOCKED_TERMS = tuple(
    term.strip().casefold()
    for term in os.getenv("BLOCKED_TERMS", "승인 우회,approval bypass").split(",")
    if term.strip()
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

app = FastAPI(
    title="watsonx Orchestrate OpenAPI Plugin Demo",
    version="1.0.0",
    description="에이전트 입력 검사와 입출력 이메일 마스킹 실습",
    servers=[{"url": PUBLIC_BASE_URL}],
)


class PluginRequest(BaseModel):
    # phase별 payload의 추가 필드를 잃지 않도록 객체 전체를 보관합니다.
    payload: dict[str, Any]
    context: dict[str, Any]


class PluginResult(BaseModel):
    continue_processing: StrictBool
    modified_payload: dict[str, Any] | None = None


def transform_content(content: Any, transform):
    """텍스트만 변경하고 tool call, 이미지 URL, 기타 메타데이터는 보존합니다."""
    if isinstance(content, str):
        return transform(content)
    if isinstance(content, list):
        return [transform_content(item, transform) for item in content]
    if isinstance(content, dict) and content.get("type") in {"text", "input_text", "output_text"}:
        if isinstance(content.get("text"), str):
            return {**content, "text": transform(content["text"])}
    return content


def message_texts(payload: dict[str, Any], role: str) -> list[str]:
    texts: list[str] = []

    def collect(text: str) -> str:
        texts.append(text)
        return text

    for message in payload.get("messages", []):
        if isinstance(message, dict) and message.get("role") == role:
            transform_content(message.get("content"), collect)
    return texts


def mask_payload(payload: dict[str, Any], role: str) -> dict[str, Any]:
    # 원본과 phase별 agent_id/추가 필드를 유지하는 깊은 복사입니다.
    output = deepcopy(payload)
    for message in output.get("messages", []):
        if isinstance(message, dict) and message.get("role") == role and "content" in message:
            message["content"] = transform_content(
                message["content"], lambda text: EMAIL.sub("[EMAIL_MASKED]", text)
            )
    return output


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.post(
    "/agent_pre_invoke",
    operation_id="purchase_guardrail_pre",
    response_model=PluginResult,
    response_model_exclude_none=True,
    openapi_extra={"x-ibm-orchestrate-plugin": {"hook": "agent_pre_invoke"}},
)
def agent_pre_invoke(request: PluginRequest) -> PluginResult:
    """사용자 입력의 차단 문구를 검사하고 이메일을 마스킹합니다."""
    # 이 실습은 권한 제어를 구현하지 않습니다. RBAC_ONLY는 내용 검사 없이 통과합니다.
    # SKIP_RBAC는 권한 검사 생략을 뜻하므로 내용 검사는 계속 수행합니다.
    if request.context.get("plugin_context", {}).get("action") == "RBAC_ONLY":
        return PluginResult(continue_processing=True)
    texts = message_texts(request.payload, "user")
    if any(term in text.casefold() for text in texts for term in BLOCKED_TERMS):
        # false는 처리 중단 신호입니다. UI에 표시될 오류 문구를 가정하지 않습니다.
        return PluginResult(continue_processing=False)
    masked = mask_payload(request.payload, "user")
    return PluginResult(
        continue_processing=True,
        modified_payload=masked if masked != request.payload else None,
    )


@app.post(
    "/agent_post_invoke",
    operation_id="purchase_email_mask_post",
    response_model=PluginResult,
    response_model_exclude_none=True,
    openapi_extra={"x-ibm-orchestrate-plugin": {"hook": "agent_post_invoke"}},
)
def agent_post_invoke(request: PluginRequest) -> PluginResult:
    """응답 messages의 assistant 텍스트에서 이메일을 마스킹합니다."""
    masked = mask_payload(request.payload, "assistant")
    return PluginResult(
        continue_processing=True,
        modified_payload=masked if masked != request.payload else None,
    )
