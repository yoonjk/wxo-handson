"""OpenAPI plug-in 전용 HTTP 엔드포인트. DB 세션 의존성이 없습니다."""
from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.plugin import PluginRequest, PluginResult
from app.services.plugin_service import post_invoke, pre_invoke

router = APIRouter(tags=["Agent Plugins"])


@router.post(
    "/agent_pre_invoke",
    operation_id="purchase_guardrail_pre",
    summary="에이전트 입력 검사 및 이메일 마스킹",
    description="user 메시지의 차단 문구를 검사하고 이메일을 마스킹합니다. 인증/인가를 수행하지 않습니다.",
    response_model=PluginResult,
    response_model_exclude_none=True,
    openapi_extra={"x-ibm-orchestrate-plugin": {"hook": "agent_pre_invoke"}},
)
def purchase_guardrail_pre(request: PluginRequest) -> PluginResult:
    return pre_invoke(request, get_settings().plugin_blocked_terms)


@router.post(
    "/agent_post_invoke",
    operation_id="purchase_email_mask_post",
    summary="에이전트 응답 이메일 마스킹",
    description="assistant 메시지 텍스트의 이메일을 [EMAIL_MASKED]로 치환합니다.",
    response_model=PluginResult,
    response_model_exclude_none=True,
    openapi_extra={"x-ibm-orchestrate-plugin": {"hook": "agent_post_invoke"}},
)
def purchase_email_mask_post(request: PluginRequest) -> PluginResult:
    return post_invoke(request)
