"""OpenAI 모델을 사용하는 Hello World A2A 에이전트의 요청 처리 로직."""

from __future__ import annotations

import logging
import os

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message
from openai import AsyncOpenAI, OpenAIError

logger = logging.getLogger(__name__)


class HelloWorldAgent:
    """OpenAI Responses API를 호출해 사용자에게 인사하는 에이전트."""

    def __init__(self) -> None:
        # API 키는 소스 코드에 저장하지 않고 환경 변수에서 읽습니다.
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다."
            )

        # 비동기 클라이언트를 사용해 A2A 서버의 이벤트 루프를 막지 않습니다.
        self.client = AsyncOpenAI(api_key=api_key, timeout=30.0)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    async def invoke(self, user_message: str) -> str:
        """사용자 입력을 OpenAI 모델에 전달하고 답변 텍스트를 반환합니다."""
        message = user_message.strip()
        if not message:
            message = "안녕하세요. 자기소개를 해주세요."

        try:
            response = await self.client.responses.create(
                model=self.model,
                instructions=(
                    "당신은 A2A 연결 확인을 위한 Hello World 에이전트입니다. "
                    "사용자가 쓴 언어로 친절하고 간결하게 답변하세요. "
                    "첫 인사에는 Hello World 에이전트임을 자연스럽게 소개하세요."
                ),
                input=message,
                max_output_tokens=200,
                # 이 예제는 대화 상태를 서버에 저장하지 않는 독립 요청입니다.
                store=False,
            )

            answer = response.output_text.strip()
            if answer:
                return answer

            # 빈 모델 응답이 Orchestrate로 전달되지 않도록 명시적인 답변을 반환합니다.
            logger.warning("OpenAI API returned an empty text response.")
            return "응답을 생성하지 못했습니다. 다른 방식으로 말씀해 주세요."

        except OpenAIError:
            # API 키, 한도, 연결 오류 등 상세 정보는 서버 로그에만 기록합니다.
            logger.exception("OpenAI Responses API 호출에 실패했습니다.")
            return "OpenAI 모델을 호출하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


class HelloWorldAgentExecutor(AgentExecutor):
    """A2A 요청 문맥과 OpenAI 기반 HelloWorldAgent를 연결합니다."""

    def __init__(self) -> None:
        self.agent = HelloWorldAgent()

    @staticmethod
    def _extract_user_text(context: RequestContext) -> str:
        """A2A 사용자 메시지에서 text part를 순서대로 추출합니다."""
        message = context.message
        if message is None:
            return ""

        text_parts: list[str] = []
        for part in message.parts or []:
            # A2A SDK Part는 실제 콘텐츠를 root 속성에 보관할 수 있습니다.
            content = getattr(part, "root", part)
            text = getattr(content, "text", None)
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())

        return "\n".join(text_parts)

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """입력 메시지를 OpenAI에 전달하고 A2A agent 메시지를 반환합니다."""
        user_message = self._extract_user_text(context)
        answer = await self.agent.invoke(user_message)

        # Hello World는 단일 응답이므로 agent Message 이벤트 하나를 전달합니다.
        await event_queue.enqueue_event(new_agent_text_message(answer))

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """짧은 단일 응답 작업이므로 취소할 별도 백그라운드 작업은 없습니다."""
        return None
