"""watsonx Orchestrate A2A 연결을 독립적으로 점검하는 CLI."""

import argparse
import json
import sys

from a2a_client.wxo_client import WXOClient, WXOClientError


def main() -> int:
    parser = argparse.ArgumentParser(description="watsonx Orchestrate A2A 0.3.0 client")
    parser.add_argument("--discover", action="store_true", help="agents/get으로 사용 가능한 agent 목록 조회")
    parser.add_argument("--message", help="Orchestrate agent에 보낼 요청. 값을 생략하면 대화형 입력을 받음")
    parser.add_argument("--context-id", help="이전 A2A 응답의 context_id로 기존 대화를 이어감")
    parser.add_argument("--task-id", help="input-required 응답의 task_id로 task를 이어감")
    parser.add_argument("--interactive", action="store_true", help="context를 유지하며 여러 번 대화")
    args = parser.parse_args()

    client = WXOClient()
    try:
        if args.discover:
            # 카드에 인증값이 들어있을 수 있으므로 인증 및 비밀 필드는 출력하지 않습니다.
            cards = client.list_agents()
            safe_cards = [
                {
                    "name": card.get("name"),
                    "description": card.get("description"),
                    "url": card.get("url"),
                    "protocolVersion": card.get("protocolVersion"),
                    "preferredTransport": card.get("preferredTransport"),
                    "skills": card.get("skills", []),
                }
                for card in cards
            ]
            print(json.dumps(safe_cards, ensure_ascii=False, indent=2))
            return 0

        if args.interactive:
            context_id, task_id = args.context_id, args.task_id
            print("Orchestrate agent 대화입니다. 종료하려면 /quit을 입력하세요.")
            while True:
                try:
                    message = input("You> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return 0
                if message.lower() in {"/quit", "/exit"}:
                    return 0
                if not message:
                    continue
                reply = client.send_message(message, context_id=context_id, task_id=task_id)
                context_id = reply.get("context_id") or context_id
                task_id = reply.get("task_id") if reply.get("state") in {"input-required", "working"} else None
                print(f"Agent> {reply.get('text') or '(응답 본문이 없습니다. raw_result를 확인하세요.)'}")
                print(f"[state={reply.get('state')} context_id={context_id} task_id={task_id}]")

        message = args.message
        if not message:
            message = input("Orchestrate agent에게 보낼 메시지: ").strip()
        reply = client.send_message(message, context_id=args.context_id, task_id=args.task_id)
        print(json.dumps(reply, ensure_ascii=False, indent=2))
        return 0
    except (WXOClientError, OSError) as exc:
        # 예외 메시지에는 token과 Authorization header를 포함하지 않습니다.
        print(f"A2A 호출 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

