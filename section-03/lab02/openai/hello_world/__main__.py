"""A2A Hello World 서버.   실행:  python -m hello_world"""
import logging
import os

import uvicorn
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from common.auth import BearerAuthMiddleware
from hello_world.agent_executor import HelloWorldAgentExecutor

load_dotenv()
logging.basicConfig(level=logging.INFO)


def build_app():
    port = int(os.getenv("HELLO_AGENT_PORT", "9999"))
    public_url = os.getenv("AGENT_PUBLIC_URL", f"http://localhost:{port}/")

    skill = AgentSkill(
        id="hello_world",
        name="Hello World",
        description="받은 메시지에 Hello World 로 응답합니다. A2A 연결 테스트용.",
        tags=["hello", "test"],
        examples=["hi", "hello world"],
    )
    card = AgentCard(
        name="Hello World Agent",
        description="A2A 연결 확인용 Hello World 에이전트",
        url=public_url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=HelloWorldAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(agent_card=card, http_handler=handler).build()
    app.add_middleware(BearerAuthMiddleware, token=os.getenv("A2A_AUTH_TOKEN", ""))
    return app


if __name__ == "__main__":
    uvicorn.run(
        build_app(),
        host=os.getenv("HELLO_AGENT_HOST", "0.0.0.0"),
        port=int(os.getenv("HELLO_AGENT_PORT", "9999")),
    )

