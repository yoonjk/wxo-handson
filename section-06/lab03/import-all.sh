#!/bin/bash
# import-all.sh — section-06/lab03 SQL Agent (Langflow REST API 방식)
# Imports resources in dependency order: connections → tools → agent

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv
if [ -f "../../../.venv/bin/activate" ]; then
  source "../../../.venv/bin/activate"
elif [ -f "../../venv/bin/activate" ]; then
  source "../../venv/bin/activate"
else
  echo "⚠ No venv found — using system Python"
fi

echo "=== 1. Importing connection: langflow_sqlflow ==="
orchestrate connections import -f connections/langflow_connection.yaml

echo ""
echo "=== 2. Configuring connection: langflow_sqlflow ==="
orchestrate connections configure \
  -a langflow_sqlflow \
  --kind api_key \
  --type team \
  --env draft

echo ""
echo "=== 3. Setting credentials: langflow_sqlflow ==="
orchestrate connections set-credentials \
  -a langflow_sqlflow \
  --env draft \
  --api-key "sk-TxdDRZj_lW50TkgewkYJIOnbFwTWOWTbPI-c5v7UZqA"

echo ""
echo "=== 4. Importing tool: query_database ==="
orchestrate tools import \
  -k python \
  -f tools/sql_tool.py \
  -r tools/requirements.txt \
  --app-id langflow_sqlflow

echo ""
echo "=== 5. Importing agent: sql_agent ==="
orchestrate agents import -f agents/sql_agent.yaml

echo ""
echo "✅ Import complete! Agent 'sql_agent' is ready."
echo ""
echo "📋 테스트 방법:"
echo "   orchestrate chat ask -n sql_agent '테이블 목록을 보여줘'"
echo "   orchestrate chat ask -n sql_agent '직원 수는 몇 명인가요?'"
