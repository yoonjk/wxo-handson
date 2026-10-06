from typing import Any


def extract_text(value: Any) -> str:
    """Orchestrate/A2A 응답에서 사람이 읽을 텍스트를 최대한 안전하게 추출합니다.

    API 버전이나 Agent 응답 구조가 달라져도 raw JSON을 잃지 않도록
    호출부에서는 원본 response도 함께 반환합니다.
    """

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        texts = [extract_text(v) for v in value]
        return "\n".join(t for t in texts if t)

    if not isinstance(value, dict):
        return ""

    # OpenAI-compatible chat/completions 형태
    choices = value.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if content is not None:
            text = extract_text(content)
            if text:
                return text

    # A2A message/artifact의 parts 형태
    parts = value.get("parts")
    if isinstance(parts, list):
        texts = []
        for part in parts:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    texts.append(text)
                elif "data" in part:
                    nested = extract_text(part["data"])
                    if nested:
                        texts.append(nested)
        if texts:
            return "\n".join(texts)

    # 일반적으로 자주 나타나는 nested keys
    for key in ("result", "message", "artifact", "artifacts", "data", "output"):
        if key in value:
            text = extract_text(value[key])
            if text:
                return text

    return ""
