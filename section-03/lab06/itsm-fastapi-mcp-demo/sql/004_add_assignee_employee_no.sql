-- 기존 itsm_service_requests 테이블에 Bob 알림 수신 대상 컬럼을 추가합니다.
-- 신규 DB에서는 001_create_itsm_service_requests.sql에 이미 포함되어 있으므로 이 스크립트는 생략해도 됩니다.
USE demo;

SET @add_assignee_column = IF(
    (SELECT COUNT(*) FROM information_schema.columns
     WHERE table_schema = DATABASE()
       AND table_name = 'itsm_service_requests'
       AND column_name = 'assignee_employee_no') = 0,
    'ALTER TABLE itsm_service_requests ADD COLUMN assignee_employee_no VARCHAR(32) NULL COMMENT ''Bob 알림 수신 직원 번호''',
    'SELECT 1'
);
PREPARE add_assignee_column_stmt FROM @add_assignee_column;
EXECUTE add_assignee_column_stmt;
DEALLOCATE PREPARE add_assignee_column_stmt;

SET @add_assignee_index = IF(
    (SELECT COUNT(*) FROM information_schema.statistics
     WHERE table_schema = DATABASE()
       AND table_name = 'itsm_service_requests'
       AND index_name = 'ix_itsm_service_requests_assignee_employee_no') = 0,
    'CREATE INDEX ix_itsm_service_requests_assignee_employee_no ON itsm_service_requests (assignee_employee_no)',
    'SELECT 1'
);
PREPARE add_assignee_index_stmt FROM @add_assignee_index;
EXECUTE add_assignee_index_stmt;
DEALLOCATE PREPARE add_assignee_index_stmt;
