
## env active
```bash
orchestrate env activate nexweb-env
```

## 1) 커넥션 애플리케이션 등록 
app-id는 db.py의 MYSQL_APP_ID와 반드시 동일해야 함

```bash
orchestrate connections add -a mysql_hr_demo
```
## 2) 종류 설정: key_value, team(공유) 또는 member(개인별)

```bash
orchestrate connections configure -a mysql_hr_demo --env draft  --kind key_value --type team
```
## 3) 자격증명 입력

- draft
```bash
orchestrate connections set-credentials -a mysql_hr_demo --env draft \
  -e MYSQL_HOST=localhost \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=user01 \
  -e MYSQL_PASSWORD='abcd1234' \
  -e MYSQL_DATABASE=test
```

- live
```
orchestrate connections set-credentials -a mysql_hr_demo --env live \
  -e MYSQL_HOST=localhost \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=user01 \
  -e MYSQL_PASSWORD='abcd1234' \
  -e MYSQL_DATABASE=test
```

## 4. watsonx Orchestrate에 Tools 등록하기

```bash
orchestrate tools import -k python -f lab01/tools.py -p lab01  -r lab01/requirements.txt --app-id mysql_hr_demo
```

## 5. Agent 등록
- 최초 등록
```bash
orchestrate agents import -f agent.yaml
```

- 수정 후 반영 (agent.yaml을 고치고 동일한 명령을 다시 실행)
```bash
orchestrate agents import -f agent.yaml
```

# HR 휴가 관리 데모 (watsonx Orchestrate + MySQL)

Python 기반 watsonx Orchestrate 데모 툴 세트입니다. 데이터는 MySQL에서 조회/저장합니다.

| 기능 | 함수 | 설명 |
|---|---|---|
| 휴가 잔여일 조회 | `get_leave_balance(employee_id)` | 직원의 총/사용/잔여 연차를 MySQL에서 조회 |
| 휴가 conflict 조회 | `check_leave_conflict(employee_id, start_date, end_date)` | 본인 기존 휴가 및 같은 매니저를 둔 팀 동료의 승인된 휴가와 기간이 겹치는지 확인. 충돌 시 동일 기간의 비어있는 대체 날짜(최대 3개)도 함께 제안 |
| 내 신청 내역 조회 | `list_leave_requests(employee_id)` | 해당 직원이 신청한 모든 휴가 내역(Pending/Approved/Rejected)을 최신순으로 조회 |
| 승인현황 조회 | `get_approval_status(request_id="", employee_id="")` | request_id로 특정 신청 건의 승인현황을 정확히 조회하거나, request_id를 모르면 employee_id로 전체 현황을 조회 |
| 팀 전체 휴가 목록 조회 | `get_team_leave_requests(manager_id, include_past=False)` | 해당 매니저 밑의 모든 팀원의 휴가 신청 내역(직원명 포함)을 시작일 순으로 조회. 기본적으로 종료일이 지난(오늘 이전) 휴가는 제외되며, include_past=True로 지난 휴가도 포함 가능 |
| 휴가 신청 폼(캘린더) | `show_leave_request_form(employee_id)` | 시작일/종료일을 캘린더에서 선택하는 폼을 보여주고, 제출 시 자동으로 apply_leave 호출 |
| 휴가 신청 | `apply_leave(employee_id, start_date, end_date, reason="", confirm_despite_conflict=False)` | 충돌이 없으면 바로 Pending 접수. 충돌이 있으면 저장하지 않고 대체 날짜 후보와 함께 확인을 요청(requires_confirmation), 사용자가 동의하면 confirm_despite_conflict=True로 재호출해야 접수됨 |

## 파일 구조

```
hr_vacation_demo/
├── schema.sql        # MySQL 테이블 생성 + 시드 데이터
├── db.py              # MySQL 커넥션 풀 및 쿼리 함수
├── tools.py           # watsonx Orchestrate @tool 3종 (MySQL 연동, 실사용 버전)
├── main.py             # tools.py(MySQL)를 테스트하는 CLI
│
├── mock_data.py       # (참고용) 메모리 기반 모의 데이터
├── tools_mock.py       # (참고용) DB 없이 동작하는 오프라인 버전
├── main_mock.py         # tools_mock.py를 테스트하는 CLI
│
├── requirements.txt
└── README.md
```

DB 없이 빠르게 로직만 확인하고 싶다면 `python main_mock.py`를,
실제 MySQL 연동을 확인하려면 아래 절차대로 `python main.py`를 실행하세요.

## 1. MySQL 준비

MySQL 서버가 이미 떠 있다는 전제로, 스키마와 시드 데이터를 적재합니다.
**한글 데이터가 깨지지 않도록 반드시 `--default-character-set=utf8mb4` 옵션을 붙이세요.**

```bash
mysql -u root -p --default-character-set=utf8mb4 < schema.sql
```

이 스크립트는 `hr_vacation_demo` 데이터베이스와 `employees`, `vacation_requests`
두 테이블을 생성하고, 이전 데모와 동일한 샘플 데이터를 넣어줍니다.

전용 계정을 쓰고 싶다면:

```sql
CREATE USER 'hrdemo'@'localhost' IDENTIFIED BY '원하는_비밀번호';
GRANT ALL PRIVILEGES ON hr_vacation_demo.* TO 'hrdemo'@'localhost';
FLUSH PRIVILEGES;
```

## 2. 접속 정보 설정 (환경 변수)

```bash
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=hrdemo
export MYSQL_PASSWORD=원하는_비밀번호
export MYSQL_DATABASE=hr_vacation_demo
```

값을 지정하지 않으면 `localhost / 3306 / root / (빈 비밀번호) / hr_vacation_demo`가
기본값으로 사용됩니다.

## 3. 패키지 설치

```bash
pip install -r requirements.txt
```

`mysql-connector-python`(공식 드라이버)과 `ibm-watsonx-orchestrate` ADK가 설치됩니다.
ADK가 없어도 `tools.py`는 동작합니다(내부에서 `@tool` 데코레이터를 자동으로
no-op 처리하는 폴백 로직이 있습니다).

## 4. 로컬 테스트

```bash
python main.py
```

정상 조회, conflict 발생, 신청 성공, 잔여일 재조회, 존재하지 않는 직원,
잔여 연차 초과 신청 등 6가지 시나리오가 실제 MySQL 데이터를 대상으로 출력됩니다.
(이 저장소를 만들며 실제 MySQL 서버에 대해 위 시나리오를 모두 검증했습니다.)

## 5. watsonx Orchestrate Connections로 접속정보 관리하기 (권장)

환경 변수 대신 Orchestrate의 **Key-Value 커넥션**으로 MySQL 접속정보를
안전하게 관리할 수 있습니다. `db.py`는 이 커넥션을 우선 사용하고,
커넥션이 없으면(로컬 개발 시) 환경 변수로 자동 폴백합니다.

```bash
# 1) 커넥션 애플리케이션 등록 (app-id는 db.py의 MYSQL_APP_ID와 반드시 동일해야 함)
orchestrate connections add -a mysql_hr_demo

# 2) 종류 설정: key_value, team(공유) 또는 member(개인별)
orchestrate connections configure -a mysql_hr_demo --env draft --kind key_value --type team

# 3) 자격증명 입력 (비밀번호에 특수문자가 있으면 작따표로 감싸기)
orchestrate connections set-credentials -a mysql_hr_demo --env draft \
  -e MYSQL_HOST=localhost \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=user \
  -e MYSQL_PASSWORD='abcd1234!' \
  -e MYSQL_DATABASE=demo

# 4) 실제 배포(live) 환경에도 동일하게 설정 (draft와 독립적으로 관리됨)
orchestrate connections configure -a mysql_hr_demo --env live --kind key_value --type team
orchestrate connections set-credentials -a mysql_hr_demo --env live \
  -e MYSQL_HOST=localhost \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=user \
  -e MYSQL_PASSWORD='abcd1234!' \
  -e MYSQL_DATABASE=demo

# 5) 확인
orchestrate connections list
```

`tools.py`의 세 함수는 모두 `expected_credentials=[{"app_id": "mysql_hr_demo", "type": ConnectionType.KEY_VALUE}]`를
선언하고 있어서, 툴 임포트 시 이 커넥션이 자동으로 연결됩니다.
`db.py`는 내부적으로 `connections.key_value("mysql_hr_demo")`를 호출해
`{MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE}` 딕셔너리를 받아옵니다.

> app-id(`mysql_hr_demo`)를 바꾸고 싶다면 `db.py`의 `MYSQL_APP_ID` 상수도
> 반드시 함께 바꿔야 합니다. 두 값이 다르면 커넥션을 찾지 못합니다.

## 6. watsonx Orchestrate에 등록하기

```bash
orchestrate tools import -k python -f tools.py
```

`tools.py` 안의 `get_leave_balance`, `check_leave_conflict`, `apply_leave` 세 함수가
각각 독립된 툴로 등록됩니다. 함수의 docstring이 툴 설명(description)으로,
타입 힌트가 파라미터 스키마로 사용됩니다.

> **주의**: watsonx Orchestrate 실행 환경(서버/컨테이너)에서도 `MYSQL_HOST` 등
> 환경 변수를 동일하게 설정해야 `db.py`가 MySQL에 접속할 수 있습니다.
> Orchestrate 배포 방식(로컬/서버)에 맞는 환경 변수 설정 방법은 Orchestrate
> 문서의 "Connections" 또는 배포 설정을 참고하세요.

## 7. 에이전트 구성 예시

지시문(instruction) 예시:
> "직원이 휴가 관련 문의를 하면 먼저 get_leave_balance로 잔여일을 확인하고,
> 휴가 신청 요청 시에는 반드시 check_leave_conflict로 충돌 여부를 안내한 뒤
> 사용자가 진행을 원하면 apply_leave로 신청을 접수하세요.
> apply_leave가 requires_confirmation=true를 반환하면, 절대 그 자리에서
> confirm_despite_conflict=true로 바로 재시도하지 마세요. 먼저 conflicts와
> suggested_alternatives를 사용자에게 보여주고, 대체 날짜 중 하나를 쓸지
> 아니면 원래 날짜 그대로 진행할지 명시적으로 물어본 뒤, 사용자의 답변에
> 따라서만 다시 호출하세요.
> 신청이 실제로 반영됐는지, 또는 상태(Pending/Approved/Rejected)를 물어보면
> list_leave_requests로 실제 DB를 조회해서 답하고, 조회 없이 결과를 추측해서
> 말하지 마세요."

대화 예시:
- "제 휴가 며칠 남았어요?" → `get_leave_balance`
- "9월 16일부터 18일까지 휴가 써도 되나요?" → `check_leave_conflict`
- "11월 2일부터 4일까지 휴가 신청해줘" → `apply_leave` (충돌 없으면 바로 접수)
- "9월 16~18일 휴가 신청해줘" (충돌 있는 기간) → `apply_leave`가
  `requires_confirmation: true` 반환 → 에이전트가 대체 날짜를 제시하며
  "그대로 진행할까요, 아니면 다른 날짜로 하시겠어요?" 확인 → 사용자가
  "그냥 이 날짜로 할게요"라고 답하면 `apply_leave(..., confirm_despite_conflict=True)`로
  재호출, "그럼 19~21일로 할게요"라고 답하면 그 날짜로 (confirm 없이) 재호출
- "제가 신청한 휴가 상태 확인해줘" / "정말 반영됐어?" → `list_leave_requests`
- "우리 팀 휴가 일정 보여줘" / "팀원들 휴가 신청 현황 알려줘" → `get_team_leave_requests(manager_id="E010")`
- "V-1005 신청 아직 승인 안 됐어?" → `get_approval_status(request_id="V-1005")`
- "제 휴가 승인현황 전체 보여줘" → `get_approval_status(employee_id="E003")`
- "휴가 신청하고 싶어요" / "달력으로 날짜 고르고 싶어요" → `show_leave_request_form`
  (사용자가 폼을 채워 제출하면 자동으로 `apply_leave`가 호출됩니다)

## 8. 캘린더 신청 폼 (`show_leave_request_form`) 동작 방식

1. 사용자가 "휴가 신청할래요" 같은 요청을 하면 에이전트가 `show_leave_request_form(employee_id)`를 호출합니다.
2. watsonx Orchestrate 채팅 UI에 사번(사전 입력됨), **시작일/종료일 캘린더(DatePicker)**, 사유 입력란이 있는 폼이 표시됩니다.
3. 사용자가 폼을 채우고 "신청하기"를 누르면, 폼의 `on_event`가 자동으로
   `apply_leave`를 호출합니다 (`confirm_despite_conflict`는 넘기지 않으므로
   기본값 False가 적용됩니다).
4. `apply_leave`의 결과가 그대로 대화창에 표시됩니다.
   - 충돌이 없으면 바로 Pending으로 접수된 결과가 보입니다.
   - 충돌이 있으면 `requires_confirmation: true`와 함께 대체 날짜 후보가
     반환되고, 에이전트가 이어서 "그대로 진행할까요, 다른 날짜로
     하시겠어요?"라고 대화로 물어봅니다. 이후 흐름은 위 "대화 예시"와 동일합니다.

> **주의**: 이 폼 위젯은 watsonx Orchestrate 배포 환경에서만 실제로 렌더링됩니다.
> ADK가 없는 로컬 환경(`main.py`, `main_mock.py`)에서는 폼 대신 구성 내용을
> 요약한 딕셔너리를 반환하도록 폴백 처리되어 있습니다. 또한 `apply_leave`가
> 같은 에이전트에 함께 등록되어 있어야 폼 제출 시 정상적으로 연결됩니다.

## 9. 에이전트 정의를 YAML로 관리하기 (`agent.yaml`)

지금까지의 Instructions, Description, 사용 툴 목록을 웹 UI에 직접
타이핑하는 대신, `agent.yaml` 파일 하나로 버전 관리하고 배포할 수
있습니다.

```bash
# 최초 등록
orchestrate agents import -f agent.yaml

# 수정 후 반영 (agent.yaml을 고치고 동일한 명령을 다시 실행)
orchestrate agents import -f agent.yaml
```

`agent.yaml`의 주요 필드와 화면(Profile) 항목의 대응 관계:

| 화면 항목 | YAML 필드 |
|---|---|
| Agent name | `display_name` (내부 식별자는 `name`으로 별도 유지: `one_hr`) |
| Model | `llm` (예: `groq/openai/gpt-oss-120b`) |
| Description | `description` |
| Instructions | `instructions` (`agent_instructions.md`의 내용을 그대로 반영) |
| (툴 연결) | `tools` (사용하는 7개 툴 이름 목록) |

`instructions`와 `description`은 YAML의 리터럴 블록(`|`) 문법으로
여러 줄을 그대로 담고 있어서, 마크다운 헤더(`##`)나 줄바꿈이 그대로
유지됩니다. 향후 툴을 추가/변경하면 `tools` 목록과 `instructions`의
"원칙 4" 부분을 함께 갱신해주세요.

> Instructions 내용 자체는 `agent_instructions.md`와 동일합니다.
> 이제부터는 `agent_instructions.md`를 사람이 읽기 편한 원본으로 두고,
> 실제 배포는 `agent.yaml`을 통해 하는 방식을 권장합니다 — 두 파일의
> 내용이 어긋나지 않도록 함께 수정해주세요.

## 실제 운영 환경에 붙이려면

- `employees`, `vacation_requests` 테이블을 실제 HRIS의 스키마에 맞게 조정하거나,
  뷰(VIEW)를 만들어 `db.py`가 기대하는 컬럼명에 맞춰주면 코드 변경 없이 연결됩니다.
- `apply_leave`의 저장 로직을 실제 결재 워크플로 트리거(예: 별도 API 호출)로
  확장할 수 있습니다.
- 연결 정보(`MYSQL_PASSWORD` 등)는 평문 환경 변수 대신 Vault/Secrets Manager 등의
  비밀 관리 도구 사용을 권장합니다.

## 참고 사항 (데모 단순화 지점)

- 팀 충돌은 "같은 `manager_id`를 가진 동료"만 확인합니다 (부서 전체가 아님).
- 잔여일 계산 시 주말(토/일)은 제외하되, 공휴일은 반영하지 않습니다.
- 신청 후 상태는 항상 `Pending`으로 저장되며, 별도의 승인/반려 기능은 포함하지
  않았습니다 (필요 시 `approve_leave(request_id)` 같은 툴을 추가하면 됩니다).
- `db.py`는 커넥션 풀(`MySQLConnectionPool`)을 사용해 매 호출마다 재연결하지
  않도록 했습니다.
- `list_leave_requests`는 상태값을 그대로 반환할 뿐 승인/반려 로직은 없습니다.
  에이전트가 "승인됐다"처럼 단정적으로 말하지 않도록, 이 툴의 응답을 그대로
  전달하게끔 지시문에 명시하는 것을 권장합니다.
- 대체 날짜 제안(`suggested_alternatives`)은 요청 기간 다음날부터 최대 30일
  범위에서, 신청 기간과 **동일한 달력 일수**로 비어있는 구간을 순서대로 최대
  3개까지 찾습니다. 주말이 포함될 수 있고, 30일 안에 못 찾으면 빈 배열을
  반환합니다. 필요하면 `_suggest_alternative_dates`의 `search_window_days`,
  `max_suggestions` 값을 조정하세요.