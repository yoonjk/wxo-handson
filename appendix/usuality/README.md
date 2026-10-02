# 유용한 WO 명령어 

## Agent 등록
```bash
orchestrate agents import -f holiday_agent.yaml
```

## Export Agent
```bash
orchestrate agents export \
  -n "holiday" \
  -k native \
  -o holiday.yaml \
  --agent-only  
```  

## Find Agents
```bash
API_ENDPOINT="https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/dc903fdf-92fd-41a6-a4de-91525417be92"
curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq .
```  

## Update Agent Name
```bash
curl --request PATCH \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "a2a_demo"
  }'
```

## Find A2A Agent
```
## A2A API로 agent 검색
```bash
curl --request POST \
  --url "${API_ENDPOINT}/v1/orchestrate/A2A" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header "Accept: application/json" \
  --header "Content-Type: application/json" \
  --data '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "agents/get",
    "params": {
      "limit": 20,
      "offset": 0
    }
  }'
  ```

## External agent 조회
```bash
orchestrate agents list --kind external
```  



# Access Controll Agent
## TOKEN
```bash
TOKEN=$(curl -s -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WO_API_KEY}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
  ```

## Agent List
```bash
curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r ".[].name"
```

## CLI만으로 agent_id 확인하기 (token 발급 없이)

raw API를 쓰지 않고, CLI가 이미 인증을 갖고 있으니 이걸로도 충분합니다:
```bash
orchestrate agents list -v |grep -B2 '"name": "IBank"'
```
## Find Agent ID
```bash
WO_URL="https://api.ca-tor.watson-orchestrate.cloud.ibm.com"
WO_TENANT_ID="6a4f1092-b48c-4340-8703-6b22d0c6821a"
API_ENDPOINT="${WO_BASE_URL}$/instances/${WO_TENANT_ID}"
AGENT_NAME="holiday"
AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "Untitled_Agent_1_2892NK") | .id')


AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r --arg agent_name "$AGENT_NAME" \
      '.[] | select(.name == $agent_name) | .id')    
```

## Search Agent List
```bash
curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r ".[].name"
```

## Update Starter Prompts in Agent
```bash
API_ENDPOINT="https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/6a4f1092-b48c-4340-8703-6b22d0c6821a"

curl --request PUT \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}/chat-starter-settings" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{
    "starter_prompts": {
      "customize": [
        {
          "title": "대한민국(KR)의 현재년도 공휴일  조회",
          "subtitle": "올해 공휴일을 확인해보세요",
          "prompt": "올해 공휴일을 알려줘"
        },        
        {
          "title": "지정한 국가의 해당년도 공휴일  조회",
          "subtitle": "해당 연도 공휴일을 확인해보세요",
          "prompt": "올해 공휴일을 알려줘"
        }     
      ]
    },
    "welcome_content": {
      "welcome_message": "안녕하세요, Holiday Assistant입니다.",
      "description": "해당 연도의 Holiday를 알려드립니다."
    }
  }'

  ```

# Tools
## List tool
```bash
orchestrate tools list  
```

## import Tool
```bash
orchestrate tools import -k openapi -f ./holiday_api.yaml
```

# Connection
 ## 2) watsonx Orchestrate 커넥션 생성 (mysql_ai_agent에서 만든 것과 별개 app-id 사용)
 ```bash
orchestrate connections add --app-id mysql_bank_demo
```

## Configure
### Key Value 유형

- draft
```bash
orchestrate connections configure --app-id mysql_bank_demo --environment draft --kind key_value --type team
```
- live

```bash
orchestrate connections configure --app-id mysql_bank_demo --environment live --kind key_value --type team
```

### Bearer Token 유형

- draft
```bash
orchestrate connections configure \
  -a purchase_approval_a2a_dev \
  --env draft \
  --type team \
  --kind bearer
```  

- live
```bash
orchestrate connections configure \
  -a purchase_approval_a2a_dev \
  --env live \
  --type team \
  --kind bearer
```  


## set-credentials
### Key_Value 등록
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
orchestrate connections set-credentials --app-id mysql_bank_demo --env live \
    -e MYSQL_HOST="localhost" \
    -e MYSQL_PORT="3306" \
    -e MYSQL_USER="user01" \
    -e MYSQL_PASSWORD='abcd1234' \
    -e MYSQL_DATABASE="demo"
```

### Bearer token 등록
```bash
orchestrate connections set-credentials \
  --app-id hello_a2a_dev \
  --env draft \
  --token "$A2A_BEARER_TOKEN"
```