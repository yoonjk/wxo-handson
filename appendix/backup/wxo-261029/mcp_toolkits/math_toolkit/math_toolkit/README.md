# section-05/lab02 — Python Tool & Python Toolkit + Agent

## 개요

이 lab에서는 watsonx Orchestrate의 두 가지 Python 기반 Tool 등록 방식을 실습합니다.

| 방식 | 명령 | 실행 방식 | 특징 |
|---|---|---|---|
| **Python Tool** | `orchestrate tools import --kind python` | 호출마다 subprocess 생성 (cold) | 단일 함수, 간단한 등록 |
| **MCP Toolkit** | `orchestrate toolkits add --kind mcp` | 상주 프로세스 (warm) | 복수 함수, MCP 프로토콜, TechZone 지원 |

---

## 파일 구조

```
section-05/lab02/
├── unit_convert.py          # Python Tool — 단위 변환 (km↔mile, kg↔lb, °C↔°F)
├── math_server.py           # MCP Toolkit server — square_root, power
├── math_toolkit/
│   ├── __init__.py
│   └── tools.py             # @tool 데코레이터 함수 (단위 테스트용)
├── requirements.txt         # mcp==2.3.0
├── math_agent.yaml          # Agent 정의
├── test_lab02.py            # pytest 단위 테스트 (29개)
├── deploy.sh                # 전체 등록 스크립트
└── README.md
```

---

## Step 1. 가상환경 활성화 및 인증

```bash
cd ~/project/python/wxo-handson
source .venv/bin/activate
orchestrate env activate nexweb-env0925
```

---

## Step 2. 단위 테스트 실행

```bash
cd section-05/lab02
pytest test_lab02.py -v
# 29 passed
```

---

## Step 3. 등록 (개별 명령)

### Python Tool — `unit_convert`

```bash
orchestrate tools import \
  --kind python \
  --file section-05/lab02/unit_convert.py \
  --requirements-file section-05/lab02/requirements.txt
```

- 파일 하나(`unit_convert.py`)를 업로드
- 함수 `unit_convert` 가 Tool 1개로 등록됨
- 호출마다 새 subprocess 생성 (stateless)

### MCP Toolkit — `math_toolkit`

```bash
cd section-05/lab02

orchestrate toolkits add \
  --kind mcp \
  --name math_toolkit \
  --description "Math toolkit with square_root and power functions." \
  --package-root "$(pwd)" \
  --command '["python3", "math_server.py"]' \
  --tools "square_root,power"
```


- `section-05/lab02/` 디렉토리 전체가 zip으로 업로드됨
- `square_root`, `power` 두 함수가 Tool 2개로 등록됨
- `--kind mcp` : TechZone/Trial 환경에서도 사용 가능 (`--kind python --tier`는 Premium 전용)
- `math_server.py` 가 상주 프로세스로 기동되어 MCP stdio 프로토콜로 요청 처리

### Agent — `math_agent`

```bash
orchestrate agents import \
  --file section-05/lab02/math_agent.yaml
```

---

## Step 4. 일괄 등록 (스크립트)

```bash
bash section-05/lab02/deploy.sh
```

---

## 실행 방식 비교

```
Python Tool (unit_convert) — cold start:
  호출 → subprocess 생성 → unit_convert.py 실행 → 반환 → 프로세스 종료
  호출 → subprocess 생성 → unit_convert.py 실행 → 반환 → 프로세스 종료

MCP Toolkit (math_toolkit) — warm:
  등록 → math_server.py 프로세스 기동 → MCP stdio 대기
  호출 → MCP 메시지 전송 → 즉시 반환
  호출 → MCP 메시지 전송 → 즉시 반환
```

---

## 테스트 대화 예시

```
사용자: 100km는 몇 마일이에요?
Agent : unit_convert(100, "km", "mile") → "100 km = 62.1371 mile"

사용자: 2의 10승은?
Agent : power(2, 10) → "2^10 = 1024.0"

사용자: 144의 제곱근은?
Agent : square_root(144) → "√144 = 12.0"
```
