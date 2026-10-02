-- Transactional outbox for ITSM events and user notifications (MySQL 8.x).
USE demo;

CREATE TABLE IF NOT EXISTS itsm_event_outbox (
    id          BIGINT NOT NULL AUTO_INCREMENT COMMENT '단조 증가 이벤트 cursor',
    ticket_key  VARCHAR(16) NOT NULL COMMENT '사람이 읽을 수 있는 SR 번호',
    event_type  VARCHAR(100) NOT NULL COMMENT '생성, 상태 변경, 작업 기록 이벤트',
    payload     JSON NOT NULL COMMENT '알림에 필요한 최소 SR 요약',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '이벤트 생성 시각',
    PRIMARY KEY (id),
    KEY ix_itsm_event_outbox_ticket (ticket_key),
    KEY ix_itsm_event_outbox_created (created_at)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci
  COMMENT='ITSM transactional outbox for business and notification events';
