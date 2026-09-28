# HR 휴가 관리 데모 (watsonx Orchestrate)

Python 기반으로 만든 watsonx Orchestrate 데모 툴 세트입니다. 아래 세 가지 기능을 제공합니다.

| 기능 | 함수 | 설명 |
|---|---|---|
| 휴가 잔여일 조회 | `get_leave_balance(employee_id)` | 직원의 총/사용/잔여 연차를 조회 |
| 휴가 conflict 조회 | `check_leave_conflict(employee_id, start_date, end_date)` | 본인 기존 휴가 및 같은 매니저를 둔 팀 동료의 승인된 휴가와 기간이 겹치는지 확인 |
| 휴가 신청 | `apply_leave(employee_id, start_date, end_date, reason="")` | 잔여 연차 확인 후 신청 접수(Pending), conflict는 경고로 함께 반환 |

## 파일 구조

```
hr_vacation_demo/
├── mock_data.py      # 모의 직원/휴가 데이터 (실제 서비스에서는 DB/HRIS로 대체)
├── tools.py           # watsonx Orchestrate @tool 데코레이터가 적용된 3개 함수
├── main.py             # watsonx Orchestrate 없이 로컬에서 바로 테스트하는 CLI
├── requirements.txt
└── README.md
```

## 로컬에서 먼저 테스트하기

watsonx Orchestrate 환경이 없어도 `tools.py`는 그대로 실행됩니다
(ADK가 없으면 `@tool` 데코레이터가 자동으로 no-op 처리됩니다).

```bash
python main.py
```

정상 케이스, 잔여일 초과, 존재하지 않는 직원 등 6가지 시나리오가 출력됩니다.

## watsonx Orchestrate에 등록하기

1. ADK 설치
   ```bash
   pip install -r requirements.txt
   ```

2. 툴 등록 (CLI 방식)
   ```bash
   orchestrate tools import -k python -f tools.py
   ```
   `tools.py` 안의 `get_leave_balance`, `check_leave_conflict`, `apply_leave` 세 함수가
   각각 독립된 툴로 등록됩니다. 함수의 docstring이 그대로 툴 설명(description)으로,
   타입 힌트가 파라미터 스키마로 사용됩니다.

3. 에이전트에 툴 연결
   Orchestrate UI(또는 agent YAML)에서 HR 에이전트를 만들고 위 3개 툴을 추가합니다.
   예시 지시문(instruction):
   > "직원이 휴가 관련 문의를 하면 먼저 get_leave_balance로 잔여일을 확인하고,
   > 휴가 신청 요청 시에는 반드시 check_leave_conflict로 충돌 여부를 안내한 뒤
   > 사용자가 진행을 원하면 apply_leave로 신청을 접수하세요."

4. 대화 예시
   - "제 휴가 며칠 남았어요?" → `get_leave_balance`
   - "9월 16일부터 18일까지 휴가 써도 되나요?" → `check_leave_conflict`
   - "11월 2일부터 4일까지 휴가 신청해줘" → `apply_leave`

## 실제 시스템에 연결하려면

`mock_data.py`의 `EMPLOYEES`, `VACATION_REQUESTS`를 실제 HRIS/DB 조회로
바꾸기만 하면 됩니다. `tools.py`의 함수 시그니처와 반환 형식은 그대로 유지하면
Orchestrate 에이전트 쪽 설정은 변경할 필요가 없습니다.

- 잔여일 데이터: HR 시스템의 연차 마스터 테이블 조회 API로 교체
- 휴가 신청/충돌 데이터: 실제 결재 시스템의 승인된 휴가 목록 API로 교체
- `apply_leave`에서 신청 저장 시, 실제로는 DB insert 또는 결재 워크플로 트리거 API 호출로 교체

## 참고 사항 (데모 단순화 지점)

- 팀 충돌은 "같은 `manager_id`를 가진 동료"만 확인합니다 (부서 전체가 아님).
- 잔여일 계산 시 주말(토/일)은 근무일수에서 제외합니다. 공휴일은 반영하지 않습니다.
- 신청 후 상태는 항상 `Pending`으로 접수되며, 별도의 승인/반려 기능은 포함하지 않았습니다
  (필요 시 `approve_leave(request_id)` 같은 툴을 추가로 만들면 됩니다).

# API ENDPOINT
```bash
API_ENDPOINT="https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/3e60f36f-30f6-48a8-8360-a561b52b58b2"
```

# Token 발급 API

IBM Cloud (SaaS) 환경인 경우 — 지금까지 흐름상 이 경우일 가능성이 높습니다.
```bash
curl -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WXO_API_KEY}"
```  
- set TOKEN
```bash
TOKEN=$(curl -s -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WXO_API_KEY}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

API_ENDPOINT="https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/3e60f36f-30f6-48a8-8360-a561b52b58b2"


# Export Agent
```bash
orchestrate agents export \
  -n "one_hr" \
  -k native \
  -o one_hr.yaml \
  --agent-only  
```

# Update Agent Name
```bash
curl --request PATCH \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "day02_decision",
    "display_name": "구매 요청 승인"
  }'

# CLI만으로 agent_id 확인하기 (token 발급 없이)

굳이 raw API를 쓰지 않아도, CLI가 이미 인증을 갖고 있으니 이걸로도 충분합니다:
```bash
orchestrate agents list -v |grep -B2 '"name": "IBank"'
```

# 5) agent_id 조회 API
```bash
curl --request GET \
  --url https://${API_ENDPOINT}/api/v1/orchestrate/agents \
  --header "Authorization: Bearer ${TOKEN}"
```

AGENT_NAME="holiday"
AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "one_hr") | .id')

# startPrompts
```bash
curl --request PUT \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}/chat-starter-settings" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{
    "starter_prompts": {
      "customize": [
        {
          "title": "휴가신청",
          "subtitle": "휴가신청 확인해보세요",
          "prompt": "휴가신청 알려줘"
        },        
        {
          "title": "팀원의 휴가 일정 조회",
          "subtitle": "팀원의 휴가 일정 확인해보세요",
          "prompt": "팀원의 휴가 일정 알려줘"
        },
        {
          "title": "남은 연차 일수 조회",
          "subtitle": "남은 연차 일수를 확인해보세요",
          "prompt": "남은 연차 알려줘"
        }        
      ]
    },
    "welcome_content": {
      "welcome_message": "안녕하세요, One-HR 입니다.",
      "description": "연차를 알려드립니다."
    }
  }'
  ```


  