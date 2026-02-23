-- TimescaleDB Continuous Aggregates 생성 스크립트
-- 실행 방법: psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -f create_cagg_views.sql

-- 1. 일별 원재료 재고 변동량 집계 뷰 (store_ingredient_txn 기반)
-- 주의: store_inventory_txn은 예비 테이블이므로 store_ingredient_txn을 기반으로 생성
CREATE MATERIALIZED VIEW IF NOT EXISTS cagg_daily_inventory_change
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', txn.occurred_at) AS day,
    txn.ingredient_sku AS sku,
    mst.ingredient_name AS display_name,
    txn.unit,
    SUM(txn.qty_delta) AS net_qty_change
FROM store_ingredient_txn txn
LEFT JOIN store_ingredient_mst mst ON txn.ingredient_sku = mst.ingredient_sku
GROUP BY day, txn.ingredient_sku, mst.ingredient_name, txn.unit;

-- 2. 일별 판매량 집계 뷰 (store_order 기반)
-- 주의: store_inventory_txn은 예비 테이블이므로 store_order를 기반으로 생성
CREATE MATERIALIZED VIEW IF NOT EXISTS cagg_daily_sales_qty
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', ordered_at) AS day,
    item->>'sku' AS sku,
    item->>'name' AS display_name,
    COALESCE(item->>'unit', 'ea') AS unit,
    SUM((item->>'qty')::numeric) AS sold_qty
FROM store_order,
     LATERAL jsonb_array_elements(items) AS item
WHERE status = 'completed'
GROUP BY day, item->>'sku', item->>'name', COALESCE(item->>'unit', 'ea');

-- 자동 갱신 정책 추가 (선택사항)
-- 최근 7일 데이터는 5분마다 갱신, 나머지는 1시간마다 갱신
SELECT add_continuous_aggregate_policy('cagg_daily_inventory_change',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => true
);

SELECT add_continuous_aggregate_policy('cagg_daily_sales_qty',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => true
);

-- 권한 부여 (필요한 사용자에게)
-- GRANT SELECT ON public.cagg_daily_inventory_change TO deepdive;
-- GRANT SELECT ON public.cagg_daily_sales_qty TO deepdive;

