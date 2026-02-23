# 개발 현황

Sandwich Server 프로젝트의 현재 개발 현황 및 기능 목록입니다.

**최종 업데이트**: 2025-01-01

## 프로젝트 개요

음식 판매점의 주문, 원재료, 메뉴 레시피를 관리하는 Flask REST API 서버입니다.

### 기술 스택

- **Framework**: Flask 3.0.0
- **Database**: PostgreSQL 16.11 + TimescaleDB
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **API Documentation**: Flasgger (Swagger UI)
- **Python**: 3.8+

## 구현된 기능

### ✅ 완료된 기능

#### 1. 주문 관리
- [x] 주문 생성 (POST /orders)
- [x] 주문 목록 조회 (GET /orders)
- [x] 주문 상세 조회 (GET /orders/<id>)
- [x] 주문 상태 변경 (PATCH /orders/<id>/status)
- [x] 주문 관리 웹 UI (`/orders-ui`)
- [x] 주문 검색 및 필터링

#### 2. 원재료 관리
- [x] 원재료 마스터 생성/조회/수정/삭제
- [x] 원재료 거래 이벤트 생성/조회
- [x] 카테고리별 조회
- [x] 활성/비활성 상태 관리

#### 3. 메뉴 레시피 BOM
- [x] 메뉴 레시피 조회
- [x] 메뉴 레시피 생성/업데이트
- [x] 레시피 항목 삭제
- [x] 모든 메뉴 레시피 목록 조회

#### 4. 대시보드
- [x] 실시간 통계 (총 주문, 오늘 주문, 오늘 매출)
- [x] 최근 주문 목록
- [x] 원재료 재고 현황 (토글 가능, 기본 숨김)
- [x] 인기 상품 TOP 5
- [x] 집계 카드 토글 기능 (기본 숨김)
- [x] 자동 새로고침 (30초)

#### 5. 분석 API
- [x] 일별 재고 변동량 조회
- [x] 일별 판매량 조회
- [x] TOP 판매 상품 조회
- [x] Fallback 로직 (뷰 없이도 동작)

#### 6. 인프라
- [x] Swagger API 문서화
- [x] 헬스체크 엔드포인트
- [x] TimescaleDB 상태 확인
- [x] 환경 변수 관리 (.env)
- [x] 데이터베이스 연결 스크립트
- [x] Continuous Aggregates 생성 스크립트

## 데이터베이스 구조

### 주요 테이블

1. **store_order** - 주문 정보
   - 주문 ID, 채널, 상태, 고객 정보
   - 주문 항목 (JSONB), 금액, 결제 상태

2. **store_ingredient_mst** - 원재료 마스터
   - 원재료 SKU, 이름, 카테고리, 단위
   - 활성 상태, 메타데이터

3. **store_ingredient_txn** - 원재료 거래 이벤트
   - 입고/사용/폐기/조정 이벤트
   - TimescaleDB hypertable

4. **store_menu_recipe_bom** - 메뉴 레시피 BOM
   - 메뉴별 원재료 구성 및 수량

### 예비 테이블

- **store_inventory_txn** - 재고 거래 이벤트 (예비)
  - 최소한의 REST API만 제공
  - 서비스 영역(대시보드, 분석)에서는 사용하지 않음

### Continuous Aggregates (선택사항)

- **cagg_daily_inventory_change** - 일별 원재료 재고 변동량
- **cagg_daily_sales_qty** - 일별 판매량

## API 엔드포인트 요약

| 카테고리 | 엔드포인트 | 메서드 | 설명 |
|---------|-----------|--------|------|
| Health | `/health` | GET | 서버 상태 확인 |
| Health | `/db/status` | GET | TimescaleDB 상태 |
| Orders | `/orders` | GET, POST | 주문 목록/생성 |
| Orders | `/orders/<id>` | GET | 주문 상세 |
| Orders | `/orders/<id>/status` | PATCH | 주문 상태 변경 |
| Ingredients | `/ingredients` | GET, POST | 원재료 목록/생성 |
| Ingredients | `/ingredients/<sku>` | GET, PATCH, DELETE | 원재료 관리 |
| Ingredients | `/ingredients/txn` | GET, POST | 원재료 거래 |
| Menu Recipe | `/menu-recipe/<menu_sku>` | GET | 메뉴 레시피 조회 |
| Menu Recipe | `/menu-recipe` | POST | 레시피 생성/업데이트 |
| Analytics | `/analytics/daily/inventory-change` | GET | 일별 재고 변동량 |
| Analytics | `/analytics/daily/sales` | GET | 일별 판매량 |
| Analytics | `/analytics/top-sales` | GET | TOP 판매 상품 |
| Inventory | `/inventory/txn` | GET, POST | 재고 이벤트 (예비) |

## 웹 UI

### 대시보드 (`/dashboard`)
- 실시간 통계 카드 (토글 가능)
- 최근 주문 목록
- 원재료 재고 현황 (토글 가능, 기본 숨김)
- 인기 상품 TOP 5

### 주문 관리 UI (`/orders-ui`)
- 주문 목록 조회 및 검색
- 새 주문 생성
- 주문 상세 보기
- 주문 상태 변경

## 주요 특징

### 1. Fallback 로직
- Continuous Aggregate 뷰가 없어도 API 정상 작동
- `store_order` 및 `store_ingredient_txn`에서 직접 계산

### 2. 토글 기능
- 집계 카드: 기본 숨김, 직원만 표시
- 재고 현황: 기본 숨김, 직원만 표시
- localStorage에 상태 저장

### 3. 트랜잭션 안전성
- 주문 상태 변경 시 `SELECT ... FOR UPDATE` 사용
- 멱등성 보장

## 향후 계획

### 🔄 진행 중
- [ ] 테스트 커버리지 확대
- [ ] 성능 최적화

### 📋 계획 중
- [ ] 인증/인가 시스템
- [ ] 로깅 시스템 개선
- [ ] 모니터링 대시보드

## 알려진 제한사항

1. **store_inventory_txn**: 예비 테이블로 최소 기능만 제공
2. **Continuous Aggregates**: 뷰가 없어도 동작하지만 성능은 낮을 수 있음
3. **인증**: 현재 인증/인가 시스템 없음

## 변경 이력

### 2025-01-01
- `store_inventory_txn` 기반 뷰를 `store_ingredient_txn` 기반으로 변경
- Fallback 로직 추가
- 대시보드 토글 기능 추가
- 문서화 개선

