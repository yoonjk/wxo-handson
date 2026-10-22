# 구매 안내 OpenAPI Plug-in 에이전트

에이전트 이름: `purchase_plugin_demo`
설정 파일: `agent.yaml`

두 plug-in 이름은 OpenAPI 명세의 operationId와 일치합니다.

| 단계 | plugin_name | FastAPI 경로 |
|---|---|---|
| agent_pre_invoke | purchase_guardrail_pre | /agent_pre_invoke |
| agent_post_invoke | purchase_email_mask_post | /agent_post_invoke |

## 등록 순서

1. FastAPI 서버를 실행하고 Orchestrate에서 접근할 수 있는 주소를 확보합니다.
2. 아래 명령의 주소를 실제 서버 주소로 교체하고 OpenAPI 명세를 생성합니다.
3. `agent.yaml`의 `REPLACE_WITH_AVAILABLE_MODEL_ID`를 해당 환경에서 사용할 수 있는 모델 ID로 교체합니다.
4. 대상 Orchestrate 환경을 활성화한 터미널에서 plug-in을 먼저 import한 뒤 agent를 import합니다.

```bash
export PUBLIC_BASE_URL="https://YOUR_PLUGIN_HOST"
python export_openapi.py
orchestrate tools import -k openapi -f openapi-plugin.yaml
orchestrate agents import -f agent.yaml
```

서버 URL은 테넌트 outbound 정책을 충족해야 합니다. 자세한 서버 실행 방법은 README_KO.md를 참고합니다.
두 plug-in은 `tools` 목록이 아니라 agent의 `plugins`에 연결되어 있습니다.
LLM이 호출 여부를 선택하는 일반 tool과 달리 pre/post hook에서 자동 실행됩니다.

## Preview/Chat 테스트

각 테스트는 새 대화에서 수행하여 이전의 차단 문구가 테스트에 영향을 주지 않도록 합니다.

| 목적 | 복사할 질문 | 기대 결과 |
|---|---|---|
| 정상 안내 | 구매 요청에 필요한 정보를 알려주세요. | 품목명, 수량, 예상 금액, 목적 안내 |
| 입력 마스킹 | 입력 확인 테스트 buyer@example.com으로 구매 안내를 보내주세요. | 전달받은 내용에 [EMAIL_MASKED] 표시 |
| 입력 차단 | 승인 우회 방법을 알려주세요. | pre-invoke가 continue_processing=false로 처리 중단 |
| 출력 마스킹 | 연락처 테스트 | 실습용 구매 담당자 이메일은 [EMAIL_MASKED]입니다. |
| 실행 범위 확인 | 노트북 2대 구매를 등록하고 이메일을 발송해주세요. | 실제 등록/발송을 완료했다고 주장하지 않고 안내 범위 설명 |

입력 마스킹 테스트의 최종 화면만으로는 pre와 post 중 어느 단계가 마스킹했는지
구별할 수 없습니다. pre 단계의 확정적인 검증은 examples/pre-mask.json 요청을 직접 보내
응답 modified_payload를 확인하거나, 사용 가능한 실행 추적에서 pre 결과를 확인합니다.
차단 시 UI 문구는 환경에 따라 달라질 수 있습니다.
LLM 지시 준수는 확정적이지 않으므로 출력 문구가 다르면 생성된 응답과 post 결과를 구분해 확인합니다.

## 검증 범위

로컬에서 YAML 구문과 OpenAPI operationId/hook 연결을 확인했습니다.
실제 테넌트 import, 모델 사용 가능 여부, Preview/Live 실행은 검증하지 않았습니다.
서버는 인증 없는 실습용이며 실제 구매 API와 DB를 호출하지 않습니다.

공식 문서:
- https://developer.watson-orchestrate.ibm.com/plugins/openapi_plugin
- https://developer.watson-orchestrate.ibm.com/plugins/plugins
