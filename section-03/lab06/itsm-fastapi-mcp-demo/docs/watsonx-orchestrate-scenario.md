# 20분 발표 시나리오: 운영 SR 접수부터 수정 배포까지

## 발표 목표

운영팀이 ITSM에 Service Request(SR)를 접수하면 Bob에 새 SR 알림이 표시되고, 개발자가 Bob에서 SR을 조회해 수정안을 만들며, Jenkins와 SonarQube 품질 게이트를 통과한 변경만 승인된 환경에 배포하는 흐름을 보여줍니다. **SR 알림은 안내용이며, 알림 수신만으로 Bob이 코드 수정이나 배포를 자동 시작하지 않습니다.**

## 시스템 역할

| 구성 요소 | 담당 역할 |
|---|---|
| ITSM FastAPI + MySQL | SR 접수·조회·상태·작업 이력의 기준 시스템. `SR-000001` 키와 담당 `assignee_employee_no`를 저장합니다. |
| IBM Bob Notification MCP Server | MySQL outbox 이벤트를 SSE `/events`로 전달하고, 전체·설정 그룹·개별 사용자 공지를 제공합니다. |
| IBM Bob | 알림을 보여주고, 개발자가 요청하면 SR 맥락을 읽고 코드 수정·테스트를 수행합니다. |
| ContextForge MCP Gateway | Bob으로 들어가는 MCP 연결과 ITSM, Jenkins, SonarQube, A2A WXO MCP 서버의 도구 접근을 관리합니다. |
| A2A WXO MCP Server | MCP 도구를 제공하고 A2A client로 watsonx Orchestrate agent와 메시지를 주고받습니다. |
| watsonx Orchestrate Agent | SR 요약·분류·다음 조치 제안 등 발표 시나리오를 수행합니다. SR 알림의 푸시 채널은 맡지 않습니다. |
| Jenkins + SonarQube | 빌드·테스트·정적 분석을 실행하고 Quality Gate 결과로 배포를 허용하거나 차단합니다. |

## SR 알림 전달 경로

```text
운영자 → ITSM FastAPI → MySQL SR + outbox (하나의 transaction)
                         └→ IBM Bob Notification MCP Server → SSE /events → Bob 알림 수신기
                                           └──────→ MCP /mcp → Gateway tool registry
```

SR 생성·상태 변경·작업 기록이 MySQL transactional outbox에 같은 transaction으로 저장됩니다. IBM Bob Notification MCP Server가 cursor 기반 `/events` SSE feed를 내보내며, 끊겼다가 재연결하는 Bob-side adapter는 마지막 SSE `id`를 `after_event_id`로 전달해 누락 이벤트를 따라잡습니다. MCP `/mcp`에는 `watch_service_request_events`와 대상별 `send_notification` 도구가 있습니다. 공지 대상은 설정된 전체 사용자, `ITSM_EVENT_USER_GROUPS_JSON`의 그룹, 또는 employee_no 한 명입니다.

알림 대상은 `assignee_employee_no`로 지정합니다. 각 Bob 확장 사용자는 개별 SSE Bearer token을 가지고, Event MCP Server는 token을 서버 측 map에서 employee_no로 변환합니다. 요청자가 query string으로 employee_no를 지정하지 않기 때문에 다른 담당자를 사칭할 수 없습니다. 이 데모의 token map은 `.env`에 두는 간단한 방식이며, 운영에서는 조직 IdP가 발급한 서명 검증 가능한 access token의 subject/employee claim으로 대체합니다.

SSE feed와 Bob UI 표시는 별도 계층입니다. 이 저장소에는 `/events`를 구독하고 `vscode.window.showInformationMessage()`를 호출하는 Bob 2.0.1용 VS Code extension 소스가 포함되어 있습니다. Bob 확장을 설치하고 사용자별 token/접근 가능한 SSE 주소를 설정하면 지정 담당자에게만 새 SR 팝업을 표시합니다. ContextForge의 일반 MCP upstream 등록만으로 별도 `/events` endpoint가 자동 전달되지는 않으므로 확장이 SSE endpoint에 직접 접근해야 합니다. MCP `/mcp`의 event watch 도구는 운영자 전용 credential로 제한하고, 일반 사용자별 push에는 `/events`를 사용합니다. VSIX 설치와 Bob UI에서의 실환경 동작은 데모 PC에서 확인합니다. Orchestrate A2A agent는 별도 사용자 요청에 답하는 역할이며, 알림을 push하는 역할은 아닙니다.

## 20분 진행 순서

| 시간 | 내용 | 발표자 진행 |
|---|---|---|
| 0–2분 | 운영 문제 | SR, 소스, 빌드 로그, 코드 품질 결과가 여러 시스템에 흩어지는 문제를 설명합니다. |
| 2–5분 | 목표 흐름 | SR 접수 → Bob 알림 → Bob SDLC → Jenkins/SonarQube → 배포 → SR 처리 기록을 소개합니다. |
| 5–8분 | 연결 구조 | MCP는 Bob과 Gateway/도구 서버 사이, A2A는 A2A WXO MCP Server와 Orchestrate agent 사이의 통신임을 설명합니다. |
| 8–10분 | 알림 경계 | SR 생성 이벤트가 Bob에 안내만 전달하며, 알림 자체가 코드 변경·pipeline 실행·배포를 일으키지 않는다고 강조합니다. |
| 10–16분 | 라이브 데모 | 샘플 SR 알림을 표시하고, Bob에서 SR 조회부터 수정 및 pipeline 결과 확인까지 시연합니다. |
| 16–19분 | 품질·운영 통제 | Quality Gate 실패 시 배포 차단, 운영 배포 승인, 실패/성공 내용을 SR에 기록하는 흐름을 보여줍니다. |
| 19–20분 | 정리 | 알림은 인지, Bob은 개발, Jenkins/SonarQube는 검증, ITSM은 이력의 기준이라고 요약합니다. |

## 라이브 시나리오

### 사전 준비

1. MySQL `demo` 데이터베이스에서 FastAPI와 ITSM MCP 서버를 실행하고, Event MCP `.env`에 Bob 사용자별 token map을 설정합니다.
2. `payments-api` 테스트 저장소에 재현 가능한 운영 결함과 테스트를 준비합니다.
3. ContextForge Gateway에 ITSM, Jenkins, SonarQube, A2A WXO MCP 서버를 등록하고 Bob이 필요한 도구만 연결합니다.
4. `python -m itsm_event_mcp.server`로 IBM Bob Notification MCP Server를 실행하고 Gateway에 `/mcp` endpoint를 등록합니다. Bob 2.0.1에 `bob-notifier-1.4.0.vsix`를 설치하고 token/SSE 주소를 설정해 팝업 표시를 미리 확인합니다. 확장 설치를 제한하는 환경에서는 MCP watch tool을 사용합니다.
5. Jenkins pipeline에 checkout, build, unit test, SonarQube scan, Quality Gate, staging deploy, smoke test 단계를 준비합니다. Production 배포에는 별도 수동 승인 단계를 둡니다.
6. watsonx Orchestrate agent는 발표용 시나리오로 준비합니다. 실제 agent, toolset, A2A 인증/연결은 해당 Orchestrate 환경에서 별도로 설정합니다.

### 1) 운영팀이 SR 접수

운영자가 `payments-api`, `production` 환경의 간헐적 500 오류를 ITSM에 등록하고 담당 employee_no를 지정합니다. FastAPI는 SR과 `assignee_employee_no`를 MySQL `itsm_service_requests` 테이블에 저장하고 `SR-000001` 같은 키를 반환합니다. SR 이벤트와 일반 사용자 알림은 `itsm_event_outbox`에 기록됩니다.

Transactional outbox에 수신 employee_no가 포함된 이벤트가 남습니다. Event MCP는 연결 token에서 직원 번호를 확인한 뒤 대상이 일치하는 Bob 확장에만 다음 최소 요약을 SSE로 보냅니다. 확장은 이를 IDE 팝업으로 표시합니다.

> 새 운영 SR: SR-000001 · payments-api · HIGH · 결제 요청 간헐적 500 오류. Bob에서 `get_service_request("SR-000001")`로 상세 내용을 확인할 수 있습니다.

Bob-side 수신기에서는 이 요약을 알림으로 표시합니다. Bob은 자동으로 저장소를 변경하거나 Jenkins를 실행하지 않습니다. 수신기가 연결되지 않은 동안 이벤트는 outbox에 남고, 마지막 event ID 이후부터 다시 읽습니다.

### 2) 개발자가 Bob에서 SR 조회 및 작업 계획

개발자는 Bob에서 알림의 SR 키를 선택/복사하고 다음과 같이 요청합니다.

> SR-000001 상세와 최근 처리 기록을 조회해 주세요. 저장소에서 관련 API와 테스트를 찾아 원인 분석 및 수정 계획을 먼저 제시하세요. 아직 파일을 수정하지 마세요.

Bob은 ITSM MCP 도구로 요청을 조회하고, 관련 코드와 테스트를 살펴 수정 계획을 제시합니다. 필요하면 A2A WXO MCP 도구를 통해 Orchestrate agent에 SR 요약이나 다음 담당 조치를 문의합니다.

### 3) IBM Bob으로 SDLC 수정

개발자가 계획을 확인한 뒤 Bob에 수정과 회귀 테스트를 요청합니다. Bob은 코드와 테스트를 수정하고 변경 파일과 테스트 결과를 요약합니다. Jenkins MCP로 기존 pipeline 정의나 최근 실행을 확인할 수 있습니다.

**Production 배포는 Bob이 직접 수행하지 않습니다.** 개발자는 변경을 branch/PR에 반영하고, 배포는 Jenkins pipeline 및 승인 절차를 거칩니다.

### 4) Jenkins와 SonarQube 품질 게이트

Jenkins pipeline은 다음 순서로 실행합니다.

1. Checkout 및 dependency 설치
2. Build와 unit/integration test
3. SonarQube scan 및 Quality Gate 대기
4. Quality Gate 통과 시 staging 배포와 smoke test
5. 수동 승인 후 production 배포

SonarQube Quality Gate가 실패하면 pipeline은 production 배포를 중단합니다. Bob은 Jenkins/SonarQube MCP 도구로 실패 단계와 새 이슈를 조회해 수정안을 보완합니다. 재실행이 통과하면 승인된 단계로 진행합니다.

### 5) SR에 결과 기록 및 조회

배포 완료 후 승인된 작업으로 SR worklog에 commit/PR, Jenkins build 번호, SonarQube Quality Gate, 배포 버전, smoke test 결과를 기록합니다. staging 검증이 끝나면 상태를 `RESOLVED`로 바꾸고, 운영 관찰 기간이 끝난 뒤 담당자가 `CLOSED` 처리합니다.

Bob은 마지막으로 SR을 재조회해 키, 현재 상태, 빌드/배포 결과와 다음 조치를 요약합니다. MySQL에는 모든 SR 상태와 기록이 남습니다.

## Orchestrate agent 지침 예시

```text
당신은 운영 유지보수 SR Coordinator입니다.
- 요청에 SR 키가 있으면 ITSM MCP로 상세 SR과 작업 이력을 먼저 조회합니다.
- SR 요약, 서비스/환경, 영향, 우선순위, 미확인 정보를 짧게 정리합니다.
- 중복 SR이 의심되면 기존 SR 후보를 제시하고 새 SR 생성 전 확인을 요청합니다.
- 사용자가 요청하지 않은 SR 등록, 상태 변경, worklog 추가는 하지 않습니다.
- Jenkins/SonarQube 결과를 받으면 빌드 번호, 실패 단계, Quality Gate를 근거와 함께 요약합니다.
- Quality Gate 실패를 통과로 표현하거나 배포를 권고하지 않습니다.
- 비밀번호, 토큰, 민감정보를 SR이나 답변에 포함하지 않습니다.
- tool 응답에 없는 결과를 추정해 사실처럼 말하지 않습니다.
```

## 운영 보완점

- **담당자 식별**: SR의 `assignee_employee_no`와 Bob별 인증 token을 연결합니다. employee_no를 클라이언트 요청 값만으로 신뢰하지 않습니다.
- **알림 중복 방지**: outbox의 증가 ID를 event cursor로 사용합니다. Bob 확장은 처리한 event ID를 저장하고 재연결에 사용합니다.
- **알림 전달 보장**: 현재 코드는 transactional outbox와 재조회 가능한 SSE cursor를 제공합니다. 장기 보관 정책과 실패 대체 채널은 운영에서 추가합니다.
- **Bob 연결 부재 처리**: Bob이 종료되어 MCP 연결이 없을 때도 SR은 MySQL에 보존하고, Bob 재연결 후 미확인 목록을 조회하거나 대체 채널에 알립니다.
- **알림 최소화**: 제목, SR 키, 서비스, 심각도만 알리고 상세 증상·개인정보는 인증된 SR 조회로 확인합니다.
- **CI/CD 분리**: Quality Gate와 테스트 통과가 배포의 필수 조건이며 production에는 독립된 승인 단계를 둡니다.
- **감사성**: SR 상태·worklog 변경자와 Jenkins build/deployment 식별자를 남깁니다.

이 저장소는 FastAPI outbox, Event MCP watch tool, SSE feed를 구현합니다. watsonx Orchestrate agent, ContextForge upstream 등록, Jenkins/SonarQube 연결과 Bob의 화면 notification adapter는 각 환경에서 설정해야 합니다. SSE feed 자체는 실행 가능하지만, 일반 MCP gateway 경로만으로 UI 표시까지 보장하지 않습니다.
