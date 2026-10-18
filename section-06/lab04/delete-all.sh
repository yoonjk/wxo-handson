#!/bin/bash
# delete-all.sh — section-06/lab04 SQL Agent (STDIO MCP Toolkit 방식)
# Removes in reverse order: agent → toolkit → connection

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
orchestrate agents remove -n sql_agent_mcp --kind native || true

echo "=== Removing toolkit ==="
orchestrate toolkits remove -n sqlflow_mcp || true

echo "=== Removing connection ==="
orchestrate connections remove -a sqlflow_mcp_env || true

echo "✅ Cleanup complete."
