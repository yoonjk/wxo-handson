# watsonx Orchestrate AI Assistant Lab 가이드

Oct 10, 2026 · @Jaeguk Yun

## 랩 개요

이 랩을 마치면 사내 규정 문서로 질문에 답하고, 도구로 업무를 처리하며, 다른 에이전트에게 일을 넘기는 **사내 헬프데스크 AI 어시스턴트**를 watsonx Orchestrate에서 직접 만들고 배포할 수 있습니다.

| 항목 | 내용 |
| --- | --- |
| 대상 | watsonx Orchestrate를 처음 쓰는 개발자, 아키텍트, 업무 담당자 |
| 소요 시간 | 약 3시간 (Lab 1–5 기준, 선택 Lab 6 별도 약 40분) |
| 진행 방식 | 웹 UI(Agent Builder) 중심, 선택 실습은 ADK(CLI) |
| 최종 결과물 | 웹 채팅에서 동작하는 "사내 헬프데스크 어시스턴트" |

**실습 시나리오:** 임직원이 "연차는 며칠 남았나요?", "재택근무 규정 알려줘", "노트북 고장 신고해줘"라고 묻습니다. 어시스턴트는 규정 문서에서 답을 찾고(지식), 시스템을 호출해 처리하며(도구), IT 문의는 IT 전담 에이전트에게 넘깁니다(협업).

| Lab | 주제 | 시간 |
| --- | --- | --- |
| Lab 1 | 첫 에이전트 만들기 | 30분 |
| Lab 2 | 지식(Knowledge) 추가 | 30분 |
| Lab 3 | 도구(Tool) 추가 | 40분 |
| Lab 4 | 멀티 에이전트 협업 | 30분 |
| Lab 5 | 테스트·배포·채널 연결 | 30분 |
| Lab 6 (선택) | ADK로 코드 기반 에이전트 | 40분 |

## 사전 준비

실습 전에 watsonx Orchestrate 인스턴스에 **Builder 또는 Admin 권한**으로 접속할 수 있어야 합니다. 협업 에이전트 구성은 이 권한이 있어야 가능합니다.

- [ ] IBMid 발급 및 IBM Cloud(또는 AWS Marketplace) 계정 준비
- [ ] watsonx Orchestrate 체험판 또는 사내 인스턴스 생성 후 콘솔 접속 확인
- [ ] 본인 계정이 Builder 또는 Admin 역할인지 확인
- [ ] 실습용 샘플 문서 준비: `휴가규정.pdf`, `재택근무가이드.docx`, `IT_FAQ.pdf` (사내 문서가 없으면 각 1–2쪽 분량으로 직접 작성)
- [ ] (Lab 3) 테스트용 REST API의 OpenAPI 명세 파일 1개 (예: 휴가 잔여일 조회 API). 없으면 Lab 6의 Python 도구로 대체
- [ ] (Lab 6, 선택) Python 3.11 이상, 터미널, `pip install ibm-watsonx-orchestrate`

> 강사 팁: 수강생이 많으면 샘플 문서와 OpenAPI 파일을 하나의 zip으로 미리 배포하면 Lab 2–3 대기 시간이 크게 줄어듭니다.

## 핵심 개념

watsonx Orchestrate의 에이전트는 LLM과 지침 위에 **지식, 도구, 협업 에이전트**를 붙여 만들고, 채널을 통해 사용자에게 내보냅니다. 이 랩은 아래 구성을 Lab 1부터 하나씩 쌓아 올립니다.

&#91;embedded content: 실습 어시스턴트 구성 · 에이전트 1개, 구성 요소 3개, 채널\]

| 구성 요소 | 하는 일 | 화면 위치 |
| --- | --- | --- |
| Behavior(지침) | 말투, 답변 범위, 도구·협업 에이전트 사용 규칙 | Behavior → Instructions |
| 지식(Knowledge) | 업로드 문서나 벡터 DB(Milvus, Elasticsearch 등)에서 근거를 찾아 답변 | Knowledge |
| 도구(Tools) | API·Python·MCP·워크플로로 시스템을 조회·처리 | Toolset → Add tool |
| 협업 에이전트 | 전문 에이전트에게 작업을 순차 위임 | Toolset → Add agent |
| 채널 | Chat 화면, 웹 페이지 임베디드 채팅 등 사용자 접점 | Channels |

작업은 **draft** 환경에서 만들고 시험한 뒤 **Deploy**로 **live**에 올립니다. 만드는 방법은 노코드 Agent Builder(Lab 1–5)와 코드 기반 ADK(Lab 6) 두 가지이며, 둘은 같은 에이전트를 다룹니다.

## Lab 1: 첫 에이전트 만들기 (30분)

목표: 지식과 도구 없이 **지침(Behavior)만으로** 일관된 말투와 범위를 지키는 HR 어시스턴트를 만들고, 미리보기 채팅에서 확인합니다.

1. 콘솔 왼쪽 메뉴에서 **Build → Agent Builder**로 이동해 **Create agent**를 클릭합니다.
2. **Create from scratch**를 선택하고 아래 값을 입력한 뒤 **Create**를 누릅니다.
   - Name: `HR Helpdesk Assistant`
   - Description: `임직원의 휴가, 재택근무, 복리후생 등 인사 규정 질문에 답하고 IT 문의는 IT 지원 에이전트에게 넘기는 사내 헬프데스크 어시스턴트`
3. 에이전트 설정 화면 상단에서 \*\*모델(LLM)\*\*을 고릅니다. 한국어 품질이 좋은 모델을 선택하고, 수강생 모두 같은 모델을 쓰도록 맞춥니다.
4. **Profile**에서 Agent style을 **ReAct Core**로 둡니다. Default와 ReAct 스타일은 향후 제거 예정이므로 새 에이전트는 ReAct Core로 만듭니다.
5. **Behavior → Instructions**에 아래 지침을 붙여넣습니다.
6. 오른쪽 **Preview** 채팅창에서 테스트 질문을 보내 응답을 확인합니다.

```text
당신은 ○○회사의 사내 헬프데스크 어시스턴트입니다.
- 항상 한국어 존댓말로, 3~5문장 이내로 답합니다.
- 인사 규정(휴가, 재택근무, 복리후생) 질문에만 답합니다.
- 규정 근거를 찾을 수 없으면 추측하지 말고 "인사팀(내선 1234)에 확인해 주세요"라고 안내합니다.
- 급여, 평가 등 개인 민감 정보는 답하지 않고 담당 부서를 안내합니다.
- 업무와 무관한 질문은 정중히 거절합니다.
```

**확인 질문**

| 질문 | 기대 결과 |
| --- | --- |
| 안녕하세요, 뭘 도와줄 수 있나요? | 역할과 범위를 존댓말로 소개 |
| 내 연봉 얼마야? | 답하지 않고 담당 부서 안내 |
| 오늘 점심 메뉴 추천해줘 | 정중히 거절 |
| 연차는 며칠인가요? | 근거가 없으므로 인사팀 확인 안내 (Lab 2에서 해결) |

> 체크포인트: 마지막 질문에서 숫자를 지어내지 않으면 성공입니다. 지어낸다면 지침의 "추측하지 말고" 문장을 맨 위로 올려 다시 테스트합니다.

## Lab 2: 지식(Knowledge) 추가 (30분)

목표: 사내 규정 문서를 올려 어시스턴트가 **문서에 근거해** 답하고 출처를 보여 주게 만듭니다. Lab 1의 "연차는 며칠인가요?" 질문이 여기서 해결됩니다.

1. 에이전트 설정 화면의 **Knowledge** 섹션에서 **Choose knowledge**를 클릭합니다.
2. **Upload files**를 선택하고 `휴가규정.pdf`, `재택근무가이드.docx`를 올립니다.
3. 지식 설명(Description)을 구체적으로 적습니다. 에이전트는 이 설명을 보고 언제 이 지식을 찾아볼지 판단합니다.
   - 예: `○○회사 인사 규정 문서. 연차·병가·경조휴가 일수와 신청 절차, 재택근무 신청 요건과 승인 절차를 담고 있음`
4. **Save**를 누르고 문서 처리가 끝날 때까지 기다립니다.
5. **Behavior → Instructions** 맨 끝에 다음 한 줄을 추가합니다: `인사 규정 질문은 반드시 Knowledge의 문서를 근거로 답하고, 답변 끝에 근거 문서명을 표시합니다.`
6. **Preview**에서 아래 질문으로 테스트합니다.

| 질문 | 기대 결과 |
| --- | --- |
| 연차는 며칠인가요? | 문서의 일수와 함께 출처(휴가규정.pdf) 표시 |
| 재택근무는 주 몇 회까지 가능한가요? | 재택근무가이드 근거로 답변 |
| 육아휴직 중 급여는 얼마인가요? | 문서에 없으면 인사팀 안내 |

> 주의: 지식 베이스는 draft와 live 환경을 구분하지 않습니다. 문서를 고치면 이미 배포된 에이전트에도 바로 반영되므로, 실습 중에는 운영 문서 대신 실습용 사본을 쓰세요.

**한 걸음 더 (선택):** Knowledge 설정에서 **Chat with documents**를 켜면 사용자가 대화 중에 직접 파일을 올려 질문할 수 있습니다. 업로드한 문서는 해당 세션에서만 쓰입니다. 스캔 이미지 PDF는 OCR을 지원하는 추출 방식을 선택해야 읽힙니다.

Sources: [Authoring native agents (ADK)](https://developer.watson-orchestrate.ibm.com/agents/build_agent), [Environments](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=agents-environments), [IBM watsonx Orchestrate 무료 평가판 가이드(한국어)](https://www.ibm.com/downloads/documents/kr-ko/1443d5c92f402c0c)

## Lab 3: 도구(Tool) 추가 (40분)

목표: OpenAPI 명세로 "휴가 잔여일 조회" 도구를 만들어 연결하고, 어시스턴트가 질문에서 사번을 뽑아 API를 호출하게 만듭니다. 문서(지식)로는 알 수 없는 **개인별 실시간 데이터**를 다루는 단계입니다.

### 3-1. 도구를 추가하는 세 가지 방법

| 방법 | 언제 쓰나 | 이 랩에서 |
| --- | --- | --- |
| Catalog | Salesforce, ServiceNow 등 미리 만들어진 도구를 바로 쓸 때 | 둘러보기만 |
| OpenAPI 업로드 | 기존 REST API가 있을 때 | **실습** |
| ADK(Python, MCP, Langflow) | 직접 로직을 코드로 짤 때 | Lab 6 |

### 3-2. OpenAPI 도구 연결

1. 에이전트 설정 화면 **Toolset** 섹션에서 **Add tool**을 클릭합니다.
2. OpenAPI 파일 업로드를 선택하고 아래 `leave_api.yaml`을 올립니다. 사내 테스트 API 주소로 `servers.url`을 바꿉니다.
3. 가져올 operation으로 `getLeaveBalance`를 선택합니다.
4. 연결(Connection)을 묻는 단계가 나오면 API 인증 방식에 맞는 연결을 고르거나 **Add a new item**으로 새로 만듭니다. 인증이 없는 테스트 API라면 생략합니다.
5. 도구가 Toolset에 추가되면 Instructions에 사용 규칙을 한 줄 더합니다: `휴가 잔여일 질문은 사번을 확인한 뒤 getLeaveBalance 도구로 조회합니다. 사번을 모르면 먼저 물어봅니다.`

```yaml
openapi: 3.0.3
info:
  title: Leave API
  version: 1.0.0
servers:
  - url: https://example-hr-api.company.com
paths:
  /leave/balance/{employeeId}:
    get:
      operationId: getLeaveBalance
      summary: 임직원의 연차 잔여일을 조회합니다
      description: 사번으로 올해 부여된 연차, 사용한 연차, 남은 연차를 돌려줍니다.
      parameters:
        - name: employeeId
          in: path
          required: true
          description: 임직원 사번 (예 E12345)
          schema:
            type: string
      responses:
        '200':
          description: 연차 정보
          content:
            application/json:
              schema:
                type: object
                properties:
                  granted: { type: number, description: 올해 부여 연차 일수 }
                  used: { type: number, description: 사용한 연차 일수 }
                  remaining: { type: number, description: 남은 연차 일수 }
```

> 핵심: 에이전트는 `summary`, `description`을 읽고 언제 어떤 값을 넣어 도구를 부를지 판단합니다. 설명을 한국어로 구체적으로 쓸수록 호출 정확도가 올라갑니다.

### 3-3. 테스트

| 질문 | 기대 결과 |
| --- | --- |
| 제 연차 며칠 남았어요? | 사번을 되물음 |
| 사번 E12345 연차 잔여일 알려줘 | getLeaveBalance 호출 후 남은 일수 답변 |
| 연차 신청 절차는요? | 도구가 아닌 지식(휴가규정) 근거로 답변 |

Preview 응답 아래의 추론(Reasoning) 보기를 펼쳐 어떤 도구가 어떤 인자로 호출됐는지 확인합니다.

> 배포 전 주의: 에이전트를 live로 배포할 때 모든 도구에 유효한 live 연결이 묶여 있지 않으면 배포가 막힙니다. Preview는 draft 연결을, 배포 후에는 live 연결을 씁니다.

Sources: [Building tools](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=building-tools), [Binding and deploying connections](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=credentials-binding-deploying-connections)

## Lab 4: 멀티 에이전트 협업 (30분)

목표: IT 문의를 전담하는 `IT Support Agent`를 따로 만들고, `HR Helpdesk Assistant`가 IT 질문을 받으면 이 에이전트에게 넘기게 합니다. 한 에이전트에 모든 도구와 문서를 몰아넣는 것보다 범위를 좁힌 전문 에이전트를 나누는 편이 답변 정확도와 유지보수에 유리합니다.

### 4-1. 협업 에이전트 만들기

1. **Build → Agent Builder → Create agent → Create from scratch**로 새 에이전트를 만듭니다.
   - Name: `IT Support Agent`
   - Description: `노트북·계정·VPN·메일 등 IT 장애와 사용 문의에 답하고 장애 신고를 접수하는 IT 지원 전문 에이전트`
2. **Knowledge**에 `IT_FAQ.pdf`를 올립니다.
3. Instructions: `IT 문의에만 답합니다. FAQ로 해결되지 않으면 증상, 장비 종류, 연락처를 물어 장애 신고 내용을 정리해 줍니다.`
4. Preview에서 "VPN 접속이 안 돼요"로 단독 동작을 확인합니다.

> Description이 중요한 이유: 협업 에이전트의 Description은 상위 에이전트가 "이 일을 누구에게 넘길지" 고를 때 읽는 문장입니다. 담당 범위를 명사로 구체적으로 나열하세요.

### 4-2. 상위 에이전트에 연결

1. `HR Helpdesk Assistant` 설정 화면으로 돌아가 **Toolset → Add agent**를 클릭합니다.
2. **Add from local instance**를 선택하고 `IT Support Agent`를 추가합니다. (Catalog에서 IBM이나 파트너가 만든 HR·IT 에이전트를 가져올 수도 있습니다.)
3. Instructions에 위임 규칙을 추가합니다: `노트북, 계정, VPN, 메일 등 IT 관련 질문은 직접 답하지 말고 IT Support Agent에게 넘깁니다.`
4. Lab 1 지침의 "인사 규정 질문에만 답합니다" 문장을 "인사 규정 질문에 답하고, IT 질문은 IT Support Agent에게 넘깁니다"로 고칩니다.

### 4-3. 테스트

| 질문 | 기대 결과 |
| --- | --- |
| 노트북 화면이 안 켜져요 | IT Support Agent로 위임되어 FAQ 기반 안내 |
| 재택근무 신청은 어떻게 하나요? | HR 어시스턴트가 직접 답변 |
| 재택근무 중 VPN이 끊겨요. 재택 규정상 출근해야 하나요? | 두 에이전트 결과를 합쳐 한 번에 답변 |

협업 에이전트는 **순차적으로** 실행됩니다. 상위 에이전트가 요청을 판단해 협업 에이전트에게 차례로 넘기고, 모두 끝나면 결과를 모아 최종 답을 만듭니다. 병렬 실행은 지원하지 않습니다. 협업 에이전트를 빼려면 Toolset에서 해당 에이전트의 ⋮ 메뉴 → **Remove**를 누릅니다.

Sources: [Orchestrating agents](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/current?topic=agents-adding-orchestration)

## Lab 5: 테스트, 배포, 채널 연결 (30분)

목표: draft에서 다듬은 어시스턴트를 live로 배포하고, 사내 포털 같은 웹 페이지에 채팅 위젯으로 붙입니다.

### 5-1. draft와 live 이해하기

지금까지의 모든 작업은 **draft** 환경에서 이뤄졌습니다. draft는 운영에 영향 없이 실험하는 공간이고, **Deploy**를 눌러야 **live**에 반영되어 연결된 모든 채널의 사용자가 쓸 수 있습니다. draft를 고쳐도 다시 배포하기 전까지 live는 바뀌지 않습니다. 단, Lab 2에서 본 것처럼 지식 베이스는 예외입니다.

### 5-2. 배포 전 점검

- [ ] Lab 1–4의 확인 질문을 Preview에서 모두 다시 돌려 기대 결과와 비교
- [ ] Toolset의 모든 도구에 live 연결이 바인딩되어 있는지 확인 (없으면 배포 실패)
- [ ] 협업 에이전트 `IT Support Agent`도 먼저 배포되어 있는지 확인
- [ ] 시작 화면 문구 정리: 에이전트 이름, 환영 메시지, 스타터 프롬프트 최대 3개 (예: "연차 잔여일 조회", "재택근무 규정", "IT 장애 신고")

### 5-3. 배포

1. `IT Support Agent` 화면 오른쪽 위 **Deploy**를 눌러 먼저 배포합니다.
2. `HR Helpdesk Assistant`도 **Deploy**합니다. 배포 시점의 스냅샷이 버전으로 남습니다.
3. 왼쪽 메뉴 **Chat**에서 드롭다운으로 `HR Helpdesk Assistant`를 고르고 live 동작을 확인합니다.

### 5-4. 웹 페이지에 채팅 위젯 붙이기

1. 에이전트 설정 화면에서 **Channels → Embedded agent**로 이동합니다.
2. 테스트 중에는 **Draft**, 운영 페이지에는 **Live** 모드의 스크립트를 복사합니다.
3. 아래처럼 빈 HTML 파일의 `</body>` 바로 앞에 붙여넣고 브라우저로 엽니다.

```html
<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><title>사내 포털 (테스트)</title></head>
<body>
  <h1>○○회사 사내 포털</h1>
  <!-- Channels > Embedded agent 에서 복사한 스크립트를 여기에 붙여넣기 -->
</body>
</html>
```

> 보안 설정 필수: 임베디드 채팅은 공개키 암호화와 JWT 인증을 쓰며, 보안 구성을 마치기 전까지 위젯이 동작하지 않습니다. 실습 환경에서는 강사가 미리 설정을 마쳐 두고, 운영 적용 시에는 [Configuring security for embedded chat](https://www.ibm.com/docs/SSAVQO/deploy/web_chat_agent/web_chat_configuring_security.html)을 따릅니다.

Sources: [Environments](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=agents-environments), [Embedding the agent with web applications](https://www.ibm.com/docs/SSAVQO/deploy/web_chat_agent/web_chat_how_embed.html), [Embedding agents in applications](https://www.ibm.com/docs/en/SSAVQO/agent_builder/using_webchat.html)

## Lab 6 (선택): ADK로 코드 기반 에이전트 만들기 (40분)

목표: Agent Development Kit(ADK)로 Python 도구와 에이전트를 코드(YAML)로 정의하고 같은 인스턴스에 올립니다. UI로 만든 것과 같은 결과를 Git으로 관리하고 CI/CD로 배포할 수 있게 됩니다.

### 6-1. ADK 설치와 인스턴스 연결

1. Python **3.11 이상**을 확인하고 ADK를 설치합니다.
2. watsonx Orchestrate 콘솔 오른쪽 위 사용자 아이콘 → **Settings → API details** 탭에서 서비스 인스턴스 URL을 복사하고 **Generate API key**로 API 키를 만듭니다. IBM Cloud 리소스 페이지의 자격 증명은 쓰지 않습니다.
3. 환경을 등록하고 활성화합니다. 명령을 실행하면 API 키를 묻습니다.

```bash
python --version                      # 3.11 이상
python -m venv .venv && source .venv/bin/activate
pip install --upgrade ibm-watsonx-orchestrate

# IBM Cloud 인스턴스: --type ibm_iam / AWS 인스턴스: --type mcsp
orchestrate env add -n lab -u <서비스-인스턴스-URL> --type ibm_iam --activate
orchestrate env list

mkdir -p adk-lab/{agents,tools}
```

### 6-2. Python 도구 만들기

`tools/leave_tools.py`를 만듭니다. 실습에서는 실제 API 대신 샘플 데이터를 돌려줍니다.

```python
from ibm_watsonx_orchestrate.agent_builder.tools import tool

_SAMPLE = {
    "E12345": {"granted": 15, "used": 6},
    "E67890": {"granted": 20, "used": 18},
}

@tool
def get_leave_balance(employee_id: str) -> dict:
    """임직원의 올해 연차 부여·사용·잔여 일수를 조회합니다.

    Args:
        employee_id (str): 임직원 사번 (예: E12345)

    Returns:
        dict: granted(부여), used(사용), remaining(잔여) 일수
    """
    rec = _SAMPLE.get(employee_id.upper())
    if rec is None:
        return {"error": f"사번 {employee_id}을(를) 찾을 수 없습니다."}
    return {**rec, "remaining": rec["granted"] - rec["used"]}
```

```bash
echo "ibm-watsonx-orchestrate" > tools/requirements.txt
orchestrate tools import -k python -f tools/leave_tools.py -r tools/requirements.txt
orchestrate tools list
```

> 에이전트는 함수의 타입 힌트와 docstring을 읽고 언제, 어떤 인자로 도구를 부를지 정합니다. docstring을 구체적으로 쓰는 것이 곧 프롬프트 엔지니어링입니다.

### 6-3. 에이전트 정의와 가져오기

`agents/hr_adk_agent.yaml`을 만듭니다. `llm` 값은 인스턴스에서 쓸 수 있는 모델로 바꿉니다.

```yaml
spec_version: v1
kind: native
name: hr_adk_assistant
description: 사내 인사 규정 질문에 답하고 연차 잔여일을 조회하는 HR 어시스턴트 (ADK 실습용)
llm: groq/openai/gpt-oss-120b
style: react_core
instructions: |
  당신은 사내 HR 어시스턴트입니다. 항상 한국어 존댓말로 간결하게 답합니다.
  연차 잔여일 질문은 사번을 확인한 뒤 get_leave_balance 도구로 조회합니다.
  사번을 모르면 먼저 물어봅니다. 근거 없는 숫자는 만들지 않습니다.
tools:
  - get_leave_balance
collaborators: []
starter_prompts:
  prompts:
    - id: balance
      title: "연차 잔여일"
      subtitle: "내 연차 며칠 남았지?"
      prompt: "제 연차 잔여일을 알려주세요"
      state: active
```

```bash
orchestrate agents import -f agents/hr_adk_agent.yaml
```

가져오기가 끝나면 Agent Builder의 에이전트 목록에 `hr_adk_assistant`가 나타납니다. 선택 후 Preview에서 "사번 E67890 연차 남은 거 알려줘"를 보내 잔여 2일이 나오는지 확인하고, UI에서 **Deploy**합니다. 이후에는 YAML을 고쳐 다시 import하는 방식으로 관리합니다.

Sources: [Getting started with the ADK](https://developer.watson-orchestrate.ibm.com/getting_started/installing), [Authoring native agents](https://developer.watson-orchestrate.ibm.com/agents/build_agent), [Choosing the agent style](https://developer.watson-orchestrate.ibm.com/agents/agent_styles)

## 트러블슈팅과 정리

| 증상 | 원인 | 조치 |
| --- | --- | --- |
| 규정에 없는 숫자를 지어냄 | 지침이 약하거나 지식 설명이 모호함 | "추측하지 말 것" 지침을 맨 위로, 지식 Description에 담긴 내용을 구체적으로 나열 |
| 질문해도 지식을 찾지 않음 | 지식 Description과 질문이 동떨어짐 | Description에 질문에 나올 단어(연차, 병가, 재택 등)를 포함 |
| 도구가 호출되지 않거나 엉뚱한 인자 | OpenAPI `description`이나 docstring이 부실 | 파라미터 설명·예시값을 한국어로 보강, 지침에 도구 이름을 명시 |
| IT 질문이 위임되지 않음 | 협업 에이전트 Description이 범위를 못 드러냄 | 담당 항목을 명사로 나열, 상위 지침에 위임 규칙 추가 |
| Deploy 버튼이 실패함 | 도구에 live 연결이 없음 | 해당 도구의 Connection에서 live 환경 설정 완료 |
| 임베디드 위젯이 안 뜸 | 임베디드 채팅 보안 미설정 또는 Draft/Live 스크립트 혼동 | 보안 구성 확인, 운영 페이지엔 Live 스크립트 사용 |
| `orchestrate env add` 인증 오류 | 잘못된 자격 증명 사용 | 콘솔 Settings → API details의 URL과 키 사용, `--type` 명시 |

### 실습 정리

- [ ] 실습용 에이전트(`HR Helpdesk Assistant`, `IT Support Agent`, `hr_adk_assistant`)를 계속 쓰지 않으면 삭제
- [ ] 실습용 지식 문서와 테스트 연결 삭제
- [ ] Lab 6에서 만든 API 키 폐기 (IBM Cloud IAM)

### 다음 단계

- **Agentic workflow(Flow Builder)**: 승인 절차처럼 순서가 정해진 업무는 도구 안에 결정적 흐름으로 묶습니다.
- **Guidelines**: "불만을 표현하면 → 사과하고 상세 내용 요청"처럼 조건-행동 규칙을 추가합니다. 매 턴 LLM 호출이 하나 늘어 지연과 비용이 커지므로 지침으로 충분하면 지침을 우선합니다.
- **평가(Evaluation Framework)**: ADK로 기대 대화를 정의해 회귀 테스트를 자동화합니다.

### 참고 자료

- [watsonx Orchestrate ADK 문서](https://developer.watson-orchestrate.ibm.com/)
- [Getting started with the ADK](https://developer.watson-orchestrate.ibm.com/getting_started/installing)
- [Authoring native agents](https://developer.watson-orchestrate.ibm.com/agents/build_agent)
- [Orchestrating agents (IBM Docs)](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/current?topic=agents-adding-orchestration)
- [Embedding the agent with web applications (IBM Docs)](https://www.ibm.com/docs/SSAVQO/deploy/web_chat_agent/web_chat_how_embed.html)
- [IBM watsonx Orchestrate 무료 평가판 가이드(한국어)](https://www.ibm.com/downloads/documents/kr-ko/1443d5c92f402c0c)
- [WXO Labs & Tutorial Guide (커뮤니티, 15개 랩)](https://markusvankempen.github.io/wxo-labs/)

> 화면 메뉴 이름은 watsonx Orchestrate 업데이트에 따라 조금씩 바뀔 수 있습니다. 실습 직전에 강사가 한 번 리허설하며 메뉴 위치를 확인하세요.
