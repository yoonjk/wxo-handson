"""가장 단순한 A2A Agent: 받은 메시지에 Hello World 로 응답합니다."""
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import UnsupportedOperationError
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError


class HelloWorldAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_text = context.get_user_input() or "(빈 메시지)"
        reply = f"Hello World! 받은 메시지: {user_text}"
        # Task 없이 Message 한 건으로 즉시 응답 (가장 단순한 A2A 응답 형태)
        await event_queue.enqueue_event(
            new_agent_text_message(reply, context.context_id, context.task_id)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())

