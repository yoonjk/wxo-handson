#!/bin/bash
# delete-all.sh — section-06/lab03 SQL Agent
# Removes resources in reverse import order: agent → tools → connections

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "../../../.venv/bin/activate" ]; then
  source "../../../.venv/bin/activate"
elif [ -f "../../venv/bin/activate" ]; then
  source "../../venv/bin/activate"
else
  echo "⚠ No venv found — using system Python"
fi

echo "=== Removing agent ==="
orchestrate agents remove -n sql_agent --kind native || true

echo "=== Removing tools ==="
orchestrate tools remove -n query_database || true
orchestrate tools remove -n sqlflow || true
orchestrate tools remove -n run_sql_query || true

echo "=== Removing connections ==="
orchestrate connections remove -a langflow_sqlflow || true
orchestrate connections remove -a mysql_db_creds || true
orchestrate connections remove -a watsonx_creds || true

echo "✅ Cleanup complete."
