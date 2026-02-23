# Sandwich Server

음식 판매점의 주문(store_order), 원재료 관리(store_ingredient_mst/txn), 메뉴 레시피(store_menu_recipe_bom)를 관리하는 Flask REST API 서버입니다.

**참고**: `store_inventory_txn` 테이블은 예비 테이블로, 최소한의 REST API만 제공하며 서비스 영역(대시보드, 분석 등)에서는 사용하지 않습니다.

## 기술 스택

- **Framework**: Flask 3.0.0
- **Database**: PostgreSQL 16.11 + TimescaleDB
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **API Documentation**: Flasgger (Swagger UI)
- **Python**: 3.8+

## 프로젝트 구조

```
sandwich_server/
├── app/
│   ├── __init__.py          # Flask 앱 팩토리
│   ├── config.py            # 설정 관리
│   ├── db.py                # DB 연결
│   ├── models.py            # SQLAlchemy 모델
│   ├── routes/              # API 라우트
│   │   ├── health.py        # 헬스체크
│   │   ├── orders.py        # 주문 API
│   │   ├── orders_ui.py     # 주문 관리 UI
│   │   ├── inventory.py     # 재고 API (예비, 최소 기능)
│   │   ├── ingredients.py   # 원재료 관리 API
│   │   ├── menu_recipe.py   # 메뉴 레시피 API
│   │   ├── analytics.py      # 분석 API
│   │   └── dashboard.py     # 대시보드 API
│   ├── services/            # 비즈니스 로직
│   │   ├── order_service.py
│   │   └── analytics_service.py
│   └── templates/           # 웹 UI 템플릿
│       ├── dashboard.html
│       └── orders.html
├── migrations/              # Alembic 마이그레이션
├── scripts/                 # 유틸리티 스크립트
│   ├── connect_db.sh
│   ├── grant_cagg_permissions.sh
│   └── create_cagg_views.sql
├── tests/                   # 테스트
├── run.py                   # 실행 스크립트
├── requirements.txt
├── alembic.ini
├── env.example              # 환경 변수 예시
└── README.md
```

## 설치 및 설정

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 내용을 설정하세요:

```bash
cp env.example .env
```

`.env` 파일 내용:
```
DB_HOST=192.168.0.27
DB_PORT=5432
DB_NAME=pinky_robot_store
DB_USER=deepdive
DB_PASSWORD=your_password_here
FLASK_ENV=development
FLASK_DEBUG=True
```

### 3. 데이터베이스 설정

PostgreSQL과 TimescaleDB가 설치되어 있어야 합니다. 데이터베이스 스키마는 이미 존재한다고 가정합니다:

**주요 테이블:**
- `store_order` - 주문 정보
- `store_ingredient_mst` - 원재료 마스터
- `store_ingredient_txn` - 원재료 거래 이벤트 (hypertable)
- `store_menu_recipe_bom` - 메뉴 레시피 BOM
- `store_inventory_txn` - 재고 거래 이벤트 (예비 테이블, 최소 기능만 제공)

**Continuous Aggregates (선택사항):**
- `cagg_daily_inventory_change` - 일별 재고 변동량 집계
- `cagg_daily_sales_qty` - 일별 판매량 집계

> **참고**: Continuous aggregates가 없어도 서버는 정상 작동하지만, 분석 API는 사용할 수 없습니다. 뷰 생성 스크립트는 `scripts/create_cagg_views.sql`을 참고하세요.

#### Continuous Aggregates 권한 설정

Continuous aggregates 뷰에 대한 SELECT 권한이 필요합니다. 뷰 소유자 또는 슈퍼유저로 다음 명령을 실행하세요:

**로컬 환경:**
```sql
-- 뷰 소유자 확인
SELECT view_name, view_owner 
FROM timescaledb_information.continuous_aggregates 
WHERE view_name IN ('cagg_daily_inventory_change', 'cagg_daily_sales_qty');

-- 권한 부여 (뷰 소유자 또는 슈퍼유저로 실행)
GRANT SELECT ON public.cagg_daily_inventory_change TO <your_db_user>;
GRANT SELECT ON public.cagg_daily_sales_qty TO <your_db_user>;
```

**AWS 환경 (RDS/EC2):**

1. **EC2 인스턴스에서 PostgreSQL 접속:**
```bash
# EC2 인스턴스에 SSH 접속
ssh -i your-key.pem ec2-user@your-ec2-instance-ip

# PostgreSQL 클라이언트 설치 (필요한 경우)
sudo yum install postgresql15 -y  # Amazon Linux 2
# 또는
sudo apt-get install postgresql-client -y  # Ubuntu

# PostgreSQL 접속 (슈퍼유저 또는 뷰 소유자로)
# 방법 1: 기본 postgres 데이터베이스로 접속
psql -h 192.168.0.27 -U postgres -d postgres

# 방법 2: 실제 데이터베이스로 직접 접속
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store

# 방법 3: RDS의 경우
psql -h your-rds-endpoint.region.rds.amazonaws.com -U postgres -d pinky_robot_store

# 방법 4: 환경 변수 사용 (.env 파일이 있는 경우)
source .env  # 또는
export PGHOST=${DB_HOST:-192.168.0.27}
export PGPORT=${DB_PORT:-5432}
export PGDATABASE=${DB_NAME:-pinky_robot_store}
export PGUSER=${DB_USER:-deepdive}
psql  # 이제 데이터베이스 이름이 자동으로 설정됨
```

2. **psql에서 권한 설정:**
```sql
-- 현재 사용자 확인
SELECT current_user;

-- 뷰 소유자 확인
SELECT view_name, view_owner 
FROM timescaledb_information.continuous_aggregates 
WHERE view_name IN ('cagg_daily_inventory_change', 'cagg_daily_sales_qty');

-- 슈퍼유저(postgres) 또는 뷰 소유자로 권한 부여
-- (deepdive 사용자가 이미 기본 사용자이므로 필요시에만 실행)
GRANT SELECT ON public.cagg_daily_inventory_change TO deepdive;
GRANT SELECT ON public.cagg_daily_sales_qty TO deepdive;

-- 권한 확인
\dp public.cagg_daily_inventory_change
\dp public.cagg_daily_sales_qty

-- 종료
\q
```

3. **AWS RDS의 경우 (psql 없이):**
```bash
# AWS CLI를 사용하여 RDS에 접속 (SSM Session Manager 사용)
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,Endpoint.Address]' --output table

# 또는 RDS Proxy를 통해 접속
psql -h your-rds-proxy-endpoint.proxy-xxx.region.rds.amazonaws.com -U postgres -d pinky_robot_store
```

4. **환경 변수 사용 (권장):**
```bash
# .env 파일의 DB 정보 사용
export PGHOST=$(grep DB_HOST .env | cut -d '=' -f2)
export PGPORT=$(grep DB_PORT .env | cut -d '=' -f2)
export PGDATABASE=$(grep DB_NAME .env | cut -d '=' -f2)
export PGUSER=postgres  # 슈퍼유저 또는 뷰 소유자

# psql 접속 (비밀번호 입력 요청됨)
psql

# 또는 비밀번호를 환경 변수로 설정
export PGPASSWORD=$(grep DB_PASSWORD .env | cut -d '=' -f2)
psql
```

5. **한 번에 실행 (스크립트):**
```bash
# grant_permissions.sh 파일 생성
cat > grant_permissions.sh << 'EOF'
#!/bin/bash
PGHOST=${DB_HOST:-192.168.0.27}
PGPORT=${DB_PORT:-5432}
PGDATABASE=${DB_NAME:-pinky_robot_store}
PGUSER=${DB_ADMIN_USER:-postgres}

psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE << SQL
-- 뷰 소유자 확인
SELECT view_name, view_owner 
FROM timescaledb_information.continuous_aggregates 
WHERE view_name IN ('cagg_daily_inventory_change', 'cagg_daily_sales_qty');

-- 권한 부여
GRANT SELECT ON public.cagg_daily_inventory_change TO deepdive;
GRANT SELECT ON public.cagg_daily_sales_qty TO deepdive;

-- 권한 확인
\dp public.cagg_daily_inventory_change
\dp public.cagg_daily_sales_qty
SQL
EOF

chmod +x grant_permissions.sh
./grant_permissions.sh
```

**주의사항:**
- RDS의 경우 기본적으로 `postgres` 사용자가 슈퍼유저입니다
- RDS에서는 일부 슈퍼유저 권한이 제한될 수 있으므로, 뷰 소유자로 권한을 부여하는 것이 더 안전합니다
- 보안 그룹에서 PostgreSQL 포트(5432)가 열려있는지 확인하세요

### 4. 마이그레이션 (선택사항)

테이블이 이미 존재하는 경우 마이그레이션은 필요하지 않습니다. 새로 생성해야 하는 경우:

```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## 실행

```bash
python run.py
```

서버가 `http://192.168.0.27:5000`에서 실행됩니다.

### 웹 대시보드

서브웨이 스타일의 웹 대시보드를 제공합니다:

```
http://192.168.0.27:5000/dashboard
```

대시보드 기능:
- 📊 실시간 통계 (총 주문, 오늘 주문, 오늘 매출, 주문 상태)
- 📋 최근 주문 목록 (페이징 지원)
- 📦 원재료 재고 현황 (최근 30일 입고/사용 요약)
- 🏆 인기 상품 TOP 5 (최근 30일 판매량 기준, continuous aggregate 필요)
- 🔄 자동 새로고침 (30초 간격)

### 주문 관리 UI

주문 생성, 조회, 상태 관리가 가능한 웹 UI:

```
http://192.168.0.27:5000/orders-ui
```

주문 관리 기능:
- 📋 주문 목록 조회 (테이블 형태)
- 🔍 검색 기능 (고객명, 전화번호, 주문ID)
- 🏷️ 상태별 필터링 (전체, 주문접수, 준비중, 준비완료, 완료, 취소)
- ➕ 새 주문 생성 (모달 폼)
- 👁️ 주문 상세 보기
- ✅ 주문 상태 변경 (완료, 취소)
- 📄 페이징 지원

## API 문서화 (Swagger)

Swagger UI를 통해 API를 시각적으로 탐색하고 테스트할 수 있습니다.

### Swagger UI 접속

서버 실행 후 다음 URL로 접속하세요:

```
http://192.168.0.27:5000/api-docs
```

### API 스펙 (JSON)

OpenAPI 스펙은 다음 URL에서 확인할 수 있습니다:

```
http://192.168.0.27:5000/apispec.json
```

Swagger UI에서:
- 모든 API 엔드포인트를 확인할 수 있습니다
- 각 엔드포인트의 요청/응답 스키마를 확인할 수 있습니다
- "Try it out" 기능으로 직접 API를 테스트할 수 있습니다

## API 엔드포인트

### 헬스체크

#### GET /health
서버 상태 확인

**응답:**
```json
{
  "status": "ok"
}
```

#### GET /db/status
TimescaleDB 상태 확인

**응답:**
```json
{
  "jobs": [...],
  "continuous_aggregates": [...]
}
```

### 주문 API

#### POST /orders
주문 생성

**요청 본문:**
```json
{
  "channel": "online",
  "customer_name": "홍길동",
  "customer_phone": "010-1234-5678",
  "items": [
    {
      "sku": "SANDWICH-001",
      "name": "치킨 샌드위치",
      "qty": 2,
      "unit": "개",
      "unit_price": 5000
    }
  ],
  "currency": "KRW",
  "total_amount": 10000,
  "payment_status": "paid",
  "meta": {}
}
```

**응답:**
```json
{
  "order_id": "uuid",
  "status": "placed",
  "channel": "online",
  "ordered_at": "2024-01-01T00:00:00"
}
```

#### GET /orders
주문 목록 조회

**쿼리 파라미터:**
- `status`: 주문 상태 필터
- `from`: 시작 날짜 (ISO 8601)
- `to`: 종료 날짜 (ISO 8601)
- `limit`: 페이지 크기 (기본값: 50)
- `offset`: 오프셋 (기본값: 0)

#### GET /orders/<order_id>
주문 상세 조회

#### PATCH /orders/<order_id>/status
주문 상태 업데이트

**요청 본문:**
```json
{
  "status": "completed"
}
```

**응답:**
```json
{
  "order_id": "uuid",
  "old_status": "placed",
  "new_status": "completed",
  "updated_at": "2024-01-01T00:00:00"
}
```

**참고**: `store_inventory_txn`은 예비 테이블이므로 주문 완료 시 자동 재고 이벤트 생성 기능은 비활성화되어 있습니다. 필요시 `/inventory/txn` API를 직접 호출하여 수동으로 생성할 수 있습니다.

### 재고 API (예비 테이블 - 최소 기능만 제공)

> **주의**: `store_inventory_txn`은 예비 테이블입니다. 서비스 영역(대시보드, 분석 등)에서는 사용하지 않으며, 최소한의 REST API만 제공합니다.

#### POST /inventory/txn
재고 이벤트 생성 (예비 기능)

**요청 본문:**
```json
{
  "sku": "SANDWICH-001",
  "display_name": "치킨 샌드위치",
  "unit": "개",
  "qty_delta": -5,
  "txn_type": "out",
  "reason": "판매 출고",
  "occurred_at": "2024-01-01T00:00:00",
  "meta": {}
}
```

**txn_type:**
- `in`: 입고 (양수 권장)
- `out`: 출고 (음수 권장, 양수 입력 시 자동 변환)
- `waste`: 폐기 (음수 권장, 양수 입력 시 자동 변환)
- `adjust`: 조정 (양수/음수 가능)
- `return`: 반품

#### GET /inventory/txn
재고 이벤트 목록 조회

**쿼리 파라미터:**
- `sku`: SKU 필터
- `txn_type`: 거래 유형 필터
- `from`: 시작 날짜
- `to`: 종료 날짜
- `limit`: 페이지 크기
- `offset`: 오프셋

### 원재료 관리 API

#### GET /ingredients
원재료 마스터 목록 조회

**쿼리 파라미터:**
- `category`: 카테고리 필터 (bread/cheese/veg/meat/sauce/etc)
- `is_active`: 활성 상태 필터 (true/false)
- `limit`: 페이지 크기
- `offset`: 오프셋

#### GET /ingredients/<ingredient_sku>
원재료 상세 조회

#### POST /ingredients
원재료 생성

**요청 본문:**
```json
{
  "ingredient_sku": "ING-BREAD-WHEAT",
  "ingredient_name": "Wheat Bread",
  "category": "bread",
  "base_unit": "g",
  "is_active": true,
  "meta": {}
}
```

#### PATCH /ingredients/<ingredient_sku>
원재료 수정

#### DELETE /ingredients/<ingredient_sku>
원재료 삭제 (또는 비활성화)

**쿼리 파라미터:**
- `hard_delete`: true면 실제 삭제, false면 is_active=false로 설정 (기본값: false)

#### POST /ingredients/txn
원재료 거래 이벤트 생성

**요청 본문:**
```json
{
  "ingredient_sku": "ING-BREAD-WHEAT",
  "qty_delta": -50,
  "txn_type": "out",
  "reason": "주문 생산 사용",
  "order_id": "uuid",
  "occurred_at": "2024-01-01T00:00:00Z",
  "meta": {}
}
```

#### GET /ingredients/txn
원재료 거래 이벤트 목록 조회

**쿼리 파라미터:**
- `ingredient_sku`: 원재료 SKU 필터
- `txn_type`: 거래 유형 필터 (in/out/waste/adjust)
- `from`: 시작 날짜
- `to`: 종료 날짜
- `limit`: 페이지 크기
- `offset`: 오프셋

### 메뉴 레시피 API

#### GET /menu-recipe/<menu_sku>
메뉴 레시피 조회

**응답:**
```json
{
  "menu_sku": "SAND-BMT-15",
  "recipe": [
    {
      "ingredient_sku": "ING-BREAD-WHEAT",
      "ingredient_name": "Wheat Bread",
      "qty_per_menu": 100,
      "unit": "g"
    }
  ]
}
```

#### POST /menu-recipe
메뉴 레시피 생성/업데이트

**요청 본문:**
```json
{
  "menu_sku": "SAND-BMT-15",
  "recipe": [
    {
      "ingredient_sku": "ING-BREAD-WHEAT",
      "qty_per_menu": 100
    },
    {
      "ingredient_sku": "ING-CHEESE-AMERICAN",
      "qty_per_menu": 30
    }
  ]
}
```

#### DELETE /menu-recipe/<menu_sku>
메뉴 레시피 전체 삭제

#### DELETE /menu-recipe/<menu_sku>/<ingredient_sku>
레시피 항목 삭제

#### GET /menu-recipe/list
모든 메뉴 레시피 목록 조회

**쿼리 파라미터:**
- `limit`: 페이지 크기
- `offset`: 오프셋

### 분석 API

#### GET /analytics/daily/inventory-change
일별 재고 변동량 조회 (cagg_daily_inventory_change 활용)

**쿼리 파라미터:**
- `sku`: SKU 필터 (선택)
- `from`: 시작 날짜 (기본값: 30일 전)
- `to`: 종료 날짜 (기본값: 현재)

#### GET /analytics/daily/sales
일별 판매량 조회 (cagg_daily_sales_qty 활용)

**쿼리 파라미터:**
- `sku`: SKU 필터 (선택)
- `from`: 시작 날짜 (기본값: 30일 전)
- `to`: 종료 날짜 (기본값: 현재)

#### GET /analytics/top-sales
TOP 판매 상품 조회

**쿼리 파라미터:**
- `days`: 기간 (기본값: 30일)
- `limit`: 상위 N개 (기본값: 20)

## 샘플 요청

### 1. 주문 생성
```bash
curl -X POST http://192.168.0.27:5000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "online",
    "customer_name": "홍길동",
    "items": [
      {
        "sku": "SANDWICH-001",
        "name": "치킨 샌드위치",
        "qty": 2,
        "unit": "개",
        "unit_price": 5000
      }
    ],
    "total_amount": 10000,
    "payment_status": "paid"
  }'
```

### 2. 주문 완료 처리
```bash
ORDER_ID="<위에서 받은 order_id>"
curl -X PATCH http://192.168.0.27:5000/orders/$ORDER_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### 3. 분석 조회
```bash
# 일별 재고 변동량
curl "http://192.168.0.27:5000/analytics/daily/inventory-change?from=2024-01-01&to=2024-01-31"

# 일별 판매량
curl "http://192.168.0.27:5000/analytics/daily/sales?from=2024-01-01&to=2024-01-31"

# TOP 판매 상품
curl "http://192.168.0.27:5000/analytics/top-sales?days=30&limit=10"
```

## 테스트

```bash
pytest tests/
```

## 문서

프로젝트 문서는 `docs/` 폴더에 체계적으로 정리되어 있습니다:

- **[문서 인덱스](docs/README.md)** - 모든 문서의 목차 및 빠른 시작 가이드
- **[개발 현황](docs/development-status.md)** - 현재 프로젝트의 개발 현황 및 기능 목록
- **[데이터베이스 가이드](docs/database-guide.md)** - DB 접속, 테이블 구조, 쿼리 방법
- **[서버 사용 가이드](docs/server-guide.md)** - 서버 실행, 환경 설정, 웹 UI 사용법
- **[API 레퍼런스](docs/api-reference.md)** - 모든 REST API 엔드포인트 상세 설명
- **[인프라 가이드](docs/infrastructure.md)** - 환경 설정, DB 접속, 문제 해결

## 주요 기능

### 트랜잭션 및 멱등성

- 주문 상태 업데이트 시 `SELECT ... FOR UPDATE`를 사용하여 주문 row를 잠금 처리합니다.
- 트랜잭션을 통한 안전한 상태 변경을 보장합니다.
- 다중 요청/재시도에도 안전합니다.

**참고**: `store_inventory_txn`은 예비 테이블이므로 주문 완료 시 자동 재고 이벤트 생성 기능은 비활성화되어 있습니다.

### TimescaleDB 연동

- Continuous aggregates를 활용한 효율적인 분석 쿼리
- Hypertable 기반의 시계열 데이터 관리
- 자동 갱신 정책 지원

## 라이선스

MIT

