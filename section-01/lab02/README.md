# HR 휴가 관리 Python Toolkit

첨부된 휴가 관리 Python tool을 watsonx Orchestrate **Python toolkit** 형식으로 옮긴 예제입니다. DB 연결, 직원·휴가 조회, 충돌 확인, 신청 처리를 하나의 toolkit 패키지로 배포합니다.

## 구성 파일

- `tools.py`: Orchestrate에 노출할 7개 tool과 휴가 업무 규칙
- `db.py`: MySQL 연결 풀 및 조회·저장 로직
- `schema.sql`: `demo` DB의 테이블과 샘플 데이터
- `requirements.txt`: toolkit 실행에 필요한 MySQL Connector
- `smoke_test.py`: 로컬 DB 연결 후 주요 tool 함수를 확인하는 예제

## 도구 이름

Toolkit으로 가져오면 에이전트 설정 및 기존 tool 참조에서 아래의 새 이름을 사용합니다.

| 기존 함수 이름 | Toolkit tool 이름 |
|---|---|
| `get_leave_balance` | `hr_leave_toolkit:get_leave_balance` |
| `check_leave_conflict` | `hr_leave_toolkit:check_leave_conflict` |
| `list_leave_requests` | `hr_leave_toolkit:list_leave_requests` |
| `get_approval_status` | `hr_leave_toolkit:get_approval_status` |
| `get_team_leave_requests` | `hr_leave_toolkit:get_team_leave_requests` |
| `apply_leave` | `hr_leave_toolkit:apply_leave` |
| `show_leave_request_form` | `hr_leave_toolkit:show_leave_request_form` |

기존 standalone tool을 참조하는 agent 설정이 있다면 tool 이름을 변경하고 agent를 다시 가져와야 합니다.

## 1. 데이터베이스 준비

`schema.sql`은 샘플 데이터 재생성을 위해 기존 `vacation_requests`, `employees` 테이블을 삭제한 뒤 생성합니다. 기존 DB에 업무 데이터가 있다면 먼저 백업하고, 이 스크립트를 그대로 재실행하지 마세요.

```bash
mysql -h <MYSQL_HOST> -P <MYSQL_PORT> -u <MYSQL_USER> -p < schema.sql
```

SQL 스크립트는 `demo` 데이터베이스를 사용합니다. `db.py`의 기본 데이터베이스 이름도 `demo`로 맞췄습니다.

## 2. Orchestrate 연결 등록

DB 접속정보를 toolkit 소스나 YAML에 평문으로 넣지 말고 key-value connection의 자격 증명으로 등록합니다. `mysql_hr_demo`의 키 이름은 다음과 같이 설정합니다.

```text
MYSQL_HOST      MySQL 서버 호스트명 또는 IP
MYSQL_PORT      MySQL 포트 (예: 3306 또는 노출된 포트)
MYSQL_USER      MySQL 사용자
MYSQL_PASSWORD  MySQL 비밀번호
MYSQL_DATABASE  demo
```

ADK CLI에서 connection을 만들고, draft와 live 각 환경에 key-value 자격 증명을 구성합니다. ADK 버전에 따라 `connections configure` / `connections set-credentials` 명령 사용법이 달라질 수 있으므로 `orchestrate connections --help`로 현재 설치 버전의 옵션을 확인하세요.

## 3. Python toolkit 가져오기

ADK CLI가 설치·인증되어 있고 현재 환경이 draft인지 확인합니다. toolkit 루트 폴더에서 실행합니다.

```bash
orchestrate env list
orchestrate env activate draft
orchestrate toolkits add \
  --kind python \
  --name hr_leave_toolkit \
  --description "HR 휴가 잔여일, 휴가 일정 충돌, 신청 및 승인현황 관리" \
  --package-root . \
  --tier small \
  --app-id mysql_hr_demo
```

- live
```bash
orchestrate connections configure \
  --app-id mysql_hr_demo --env live --kind key_value --type team
```

`--tier small`은 Python toolkit 전용 실행 tier가 계정에서 활성화되어 있어야 사용할 수 있습니다. IBM ADK 문서상 tier는 Python toolkit에 필요하며 플랜별로 제공 여부가 다를 수 있습니다. 명령 옵션이 설치된 ADK와 다르면 `orchestrate toolkits add --help` 결과를 따르세요.

Toolkit은 공용 프로세스에서 실행되므로 MySQL 연결 풀을 사용하고, 풀 최초 생성은 lock으로 보호합니다. 휴가 신청 저장은 DB named lock과 트랜잭션으로 처리해 동시 호출에서 요청 ID 중복과 연차 초과 차감을 방지합니다.

## 4. 가져오기 확인 및 agent 연결

```bash
orchestrate tools list
```

agent 설정 파일의 tool 이름을 `hr_leave_toolkit:<함수명>` 형식으로 바꿉니다. 예를 들면:

```yaml
tools:
  - hr_leave_toolkit:get_leave_balance
  - hr_leave_toolkit:check_leave_conflict
  - hr_leave_toolkit:apply_leave
```

이후 agent를 draft에서 가져와 각 조회 및 신청 시나리오를 확인하고, 승인된 절차에 따라 live에 배포합니다. Toolkit을 갱신한 경우 toolkit을 사용하는 agent도 재배포해야 합니다.

## 5. 로컬 테스트

테스트 환경에 의존성을 설치하고 DB 환경 변수를 설정한 뒤 실행합니다. 샘플 신청 tool은 DB 데이터를 변경하므로 개발용 데이터베이스에서만 사용하세요.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export MYSQL_HOST=<MYSQL_HOST>
export MYSQL_PORT=<MYSQL_PORT>
export MYSQL_USER=<MYSQL_USER>
export MYSQL_PASSWORD='<MYSQL_PASSWORD>'
export MYSQL_DATABASE=demo
python smoke_test.py
```

`smoke_test.py`에서 tool의 입력 날짜와 사번을 조정할 수 있습니다. 반복 실행 시 신청 row와 사용 연차가 누적됩니다.

## 적용 및 확인한 변경

1. 기존 7개 `@tool` 함수를 toolkit 패키지로 묶었습니다.
2. MySQL DB 기본 이름을 제공된 `schema.sql`과 일치하는 `demo`로 맞췄습니다.
3. toolkit worker 간 공유되는 DB pool의 최초 생성에 thread lock을 적용했습니다.
4. 신청 저장 시 MySQL named lock과 트랜잭션을 사용해 ID 발급, 잔여 연차 재검증, 신청 저장, 연차 차감을 함께 처리합니다.
5. 달력 폼 제출 이벤트가 toolkit 내부의 `hr_leave_toolkit:apply_leave`를 호출하도록 변경했습니다.
