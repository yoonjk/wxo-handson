# 구매 승인 판정 Knowledge Agent 실습 패키지

watsonx Orchestrate 에이전트가 Custom service 지식 기반으로 구매 승인 규정을 검색하도록 구성하는 실습용 파일입니다. 단계별 절차는 실습 가이드 문서를 따르세요.

```
Orchestrate agent --(Basic Auth)--> nginx :3464 --> FastAPI :8070 --> data/*.md 검색
```

## 구성

| 경로 | 내용 |
| --- | --- |
| `simple_service/server.py` | FastAPI 검색 서버 (Basic / API key 인증, 요청 로그, 키워드 검색) |
| `data/purchase_approval_policy.md` | 가상의 구매 승인 규정 샘플 (실습용, 실제 규정 아님) |
| `.env.example` | 서버 설정 예시 (`.env`로 복사해 사용) |
| `nginx/custom-service.conf` | nginx 리버스 프록시 설정 (http 블록용) |
| `orchestrate/purchase_knowledge_basic.yaml` | ADK 지식 기반 정의 |
| `orchestrate/cli_commands.sh` | ADK CLI 참고 명령 |
| `scripts/test_search.sh` | 연결 확인과 검색을 curl로 점검 |
| `requirements.txt` | Python 패키지 |

## 빠른 시작

```bash
cd procurement-kb-lab
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # AUTH_PASSWORD를 임의 값으로 바꾸기
python -m simple_service.server # 다른 터미널에서: scripts/test_search.sh
```

## 서버 동작

- `POST /` 또는 `POST /query`: `{"query", "filter", "metadata"}`를 받아 `{"search_results": [...]}`를 돌려줍니다.
- `HEAD /`, `GET /`: Orchestrate가 연결을 저장할 때 보내는 확인 요청에 인증 결과로 응답합니다(200 또는 401).
- `GET /health`: 인증 없이 서버가 살아 있는지 확인합니다.
- 검색: `data/*.md`를 `## ` 제목 단위로 나누고, 질문과 겹치는 글자 쌍(bigram)이 많은 조항부터 최대 `SEARCH_TOP_K`개를 돌려줍니다. 점수가 `SEARCH_MIN_SCORE`보다 낮으면 버립니다. 규정이 한국어라 영어 질문은 결과가 없을 수 있습니다.
- 로그: 모든 요청을 `[REQ]`, `[AUTH]`, `[SEARCH]`, `[RES]` 줄로 콘솔과 `simple_service/custom_service.log`에 남깁니다.

## 규정 바꾸기

`data/` 폴더의 Markdown 파일을 고치거나 추가하고 서버를 재시작하면 됩니다. 한 조항은 `## 제목` 한 개입니다.

## 알려진 제약

- Orchestrate의 API Key 지식 연결은 검색 단계에서 `KeyError: 'apikey'`로 실패합니다(서버를 호출하지 않음). Basic Auth를 쓰세요.
- 지식 기반에 쓰인 연결은 인증 방식을 바꾸거나 삭제할 수 없습니다. 새 연결을 만드세요.
