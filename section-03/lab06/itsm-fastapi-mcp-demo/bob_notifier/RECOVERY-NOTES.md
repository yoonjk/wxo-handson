# Bob Notifier 1.8.3 소스 복원 기록

첨부된 bob-notifier-1.8.3.vsix의 배포 코드를 기준으로 복원했습니다.
extension.js, package.json, README.md, LICENSE, media/bob-logo.png는 VSIX 내 파일입니다.
.vscodeignore와 package-lock.json은 제공된 1.8.2 소스에서 유지하고 lock의 루트 버전만 1.8.3으로 맞췄습니다.
원래 1.8.3 개발 작업 폴더 전체나 당시 빌드 환경을 복구한 것은 아닙니다.

## 확인된 코드 차이
- 중복 event_id 수신 시 event_duplicate 로그를 기록하고 팝업 표시를 생략합니다.
- 기존 알림 패널이 있으면 새 알림 수신 시 앞으로 표시합니다.
- 관리자 작성 drawer가 열려 있으면 해당 reveal을 생략합니다.
- package.json 버전과 패키징 출력 파일명을 1.8.3으로 변경했습니다.

## 검증
- 복원된 extension.js와 package.json은 첨부 VSIX와 바이트 단위로 동일합니다.
- Node.js 구문 검사를 수행했습니다.
- IBM Bob IDE 및 실제 Event 서버 연동 실행 테스트는 수행하지 않았습니다.

## 빌드
npm ci
npm run package

설치는 IBM Bob Extensions 화면의 Install from VSIX에서 원본 bob-notifier-1.8.3.vsix를 선택합니다.
