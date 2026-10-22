"""watsonx Orchestrate OpenAPI plug-in의 공통 입출력 계약."""
from typing import Any

from pydantic import BaseModel, Field, StrictBool, field_validator


class PluginRequest(BaseModel):
    # payload 전체를 유지하여 agent_id나 향후 추가되는 필드가 사라지지 않습니다.
    payload: dict[str, Any] = Field(description="해당 hook의 원본 agent payload")
    context: dict[str, Any] = Field(
        description="system_context, request_context, plugin_context를 포함하는 실행 컨텍스트"
    )

    @field_validator("payload")
    @classmethod
    def validate_messages(cls, payload: dict[str, Any]) -> dict[str, Any]:
        # messages가 없는 payload는 그대로 통과시키되 잘못된 형식은 422로 반환합니다.
        if "messages" in payload:
            messages = payload["messages"]
            if not isinstance(messages, list) or any(not isinstance(m, dict) for m in messages):
                raise ValueError("payload.messages must be an array of message objects")
        return payload


class PluginResult(BaseModel):
    continue_processing: StrictBool = Field(description="false이면 에이전트 처리 중단")
    modified_payload: dict[str, Any] | None = Field(
        default=None, description="변경된 전체 payload. 변경이 없으면 응답에서 생략"
    )
