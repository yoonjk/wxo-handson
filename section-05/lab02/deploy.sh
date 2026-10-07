#!/usr/bin/env bash
# deploy.sh — lab02 전체 등록 스크립트
#
# 사용법:
#   cd ~/project/python/wxo-handson
#   source .venv/bin/activate
#   orchestrate env activate nexweb-env0925
#   bash section-05/lab02/deploy.sh

set -e
LAB="$(cd "$(dirname "$0")" && pwd)"

echo "=== [1/4] Python Tool: unit_convert ==="
orchestrate tools import \
  --kind python \
  --file "${LAB}/unit_convert.py" \
  --requirements-file "${LAB}/requirements.txt"

echo ""
echo "=== [2/4] MCP Toolkit: math_toolkit ==="
orchestrate toolkits add \
  --kind mcp \
  --name math_toolkit \
  --description "Math toolkit with square_root and power functions." \
  --package-root "${LAB}/math_mcp" \
  --command "python math_server.py" \
  --tools "square_root,power"

echo ""
echo "=== [3/4] Agent: math_agent ==="
orchestrate agents import \
  --file "${LAB}/math_agent.yaml"

echo ""
echo "=== [4/4] 등록 확인 ==="
echo "--- tools ---"
orchestrate tools list
echo "--- toolkits ---"
orchestrate toolkits list
echo "--- agents ---"
orchestrate agents list

echo ""
echo "✅ lab02 배포 완료"
