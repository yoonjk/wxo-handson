-- ---------------------------------------------------------------------------
-- Banking demo schema + seed data
-- Matches the mock data that used to be hardcoded in banking_tools.py
--
-- Run against the "demo" database, e.g.:
--   mysql -u nexweb -p -h nexweb.ddnsgeek.com -P 13306 demo < schema.sql
-- ---------------------------------------------------------------------------

-- identifier(고객명/고객번호)와 account_id는 N:1이 아니라 N:M 관계입니다.
-- 즉 한 identifier(예: alice)가 여러 계좌(체크/저축 등)를 가질 수 있으므로
-- identifier 단독 PK가 아니라 (identifier, account_id) 복합 PK로 둡니다.
CREATE TABLE IF NOT EXISTS customers (
    identifier  VARCHAR(64)  NOT NULL,
    account_id  VARCHAR(32)  NOT NULL,
    PRIMARY KEY (identifier, account_id),
    INDEX idx_identifier (identifier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- 마이그레이션: customers 테이블이 이미 예전 스키마(identifier 단독 PK)로
-- 생성되어 있는 환경이라면, 위 CREATE TABLE IF NOT EXISTS는 아무 효과가
--없습니다 (테이블이 이미 존재하므로 건너뜀). 그런 경우 아래를 대신 실행해
-- 복합 PK로 바꿔주세요.
--
--   ALTER TABLE customers DROP PRIMARY KEY;
--   ALTER TABLE customers ADD PRIMARY KEY (identifier, account_id);
--   ALTER TABLE customers ADD INDEX idx_identifier (identifier);
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS accounts (
    account_id         VARCHAR(32)   NOT NULL PRIMARY KEY,
    currency           VARCHAR(8)    NOT NULL,
    available_balance  DECIMAL(18,2) NOT NULL,
    ledger_balance     DECIMAL(18,2) NOT NULL,
    email              VARCHAR(255)  NULL,
    phone              VARCHAR(32)   NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS transactions (
    txn_id       VARCHAR(32)   NOT NULL PRIMARY KEY,
    account_id   VARCHAR(32)   NOT NULL,
    txn_date     DATE          NOT NULL,
    txn_type     VARCHAR(16)   NOT NULL,
    amount       DECIMAL(18,2) NOT NULL,
    description  VARCHAR(255)  NULL,
    INDEX idx_account_date (account_id, txn_date),
    CONSTRAINT fk_txn_account FOREIGN KEY (account_id) REFERENCES accounts(account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS branches (
    branch_query  VARCHAR(64)  NOT NULL PRIMARY KEY,  -- lowercase city/name
    branch_code   VARCHAR(16)  NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS transfers (
    transaction_id  VARCHAR(32)   NOT NULL PRIMARY KEY,
    from_account    VARCHAR(32)   NOT NULL,
    to_account      VARCHAR(32)   NOT NULL,
    amount          DECIMAL(18,2) NOT NULL,
    currency        VARCHAR(8)    NOT NULL,
    status          VARCHAR(16)   NOT NULL,
    reference       VARCHAR(255)  NULL,
    created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- Seed data (mirrors the original mock dictionaries)
-- ---------------------------------------------------------------------------

INSERT INTO accounts (account_id, currency, available_balance, ledger_balance, email, phone) VALUES
    ('ACC10001', 'USD', 12500.75, 12750.75, NULL, NULL),
    ('ACC10002', 'USD',   320.50,   320.50, NULL, NULL),
    ('ACC10003', 'EUR',  9800.00,  9800.00, NULL, NULL),
    ('ACC10004', 'USD',  4200.00,  4200.00, NULL, NULL)
ON DUPLICATE KEY UPDATE currency = VALUES(currency);

-- alice는 계좌를 2개(ACC10001 체크, ACC10004 저축) 보유한 예시로,
-- "한 고객이 여러 계좌를 가진 경우"를 재현/테스트하기 위한 시드입니다.
INSERT INTO customers (identifier, account_id) VALUES
    ('alice',    'ACC10001'),
    ('alice',    'ACC10004'),
    ('bob',      'ACC10002'),
    ('cust-555', 'ACC10003')
ON DUPLICATE KEY UPDATE account_id = VALUES(account_id);

INSERT INTO transactions (txn_id, account_id, txn_date, txn_type, amount, description) VALUES
    ('T1001', 'ACC10001', '2025-10-01', 'debit',   -50.00, 'Coffee Shop'),
    ('T1002', 'ACC10001', '2025-09-28', 'credit', 1500.00, 'Payroll'),
    ('T1003', 'ACC10001', '2025-09-15', 'debit',  -200.00, 'Electric Bill'),
    ('T2001', 'ACC10002', '2025-10-02', 'debit',   -20.00, 'Lunch'),
    ('T4001', 'ACC10004', '2025-09-20', 'credit',  300.00, 'Savings Deposit')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT INTO branches (branch_query, branch_code) VALUES
    ('new york',      'BR001'),
    ('san francisco', 'BR002'),
    ('chennai',       'BR003'),
    ('london',        'BR004')
ON DUPLICATE KEY UPDATE branch_code = VALUES(branch_code);