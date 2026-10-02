-- 재실행 시 기존 샘플을 덮어쓰지 않습니다. 예시 키는 SR-900001 이후입니다.
USE demo;
INSERT IGNORE INTO itsm_service_requests
    (id, title, description, service_name, environment, severity, status, requester, assignee, worklog)
VALUES
    (900001, '결제 API 간헐적 500 오류', '최근 배포 이후 결제 요청 일부가 500으로 실패합니다. correlation ID와 오류 시각을 확인해 주세요.', 'payments-api', 'production', 'HIGH', 'NEW', 'demo.user', 'payments.oncall', ''),
    (900002, '주문 조회 API 응답 지연 개선', 'p95 응답 시간이 4초를 넘어 인덱스와 쿼리 실행 계획 검토가 필요합니다.', 'orders-api', 'production', 'MEDIUM', 'IN_PROGRESS', 'service.desk', 'orders.team', '[2026-09-30 09:10 UTC] orders.team: slow query와 실행 계획을 확인 중입니다.'),
    (900003, '인증 캐시 만료 처리 수정', '만료 시점에 인증 요청 일부가 401로 실패합니다. 재현 테스트와 코드 수정이 필요합니다.', 'identity-api', 'production', 'HIGH', 'RESOLVED', 'app.support', 'identity.team', '[2026-09-30 08:30 UTC] identity.team: 수정 배포 후 smoke test 통과, 관찰 중입니다.'),
    (900004, '개발 배치 날짜 파라미터 보완', '테스트 배치가 날짜 경계에서 입력값 오류로 종료됩니다.', 'batch-service', 'development', 'LOW', 'CLOSED', 'batch.operator', 'batch.team', '[2026-09-29 23:45 UTC] batch.team: 수정 배포와 재실행 확인 후 종료했습니다.'),
    (900005, '재고 동기화 누락 복구', '일부 SKU 수량이 외부 시스템과 다릅니다. 재처리 범위와 정합성 검증이 필요합니다.', 'inventory-sync', 'production', 'CRITICAL', 'NEW', 'inventory.monitor', 'integration.oncall', '');
