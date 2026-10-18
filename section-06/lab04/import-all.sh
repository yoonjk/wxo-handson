#!/bin/bash
# import-all.sh — section-06/lab04 SQL Agent (STDIO MCP Toolkit 방식)
# Imports: connection → mcp toolkit (package-root) → agent

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "../../../.venv/bin/activate" ]; then
  source "../../../.venv/bin/activate"
elif [ -f "../../venv/bin/activate" ]; then
  source "../../venv/bin/activate"
else
  echo "⚠ No venv found — using system Python"
fi

echo "=== 1. Importing connection: sqlflow_mcp_env ==="
orchestrate connections import -f connections/sqlflow_mcp_env.yaml

echo ""
echo "=== 2. Configuring connection: sqlflow_mcp_env ==="
# key_value connection → 환경변수로 MCP 서버에 주입됨
orchestrate connections configure \
  -a sqlflow_mcp_env \
  --kind key_value \
  --type team \
  --env draft

echo ""
echo "=== 3. Setting credentials: sqlflow_mcp_env ==="
# LANGFLOW_API_KEY → server.py의 os.environ.get("LANGFLOW_API_KEY")로 주입
orchestrate connections set-credentials \
  -a sqlflow_mcp_env \
  --env draft \
  --entries "LANGFLOW_API_KEY="

echo ""
echo "=== 4. Adding MCP Toolkit (STDIO, Python, package-root) ==="
# --package-root : tools/ 폴더 전체 업로드
# --language python : python 실행환경
# --command : MCP 서버 시작 명령 (server.py의 if __name__ == "__main__" 진입)
# --app-id : key_value connection → 환경변수로 주입
# --tools "*" : 모든 tool 등록
orchestrate toolkits add \
  -k mcp \
  -n sqlflow_mcp \
  --description "Langflow REST API를 통해 MySQL DB를 자연어로 조회하는 STDIO MCP 서버" \
  --package-root tools \
  --language python \
  --command "python server.py" \
  --app-id sqlflow_mcp_env \
  --tools "*"

echo ""
echo "=== 5. Importing agent: sql_agent_mcp ==="
orchestrate agents import -f agents/sql_agent.yaml

echo ""
echo "✅ Import complete! Agent 'sql_agent_mcp' is ready."
echo ""
echo "📋 테스트 방법:"
echo "   orchestrate chat ask -n sql_agent_mcp '테이블 목록을 보여줘'"
echo "   orchestrate chat ask -n sql_agent_mcp '직원 수는 몇 명인가요?'"
