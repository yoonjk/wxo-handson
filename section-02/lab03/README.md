



## import Tool

```bash
orchestrate tools import -k openapi -f ./holiday_api.yaml
orchestrate tools list
```

## Agent 등록
```bash
orchestrate agents import -f holiday_agent.yaml
```

## TOKEN
```bash
TOKEN=$(curl -s -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WXO_API_KEY}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
  ```


# Export Agent
```bash
orchestrate agents export \
  -n "holiday" \
  -k native \
  -o holiday.yaml \
  --agent-only  
```  

## Agent 등록
```bash
orchestrate agents import -f holiday.yaml

## Find Agents
```bash
API_ENDPOINT="https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/6a4f1092-b48c-4340-8703-6b22d0c6821a"
curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq .
```  

```bash
curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r ".[].name"
```

# CLI만으로 agent_id 확인하기 (token 발급 없이)

굳이 raw API를 쓰지 않아도, CLI가 이미 인증을 갖고 있으니 이걸로도 충분합니다:
```bash
orchestrate agents list -v |grep -B2 '"name": "IBank"'
```

AGENT_NAME="holiday"
AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "Untitled_Agent_1_9510Qd") | .id')


AGENT_NAME="holiday"
curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "Untitled_Agent_1_5849T6")'


orchestrate agents export \
  -n "Untitled_Agent_1_5849T6" \
  -k native \
  -o day02-Decision.agent.yaml \
  --agent-only  
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