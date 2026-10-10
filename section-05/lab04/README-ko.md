
## Create the standard operating procedure document

- Click Start New Task to begin a new task for this step.

Note: Starting new tasks regularly reduces context size and lowers resource usage.

- Make sure that you enable Advanced mode and disable auto-approval. Advanced mode activates Bob skills.

- Create a new folder named bpmn. Download the file BPMN-order-process.bpmn into this folder.
- Provide Bob with instructions to generate the SOP document.

```
@section-05/lab04/mermaid/BPMN-order-process.md 을 읽어서  SOP 문서를 lab04/sop/order-processing-sop.md 파일을 생성합니다.
```
![alt text](create-sop.png)


Open the document and review the content. The document converts the BPMN workflow into clear business language. You will use the document in later steps to generate a watsonx Orchestrate agent.

The document includes the following sections:

- Executive summary
- Business process flow diagram
- Business context
- Procedure overview
- Data requirements
- Business procedure steps

This document serves as the foundation for implementing an automated order processing agent in watsonx Orchestrate. To view the Mermaid diagrams in the document, install the Mermaid Chart extension.

## Create the agentic workflow from the SOP document
1. Click Start `New Task` to begin a new task for this step.
2. Keep Advanced mode enabled. `Agent(Advanced)` mode allows Bob to use Bob skills and access watsonx Orchestrate ADK MCP servers.
3. Provide Bob with the instructions to create the agent. Review the proposed plan and click Approve.
```
@lab04/mermaid/BPMN-order-process.md와 이 SOP 문서 @lab04/sop/order-processing-sop.md 를 기반으로 watsonx Orchestrate 프로젝트를 생성합니다.

추가 세부 정보:
- watsonx Orchestrate 플로우나 에이전트 코드를 작성하기 전에는 반드시 Bob Skill을 참조하십시오.
- 검증된 플로우 생성 패턴(조건부 분기, 순차적 도구 연쇄)에 대해서는 @/ibm-watsonx-orchestrate-adk/examples를 참조하십시오.
- API 참조를 위해서는 watsonx Orchestrate ADK 문서 MCP 서버를 사용하십시오.
- 이 프로젝트를 위해 `lab04/order-processing-agent`라는 새 폴더를 생성하십시오.
- 시뮬레이션/모의 통합을 사용하여 구현하십시오(외부 종속성 없음).
- 비즈니스 로직은 복잡한 플로우 표현식이 아닌 Python 도구 내에 유지하십시오.
- 가능한 경우 복잡한 매핑 대신 자동 매핑을 사용하고, 자동 매핑을 활성화하기 위해 중첩된 객체(예: `customer.email`) 대신 평면 필드 스키마(예: `customer_email`)를 사용하십시오.
```

## Deploy the agentic workflow and agent
1. Click Start `New Task` to begin a new task for this step.
2. Provide Bob with the following instruction to deploy the agent and tools:
```
임포트 스크립트를 실행하여 주문 처리용 플로우와 에이전트를 내 Watsonx Orchestrate 환경에 배포합니다.
임포트 과정에서 문제가 발생하면 Bob 스킬, Watsonx Orchestrate 문서(MCP 서버) 및 예제 프로젝트를 참고하십시오.
콘솔 출력 내용을 로그 파일에 추가하십시오.
```

## Run unit tests for the agentic workflow and the agent
1. Click Start `New Task` 
2. Provide Bob with instructions to run unit tests for the deployed order processing agent and workflow.

```
@lab04/order-processing-agent 에 있는 기존 테스트 파일을 사용하여 watsonx Orchestrate 도구 및 워크플로우에 대한 프로그래밍 방식의 단위 테스트를 실행해 주십시오. 오류가 발생하면 이를 수정하고, 도구를 다시 가져온 후 테스트가 성공할 때까지 재시도해 주십시오.

추가 세부 정보:
- 플로우 로직을 변경하기 전에는 반드시 Bob 스킬 “wxo-builder”를 사용하여 모범 사례를 확인해야 합니다.
- 구체적인 API 참조나 구현 세부 사항이 필요한 경우, watsonx Orchestrate ADK 문서 MCP 서버를 활용하십시오.
- 흐름 관련 문제가 발생할 경우, Bob 스킬을 참조하고 @/ibm-watsonx-orchestrate-adk/examples에 있는 기존 흐름 예제를 참고하십시오.
- 변경을 수행하기 전에 모든 관련 파일(도구, 흐름, 테스트 스크립트)을 함께 읽어 전체적인 맥락을 파악하십시오.
```

Instruct Bob to test the deployed agent
```
안녕하세요, Bob 님. Watsonx Orchestrate ADK MCP 서버를 사용하여 에이전트와 대화를 나누며 테스트를 진행해 주세요.

문제가 발생하면 이를 해결하고, 가져오기 스크립트를 통해 다시 배포한 후, 모든 문제가 해결될 때까지 이 과정을 반복해 주세요.

마지막으로, 테스트 폴더에 에이전트와 도구에 대한 테스트 요약 보고서를 작성해 주세요.
```

```
고객 Jaeguk(jgyun@example.com)의 주문(주문 ID: ORD-2024-003, 고객 ID: CUST-67890, 전화번호: +82-10-555-9876)을 처리하십시오. 상품: 게이밍 노트북(PROD-003) 2대($1899.99), 게이밍 마우스(PROD-004) 3개($79.99). 배송지: 456 Oak Avenue, New York, NY 10001, USA. 결제 수단: credit_card
```

# 참조
- (Turn BPMN diagrams into production‑ready agents with Bob skills and watsonx Orchestrate)[https://developer.ibm.com/tutorials/bpmn-to-agents-bob-skills-watsonx-orchestrate/]