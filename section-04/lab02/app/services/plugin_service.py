"""DB와 독립적인 입력 검사 및 메시지 이메일 마스킹 로직."""
import re
from copy import deepcopy
from typing import Any, Callable

from app.schemas.plugin import PluginRequest, PluginResult

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def transform_content(content: Any, transform: Callable[[str], str]) -> Any:
    """텍스트만 변환하고 tool call, 이미지 URL, 기타 메타데이터는 보존합니다."""
    if isinstance(content, str):
        return transform(content)
    if isinstance(content, list):
        return [transform_content(block, transform) for block in content]
    if isinstance(content, dict) and content.get("type") in {"text", "input_text", "output_text"}:
        if isinstance(content.get("text"), str):
            return {**content, "text": transform(content["text"])}
    return content


def mask_payload(payload: dict[str, Any], role: str) -> dict[str, Any]:
    output = deepcopy(payload)
    for message in output.get("messages", []):
        if message.get("role") == role and "content" in message:
            message["content"] = transform_content(
                message["content"], lambda text: EMAIL_PATTERN.sub("[EMAIL_MASKED]", text)
            )
    return output


def pre_invoke(request: PluginRequest, blocked_terms: str) -> PluginResult:
    # 이 플러그인은 인증/인가를 구현하지 않습니다.
    # RBAC_ONLY에는 내용 검사를 적용하지 않고 권한 검사 단계만 통과시킵니다.
    plugin_context = request.context.get("plugin_context")
    if isinstance(plugin_context, dict) and plugin_context.get("action") == "RBAC_ONLY":
        return PluginResult(continue_processing=True)

    terms = [term.strip().casefold() for term in blocked_terms.split(",") if term.strip()]
    texts: list[str] = []

    def collect(text: str) -> str:
        texts.append(text)
        return text

    # ALL 및 SKIP_RBAC에서는 입력 내용을 검사합니다.
    for message in request.payload.get("messages", []):
        if message.get("role") == "user":
            transform_content(message.get("content"), collect)
    if any(term in text.casefold() for text in texts for term in terms):
        return PluginResult(continue_processing=False)

    masked = mask_payload(request.payload, "user")
    return PluginResult(
        continue_processing=True,
        modified_payload=masked if masked != request.payload else None,
    )


def post_invoke(request: PluginRequest) -> PluginResult:
    masked = mask_payload(request.payload, "assistant")
    return PluginResult(
        continue_processing=True,
        modified_payload=masked if masked != request.payload else None,
    )
