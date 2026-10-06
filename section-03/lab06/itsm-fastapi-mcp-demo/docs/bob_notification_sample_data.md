# Bob 사용자·그룹·token 예제 데이터

`sql/005_create_bob_notification_management.sql`로 테이블을 만든 뒤 `sql/006_seed_bob_notification_sample_data.sql`을 실행하세요. FastAPI 시작 시 테이블이 자동 생성되는 개발 환경이라면 FastAPI를 먼저 시작해도 됩니다.

## 샘플 계정

| Employee no. | 권한 | 그룹 |
|---|---|---|
| `EMP1001` | 알림 관리자 | `operations`, `managers` |
| `EMP1002` | 일반 사용자 | `operations` |
| `EMP1003` | 일반 사용자 | `payments` |

## 최초 관리자 지정 위치

새 DB를 처음 시작할 때 프로젝트 루트의 `.env`에 지정합니다. 관리자 employee no.는 `ITSM_EVENT_USER_TOKENS_JSON`에도 있어야 실제 Bob 사용자로 등록됩니다.

```dotenv
ITSM_EVENT_USER_TOKENS_JSON={"EMP1001":"<EMP1001용 token>"}
ITSM_EVENT_USER_GROUPS_JSON={"EMP1001":["operations","managers"]}
ITSM_EVENT_ADMIN_EMPLOYEE_NOS_JSON=["EMP1001"]
```

이 설정은 Bob 사용자 테이블이 비어 있을 때 FastAPI가 처음 시작하면서 한 번만 가져옵니다. 이 최초 관리자의 Bob에서 token을 SecretStorage에 등록한 뒤 **Users & Groups**를 열어 다른 사용자를 등록하고 관리자를 추가로 지정하면 됩니다. 이 문서의 샘플 seed SQL을 실행하면 `EMP1001`이 활성 관리자이므로 `.env`에 최초 관리자 목록을 따로 지정할 필요가 없습니다.

DB가 이미 초기화되어 환경 설정이 반영되지 않는다면 `.env`를 바꿔도 기존 데이터는 갱신되지 않습니다. 기존 활성 사용자를 최초 관리자로 지정하려면 DB에서 다음을 실행하세요. 해당 사용자의 유효한 token도 있어야 관리자 화면에 로그인할 수 있습니다.

```sql
UPDATE bob_user
SET is_admin = TRUE, status = 'active'
WHERE employee_no = 'EMP1001';
```

## Bob SecretStorage에 등록할 데모 token

각 Bob에서 **IBM Bob Notifier: Set Bearer Token** 명령을 실행하고, 해당 직원 번호의 token을 입력하세요. `Bearer ` 접두사는 붙이지 않습니다. DB에는 token 원문 대신 SHA-256 해시와 마지막 네 자리만 저장됩니다.

| Employee no. | 데모 token |
|---|---|
| `EMP1001` | `IOipLm-1puL5vI00ftUZyIc5nWiQ50oK9hl9usyKm8I` |
| `EMP1002` | `AZtVXrc42DNBh8FB85IIeWXuQnUvNRbNPo6UavmbHJA` |
| `EMP1003` | `izheRPMRZ2izv6Ni-oD99tG7PfOWl7z53US0Bmo4Vw8` |

> 이 token들은 예제 환경 전용입니다. 운영 환경에서는 관리자 화면에서 token을 재발급하고, 각 사용자에게 안전한 별도 token을 배포하세요. seed SQL 재실행 시 세 개의 샘플 token이 다시 활성화됩니다.

## 새 token 생성 방법

가장 간단한 방법은 관리자 화면에서 발급하는 것입니다. `Users & Groups` → **Register user**를 선택하면 token이 생성되어 한 번 표시됩니다. 기존 사용자는 **Issue token**으로 재발급할 수 있습니다. 발급 직후 token을 복사해 해당 사용자의 Bob에서 **IBM Bob Notifier: Set Bearer Token** 명령으로 SecretStorage에 저장하세요. 재발급하면 이전 token은 즉시 사용할 수 없습니다.

빈 사용자 DB를 처음 bootstrap할 때 token을 직접 만들려면 Python의 `secrets` 모듈을 사용합니다. 아래 명령은 employee no.별 암호학적으로 안전한 token을 생성합니다.

```bash
python3 - <<'PY'
import secrets

for employee_no in ("EMP1001", "EMP1002", "EMP1003"):
    print(f"{employee_no}={secrets.token_urlsafe(32)}")
PY
```

출력된 값을 `.env`의 `ITSM_EVENT_USER_TOKENS_JSON`에 JSON object로 넣고, 그룹과 관리자 목록도 설정한 뒤 사용자 테이블이 비어 있는 상태에서 FastAPI를 처음 시작하세요. 예를 들면 다음 형태입니다.

```dotenv
ITSM_EVENT_USER_TOKENS_JSON={"EMP1001":"<생성한 EMP1001 token>","EMP1002":"<생성한 EMP1002 token>","EMP1003":"<생성한 EMP1003 token>"}
ITSM_EVENT_USER_GROUPS_JSON={"EMP1001":["operations","managers"],"EMP1002":["operations"],"EMP1003":["payments"]}
ITSM_EVENT_ADMIN_EMPLOYEE_NOS_JSON=["EMP1001"]
```

최초 bootstrap 시 서버가 token 원문을 SHA-256으로 변환해 DB에 저장하므로, 각 Bob의 SecretStorage에는 생성했던 원문 token을 넣으면 됩니다. bootstrap이 끝난 뒤에는 `.env`를 token 보관용으로 사용하지 말고 관리자 화면으로 발급·회수하세요. `sql/006_seed_bob_notification_sample_data.sql`을 쓰는 경우에는 문서 위쪽의 고정 데모 token을 사용합니다. SQL의 token hash와 원문이 서로 연결되어 있으므로, token을 바꾸려면 관리자 화면에서 재발급하는 편이 안전합니다.

## 검증 예시

- `EMP1001`은 `operations`, `managers` 그룹의 관리자입니다.
- `EMP1002`는 일반 사용자이며 `operations` 그룹에 속합니다.
- `EMP1003`은 일반 사용자이며 `payments` 그룹에 속합니다.
- 관리자 Bob에서 `Users & Groups`를 열어 멤버십과 token 상태를 확인할 수 있습니다.
