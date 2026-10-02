-- Bob 사용자/token/group 관리와 공지 대상·읽음 상태를 저장합니다.
-- FastAPI 시작 시 SQLAlchemy create_all로 생성할 수도 있습니다.

CREATE TABLE IF NOT EXISTS bob_user (
    employee_no VARCHAR(32) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (employee_no),
    KEY ix_bob_user_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bob_user_token (
    token_id CHAR(36) NOT NULL,
    employee_no VARCHAR(32) NOT NULL,
    token_hash CHAR(64) NOT NULL,
    token_last_four CHAR(4) NOT NULL,
    issued_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at DATETIME NULL,
    PRIMARY KEY (token_id),
    UNIQUE KEY uq_bob_user_token_hash (token_hash),
    KEY ix_bob_user_token_employee_no (employee_no),
    CONSTRAINT fk_bob_user_token_user FOREIGN KEY (employee_no)
        REFERENCES bob_user (employee_no) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bob_group (
    group_name VARCHAR(64) NOT NULL,
    description VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bob_user_group (
    employee_no VARCHAR(32) NOT NULL,
    group_name VARCHAR(64) NOT NULL,
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (employee_no, group_name),
    KEY ix_bob_user_group_group_name (group_name),
    CONSTRAINT fk_bob_user_group_user FOREIGN KEY (employee_no)
        REFERENCES bob_user (employee_no) ON DELETE CASCADE,
    CONSTRAINT fk_bob_user_group_group FOREIGN KEY (group_name)
        REFERENCES bob_group (group_name) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notification (
    notification_id CHAR(36) NOT NULL,
    request_id VARCHAR(64) NULL,
    message VARCHAR(200) NOT NULL,
    link_url TEXT NULL,
    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(32) NOT NULL,
    PRIMARY KEY (notification_id),
    KEY ix_notification_created_by (created_by),
    CONSTRAINT fk_notification_created_by FOREIGN KEY (created_by)
        REFERENCES bob_user (employee_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notification_target (
    target_id CHAR(36) NOT NULL,
    notification_id CHAR(36) NOT NULL,
    target_type VARCHAR(16) NOT NULL,
    target_value VARCHAR(64) NULL,
    PRIMARY KEY (target_id),
    KEY ix_notification_target_notification_id (notification_id),
    CONSTRAINT fk_notification_target_notification FOREIGN KEY (notification_id)
        REFERENCES notification (notification_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notification_receipt (
    notification_id CHAR(36) NOT NULL,
    employee_no VARCHAR(32) NOT NULL,
    delivered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at DATETIME NULL,
    PRIMARY KEY (notification_id, employee_no),
    KEY ix_notification_receipt_employee_read (employee_no, read_at),
    CONSTRAINT fk_notification_receipt_notification FOREIGN KEY (notification_id)
        REFERENCES notification (notification_id) ON DELETE CASCADE,
    CONSTRAINT fk_notification_receipt_user FOREIGN KEY (employee_no)
        REFERENCES bob_user (employee_no) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
