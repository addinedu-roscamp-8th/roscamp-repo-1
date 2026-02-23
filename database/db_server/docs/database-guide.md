# 데이터베이스 가이드

Sandwich Server 프로젝트의 데이터베이스 사용 가이드입니다.

## 데이터베이스 정보

- **Host**: 192.168.0.27
- **Port**: 5432
- **Database**: pinky_robot_store
- **User**: deepdive
- **Version**: PostgreSQL 16.11 + TimescaleDB

## 접속 방법

### 1. 환경 변수 사용 (권장)

```bash
# .env 파일 로드
source .env

# PostgreSQL 환경 변수 설정
export PGHOST=$DB_HOST
export PGPORT=$DB_PORT
export PGDATABASE=$DB_NAME
export PGUSER=$DB_USER
export PGPASSWORD=$DB_PASSWORD

# 접속
psql
```

### 2. 직접 접속

```bash
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store
```

### 3. 제공된 스크립트 사용

```bash
chmod +x scripts/connect_db.sh
./scripts/connect_db.sh
```

## 테이블 구조

### store_order (주문)

```sql
CREATE TABLE store_order (
    order_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    channel text NOT NULL,
    status text NOT NULL DEFAULT 'placed',
    customer_name text,
    customer_phone text,
    items jsonb NOT NULL,
    currency text,
    total_amount numeric(10, 2),
    payment_status text,
    ordered_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    meta jsonb
);
```

**주요 필드:**
- `order_id`: 주문 UUID
- `channel`: 주문 채널 (pickup, delivery, kiosk, online 등)
- `status`: 주문 상태 (placed, preparing, ready, completed, canceled, refunded)
- `items`: 주문 항목 (JSONB 배열)
- `total_amount`: 총 금액

### store_ingredient_mst (원재료 마스터)

```sql
CREATE TABLE store_ingredient_mst (
    ingredient_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ingredient_sku text UNIQUE NOT NULL,
    ingredient_name text NOT NULL,
    category text NOT NULL,
    base_unit text NOT NULL DEFAULT 'g',
    is_active boolean NOT NULL DEFAULT true,
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

**주요 필드:**
- `ingredient_sku`: 원재료 SKU (예: ING-BREAD-WHEAT)
- `ingredient_name`: 원재료 이름
- `category`: 카테고리 (bread, cheese, veg, meat, sauce 등)
- `base_unit`: 기본 단위 (g, ml, ea)

### store_ingredient_txn (원재료 거래)

```sql
CREATE TABLE store_ingredient_txn (
    ingredient_txn_id uuid NOT NULL DEFAULT gen_random_uuid(),
    ingredient_sku text NOT NULL REFERENCES store_ingredient_mst(ingredient_sku),
    unit text NOT NULL DEFAULT 'g',
    qty_delta numeric(12,3) NOT NULL,
    txn_type text NOT NULL,
    reason text,
    order_id uuid REFERENCES store_order(order_id),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    meta jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (occurred_at, ingredient_txn_id)
);
```

**주요 필드:**
- `ingredient_sku`: 원재료 SKU
- `qty_delta`: 수량 변동 (양수: 입고, 음수: 사용/폐기)
- `txn_type`: 거래 유형 (in, out, waste, adjust)
- `occurred_at`: 발생 시각 (TimescaleDB hypertable)

### store_menu_recipe_bom (메뉴 레시피 BOM)

```sql
CREATE TABLE store_menu_recipe_bom (
    menu_sku text NOT NULL,
    ingredient_sku text NOT NULL REFERENCES store_ingredient_mst(ingredient_sku),
    qty_per_menu numeric(12,3) NOT NULL,
    PRIMARY KEY (menu_sku, ingredient_sku)
);
```

**주요 필드:**
- `menu_sku`: 메뉴 SKU (예: SAND-BMT-15)
- `ingredient_sku`: 원재료 SKU
- `qty_per_menu`: 메뉴당 원재료 수량

### store_inventory_txn (예비 테이블)

```sql
CREATE TABLE store_inventory_txn (
    inventory_txn_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at timestamptz NOT NULL DEFAULT now(),
    sku text NOT NULL,
    display_name text,
    unit text,
    qty_delta numeric(10, 2) NOT NULL,
    txn_type text NOT NULL,
    reason text,
    order_id uuid REFERENCES store_order(order_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    meta jsonb
);
```

**참고**: 이 테이블은 예비 테이블로, 최소한의 REST API만 제공하며 서비스 영역에서는 사용하지 않습니다.

## Continuous Aggregates

TimescaleDB Continuous Aggregates를 사용하여 효율적인 분석 쿼리를 제공합니다.

### cagg_daily_inventory_change

일별 원재료 재고 변동량 집계:

```sql
CREATE MATERIALIZED VIEW cagg_daily_inventory_change
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
```

### cagg_daily_sales_qty

일별 판매량 집계:

```sql
CREATE MATERIALIZED VIEW cagg_daily_sales_qty
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
```

## 뷰 생성 방법

### 스크립트 실행 (권장)

```bash
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -f scripts/create_cagg_views.sql
```

### 권한 부여

```bash
chmod +x scripts/grant_cagg_permissions.sh
./scripts/grant_cagg_permissions.sh deepdive
```

또는 직접 SQL 실행:

```sql
GRANT SELECT ON public.cagg_daily_inventory_change TO deepdive;
GRANT SELECT ON public.cagg_daily_sales_qty TO deepdive;
```

## 주요 쿼리 예시

### 주문 조회

```sql
-- 오늘 완료된 주문
SELECT * FROM store_order
WHERE status = 'completed'
  AND DATE(ordered_at) = CURRENT_DATE
ORDER BY ordered_at DESC;

-- 주문별 총액 합계
SELECT 
    DATE(ordered_at) AS order_date,
    COUNT(*) AS order_count,
    SUM(total_amount) AS total_revenue
FROM store_order
WHERE status = 'completed'
GROUP BY DATE(ordered_at)
ORDER BY order_date DESC;
```

### 원재료 재고 조회

```sql
-- 원재료별 최근 거래
SELECT 
    txn.ingredient_sku,
    mst.ingredient_name,
    SUM(txn.qty_delta) AS net_change
FROM store_ingredient_txn txn
JOIN store_ingredient_mst mst ON txn.ingredient_sku = mst.ingredient_sku
WHERE txn.occurred_at >= NOW() - INTERVAL '30 days'
GROUP BY txn.ingredient_sku, mst.ingredient_name
ORDER BY net_change DESC;
```

### 메뉴 레시피 조회

```sql
-- 특정 메뉴의 레시피
SELECT 
    bom.menu_sku,
    bom.ingredient_sku,
    mst.ingredient_name,
    bom.qty_per_menu,
    mst.base_unit
FROM store_menu_recipe_bom bom
JOIN store_ingredient_mst mst ON bom.ingredient_sku = mst.ingredient_sku
WHERE bom.menu_sku = 'SAND-BMT-15';
```

## 백업 및 복구

### 백업

```bash
# 전체 데이터베이스 백업
pg_dump -h 192.168.0.27 -U deepdive -d pinky_robot_store > backup.sql

# 특정 테이블만 백업
pg_dump -h 192.168.0.27 -U deepdive -d pinky_robot_store -t store_order > orders_backup.sql
```

### 복구

```bash
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store < backup.sql
```

## 문제 해결

### 연결 오류

```bash
# 연결 테스트
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -c "SELECT version();"

# 방화벽 확인
telnet 192.168.0.27 5432
```

### 권한 오류

```sql
-- 현재 사용자 확인
SELECT current_user;

-- 테이블 권한 확인
SELECT * FROM information_schema.table_privileges 
WHERE grantee = 'deepdive';
```

### 성능 최적화

```sql
-- 인덱스 확인
SELECT * FROM pg_indexes WHERE tablename = 'store_order';

-- 쿼리 실행 계획 확인
EXPLAIN ANALYZE SELECT * FROM store_order WHERE status = 'completed';
```

## 참고 자료

- [PostgreSQL 공식 문서](https://www.postgresql.org/docs/)
- [TimescaleDB 문서](https://docs.timescale.com/)
- [프로젝트 README](../README.md)

