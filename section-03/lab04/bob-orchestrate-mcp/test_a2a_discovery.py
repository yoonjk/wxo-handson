import asyncio
import json

from app.orchestrate.a2a_client import discover_agent


async def main():
    result = await discover_agent()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
