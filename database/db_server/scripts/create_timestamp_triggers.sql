-- Timestamp 보호 트리거 생성 스크립트
-- ordered_at 변경 방지 및 updated_at 자동 갱신 보장
-- 실행 방법: psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -f scripts/create_timestamp_triggers.sql

-- 1. ordered_at 변경 방지 트리거 함수
CREATE OR REPLACE FUNCTION prevent_ordered_at_update()
RETURNS TRIGGER AS $$
BEGIN
    -- ordered_at이 변경되려고 하면 에러 발생
    IF OLD.ordered_at IS DISTINCT FROM NEW.ordered_at THEN
        RAISE EXCEPTION 'ordered_at cannot be modified after creation. Original: %, Attempted: %', 
            OLD.ordered_at, NEW.ordered_at;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. updated_at 자동 갱신 보장 트리거 함수
CREATE OR REPLACE FUNCTION ensure_updated_at_current()
RETURNS TRIGGER AS $$
BEGIN
    -- updated_at을 항상 현재 시간으로 설정 (onupdate가 작동하지 않는 경우 대비)
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. 트리거 생성
-- ordered_at 변경 방지 트리거
DROP TRIGGER IF EXISTS check_ordered_at_update ON store_order;
CREATE TRIGGER check_ordered_at_update
BEFORE UPDATE ON store_order
FOR EACH ROW
EXECUTE FUNCTION prevent_ordered_at_update();

-- updated_at 자동 갱신 보장 트리거
DROP TRIGGER IF EXISTS ensure_updated_at_current ON store_order;
CREATE TRIGGER ensure_updated_at_current
BEFORE UPDATE ON store_order
FOR EACH ROW
EXECUTE FUNCTION ensure_updated_at_current();

-- 4. 트리거 확인
SELECT 
    trigger_name,
    event_manipulation,
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE event_object_table = 'store_order'
ORDER BY trigger_name;

-- 5. 테스트 (선택사항)
-- 다음 명령으로 테스트할 수 있습니다:
-- 
-- -- ordered_at 변경 시도 (에러 발생해야 함)
-- UPDATE store_order 
-- SET ordered_at = NOW() 
-- WHERE order_id = 'some-uuid';
-- 
-- -- updated_at 자동 갱신 확인
-- SELECT order_id, ordered_at, updated_at FROM store_order WHERE order_id = 'some-uuid';
-- UPDATE store_order SET status = 'completed' WHERE order_id = 'some-uuid';
-- SELECT order_id, ordered_at, updated_at FROM store_order WHERE order_id = 'some-uuid';
-- -- updated_at이 갱신되었는지 확인

