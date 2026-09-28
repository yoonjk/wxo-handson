-- ---------------------------------------------------------------------------
-- HR 휴가 관리 데모 - MySQL 스키마 + 시드 데이터
-- ---------------------------------------------------------------------------
-- 사용법:
--   mysql -u root -p < schema.sql
-- 또는 접속 후:
--   SOURCE schema.sql;
-- ---------------------------------------------------------------------------

CREATE DATABASE IF NOT EXISTS demo
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE demo;

DROP TABLE IF EXISTS vacation_requests;
DROP TABLE IF EXISTS employees;

CREATE TABLE employees (
    employee_id       VARCHAR(10)  NOT NULL PRIMARY KEY,
    name              VARCHAR(100) NOT NULL,
    department        VARCHAR(100) NOT NULL,
    manager_id        VARCHAR(10)  NULL,
    annual_leave_days INT          NOT NULL DEFAULT 15,
    used_leave_days   INT          NOT NULL DEFAULT 0,
    CONSTRAINT fk_employees_manager
        FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
) ;

CREATE TABLE vacation_requests (
    request_id  VARCHAR(20)  NOT NULL PRIMARY KEY,
    employee_id VARCHAR(10)  NOT NULL,
    start_date  DATE         NOT NULL,
    end_date    DATE         NOT NULL,
    status      VARCHAR(20)  NOT NULL DEFAULT 'Pending',
    reason      VARCHAR(255) NULL,
    CONSTRAINT fk_requests_employee
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    INDEX idx_requests_dates (start_date, end_date),
    INDEX idx_requests_status (status)
) ;

-- 매니저(팀장)을 먼저 넣어야 FK 제약을 만족합니다.
INSERT INTO employees
    (employee_id, name, department, manager_id, annual_leave_days, used_leave_days)
VALUES
    ('E010', '최영희', 'Sales',       NULL, 20, 5),
    ('E011', '정하늘', 'Engineering', NULL, 20, 6),
    ('E001', '김민준', 'Sales',       'E010', 15, 4),
    ('E002', '이서연', 'Sales',       'E010', 15, 9),
    ('E003', '박지훈', 'Engineering', 'E011', 18, 2);

INSERT INTO vacation_requests
    (request_id, employee_id, start_date, end_date, status, reason)
VALUES
    ('V-1001', 'E002', '2026-09-15', '2026-09-17', 'Approved', '가족 여행'),
    ('V-1002', 'E001', '2026-10-05', '2026-10-06', 'Approved', '개인 사정');
