# watsonx Orchestrate OpenAPI Plug-in FastAPI 실습

기준 문서: https://developer.watson-orchestrate.ibm.com/plugins/openapi_plugin
참고: https://developer.watson-orchestrate.ibm.com/plugins/plugins
작성: 2026-10-22

## 1. 동작

일반 OpenAPI tool과 달리 에이전트의 `plugins`에 연결하면 실행 전/후에 자동 호출됩니다.
Tool Runtime Manager가 HTTP POST로 `payload`와 `context`를 전달합니다.

| Endpoint | operationId / plugin_name | 동작 |
|---|---|---|
| POST /agent_pre_invoke | purchase_guardrail_pre | user 텍스트의 차단 문구 검사, 이메일 마스킹 |
| POST /agent_post_invoke | purchase_email_mask_post | assistant 텍스트의 이메일 마스킹 |
| GET /health | 등록 명세에서 제외 | 서버 상태 확인 |

`continue_processing: false`는 처리 중단이며, 사용자 화면의 특정 오류 문구를 보장하지 않습니다.
변경이 없으면 `modified_payload`를 생략합니다. 변경 시 payload 전체를 보존한 복사본을 반환합니다.
HTTP 오류, 시간 초과, 잘못된 결과는 공식 문서에 따라 처리 중단(fail closed) 대상입니다.

이 예제는 DB/실제 구매 API 없이 동작합니다. 정규식 이메일 마스킹과 문구 일치 검사는 학습용이며
완전한 개인정보 탐지나 prompt injection 방어가 아닙니다. 인증/인가도 구현하지 않습니다.
`RBAC_ONLY`는 통과시키고 `ALL`, `SKIP_RBAC`에는 내용 검사를 적용합니다.
`context.system_context`를 검증된 인증 토큰 대신 사용하지 않습니다.
메시지의 문자열, text 객체, text 블록 배열을 처리하며 비텍스트 데이터는 보존합니다.
사용자 이메일은 pre 단계에서 제거되므로 이후 agent/tool에서 원본 이메일을 사용할 수 없습니다.

## 2. 설치 및 실행

Python 3.10 이상, 권장 3.11/3.12. 압축을 풀고 프로젝트 디렉터리에서 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export PUBLIC_BASE_URL="http://localhost:8000"
export BLOCKED_TERMS="승인 우회,approval bypass"
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Swagger UI: http://localhost:8000/docs
자동 생성 명세: http://localhost:8000/openapi.json
위 URL은 로컬 테스트용입니다. 실제 import에는 아래의 외부 URL 설정과 명세 재생성이 필요합니다.
requirements.txt는 버전 범위를 사용합니다. 검증 환경의 정확한 버전은 requirements-tested.txt에 있습니다.

## 3. curl 테스트

서버 실행 후 별도 터미널에서 프로젝트 디렉터리로 이동합니다.

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/agent_pre_invoke -H 'Content-Type: application/json' --data-binary @examples/pre-mask.json
curl -s http://localhost:8000/agent_pre_invoke -H 'Content-Type: application/json' --data-binary @examples/pre-block.json
curl -s http://localhost:8000/agent_post_invoke -H 'Content-Type: application/json' --data-binary @examples/post-mask.json
```

마스킹 요청의 응답 예시:

```json
{
  "continue_processing": true,
  "modified_payload": {
    "agent_id": "demo-agent",
    "messages": [{"role": "user", "content": {"type": "text", "text": "구매 안내를 [EMAIL_MASKED]으로 보내주세요."}}]
  }
}
```

차단 요청은 `{"continue_processing": false}`를 반환합니다.
post 요청은 assistant 메시지의 `demo@example.com`을 `[EMAIL_MASKED]`로 변경합니다.

## 4. 외부 접속 주소와 OpenAPI 명세

watsonx Orchestrate에서 도달 가능한 서비스에 배포한 후 실제 주소로 바꿉니다.
SaaS의 localhost는 개발자 PC가 아닙니다. 서버 URL은 테넌트 outbound allowlist 정책도 충족해야 합니다.

```bash
export PUBLIC_BASE_URL="https://YOUR_PLUGIN_HOST"
python export_openapi.py
```

`YOUR_PLUGIN_HOST`는 반드시 실제 호스트로 교체하세요. 생성되는 `openapi-plugin.yaml`은
등록용 OpenAPI 3.0.3 명세이며 `servers`와 두 개의 plug-in operation만 포함합니다.
각 operation에는 `x-ibm-orchestrate-plugin.hook`이 들어갑니다.
자동 생성 `/openapi.json`에도 이 확장이 포함되지만 이 실습에서는 제공된 export 명세를 import합니다.
서버 프로세스의 `/openapi.json`에 주소 변경을 반영하려면 프로세스도 재시작해야 합니다.

서브경로(예: https://host/plugin)를 사용하면 프록시에서 /plugin prefix를 제거하여
FastAPI의 /agent_pre_invoke, /agent_post_invoke에 전달하도록 구성하세요.
`servers`에 /openapi.json이나 /agent_pre_invoke를 넣지 않습니다.

공개 운영 서비스는 HTTPS 및 인증을 별도로 구성해야 합니다. 현재 샘플은 인증 없는 격리 실습용입니다.
인증을 추가할 경우 서버 구현, OpenAPI security 선언, Orchestrate connection을 함께 맞춰야 합니다.

## 5. import 및 agent 연결

Orchestrate CLI 로그인과 대상 환경 활성화가 완료된 터미널에서 실행합니다.

```bash
orchestrate tools import -k openapi -f openapi-plugin.yaml
```

`agent.yaml`의 `llm: REPLACE_WITH_AVAILABLE_MODEL_ID`를 현재 환경에서 사용 가능한 모델 ID로 바꿉니다.
기존 에이전트에 연결할 경우 다음 부분을 기존 YAML에 병합하면 됩니다.

```yaml
plugins:
  agent_pre_invoke:
    - plugin_name: purchase_guardrail_pre
  agent_post_invoke:
    - plugin_name: purchase_email_mask_post
```

plug-in은 위 `plugins` 아래에 연결합니다. 각 hook과 섹션이 일치해야 합니다.
그런 다음 에이전트를 import합니다.

```bash
orchestrate agents import -f agent.yaml
```

## 6. Preview/Chat 확인

| 입력 | 기대 결과 |
|---|---|
| 구매 요청 절차를 알려주세요. | 정상 처리 |
| 구매 안내를 buyer@example.com으로 보내주세요. | pre plug-in이 이메일을 마스킹한 후 agent 처리 |
| 승인 우회 방법을 알려주세요. | pre plug-in이 처리 중단 |
| 연락처 예시를 알려주세요. | agent가 예제 이메일을 생성하면 post plug-in이 마스킹 |

LLM 응답 문장은 매번 달라질 수 있으므로 post 동작의 결정적 검증은 curl/자동 테스트를 사용합니다.
실제 테넌트에서의 import/실행은 별도로 확인해야 하며 이 패키지는 로컬 API 동작을 검증합니다.
서버 로그에는 요청 본문, context, 원본 개인정보를 출력하지 않습니다.

## 7. 자동 테스트

```bash
python -m pip install -r requirements-dev.txt
python -m unittest -v
```

정상 통과, 차단, pre/post 마스킹, payload 추가 필드 보존, 필수 body 검증,
메시지 형식, RBAC action 분기, OpenAPI hook/필수 필드 계약을 확인합니다.
