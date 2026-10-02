# Demo ITSM Service Request: FastAPI + MySQL + MCP

IBM Bob, ContextForge MCP Gateway, A2A WXO MCP Server, watsonx Orchestrate, Jenkins와 SonarQube를 연결하는 운영 유지보수 발표 데모입니다. 사용자 이미지를 기준으로 FastAPI 코드를 `api / core / db / models / repositories / schemas / services`로 나눴습니다.

## 구성

```text
운영 요청 → FastAPI ITSM → MySQL SR + transactional outbox
                    ├──▶ ITSM MCP Server ─────▶ ContextForge Gateway ──▶ IBM Bob
                    └──▶ IBM Bob Notification MCP Server ──▶ 전체/그룹/개인 대상 SSE ──▶ Bob
                                  └─────────────▶ Gateway MCP tool registry

Bob ──MCP──▶ Gateway ──▶ Jenkins MCP / SonarQube MCP / ITSM MCP / A2A WXO MCP
                                                       A2A WXO MCP ──A2A──▶ watsonx Orchestrate agent
```

Bob은 SR 알림을 표시하고, 개발자가 요청한 경우 SR 조회와 코드 SDLC를 보조합니다. 알림 수신만으로 코드 수정이나 배포를 자동 수행하지 않습니다. Orchestrate는 요청 요약과 다음 단계 제안을 맡는 시나리오입니다.

> IBM Bob Notification MCP Server는 직원별 Bearer token을 검증하고, 담당 SR 이벤트와 공지 메시지를 SSE로 전달합니다. 공지 대상은 전체 등록 사용자, 설정된 그룹, 개별 employee_no 중에서 고릅니다. 메시지와 SR 이벤트는 MySQL transactional outbox에 저장되며, FastAPI의 `POST /internal/event-notify`는 relay를 깨우는 용도입니다. 연결이 끊긴 사용자는 저장된 cursor로 재접속하면 대상 메시지를 다시 받을 수 있습니다.

## 소스 구조

```text
app/
├── api/routes/       # REST 경로
├── core/             # 설정과 인증
├── db/               # SQLAlchemy 연결과 Base
├── models/           # ORM 모델
├── repositories/     # DB 조회/저장
├── schemas/          # 입력/출력 검증
├── services/         # SR 업무 규칙과 상태 전이
└── main.py
itsm_mcp/              # ITSM REST API를 MCP 도구로 제공
a2a_client/            # Orchestrate A2A client/CLI
itsm_event_mcp/         # IBM Bob Notification MCP tool, 대상별 공지 발행과 SSE feed
a2a_wxo_mcp/           # Bob/Gateway에 A2A 도구를 제공
bob_notifier/           # Bob 2.0.1용 SSE 구독/VS Code 팝업 확장
sql/                   # MySQL DDL 및 예제 데이터
scripts/               # REST 저장/조회 스모크 테스트
docs/                  # 발표 시나리오
```

## 제공 기능

| MCP 도구 | 기능 |
|---|---|
| `list_service_requests` | 상태·우선순위·서비스별 SR 목록 조회 |
| `get_service_request` | `SR-000001` 상세 조회 |
| `create_service_request` | 새 SR 생성 (담당 employee_no 지정 가능) |
| `update_service_request_status` | 허용 상태 전이에 따라 상태 변경 |
| `add_worklog` | 작업 결과·빌드·품질 게이트·배포 기록 추가 |
| `watch_service_request_events` | outbox 이벤트를 cursor 기반으로 기다리고 읽기 |
| `send_notification` | 전체(all), 그룹(group), 개별 사용자(user)에게 공지 발행 |

상태 흐름은 `NEW → IN_PROGRESS → RESOLVED → CLOSED`입니다. `RESOLVED`는 검증/관찰 중 재작업을 위해 `IN_PROGRESS`로 되돌릴 수 있고, `CLOSED`는 최종 상태입니다.

## 준비 및 실행

필요한 환경은 Python 3.11 이상과 MySQL 8.x입니다. MySQL에 `demo` DB와 `nexweb` 사용자를 준비한 뒤:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

`.env`에서 `DB_PASSWORD`, `APP_HOST`, `APP_PORT`, `ITSM_API_TOKEN`, `ITSM_MCP_BEARER_TOKEN`, `ITSM_EVENT_MCP_BEARER_TOKEN`, `WXO_MCP_BEARER_TOKEN`을 설정하세요. `ITSM_EVENT_USER_TOKENS_JSON`, `ITSM_EVENT_USER_GROUPS_JSON`, `ITSM_EVENT_ADMIN_EMPLOYEE_NOS_JSON`은 빈 사용자 DB를 처음 채우는 bootstrap 입력이며, 기존 설치의 `SR_EVENT_*` 이름도 bootstrap 시 호환됩니다. 기본 FastAPI 주소는 `0.0.0.0:8000`, MySQL은 `127.0.0.1:3306`, DB `demo`, 사용자 `nexweb`입니다. 비밀번호와 사용자 token을 소스/저장소에 기록하지 마세요.

애플리케이션 시작 시 ORM이 서비스 요청/이벤트 테이블과 Bob 사용자 관리 테이블을 생성합니다. 기존 DB에는 `sql/005_create_bob_notification_management.sql`을 적용할 수도 있습니다. `demo`는 데이터베이스 이름으로 유지하고, 테이블 이름은 애플리케이션 도메인을 나타내도록 정리했습니다. 기존 데모 데이터를 보존하지 않고 새로 시작하려면 먼저 초기화 SQL을 실행하세요. 이 스크립트는 기존 `demo_*` 테이블과 신규 테이블을 모두 삭제합니다.

```bash
mysql -h 127.0.0.1 -P 3306 -u nexweb -p demo < sql/000_reset_itsm_tables.sql
mysql -h 127.0.0.1 -P 3306 -u nexweb -p demo < sql/001_create_itsm_service_requests.sql
mysql -h 127.0.0.1 -P 3306 -u nexweb -p demo < sql/002_seed_sample_service_requests.sql
mysql -h 127.0.0.1 -P 3306 -u nexweb -p demo < sql/003_create_itsm_event_outbox.sql
mysql -h 127.0.0.1 -P 3306 -u nexweb -p demo < sql/005_create_bob_notification_management.sql
```

`itsm_service_requests`에는 담당 직원 번호 컬럼이 신규 DDL에 포함되어 있으므로 새로 시작할 때 `004_add_assignee_employee_no.sql`은 실행하지 않아도 됩니다.

API:

```bash
python -m app.main
```

이 명령은 `.env`의 `APP_HOST`와 `APP_PORT`를 읽습니다. `uvicorn app.main:app` CLI로 직접 실행하는 경우에는 Uvicorn CLI에 host/port를 별도로 지정해야 합니다.

다른 터미널에서 ITSM MCP 서버:

```bash
python -m itsm_mcp.server
```

IBM Bob Notification MCP Server:

```bash
python -m itsm_event_mcp.server
```

Bob 사용자, token hash, 그룹, 멤버십, 공지 대상과 사용자별 읽음 상태는 `bob_user`, `bob_user_token`, `bob_group`, `bob_user_group`, `notification`, `notification_target`, `notification_receipt`에 저장합니다. 빈 DB의 첫 기동에서만 `ITSM_EVENT_USER_TOKENS_JSON`, `ITSM_EVENT_USER_GROUPS_JSON`, `ITSM_EVENT_ADMIN_EMPLOYEE_NOS_JSON`을 초기 데이터로 가져옵니다. 이 환경 설정은 이후 동기화되지 않으며, 초기 등록 후 관리자 화면에서 사용자를 추가하고 token을 발급/회수할 수 있습니다. token 원문은 발급 때 한 번만 보이고 DB에는 해시와 마지막 네 자리만 보관됩니다. 각 Bob 사용자는 본인 token을 확장 명령으로 SecretStorage에 저장합니다.

개발용 사용자·그룹·token 데이터는 [`docs/bob_notification_sample_data.md`](docs/bob_notification_sample_data.md)에 정리되어 있습니다. `sql/005_create_bob_notification_management.sql` 적용 후 `sql/006_seed_bob_notification_sample_data.sql`을 실행하면 `EMP1001`~`EMP1003`, `operations`/`payments`/`managers` 그룹과 데모 token이 등록됩니다.

관리자 권한이 있는 Bob에서 알림 작성 화면의 `Users & Groups`를 열어 사용자를 등록하고 그룹과 멤버십을 관리합니다. 그룹명은 소문자로 시작하며 소문자, 숫자, 점, 하이픈, 밑줄을 사용할 수 있습니다. 관리자 REST API는 `/service-request-events/admin/*` 아래에 있고 사용자 token 및 관리자 역할을 서버에서 검증합니다. 기존 `.env` 호환을 위해 `SR_EVENT_*` 별칭도 초기 bootstrap 중에 읽습니다. FastAPI의 SR 이벤트는 `assignee_employee_no`가 일치하는 사용자에게 전달됩니다. 공지 발행은 전체 `all`, 그룹 `group`, 개별 복수 선택 `user` scope와 MCP `send_notification` 도구를 지원합니다. 알림 읽음 상태는 사용자별 receipt로 저장됩니다. MCP endpoint에는 `ITSM_EVENT_MCP_BEARER_TOKEN`이 필요하고, Bob SSE `/events`는 직원별 token을 사용합니다. 확장 빌드/설치 절차는 [`bob_notifier/README.md`](bob_notifier/README.md)에 있습니다.

A2A WXO MCP 서버는 WXO A2A endpoint와 인증값을 `.env`에 넣은 뒤 실행합니다.

```bash
python -m a2a_wxo_mcp.server
```

REST 문서: `http://127.0.0.1:8000/docs`, DB 상태: `http://127.0.0.1:8000/health/db`, ITSM MCP: `http://127.0.0.1:8030/mcp`, A2A WXO MCP: `http://127.0.0.1:8031/mcp`, Notification MCP/SSE: `http://127.0.0.1:8032/mcp`, `http://127.0.0.1:8032/events`, 공지 발행 `POST http://127.0.0.1:8032/admin/messages`.

## API 예시

```bash
curl -H "Authorization: Bearer $ITSM_API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"title":"결제 API 간헐 오류","description":"production에서 결제 요청이 500으로 실패합니다. 발생 시각과 trace ID를 확인해 주세요.","service_name":"payments-api","environment":"production","severity":"HIGH","requester":"demo.user","assignee":"payments.oncall"}' \\
  http://127.0.0.1:8000/service-requests

curl -H "Authorization: Bearer $ITSM_API_TOKEN" \\
  http://127.0.0.1:8000/service-requests/SR-000001
```

실제 MySQL 연결/저장/재조회를 확인하려면 API가 동작하는 동안:

```bash
python -m scripts.smoke_test_api
```

Bob 팝업 end-to-end 테스트는 먼저 Bob에서 `IBM Bob Notifier: Start`를 실행해 둔 후 프로젝트 루트에서 실행합니다. 테스트 스크립트가 새 SR을 FastAPI에 등록하고 MySQL outbox의 `service_request.created` 이벤트까지 확인합니다. Bob 화면의 알림과 Output 채널도 함께 확인하세요.

```bash
python -m scripts.test_bob_popup --assignee-employee-no EMP1001
```

테스트 SR은 실제 MySQL에 저장됩니다. `--assignee-employee-no`에는 token map에 등록된 직원 번호를 넣으세요. 예: `python -m scripts.test_bob_popup --assignee-employee-no EMP1002 --title "SR 알림 검증" --service payments-api --severity HIGH`.


전체/그룹/개별 대상 테스트는 Notification MCP Server와 FastAPI를 실행한 상태에서 실행합니다. 테스트 스크립트는 `ITSM_API_TOKEN`으로 FastAPI의 `/service-request-events/notifications`에 공지를 등록하고, `.env`에 등록된 각 Bob 사용자의 token으로 SSE를 구독해 지정 대상만 수신하는지 확인합니다. `/admin/messages`는 Bob 관리자용으로 사용자 token과 관리자 권한을 요구하므로, 이 스크립트의 내부 API token과 혼용하지 않습니다.

각 테스트 공지에는 자료 링크 두 건이 포함됩니다. 스크립트는 대상 범위뿐 아니라 링크 제목과 URL이 Bob SSE 데이터까지 전달되는지도 확인합니다.

```bash
# 모든 등록 사용자
python -m scripts.test_notification_targets --target all

# operations 그룹 구성원만
python -m scripts.test_notification_targets --target group --group operations

# 개별 employee_no 한 명
python -m scripts.test_notification_targets --target user --employee-no EMP1001
```

테스트 공지는 실제 MySQL outbox와 Bob 팝업에 남습니다. 테스트 payload의 링크가 SSE까지 전달되는지도 확인합니다. 별도의 DDL 변경은 필요하지 않습니다. 기존 JSON payload outbox를 재사용합니다. group을 추가/수정하면 `ITSM_EVENT_USER_GROUPS_JSON`을 갱신하고 Notification MCP 프로세스를 재시작하세요. `all`은 등록된 전체 사용자 대상이며, 현재 연결된 Bob에는 즉시 전달되고 오프라인 사용자는 이벤트가 outbox에 보관된 동안 다시 연결하면 받을 수 있습니다.

자료가 포함된 공지는 `/admin/messages`에 `links` 배열을 함께 전달합니다. 각 원소는 `title`, `url` 필드이며 최대 10개 HTTP/HTTPS 링크를 허용합니다.

```json
{
  "target_type": "group",
  "target_group": "operations",
  "title": "배포 안내",
  "message": "배포 절차와 변경 내역을 확인하세요.",
  "links": [
    {"title": "운영 Runbook", "url": "https://docs.example.com/runbook"},
    {"title": "Release Notes", "url": "https://docs.example.com/releases/1.4"}
  ]
}
```

## CI/CD 발표 흐름

Jenkins pipeline: checkout → build/test → SonarQube scan/Quality Gate → staging deploy/smoke test → 수동 승인 → production deploy. Quality Gate 실패는 배포를 차단합니다. 배포 결과는 ITSM MCP의 `add_worklog`로 SR에 기록하고, 운영 관찰이 끝나면 담당자가 `CLOSED`로 전환합니다.

ContextForge에 등록할 URL은 Bob/Gateway가 접근 가능한 주소여야 합니다. 컨테이너/원격 실행 환경에서는 `127.0.0.1` 대신 접근 가능한 호스트 이름과 TLS를 사용하세요. 설치된 버전에 맞춰 인증과 권한을 설정합니다.

## 검증 및 제한

```bash
python -m compileall app itsm_mcp a2a_client a2a_wxo_mcp itsm_event_mcp scripts
python -m unittest tests.test_notification_routing tests.test_notification_links -v
```

이 데모는 Bob/Gateway/WXO tenant 및 agent, Jenkins/SonarQube를 설치하거나 생성하지 않습니다. FastAPI outbox, SSE endpoint, Bob 2.0.1용 팝업 확장 소스와 VSIX 빌드 절차를 제공합니다. Bob에서 VSIX를 실제 설치해 팝업이 표시되는지는 대상 PC에서 검증해야 합니다. MySQL 비밀번호 및 토큰을 설정한 실행 환경에서 실제 DB 연동을 확인하고, 운영 배포 전에는 조직 인증/승인, 감사, 비밀 관리, TLS와 네트워크 정책을 적용하세요.
