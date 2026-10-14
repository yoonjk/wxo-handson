#!/usr/bin/env bash
# Checks the custom search service the same way watsonx Orchestrate calls it.
# Usage:
#   scripts/test_search.sh                                  # local app, values from .env
#   scripts/test_search.sh http://nexweb.ddnsgeek.com:3464  # through nginx / from outside
set -uo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
BASE_URL="${1:-http://127.0.0.1:${CUSTOM_SERVICE_PORT:-8000}}"
AUTH=()
if [ -n "${AUTH_USERNAME:-}" ] && [ -n "${AUTH_PASSWORD:-}" ]; then
  AUTH=(-u "${AUTH_USERNAME}:${AUTH_PASSWORD}")
fi

pass=0; fail=0
check() {  # name, expected HTTP code, actual HTTP code
  if [ "$2" = "$3" ]; then echo "  PASS  $1 ($3)"; pass=$((pass+1)); else echo "  FAIL  $1 (expected $2, got $3)"; fail=$((fail+1)); fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "Target: $BASE_URL"
echo "1. Reachability"
check "GET /health (no auth)" 200 "$(code "$BASE_URL/health")"

echo "2. Connection check (what Orchestrate sends when a connection is saved)"
check "HEAD / with credentials" 200 "$(code -I "${AUTH[@]}" "$BASE_URL/")"
if [ ${#AUTH[@]} -gt 0 ]; then
  check "HEAD / without credentials" 401 "$(code -I "$BASE_URL/")"
  check "HEAD / with wrong password" 401 "$(code -I -u "${AUTH_USERNAME}:wrong-password" "$BASE_URL/")"
fi

echo "3. Search"
search() {
  curl -s "${AUTH[@]}" -X POST "$BASE_URL/" -H 'Content-Type: application/json' \
       -d "{\"query\": \"$1\", \"filter\": \"\", \"metadata\": {}}"
}
for q in "구매 요청 승인 기준 판정 순서" "500만 원 이상 구매 요청 승인권자" "긴급 구매 승인 절차" "휴가 신청 절차"; do
  out="$(search "$q")"
  top="$(printf '%s' "$out" | python3 -c 'import sys,json; r=json.load(sys.stdin).get("search_results",[]); print(r[0]["title"].split(" - ")[-1] if r else "(no results)")' 2>/dev/null || echo "(invalid response)")"
  printf '  %-36s -> %s\n' "$q" "$top"
done

echo "Result: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
