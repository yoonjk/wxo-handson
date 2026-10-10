#!/usr/bin/env bash
# watsonx Orchestrate(SaaS)에 Bob 공지 발송 MCP 도구와 에이전트를 등록합니다.
# 필요: pip install ibm-watsonx-orchestrate (ADK)
#
# 사용 예:
#   export WXO_INSTANCE_URL="https://api.<region>.watson-orchestrate.cloud.ibm.com/instances/<id>"
#   export WXO_API_KEY="<IBM Cloud API key>"
#   export WXO_NOTIFY_MCP_BEARER_TOKEN="<서버 .env와 같은 값>"
#   export NOTIFY_MCP_URL="https://notify.example.com/mcp"
#   ./setup_wxo.sh
set -euo pipefail

: "${WXO_INSTANCE_URL:?WXO_INSTANCE_URL이 필요합니다}"
: "${WXO_API_KEY:?WXO_API_KEY가 필요합니다}"
: "${WXO_NOTIFY_MCP_BEARER_TOKEN:?WXO_NOTIFY_MCP_BEARER_TOKEN이 필요합니다}"
: "${NOTIFY_MCP_URL:?NOTIFY_MCP_URL이 필요합니다 (예: https://notify.example.com/mcp)}"

ENV_NAME="${WXO_ENV_NAME:-saas}"
CONN_APP_ID="bob_notify_mcp"
TOOLKIT_NAME="bob_notifier"
AGENT_FILE="$(dirname "$0")/agents/bob_notifier_agent.yaml"

echo "== 0. 공개 엔드포인트 사전 점검"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$NOTIFY_MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer $WXO_NOTIFY_MCP_BEARER_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"setup","version":"1.0"}}}' || true)
echo "initialize -> HTTP $code"
if [ "$code" != "200" ]; then
  echo "200이 아닙니다. 421=Host 허용 목록, 401=토큰, 000=DNS/방화벽/프록시를 먼저 확인하세요." >&2
  exit 1
fi

echo "== 1. wxO 환경 연결 (IBM Cloud는 ibm_iam, AWS 호스팅은 mcsp)"
orchestrate env add -n "$ENV_NAME" -u "$WXO_INSTANCE_URL" --type "${WXO_AUTH_TYPE:-ibm_iam}" 2>/dev/null || true
orchestrate env activate "$ENV_NAME" --api-key "$WXO_API_KEY"

echo "== 2. Bearer 연결(connection) 생성"
orchestrate connections add -a "$CONN_APP_ID" 2>/dev/null || true
for env in draft live; do
  orchestrate connections configure -a "$CONN_APP_ID" --env "$env" --type team --kind bearer
  orchestrate connections set-credentials -a "$CONN_APP_ID" --env "$env" --token "$WXO_NOTIFY_MCP_BEARER_TOKEN"
done

echo "== 3. 원격 MCP toolkit 등록 (send_notification, get_service_request, list_service_requests, create_service_request)"
orchestrate toolkits remove -n "$TOOLKIT_NAME" 2>/dev/null || true
orchestrate toolkits add \
  --kind mcp \
  --name "$TOOLKIT_NAME" \
  --description "IBM Bob 공지 발송, SR 조회·발행 (Bob Notifier)" \
  --url "$NOTIFY_MCP_URL" \
  --transport streamable_http \
  --tools "send_notification,get_service_request,list_service_requests,create_service_request" \
  --app-id "$CONN_APP_ID"

echo "== 4. 에이전트 import / deploy"
orchestrate agents import -f "$AGENT_FILE"
orchestrate agents deploy --name bob_notifier_agent

echo "완료: wxO 채팅에서 bob_notifier_agent를 선택해 테스트하세요."