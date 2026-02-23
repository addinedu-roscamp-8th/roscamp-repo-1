# API 레퍼런스

Sandwich Server의 모든 REST API 엔드포인트 상세 설명입니다.

**Swagger UI**: http://192.168.0.27:5000/api-docs (인터랙티브 API 문서)

## 기본 정보

- **Base URL**: `http://192.168.0.27:5000`
- **Content-Type**: `application/json`
- **API 버전**: 1.0.0

## 헬스체크

### GET /

루트 경로 - API 정보

**응답:**
```json
{
  "name": "Sandwich Server API",
  "version": "1.0.0",
  "swagger_ui": "/api-docs",
  "api_spec": "/apispec.json",
  "endpoints": {
    "health": "/health",
    "db_status": "/db/status",
    "orders": "/orders",
    "inventory": "/inventory/txn",
    "analytics": "/analytics"
  }
}
```

### GET /health

서버 상태 확인

**응답:**
```json
{
  "status": "ok"
}
```

### GET /db/status

TimescaleDB 상태 확인

**응답:**
```json
{
  "jobs": [...],
  "continuous_aggregates": [...]
}
```

## 주문 API

### POST /orders

주문 생성

**요청 본문:**
```json
{
  "channel": "pickup",
  "customer_name": "홍길동",
  "customer_phone": "010-1234-5678",
  "items": [
    {
      "sku": "SAND-BMT-15",
      "name": "Italian B.M.T (15cm)",
      "qty": 2,
      "unit": "ea",
      "unit_price": 6100
    }
  ],
  "currency": "KRW",
  "total_amount": 12200,
  "payment_status": "paid",
  "meta": {}
}
```

**응답:**
```json
{
  "order_id": "uuid",
  "status": "placed",
  "channel": "pickup",
  "ordered_at": "2024-01-01T00:00:00"
}
```

### GET /orders

주문 목록 조회

**쿼리 파라미터:**
- `status`: 주문 상태 필터 (placed, preparing, ready, completed, canceled, refunded)
- `from`: 시작 날짜 (ISO 8601)
- `to`: 종료 날짜 (ISO 8601)
- `limit`: 페이지 크기 (기본값: 50)
- `offset`: 오프셋 (기본값: 0)

**응답:**
```json
{
  "orders": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

### GET /orders/<order_id>

주문 상세 조회

**응답:**
```json
{
  "order_id": "uuid",
  "channel": "pickup",
  "status": "completed",
  "customer_name": "홍길동",
  "items": [...],
  "total_amount": 12200,
  "ordered_at": "2024-01-01T00:00:00"
}
```

### PATCH /orders/<order_id>/status

주문 상태 변경

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

## 원재료 관리 API

### GET /ingredients

원재료 목록 조회

**쿼리 파라미터:**
- `category`: 카테고리 필터 (bread, cheese, veg, meat, sauce 등)
- `is_active`: 활성 상태 필터 (true/false)
- `limit`: 페이지 크기
- `offset`: 오프셋

**응답:**
```json
{
  "ingredients": [
    {
      "ingredient_id": "uuid",
      "ingredient_sku": "ING-BREAD-WHEAT",
      "ingredient_name": "Wheat Bread",
      "category": "bread",
      "base_unit": "g",
      "is_active": true
    }
  ],
  "total": 50
}
```

### GET /ingredients/<ingredient_sku>

원재료 상세 조회

**응답:**
```json
{
  "ingredient_id": "uuid",
  "ingredient_sku": "ING-BREAD-WHEAT",
  "ingredient_name": "Wheat Bread",
  "category": "bread",
  "base_unit": "g",
  "is_active": true,
  "meta": {}
}
```

### POST /ingredients

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

### PATCH /ingredients/<ingredient_sku>

원재료 수정

**요청 본문:**
```json
{
  "ingredient_name": "Updated Name",
  "category": "bread",
  "is_active": false
}
```

### DELETE /ingredients/<ingredient_sku>

원재료 삭제/비활성화

**쿼리 파라미터:**
- `hard_delete`: true면 실제 삭제, false면 is_active=false로 설정 (기본값: false)

### POST /ingredients/txn

원재료 거래 이벤트 생성

**요청 본문:**
```json
{
  "ingredient_sku": "ING-BREAD-WHEAT",
  "qty_delta": -100,
  "txn_type": "out",
  "reason": "주문 생산 사용",
  "order_id": "uuid",
  "occurred_at": "2024-01-01T00:00:00Z",
  "meta": {}
}
```

**txn_type:**
- `in`: 입고 (양수 권장)
- `out`: 사용 (음수 권장, 양수 입력 시 자동 변환)
- `waste`: 폐기 (음수 권장, 양수 입력 시 자동 변환)
- `adjust`: 조정 (양수/음수 가능)

### GET /ingredients/txn

원재료 거래 이벤트 목록 조회

**쿼리 파라미터:**
- `ingredient_sku`: 원재료 SKU 필터
- `txn_type`: 거래 유형 필터 (in/out/waste/adjust)
- `from`: 시작 날짜
- `to`: 종료 날짜
- `limit`: 페이지 크기
- `offset`: 오프셋

## 메뉴 레시피 API

### GET /menu-recipe/<menu_sku>

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

### POST /menu-recipe

메뉴 레시피 생성/업데이트 (전체 교체)

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

### DELETE /menu-recipe/<menu_sku>

메뉴 레시피 전체 삭제

### DELETE /menu-recipe/<menu_sku>/<ingredient_sku>

레시피 항목 삭제

### GET /menu-recipe/list

모든 메뉴 레시피 목록 조회

**쿼리 파라미터:**
- `limit`: 페이지 크기
- `offset`: 오프셋

## 분석 API

### GET /analytics/daily/inventory-change

일별 재고 변동량 조회

**쿼리 파라미터:**
- `sku`: SKU 필터 (선택)
- `from`: 시작 날짜 (기본값: 30일 전)
- `to`: 종료 날짜 (기본값: 현재)

**응답:**
```json
{
  "from_date": "2024-01-01T00:00:00",
  "to_date": "2024-01-31T00:00:00",
  "data": [
    {
      "day": "2024-01-01",
      "sku": "ING-BREAD-WHEAT",
      "display_name": "Wheat Bread",
      "unit": "g",
      "net_qty_change": 1000.0
    }
  ],
  "note": "Calculated from store_ingredient_txn (fallback, view not available)"
}
```

**참고**: Continuous Aggregate 뷰가 없으면 `store_ingredient_txn`에서 직접 계산합니다.

### GET /analytics/daily/sales

일별 판매량 조회

**쿼리 파라미터:**
- `sku`: SKU 필터 (선택)
- `from`: 시작 날짜 (기본값: 30일 전)
- `to`: 종료 날짜 (기본값: 현재)

**응답:**
```json
{
  "from_date": "2024-01-01T00:00:00",
  "to_date": "2024-01-31T00:00:00",
  "data": [
    {
      "day": "2024-01-01",
      "sku": "SAND-BMT-15",
      "display_name": "Italian B.M.T (15cm)",
      "unit": "ea",
      "sold_qty": 50.0
    }
  ]
}
```

**참고**: Continuous Aggregate 뷰가 없으면 `store_order`에서 직접 계산합니다.

### GET /analytics/top-sales

TOP 판매 상품 조회

**쿼리 파라미터:**
- `days`: 기간 (기본값: 30일)
- `limit`: 상위 N개 (기본값: 20)

**응답:**
```json
{
  "days": 30,
  "from_date": "2024-01-01T00:00:00",
  "to_date": "2024-01-31T00:00:00",
  "top_products": [
    {
      "sku": "SAND-BMT-15",
      "display_name": "Italian B.M.T (15cm)",
      "unit": "ea",
      "total_sold_qty": 150.0
    }
  ]
}
```

## 재고 API (예비)

### POST /inventory/txn

재고 이벤트 생성 (예비 기능)

**참고**: `store_inventory_txn`은 예비 테이블로, 최소한의 REST API만 제공합니다.

### GET /inventory/txn

재고 이벤트 목록 조회 (예비 기능)

## 에러 응답

### 400 Bad Request

```json
{
  "error": "Missing required field: customer_name"
}
```

### 404 Not Found

```json
{
  "error": "Order not found"
}
```

### 500 Internal Server Error

```json
{
  "error": "Failed to get daily sales: ..."
}
```

## 샘플 요청

### Python requests

```python
import requests

BASE_URL = "http://192.168.0.27:5000"

# 주문 생성
response = requests.post(
    f"{BASE_URL}/orders",
    json={
        "channel": "pickup",
        "customer_name": "홍길동",
        "items": [{"sku": "SAND-BMT-15", "name": "Italian B.M.T", "qty": 1, "unit_price": 6100}],
        "total_amount": 6100,
        "payment_status": "paid"
    }
)
order = response.json()
print(f"주문 ID: {order['order_id']}")
```

### cURL

```bash
# 주문 생성
curl -X POST http://192.168.0.27:5000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "pickup",
    "customer_name": "홍길동",
    "items": [{"sku": "SAND-BMT-15", "name": "Italian B.M.T", "qty": 1, "unit_price": 6100}],
    "total_amount": 6100,
    "payment_status": "paid"
  }'
```

## 참고 자료

- [Swagger UI](http://192.168.0.27:5000/api-docs) - 인터랙티브 API 문서
- [서버 사용 가이드](./server-guide.md)
- [데이터베이스 가이드](./database-guide.md)

