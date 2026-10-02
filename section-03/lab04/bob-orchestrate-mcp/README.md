# Bob Chat -> MCP -> watsonx Orchestrate

IBM Bob Chat에서 MCP Tool을 호출하고, Python MCP Gateway가 IBM watsonx Orchestrate Agent를 호출하는 예제입니다.

## 1. 구조

- Bob IDE -> Streamable HTTP MCP
- MCP Gateway -> IBM Cloud IAM
- MCP Gateway -> watsonx Orchestrate
  - 기본: Agent `chat/completions`
  - 선택: A2A `agents/get` -> agent interaction endpoint -> `message/send`

## 2. Python 환경

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 3. 환경설정

```bash
cp .env.example .env
```

`.env`에 실제 값을 설정합니다.

```dotenv
WXO_BASE_URL=https://api.<region>.watson-orchestrate.cloud.ibm.com
WXO_INSTANCE_ID=<tenant-id>
WXO_AGENT_ID=<agent-id>
WXO_API_KEY=<api-key>
DEFAULT_CALL_MODE=chat
```

API Key는 Git에 commit하지 마세요.

## 4. Orchestrate API만 먼저 테스트

```bash
python test_chat.py
```

A2A discovery:

```bash
python test_a2a_discovery.py
```

A2A는 먼저 실제 `agents/get` JSON을 확인하십시오. 환경의 응답 필드가 코드의 interaction URL 탐색 규칙과 다르면 `app/orchestrate/a2a_client.py`의 `_find_interaction_url()`만 조정하면 됩니다.

## 5. MCP Server 실행

```bash
python -m app.main
```

기본 MCP URL:

```text
http://localhost:8000/mcp
```

## 6. Bob IDE 설정

프로젝트 루트의 `.bob/mcp.json`:

```json
{
  "mcpServers": {
    "watsonx-orchestrate": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp",
      "alwaysAllow": [],
      "disabled": false
    }
  }
}
```

원격 서버라면 localhost를 실제 HTTPS MCP URL로 변경합니다.

## 7. Bob Chat 테스트

Bob Chat:

```text
구매요청 PR-1001의 현재 승인 상태를 알려줘.
```

Bob이 `ask_purchase_agent` Tool을 선택하면:

```text
Bob Chat
 -> MCP tools/call
 -> ask_purchase_agent()
 -> MCP Gateway
 -> IBM IAM token
 -> Orchestrate /chat/completions
 -> Purchase Agent
 -> Tool/Workflow
 -> Enterprise API/MySQL
 -> Bob Chat
```

범용 Agent 호출 예:

```text
ask_orchestrate_agent(
  message="구매요청 PR-1001 상태를 알려줘",
  mode="chat"
)
```

A2A 호출 예:

```text
ask_orchestrate_agent(
  message="구매요청 PR-1001 상태를 알려줘",
  mode="a2a"
)
```

## 8. 운영 시 보완사항

1. MCP endpoint 자체에도 인증을 적용합니다.
2. IBM Cloud API Key는 Secret Manager/Vault에 저장합니다.
3. Agent별 허용 목록(allow-list)을 적용합니다.
4. Tool별 authorization을 추가합니다.
5. request/correlation ID와 audit log를 기록합니다.
6. TLS/HTTPS를 사용합니다.
7. MCP Server에서 임의 agent_id 호출을 허용하지 않도록 정책을 적용합니다.

## 9. 주의

Orchestrate A2A discovery/interaction의 세부 JSON 필드는 배포 버전 및 API 스펙을 실제 환경에서 확인해야 합니다. 이 프로젝트는 존재하지 않는 interaction URL을 추측해서 호출하지 않으며, discovery 응답에서 찾지 못하면 명시적인 오류를 발생시킵니다.
