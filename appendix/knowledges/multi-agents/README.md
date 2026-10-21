orchestrate agents export \
  -n "office_faq" \
  -k native \
  -o multi_office_faq.yaml \
  --agent-only  


  ```bash

AGENT_NAME="holiday"
AGENT_NAME="office_faq"
AGENT_ID=$(curl -s --request GET \
  --url "${API_ENDPOINT}/v1/orchestrate/agents" \
  --header "Authorization: Bearer ${TOKEN}" \
  | jq -r --arg agent_name "$AGENT_NAME" \
      '.[] | select(.name == $agent_name) | .id')   

curl --request PUT \
  --url "${API_ENDPOINT}/v1/orchestrate/agents/${AGENT_ID}/chat-starter-settings" \
  --header "Authorization: Bearer ${TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{
    "starter_prompts": {
      "customize": [
        {
          "title": "내 연차는 몇일",
          "subtitle": "내 연차를 확인해보세요",
          "prompt": "내 연차는 몇일인지 알려줘"
        },
        {
          "title": "재택 근무 규정",
          "subtitle": "재택근무 규정에 대해 물어보세요",
          "prompt": "재택근무 신청은 어떻게 하나요?"
        },
        {
          "title": "IT FAQ",
          "subtitle": "노트북, VPN 관련 FAQ",
          "prompt": "노트북 화면이 안 켜져요"
        }    
      ]
    },
    "welcome_content": {
      "welcome_message": "안녕하세요, Office Assistant 입니다.",
      "description": "연차, 재택, IT FAQ를 도와드립니다."
    }
  }'