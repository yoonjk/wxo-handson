
# Active env
```bash
orchestrate env activate nexweb-env
```

## TOKEN
```bash
TOKEN=$(curl -s -X POST \
  --url https://iam.cloud.ibm.com/identity/token \
  --header "Content-Type: application/x-www-form-urlencoded" \
  --data "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=${WXO_API}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
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
  --name tool_04_foreach_adv_7664Sg \
  --output day05_foreach_adv_workflow01.zip
```  

```bash
orchestrate tools export \
  --name get_product_by_sku \
  --output day05_foreach_adv_workflow02.zip
```  


# List Agents
## API-ENDPOINT
```bash
API_ENDPOINT="https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/6a4f1092-b48c-4340-8703-6b22d0c6821a"
```
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
  | jq -r '.[] | select(.name == "day04_foreach_adv")'

AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "day04_foreach_adv") | .id')  


AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r '.[] | select(.name == "cal_leave_date") | .id')  

```

# Export Agent
```bash
orchestrate agents export \
  -n "day05_foreach_adv" \
  -k native \
  -o day05_foreach_adv.yaml \
  --agent-only  
```

# Update Agent Name
```bash
curl --request PATCH \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "day04_foreach_adv",
    "display_name": "day04-foreach-adv"
  }'
```

```bash
curl --request PATCH \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header "Content-Type: application/json" \
  --data '{
    "name": "day05_foreach_adv",
    "display_name": "day05_foreach_adv"
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

# export workflow
```bash
orchestrate tools list -v|grep "adv"

orchestrate tools export \
  --name tool_04_array_96778s \
  --output day04_foreach_workflow.zip
```

# import workflow
```bash
orchestrate tools import \
  --kind flow \
  --file day04_foreach_adv_workflow.json