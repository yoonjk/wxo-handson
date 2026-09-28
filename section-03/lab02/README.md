# Purchase Approval FastAPI

watsonx Orchestrate의 구매 승인 플로우가 승인/반려 결과를 MySQL에 저장할 때 사용하는 API입니다.

## 구조

- `app/db/connection.py`: DB 연결과 세션 생성
- `app/repositories/purchase_repository.py`: SQL/DB 처리
- `app/services/purchase_service.py`: 상태 전이 업무 규칙
- `app/api/routes/purchases.py`: FastAPI 엔드포인트
- `sql/schema.sql`: MySQL 테이블 생성문

## 1. 테이블 생성

```bash
mysql -h nexweb.ddnsgeeki.com -P 13306 -u nexweb -p demo < sql/schema.sql
```

## 2. 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env의 DB_PASSWORD를 실제 값으로 변경
uvicorn app.main:app --host 0.0.0.0 --port 8010--reload
```

- Swagger UI: `http://localhost:8010/docs`
- OpenAPI 문서: `http://localhost:8010/openapi.json`
- 상태 확인: `http://localhost:8010/health`

## 3. 테스트용 구매 요청 생성

```bash
curl -X POST http://localhost:8010/api/purchase-requests \
  -H 'Content-Type: application/json' \
  -d '{
    "purchase_type": "IT_EQUIPMENT",
    "requester": "hong.gildong",
    "total_amount": 1500000,
    "reason": "개발용 노트북 구매"
  }'
```

응답의 `id`를 Orchestrate 플로우의 `request_id` 입력값으로 사용합니다.

## 4. 승인 결과 API 테스트

승인:

```bash
curl -X PATCH http://localhost:8010/api/purchase-requests/1/status \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "APPROVED",
    "comment": "예산 확인 완료",
    "approver_role": "IT_MANAGER"
  }'
```

반려할 때는 `status`를 `REJECTED`로 전달합니다.

## 5. watsonx Orchestrate Tool 등록

1. FastAPI를 Orchestrate에서 접근 가능한 **HTTPS 주소**로 배포합니다. 클라우드 Orchestrate는 `localhost`에 접근할 수 없습니다.
2. Orchestrate의 Tools에서 OpenAPI 문서 URL `https://<호스트>/openapi.json`을 가져옵니다.
3. operation ID가 `update_purchase_status`인 작업을 활성화합니다.
4. 승인 Branch에서 Call a tool을 추가하고 다음처럼 매핑합니다.

| Tool 입력 | 승인 경로 | 반려 경로 |
|---|---|---|
| `request_id` | 플로우 입력의 구매 요청 ID | 동일 |
| `status` | `APPROVED` | `REJECTED` |
| `comment` | `approval_comment` | `approval_comment` |
| `approver_role` | Decision 출력 `approver_role` | 동일 |

현재 API는 실습용으로 인증을 넣지 않았습니다. 외부 공개 배포 시 API Gateway 또는 애플리케이션 인증을 추가하세요.

# Active env


```bash
orchestrate env activate nexweb-env
```

# Export openapi
```bash
curl http://nexweb.ddnsgeek.com/purchase/openapi.json \
  -o openapi.json 
```

## Import tool
```bash
 orchestrate tools import \
  -k openapi \
  -f openapi.json 
```  

## export tool
```bash
orchestrate tools export \
  --name update_purchase_status \
  --output update_purchase_status.zip
```
## TOKEN
```bash
TOKEN=$(curl -s -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WXO_API}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

# List Agents
```bash
curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r ".[].name"
```

# findByName : AGENT_ID
```bash
orchestrate agents list -v


curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "day02_decision")'

AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "day02_decision") | .id')  

```
# Import Agent
```
orchestrate agents import -f day02_decision.yaml
```

# Export Agent
```bash
orchestrate agents export \
  -n "day02_decision" \
  -k native \
  -o day02_decision.yaml \
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
```

```bash
curl --request PATCH \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "day01_firstworkflow",
    "display_name": "day01-firstworkflow"
  }'
```

# Update Agent
```bash
curl --request PUT \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}/chat-starter-settings" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{
    "starter_prompts": {
      "customize": [
         {
          "title": "구매 요청 조회",
          "subtitle": "나의 구매 요청 조회",
          "prompt": "구매 요청 조회"
        },          
        {
          "title": "구매 승인 요청",
          "subtitle": "구매 승인 요청해 보세요",
          "prompt": "구매 승인 요청"
        },
        {
          "title": "구매 승인 승인 or 취소",
          "subtitle": "승인 or 취소",
          "prompt": "구매 승인 or 취소"
        }         
      ]
    },
    "welcome_content": {
      "welcome_message": "안녕하세요, 구매 Assistant입니다.",
      "description": "구매 신청."
    }
  }'
```