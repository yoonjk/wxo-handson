# Purchase Approval FastAPI

watsonx Orchestrate의 구매 승인 플로우가 승인/반려 결과를 MySQL에 저장할 때 사용하는 API입니다.

## 구조

- `app/db/connection.py`: DB 연결과 세션 생성
- `app/repositories/purchase_repository.py`: SQL/DB 처리
- `app/services/purchase_service.py`: 상태 전이 업무 규칙
- `app/api/routes/purchases.py`: FastAPI 엔드포인트
- `sql/schema.sql`: MySQL 테이블 생성문

## 1. 테이블 생성

```bash
set -a
source .env
set +a
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p "$DB_NAME" < sql/schema.sql
```

## 2. 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env의 DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME을 실제 값으로 변경
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI 문서: `http://localhost:8000/openapi.json`
- 상태 확인: `http://localhost:8000/health`

`/docs`의 작업을 펼치면 한국어 요약·업무 설명, 경로 파라미터 설명, 요청 필드 제약과 예시, 성공/오류 응답 예시를 확인할 수 있습니다. Orchestrate Tool 등록 시 `/openapi.json`을 사용하세요.

## 3. 테스트용 구매 요청 생성

```bash
curl -X POST http://localhost:8000/api/purchase-requests \
  -H 'Content-Type: application/json' \
  -d '{
    "purchase_type": "IT_EQUIPMENT",
    "requester": "hong.gildong",
    "total_amount": 1500000,
    "reason": "개발용 노트북 구매"
  }'
```

응답의 `id`를 Orchestrate 플로우의 `request_id` 입력값으로 사용합니다.

## 4. 승인 결과 API 테스트

승인:

```bash
curl -X PATCH http://localhost:8000/api/purchase-requests/1/status \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "APPROVED",
    "comment": "예산 확인 완료",
    "approver_role": "IT_MANAGER"
  }'
```

반려할 때는 `status`를 `REJECTED`로 전달합니다.

## 5. watsonx Orchestrate Tool 등록

1. FastAPI를 Orchestrate에서 접근 가능한 **HTTPS 주소**로 배포합니다. 클라우드 Orchestrate는 `localhost`에 접근할 수 없습니다.
2. Orchestrate의 Tools에서 OpenAPI 문서 URL `https://<호스트>/openapi.json`을 가져옵니다.
3. operation ID가 `update_purchase_status`인 작업을 활성화합니다.
4. 승인 Branch에서 Call a tool을 추가하고 다음처럼 매핑합니다.

| Tool 입력 | 승인 경로 | 반려 경로 |
|---|---|---|
| `request_id` | 플로우 입력의 구매 요청 ID | 동일 |
| `status` | `APPROVED` | `REJECTED` |
| `comment` | `approval_comment` | `approval_comment` |
| `approver_role` | Decision 출력 `approver_role` | 동일 |

현재 API는 실습용으로 인증을 넣지 않았습니다. 외부 공개 배포 시 API Gateway 또는 애플리케이션 인증을 추가하세요.

## 6. Google A2A Agent로 watsonx Orchestrate에 등록

이 프로젝트에는 기존 MySQL 구매 서비스와 동일한 `PurchaseService`를 호출하는
A2A JSON-RPC endpoint가 포함되어 있습니다. 별도 데이터베이스 처리 로직을 만들지
않으므로 REST 호출과 A2A 호출이 같은 상태 전이 규칙과 트랜잭션을 사용합니다.

### Agent Card와 endpoint

```text
https://<호스트>/.well-known/agent-card.json
https://<호스트>/a2a
```

`PUBLIC_BASE_URL`은 Agent Card의 `url`을 생성하는 데 사용됩니다.

### A2A 구매 요청 생성

```bash
curl -X POST https://<호스트>/a2a \
  -H 'Content-Type: application/json' \
  -H 'X-A2A-API-Key: <A2A_API_KEY>' \
  -d '{
    "jsonrpc": "2.0",
    "id": "create-1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "message-1",
        "role": "user",
        "parts": [{
          "kind": "data",
          "data": {
            "purchase_type": "IT_EQUIPMENT",
            "requester": "hong.gildong",
            "total_amount": 1500000,
            "reason": "개발용 노트북 구매"
          }
        }]
      }
    }
  }'
```

### A2A 승인 결과 저장

생성 응답의 `artifacts[0].parts[0].data.id`를 사용해 다음 요청을 보냅니다.

```bash
curl -X POST https://<호스트>/a2a \
  -H 'Content-Type: application/json' \
  -H 'X-A2A-API-Key: <A2A_API_KEY>' \
  -d '{
    "jsonrpc": "2.0",
    "id": "approve-1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "message-2",
        "role": "user",
        "parts": [{
          "kind": "data",
          "data": {
            "request_id": 1,
            "approval": "APPROVED",
            "approval_comment": "예산 확인 완료",
            "approver_role": "IT_MANAGER"
          }
        }]
      }
    }
  }'
```

`approval`은 `APPROVED` 또는 `REJECTED`만 허용되며, `request_id` 없이 보내면
새 구매 요청을 생성합니다. `tasks/get`은 A2A task 결과를 조회하고, 실제 구매
상태는 MySQL의 `purchase_requests`에서 조회합니다.

### 환경 변수

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=test
DB_PASSWORD=<환경변수로 주입>
DB_NAME=demo
PUBLIC_BASE_URL=https://<공개 HTTPS 주소>
A2A_API_KEY=<강력한 임의의 비밀값>
AUTO_CREATE_TABLES=false
```

비밀번호는 `.env` 파일을 Git에 커밋하지 마세요. 운영에서는 Secret Manager 또는
컨테이너 환경변수로 주입해야 합니다.
