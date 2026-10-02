-- ITSM service request 테이블 (MySQL 8.x, database: demo)
USE demo;

CREATE TABLE IF NOT EXISTS itsm_service_requests (
    id           BIGINT NOT NULL AUTO_INCREMENT COMMENT '내부 SR 식별자',
    title        VARCHAR(200) NOT NULL COMMENT '요청 제목',
    description  TEXT NOT NULL COMMENT '증상, 영향, 재현 절차',
    service_name VARCHAR(120) NOT NULL COMMENT '대상 애플리케이션/서비스',
    environment  VARCHAR(32) NOT NULL DEFAULT 'production' COMMENT '대상 환경',
    severity     VARCHAR(16) NOT NULL COMMENT 'LOW, MEDIUM, HIGH, CRITICAL',
    status       VARCHAR(24) NOT NULL DEFAULT 'NEW' COMMENT 'NEW, IN_PROGRESS, RESOLVED, CLOSED',
    requester    VARCHAR(120) NOT NULL COMMENT '요청자',
    assignee     VARCHAR(120) NULL COMMENT '담당자 또는 담당 그룹',
    assignee_employee_no VARCHAR(32) NULL COMMENT 'Bob 알림 수신 직원 번호',
    worklog      TEXT NOT NULL COMMENT '시간과 작성자가 포함된 작업 기록',
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '접수 시각',
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '최종 변경 시각',
    PRIMARY KEY (id),
    KEY ix_itsm_service_requests_service_name (service_name),
    KEY ix_itsm_service_requests_severity (severity),
    KEY ix_itsm_service_requests_status (status),
    KEY ix_itsm_service_requests_assignee_employee_no (assignee_employee_no)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci
  COMMENT='ITSM Service Request';
