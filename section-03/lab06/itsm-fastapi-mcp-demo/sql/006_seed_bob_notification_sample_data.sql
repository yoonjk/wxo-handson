-- 개발/데모용 Bob 사용자 예제 데이터입니다.
-- 먼저 sql/005_create_bob_notification_management.sql을 적용하세요.
-- 재실행해도 중복되지 않습니다. 샘플 사용자의 역할/상태와 토큰 값은 이 seed 값으로 갱신됩니다.

INSERT INTO bob_user (employee_no, is_admin, status) VALUES
    ('EMP1001', TRUE, 'active'),
    ('EMP1002', FALSE, 'active'),
    ('EMP1003', FALSE, 'active')
ON DUPLICATE KEY UPDATE is_admin = VALUES(is_admin), status = VALUES(status);

INSERT INTO bob_group (group_name, description) VALUES
    ('operations', 'Operations team notifications'),
    ('payments', 'Payments team notifications'),
    ('managers', 'Manager notifications')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT INTO bob_user_group (employee_no, group_name) VALUES
    ('EMP1001', 'operations'),
    ('EMP1001', 'managers'),
    ('EMP1002', 'operations'),
    ('EMP1003', 'payments')
ON DUPLICATE KEY UPDATE added_at = added_at;

-- SHA-256 hashes only; raw demo tokens are documented in docs/bob_notification_sample_data.md.
INSERT INTO bob_user_token (token_id, employee_no, token_hash, token_last_four, revoked_at) VALUES
    ('738281a9-956a-5146-b6de-fd38b222b469', 'EMP1001', '58501fa825428a9bc31b89e1de77d9c47d016c86674f3b878078d5c4c7157dc1', 'Km8I', NULL),
    ('9d65f922-e8b6-5cca-b712-29c17f544174', 'EMP1002', '0400355fd427c844bb88ceab2a82c56564346434c823a77c40aaea765172265c', 'bHJA', NULL),
    ('d89ef751-904a-529d-b93c-f96a55daffe5', 'EMP1003', '30e1e0b15501ce0635c7f3f76ab5288bd91fa7ffd23d2011bb429e61cd52d8b6', '4Vw8', NULL)
ON DUPLICATE KEY UPDATE employee_no = VALUES(employee_no), token_hash = VALUES(token_hash), token_last_four = VALUES(token_last_four), revoked_at = NULL;
