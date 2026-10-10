#!/usr/bin/env bash
# wxo_notify_server → ITSM FastAPI 연결 테스트 (wxo_notify_server가 설치된 서버에서 실행)
#
# 기본 테스트는 모두 읽기 전용입니다(SR·알림을 만들지 않습니다).
#   ./test_itsm_api.sh                  # 1~7단계
#   ./test_itsm_api.sh SR-123           # 실제 SR 번호로 조회까지 확인
#   ./test_itsm_api.sh SR-123 --notify E1001   # 추가: 사번 E1001에게 테스트 공지 1건 발송(쓰기)
#
# 필요: bash, curl, python3. 같은 디렉터리의 .env를 읽습니다(WXO_NOTIFY_* 변수).
set -uo pipefail

SR_KEY="${1:-}"
NOTIFY_EMP=""
if [[ "${2:-}" == "--notify" ]]; then NOTIFY_EMP="${3:-}"; fi
[[ "$SR_KEY" == "--notify" ]] && { echo "사용법: $0 [SR-번호] [--notify 사번]"; exit 2; }

if [[ -f .env ]]; then set -a; . ./.env; set +a; fi
API="${WXO_NOTIFY_ITSM_API_BASE_URL:-http://127.0.0.1:8030}"; API="${API%/}"
API_TOKEN="${WXO_NOTIFY_ITSM_API_TOKEN:-}"
MCP_TOKEN="${WXO_NOTIFY_MCP_BEARER_TOKEN:-}"
HOST="${WXO_NOTIFY_MCP_HOST:-127.0.0.1}"; [[ "$HOST" == "0.0.0.0" ]] && HOST="127.0.0.1"
PORT="${WXO_NOTIFY_MCP_PORT:-8041}"
NOTIFY="${NOTIFY_BASE_URL:-http://${HOST}:${PORT}}"   # 공개 도메인으로 시험하려면 NOTIFY_BASE_URL=https://notify.example.com
TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT

PASS=0; FAIL=0
ok()   { echo "  [PASS] $*"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL] $*"; FAIL=$((FAIL+1)); }
step() { echo; echo "== $*"; }
code() { curl -sS -o "$TMP" -w '%{http_code}' --max-time 10 "$@" 2>"$TMP.err" || true; }

echo "ITSM API : $API"
echo "notify   : $NOTIFY"
[[ -z "$API_TOKEN" || "$API_TOKEN" == replace-* ]] && echo "경고: WXO_NOTIFY_ITSM_API_TOKEN이 비어 있거나 예시 값입니다."
[[ -z "$MCP_TOKEN" || "$MCP_TOKEN" == replace-* ]] && echo "경고: WXO_NOTIFY_MCP_BEARER_TOKEN이 비어 있거나 예시 값입니다."

# ---------------------------------------------------------------- 1~3: 이 서버 → ITSM FastAPI 직접
step "1. ITSM API 도달 (네트워크·방화벽)"
c=$(code "$API/health")
if [[ "$c" == "000" ]]; then
  bad "연결 실패: $(head -c 200 "$TMP.err")  → 주소/포트, FastAPI 호스트 방화벽(OCI Security List·iptables) 확인"
elif [[ "$c" -lt 500 ]]; then ok "서버 응답 HTTP $c (/health가 없어 404여도 도달은 성공)"
else bad "서버 오류 HTTP $c"; fi

step "2. 토큰 인증 (GET /service-requests?limit=1, 읽기 전용)"
c=$(code -H "Authorization: Bearer $API_TOKEN" "$API/service-requests?limit=1")
case "$c" in
  200) ok "HTTP 200 — 토큰 유효";;
  401|403) bad "HTTP $c — WXO_NOTIFY_ITSM_API_TOKEN이 FastAPI의 require_demo_token과 다릅니다";;
  000) bad "연결 실패 (1단계 확인)";;
  *) bad "예상 밖 HTTP $c: $(head -c 200 "$TMP")";;
esac

step "3. SR 조회 경로 (GET /service-requests/{번호})"
probe="${SR_KEY:-SR-0}"
c=$(code -H "Authorization: Bearer $API_TOKEN" "$API/service-requests/$probe")
if [[ -n "$SR_KEY" ]]; then
  [[ "$c" == "200" ]] && ok "$probe 조회 성공 (HTTP 200)" || bad "$probe 조회 HTTP $c: $(head -c 200 "$TMP")"
else
  [[ "$c" == "404" ]] && ok "없는 번호(SR-0)에 404 — 라우트와 인증 정상" || bad "SR-0 조회 기대 404, 실제 HTTP $c"
fi

# ---------------------------------------------------------------- 4~7: wxo_notify_server 경유 (wxO가 쓰는 경로)
step "4. wxo_notify_server /health"
c=$(code "$NOTIFY/health")
if [[ "$c" == "200" ]]; then
  reach=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("itsm_api_reachable"))' "$TMP" 2>/dev/null)
  [[ "$reach" == "True" ]] && ok "서버 정상, itsm_api_reachable=true" || bad "서버는 떠 있으나 itsm_api_reachable=$reach"
else bad "HTTP $c — wxo_notify_server가 실행 중인지, 포트($PORT)를 확인"; fi

mcp() {  # mcp <token> <json-rpc body>  → 본문은 SSE일 수 있어 data: 줄만 추출해 $TMP.json 에 저장
  local tok="$1" body="$2" c
  c=$(code -X POST "$NOTIFY/mcp" -H "Authorization: Bearer $tok" -H 'Content-Type: application/json' \
      -H 'Accept: application/json, text/event-stream' -d "$body")
  python3 - "$TMP" "$TMP.json" <<'PY' 2>/dev/null || true
import sys,re
raw=open(sys.argv[1],encoding="utf8",errors="replace").read()
m=re.findall(r'^data:\s*(.*)$',raw,re.M)
open(sys.argv[2],"w",encoding="utf8").write(m[-1] if m else raw)
PY
  echo "$c"
}

step "5. MCP 인증 (토큰 없음/틀림 → 401이어야 정상)"
c=$(mcp "wrong-token" '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
[[ "$c" == "401" ]] && ok "잘못된 토큰 거부 (401)" || bad "잘못된 토큰인데 HTTP $c"

step "6. MCP tools/list (올바른 토큰)"
c=$(mcp "$MCP_TOKEN" '{"jsonrpc":"2.0","id":2,"method":"tools/list"}')
if [[ "$c" == "200" ]]; then
  names=$(python3 -c 'import json;d=json.load(open("'"$TMP"'.json"));print(",".join(sorted(t["name"] for t in d["result"]["tools"])))' 2>/dev/null)
  want="create_service_request,get_service_request,list_service_requests,send_notification"
  [[ "$names" == "$want" ]] && ok "도구 4개 확인: $names" || bad "도구 목록 불일치: [$names] (기대: $want) — 서버 재시작 여부 확인"
elif [[ "$c" == "401" ]]; then bad "401 — WXO_NOTIFY_MCP_BEARER_TOKEN 불일치"
elif [[ "$c" == "421" ]]; then bad "421 — WXO_NOTIFY_MCP_ALLOWED_HOSTS에 접속 도메인(포트 없는 값 포함) 누락"
else bad "HTTP $c: $(head -c 200 "$TMP")"; fi

step "7. MCP → ITSM API 종단 (get_service_request)"
probe="${SR_KEY:-SR-0}"
c=$(mcp "$MCP_TOKEN" '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_service_request","arguments":{"ticket_key":"'"$probe"'"}}}')
if [[ "$c" == "200" ]]; then
  res=$(python3 - "$TMP.json" <<'PY' 2>/dev/null
import json,sys
d=json.load(open(sys.argv[1]))["result"]
sc=d.get("structuredContent")
if sc is None:
    sc=json.loads(d["content"][0]["text"])
print(sc.get("error") or sc.get("ticket_key") or "?", "|", sc.get("status",""))
PY
)
  if [[ -n "$SR_KEY" ]]; then
    [[ "$res" == "$SR_KEY"* ]] && ok "$SR_KEY 조회 성공 → $res" || bad "조회 결과: $res"
  else
    [[ "$res" == service_request_not_found* ]] && ok "FastAPI까지 도달해 not_found 응답 (정상 경로)" || bad "결과: $res (service_request_lookup_failed면 notify 서버 → FastAPI 연결/토큰 문제)"
  fi
else bad "HTTP $c: $(head -c 200 "$TMP")"; fi

step "7-1. MCP → ITSM API 종단 (list_service_requests, 읽기 전용)"
c=$(mcp "$MCP_TOKEN" '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"list_service_requests","arguments":{"limit":3}}}')
if [[ "$c" == "200" ]]; then
  res=$(python3 - "$TMP.json" <<'PY' 2>/dev/null
import json,sys
d=json.load(open(sys.argv[1]))["result"]
sc=d.get("structuredContent")
if sc is None:
    sc=json.loads(d["content"][0]["text"])
if sc.get("error"):
    print("ERR", sc["error"], sc.get("status",""), str(sc.get("detail",""))[:120])
else:
    keys=",".join(sorted(sc["items"][0].keys())) if sc["items"] else "-"
    print("OK", sc["count"], keys)
PY
)
  case "$res" in
    OK*) ok "목록 조회 성공 → 건수/필드: ${res#OK }";;
    *)   bad "목록 조회 실패: $res";;
  esac
else bad "HTTP $c: $(head -c 200 "$TMP")"; fi

# ---------------------------------------------------------------- 선택: 실제 공지 1건 (쓰기)
if [[ -n "$NOTIFY_EMP" ]]; then
  step "8. 테스트 공지 발송 (사번 $NOTIFY_EMP 에게 1건, 쓰기)"
  c=$(mcp "$MCP_TOKEN" '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"send_notification","arguments":{"target_type":"user","employee_nos":["'"$NOTIFY_EMP"'"],"title":"연결 테스트","message":"wxo_notify_server 연결 테스트 공지입니다. 무시하셔도 됩니다."}}}')
  if [[ "$c" == "200" ]]; then
    res=$(python3 - "$TMP.json" <<'PY' 2>/dev/null
import json,sys
d=json.load(open(sys.argv[1]))["result"]; sc=d.get("structuredContent") or json.loads(d["content"][0]["text"])
print(sc.get("error") or ("event_id=%s" % sc.get("event_id")))
PY
)
    [[ "$res" == event_id=* ]] && ok "발송 성공 ($res) — 해당 사번 Bob Notifier에 알림이 뜨는지 확인" || bad "발송 실패: $res"
  else bad "HTTP $c: $(head -c 200 "$TMP")"; fi
fi

echo; echo "결과: PASS=$PASS FAIL=$FAIL"
[[ $FAIL -eq 0 ]]