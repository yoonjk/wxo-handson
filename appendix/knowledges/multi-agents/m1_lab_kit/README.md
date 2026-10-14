# watsonx Orchestrate Module 1 실습 키트

가상 회사 **한빛솔루션**의 HR 도우미 에이전트를 만드는 데 필요한 샘플 자료입니다. 단계별 진행은 "Module 1 기본과정 Step-by-step Lab" 문서를 따릅니다.

| 폴더/파일 | 내용 | 사용 Lab |
| --- | --- | --- |
| `data/hr_policy_leave.pdf` | 휴가 규정 (연차·반차·이월·경조휴가·병가) | Lab 3 |
| `data/hr_policy_parental.pdf` | 육아휴직 및 모성보호 규정 | Lab 3 |
| `data/hr_policy_expense.pdf` | 출장 및 경비 정산 규정 | Lab 3 |
| `api/mock_hr_api.yaml` | Mock HR API OpenAPI 3.0 스펙 (연차 조회, 프로필, 휴가 신청) | Lab 4 |
| `api/mock_server/` | Mock HR API 서버 (FastAPI) + Dockerfile + 직원 10명 데이터 | Lab 0 (강사) |
| `prompts/` | 에이전트 설명·Instructions·지식/도구 설명 복사용 텍스트 | Lab 2–4 |
| `webchat/index.html` | 웹챗 임베드 테스트 페이지 | Lab 5 |
| `worksheets/lab5_test_record.csv` | 테스트 질문 10개와 기대 동작 기록표 | Lab 3, 5 |
| `instructor/pdf_source/` | 규정 PDF 원본(HTML 생성 코드) | 강사용 |

## Mock API 빠른 실행 (강사)

```bash
cd api/mock_server
pip install -r requirements.txt
MOCK_API_KEY=wxo-lab-2026 uvicorn app:app --host 0.0.0.0 --port 8080
# 확인
curl -H "X-API-Key: wxo-lab-2026" http://localhost:8080/employees/E1001/leave-balance
```

watsonx Orchestrate(SaaS)가 호출하려면 **공개 HTTPS 주소**가 필요합니다. IBM Cloud Code Engine 등에 컨테이너로 배포하거나, 터널(cloudflared/ngrok)로 노출한 뒤 `api/mock_hr_api.yaml`의 `servers.url`을 그 주소로 바꿔서 수강생에게 배포하세요.

기본 API Key `wxo-lab-2026`은 실습용입니다. 공개 주소로 띄울 때는 `MOCK_API_KEY`를 바꾸고 교육이 끝나면 서버를 내리세요.

> 규정·직원 데이터는 모두 교육용 가상 데이터입니다.
