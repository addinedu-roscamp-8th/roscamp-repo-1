-- Timestamp 데이터 정리 스크립트
-- ordered_at > updated_at인 데이터를 수정
-- 실행 방법: psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -f scripts/fix_timestamp_data.sql

-- 1. 문제가 있는 데이터 확인
SELECT 
    order_id,
    ordered_at,
    updated_at,
    (ordered_at - updated_at) AS time_diff
FROM store_order
WHERE updated_at < ordered_at
ORDER BY ordered_at DESC;

-- 2. 데이터 수정: updated_at이 ordered_at보다 작은 경우, updated_at을 ordered_at으로 설정
-- (최소한 ordered_at과 같거나 더 크도록 보장)
UPDATE store_order
SET updated_at = ordered_at
WHERE updated_at < ordered_at;

-- 3. 수정 결과 확인
SELECT 
    COUNT(*) AS fixed_count,
    MIN(ordered_at) AS min_ordered_at,
    MAX(ordered_at) AS max_ordered_at,
    MIN(updated_at) AS min_updated_at,
    MAX(updated_at) AS max_updated_at
FROM store_order
WHERE updated_at < ordered_at;

-- 4. 최종 검증: 문제가 있는 데이터가 없는지 확인
SELECT COUNT(*) AS remaining_issues
FROM store_order
WHERE updated_at < ordered_at;

-- 결과가 0이면 정상

