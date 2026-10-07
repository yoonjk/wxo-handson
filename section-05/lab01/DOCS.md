# Factorial MCP Server — 문서

**위치:** `~/project/python/wxo-handson/section-05/lab01`  
**런타임:** Python 3.12 · FastMCP 4.x · MCP 2.x  
**Virtual environment:** `~/project/python/wxo-handson/.venv`

---

## 개요

이 lab은 **FastMCP**를 사용하여 최소한의 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server를 구현합니다. server는 임의의 음수가 아닌 정수에 대해 factorial 값과 자릿수를 계산하는 두 가지 수학 tool을 제공합니다.

---

## 프로젝트 구조

```
section-05/lab01/
├── server.py        # MCP server + tool 정의
├── test_server.py   # pytest 단위 테스트 스위트 (25개 테스트)
└── DOCS.md          # 이 문서
```

---

## 설정

### 1. Virtual environment 활성화

```bash
source ~/project/python/wxo-handson/.venv/bin/activate
```

### 2. 의존성 설치 (최초 1회)

```bash
pip install fastmcp pytest
```

---

## Server 실행

```bash
cd ~/project/python/wxo-handson/section-05/lab01
python server.py
```

Server는 기본 MCP transport 방식인 stdio mode로 시작되며, MCP 호환 client의 tool 호출을 수신할 준비가 됩니다.

---

## Tool

### `factorial_value(n: int) → str`

`n!`의 **정확한 10진수 값**을 string으로 반환합니다.

| Parameter | 타입 | 설명 |
|-----------|------|------|
| `n` | `int` | 음수가 아닌 정수 |

**반환값:** `n!`의 정확한 값을 10진수 string으로 반환합니다.

**예시:**

```python
factorial_value(10)   # → "3628800"
factorial_value(100)  # → "933262154439441526816992388562667..."  (158자리)
```

**오류:** `n < 0`이면 `ValueError`를 발생시킵니다.

---

### `factorial_digits(n: int) → int`

`n!`의 **10진수 자릿수**를 반환합니다.

`n!`이 너무 커서 전체를 표시할 수 없을 때 유용합니다. 예를 들어 `1000!`은 2,568자리입니다.

| Parameter | 타입 | 설명 |
|-----------|------|------|
| `n` | `int` | 음수가 아닌 정수 |

**반환값:** `n!`의 자릿수를 integer로 반환합니다.

**예시:**

```python
factorial_digits(5)    # → 3        (5! = 120)
factorial_digits(10)   # → 7        (10! = 3628800)
factorial_digits(100)  # → 158
```

**오류:** `n < 0`이면 `ValueError`를 발생시킵니다.

---

## 내부 Helper

### `_compute_factorial(n: int) → int`

두 tool이 공유하는 private helper 함수로, `n!`을 계산합니다.  
`n ≥ 0`인지 검증한 후 `math.factorial(n)`에 위임합니다.  
이를 통해 유효성 검사 및 계산 로직의 코드 중복을 방지합니다.

---

## 아키텍처

```
┌─────────────────────────────────────┐
│         FastMCP Server              │
│   name: "Factorial MCP Server"      │
│                                     │
│  ┌──────────────┐  ┌─────────────┐  │
│  │factorial_    │  │factorial_   │  │
│  │value()       │  │digits()     │  │
│  └──────┬───────┘  └──────┬──────┘  │
│         │                 │         │
│         └────────┬────────┘         │
│                  │                  │
│      ┌───────────▼──────────┐       │
│      │  _compute_factorial  │       │
│      │  (공유 helper 함수)   │       │
│      └───────────┬──────────┘       │
│                  │                  │
│          math.factorial(n)          │
└─────────────────────────────────────┘
```

---

## 테스트 실행

```bash
cd ~/project/python/wxo-handson/section-05/lab01
python -m pytest test_server.py -v
```

### 테스트 범위

| Test class | 테스트 수 | 검증 내용 |
|---|---|---|
| `TestComputeFactorial` | 7 | Helper 정확성, 음수 입력 시 `ValueError` 발생 확인 |
| `TestFactorialValue` | 7 | 반환 타입 (`str`), 경계값 (0, 1, 5, 10, 100), 오류 전파 |
| `TestFactorialDigits` | 8 | 반환 타입 (`int`), 경계값 (0, 1, 5, 10, 100), `factorial_value`와 일관성 |
| `TestMCPServerRegistration` | 3 | Server 이름, 두 tool 등록 여부, tool 개수 = 2 |
| **합계** | **25** | **모두 통과 ✓** |

---

## 발견 및 수정된 문제

| 파일 | 문제 | 수정 내용 |
|---|---|---|
| `server.py` | `FastMCP(description=...)` — v4에서 해당 kwarg 제거됨 | `instructions=`으로 교체 |
| `test_server.py` | `mcp._tool_manager.list_tools()` — v4에서 private API 제거됨 | `asyncio.run(mcp.list_tools())`으로 교체 |
