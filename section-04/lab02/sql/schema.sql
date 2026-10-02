CREATE TABLE IF NOT EXISTS products (
    sku VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    unit_price DECIMAL(15, 2) NOT NULL,
    description TEXT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (sku),
    INDEX ix_products_active (active)
) ;

INSERT INTO products (sku, name, unit_price, description, active)
VALUES
    ('NOTEBOOK', '노트북', 1200000.00, '개발용 노트북', TRUE),
    ('MONITOR', '모니터', 300000.00, '업무용 모니터', TRUE),
    ('KEYBOARD', '키보드', 100000.00, '업무용 키보드', TRUE)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    unit_price = VALUES(unit_price),
    description = VALUES(description),
    active = VALUES(active);

CREATE TABLE IF NOT EXISTS purchase_requests (
    id BIGINT NOT NULL AUTO_INCREMENT,
    purchase_type VARCHAR(50) NOT NULL,
    requester VARCHAR(100) NOT NULL,
    total_amount DECIMAL(15, 2) NOT NULL,
    reason TEXT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    approver_role VARCHAR(100) NULL,
    approval_comment TEXT NULL,
    approved_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_purchase_requests_type (purchase_type),
    INDEX ix_purchase_requests_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
