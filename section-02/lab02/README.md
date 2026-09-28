
# 1) 스키마 + 시드 데이터 적재
mysql -u nexweb -p -h nexweb.ddnsgeek.com -P 13306 demo < schema.sql

# 2) watsonx Orchestrate 커넥션 생성 (mysql_ai_agent에서 만든 것과 별개 app-id 사용)
orchestrate connections add --app-id mysql_bank_demo
```bash
orchestrate connections configure --app-id mysql_bank_demo --environment draft --kind key_value --type team
```

- draft
```bash
orchestrate connections set-credentials --app-id mysql_bank_demo --env draft \
    -e MYSQL_HOST="localhost" \
    -e MYSQL_PORT="3306" \
    -e MYSQL_USER="user01" \
    -e MYSQL_PASSWORD='abcd1234' \
    -e MYSQL_DATABASE="demo"
```

- live
```bash
orchestrate connections configure --app-id mysql_bank_demo --environment live --kind key_value --type team
```
```bash
orchestrate connections set-credentials --app-id mysql_bank_demo --env live \
    -e MYSQL_HOST="localhost" \
    -e MYSQL_PORT="3306" \
    -e MYSQL_USER="user01" \
    -e MYSQL_PASSWORD='abcd1234' \
    -e MYSQL_DATABASE="demo"
```


# 3) 툴 등록 시 db.py처럼 banking_db.py를 같은 패키지에 포함해서 임포트
orchestrate tools import -k python -f lab11/banking_tools.py -p lab11 -r lab11/requirements.txt --app-id mysql_bank_demo

# 4) Token 발급 API

IBM Cloud (SaaS) 환경인 경우 — 지금까지 흐름상 이 경우일 가능성이 높습니다.
```bash
curl -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WO_API_KEY}"
```  
- set TOKEN
```bash
TOKEN=$(curl -s -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WO_API_KEY}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

## 4. watsonx Orchestrate에 Tools 등록하기

```bash
orchestrate tools import -k python -f lab02/banking_tools.py -p lab02  -r lab02/requirements.txt --app-id mysql_hr_demo
```

# 5) agent_id 조회 API
```bash
API_ENDPOINT="https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/6a4f1092-b48c-4340-8703-6b22d0c6821a"
curl --request GET \
  --url ${API_ENDPOINT}/api/v1/orchestrate/agents \
  --header "Authorization: Bearer ${TOKEN}"
```
```bash
curl --request GET \
  --url "https://${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}"
```

```bash
AGENT_NAME="IBank"
AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] -| select(.name == "IBank") | .id')




AGENT_NAME="IBank"

AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r --arg agent_name "$AGENT_NAME" \
      '.[] | select(.name == $agent_name) | .id')  
```

/api만 빼고 나머지는 그대로입니다. agent_id 필터링까지 같이 하시려면:  


```bash
curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name=="IBank") | .id'
```  

## Agent 등록
```bash
orchestrate agents import -f banking_agent.yaml
```

# Export Agent
```bash
orchestrate agents export \
  -n "IBank" \
  -k native \
  -o IBank.yaml \
  --agent-only  
```



## CLI만으로 agent_id 확인하기 (token 발급 없이)

굳이 raw API를 쓰지 않아도, CLI가 이미 인증을 갖고 있으니 이걸로도 충분합니다:
```bash
orchestrate agents list -v |grep -B2 '"name": "IBank"'
```

```bash
curl --request PUT \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}/chat-starter-settings" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{
    "starter_prompts": {
      "customize": [
        {
          "title": "잔액 조회",
          "subtitle": "내 계좌 잔액을 확인해보세요",
          "prompt": "내 계좌 잔액 알려줘"
        },
        {
          "title": "최근 거래 5건 조회",
          "subtitle": "최근 거래 내역을 확인해보세요",
          "prompt": "최근 거래 5건 보여줘"
        },
        {
          "title": "이체",
          "subtitle": "이체",
          "prompt": "이체해줘"
        },
        {
          "title": "나의 계좌목록",
          "subtitle": "계좌 목록을 보여주세요",
          "prompt": "나의 계좌목록을 보여줘"
        }        
      ]
    },
    "welcome_content": {
      "welcome_message": "안녕하세요, IBank입니다.",
      "description": "계좌 조회, 이체, 연락처 변경을 도와드립니다."
    }
  }'

  ```
# Agent 등록
```bash
  orchestrate agents import -f agent.yaml
  ```