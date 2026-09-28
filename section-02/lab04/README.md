
## tool 등록
```
orchestrate tools import -k python -f leave_calculator.py
orchestrate tools list



## Agent 등록
```bash
orchestrate agents import -f leave_agent.yaml
```

## TOKEN
```bash
TOKEN=$(curl -s -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WXO_API}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

## Find Agents
```bash
API_ENDPOINT="https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/dc903fdf-92fd-41a6-a4de-91525417be92"
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

# Export Agent
```bash
orchestrate agents export \
  -n "cal_leave_date" \
  -k native \
  -o cal_leave_date.yaml \
  --agent-only  

# CLI만으로 agent_id 확인하기 (token 발급 없이)

굳이 raw API를 쓰지 않아도, CLI가 이미 인증을 갖고 있으니 이걸로도 충분합니다:
```bash
orchestrate agents list -v |grep -B2 '"name": "IBank"'
```

AGENT_NAME="holiday"
AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "cal_leave_date") | .id')

```bash
curl --request PUT \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}/chat-starter-settings" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{
    "starter_prompts": {
      "customize": [
        {
          "title": "나의 연차는",
          "subtitle": "나의 연차를 확인해보세요",
          "prompt": "연차를 알려줘"
        } 
      ]
    },
    "welcome_content": {
      "welcome_message": "안녕하세요, 연차계산 Assistant입니다.",
      "description": "당신의 연차를 알려드립니다."
    }
  }'

  ```