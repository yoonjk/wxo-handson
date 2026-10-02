-- 이 스크립트는 기존 SR/알림 이벤트 데이터를 모두 삭제합니다.
-- 완전히 새로 시작할 때만 실행하세요. database 자체(demo)는 삭제하지 않습니다.
USE demo;

DROP TABLE IF EXISTS itsm_event_outbox;
DROP TABLE IF EXISTS itsm_service_requests;

-- 이전 데모 이름으로 생성된 테이블도 함께 제거해 잔존 데이터가 남지 않게 합니다.
DROP TABLE IF EXISTS demo_sr_event_outbox;
DROP TABLE IF EXISTS demo_service_requests;
