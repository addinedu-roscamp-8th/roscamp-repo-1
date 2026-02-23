# 인프라 사용 가이드

팀원들을 위한 Sandwich Server 인프라 및 API 사용 가이드입니다.

## 목차

1. [환경 설정](#환경-설정)
2. [데이터베이스 접속](#데이터베이스-접속)
3. [서버 실행](#서버-실행)
4. [API 사용법](#api-사용법)
5. [웹 UI 사용법](#웹-ui-사용법)
6. [문제 해결](#문제-해결)

---

## 환경 설정

### 1. 프로젝트 클론 및 의존성 설치

```bash
# 프로젝트 디렉토리로 이동
cd sandwich_server

# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 데이터베이스 연결 정보를 설정하세요:

```bash
# env.example을 복사
cp env.example .env

# .env 파일 편집
nano .env  # 또는 원하는 에디터 사용
```

**.env 파일 내용:**
```bash
DB_HOST=192.168.0.27               # 데이터베이스 호스트
DB_PORT=5432                        # PostgreSQL 포트
DB_NAME=pinky_robot_store          # 데이터베이스 이름
DB_USER=deepdive                   # 데이터베이스 사용자
DB_PASSWORD=your_password_here     # 데이터베이스 비밀번호
FLASK_ENV=development              # Flask 환경
FLASK_DEBUG=True                   # 디버그 모드
```

**AWS RDS 사용 시:**
```bash
DB_HOST=your-rds-endpoint.region.rds.amazonaws.com
DB_PORT=5432
DB_NAME=pinky_robot_store
DB_USER=your_db_user
DB_PASSWORD=your_db_password
FLASK_ENV=production
FLASK_DEBUG=False
```

---

## 데이터베이스 접속

### 데이터베이스 접속

```bash
# 실제 데이터베이스로 직접 접속
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store

# 또는 기본 postgres 데이터베이스로 접속 (슈퍼유저인 경우)
psql -h 192.168.0.27 -U postgres -d postgres
```

### AWS RDS 접속 (필요한 경우)

```bash
# RDS 엔드포인트로 접속
psql -h your-rds-endpoint.region.rds.amazonaws.com \
     -U deepdive \
     -d pinky_robot_store
```

### 환경 변수 사용 (권장)

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

### 제공된 스크립트 사용

```bash
# 데이터베이스 접속 스크립트
chmod +x scripts/connect_db.sh
./scripts/connect_db.sh pinky_robot_store
```

---

## 서버 실행

### 개발 모드

```bash
python run.py
```

서버가 `http://192.168.0.27:5000`에서 실행됩니다.

### 프로덕션 모드

```bash
# gunicorn 사용 (권장)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"

# 또는 systemd 서비스로 등록
```

---

## API 사용법

### 1. Swagger UI 사용 (권장)

가장 쉬운 방법은 Swagger UI를 사용하는 것입니다:

```
http://192.168.0.27:5000/api-docs
```

Swagger UI에서:
- 모든 API 엔드포인트 확인
- 요청/응답 스키마 확인
- "Try it out" 버튼으로 직접 테스트
- 예제 요청 본문 제공

### 2. curl 사용

#### 헬스체크
```bash
curl http://192.168.0.27:5000/health
```

#### 주문 생성
```bash
curl -X POST http://192.168.0.27:5000/orders \
  -H "Content-Type: application/json" \
  -d '{
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
    "total_amount": 12200,
    "payment_status": "paid"
  }'
```

#### 주문 조회
```bash
# 주문 목록
curl "http://192.168.0.27:5000/orders?status=completed&limit=10"

# 주문 상세
curl "http://192.168.0.27:5000/orders/<order_id>"
```

#### 주문 상태 변경
```bash
curl -X PATCH http://192.168.0.27:5000/orders/<order_id>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

#### 원재료 생성
```bash
curl -X POST http://192.168.0.27:5000/ingredients \
  -H "Content-Type: application/json" \
  -d '{
    "ingredient_sku": "ING-BREAD-WHEAT",
    "ingredient_name": "Wheat Bread",
    "category": "bread",
    "base_unit": "g"
  }'
```

#### 원재료 거래 이벤트 생성
```bash
curl -X POST http://192.168.0.27:5000/ingredients/txn \
  -H "Content-Type: application/json" \
  -d '{
    "ingredient_sku": "ING-BREAD-WHEAT",
    "qty_delta": -100,
    "txn_type": "out",
    "reason": "주문 생산 사용",
    "order_id": "<order_id>"
  }'
```

#### 메뉴 레시피 생성
```bash
curl -X POST http://192.168.0.27:5000/menu-recipe \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### 3. Python requests 사용

```python
import requests

BASE_URL = "http://192.168.0.27:5000"

# 주문 생성
response = requests.post(
    f"{BASE_URL}/orders",
    json={
        "channel": "pickup",
        "customer_name": "홍길동",
        "items": [
            {
                "sku": "SAND-BMT-15",
                "name": "Italian B.M.T (15cm)",
                "qty": 1,
                "unit_price": 6100
            }
        ],
        "total_amount": 6100,
        "payment_status": "paid"
    }
)
order = response.json()
print(f"주문 ID: {order['order_id']}")

# 주문 완료 처리
order_id = order['order_id']
response = requests.patch(
    f"{BASE_URL}/orders/{order_id}/status",
    json={"status": "completed"}
)
print(response.json())
```

---

## 웹 UI 사용법

### 대시보드

```
http://192.168.0.27:5000/dashboard
```

**기능:**
- 실시간 통계 확인
- 최근 주문 목록
- 원재료 재고 현황
- 인기 상품 (continuous aggregate 필요)

### 주문 관리 UI

```
http://192.168.0.27:5000/orders-ui
```

**기능:**
- 주문 목록 조회 및 검색
- 새 주문 생성
- 주문 상세 보기
- 주문 상태 변경

---

## 문제 해결

### 1. 데이터베이스 연결 오류

**증상:**
```
psycopg2.OperationalError: could not connect to server
```

**해결:**
- `.env` 파일의 DB 연결 정보 확인
- 데이터베이스 서버가 실행 중인지 확인
- 방화벽/보안 그룹에서 포트 5432가 열려있는지 확인

### 2. Continuous Aggregate 뷰 없음 오류

**증상:**
```
relation "public.cagg_daily_sales_qty" does not exist
```

**해결:**
```bash
# 뷰 생성 스크립트 실행
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f scripts/create_cagg_views.sql
```

### 3. 권한 오류

**증상:**
```
permission denied for view cagg_daily_sales_qty
```

**해결:**
```bash
# 권한 부여 스크립트 실행
chmod +x scripts/grant_cagg_permissions.sh
./scripts/grant_cagg_permissions.sh <your_db_user>
```

### 4. 포트 충돌

**증상:**
```
Address already in use
```

**해결:**
```bash
# 다른 포트 사용
export FLASK_RUN_PORT=5001
python run.py

# 또는 run.py에서 포트 변경
```

---

## 주요 엔드포인트 요약

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/health` | GET | 서버 상태 확인 |
| `/db/status` | GET | TimescaleDB 상태 |
| `/orders` | GET, POST | 주문 목록/생성 |
| `/orders/<id>` | GET | 주문 상세 |
| `/orders/<id>/status` | PATCH | 주문 상태 변경 |
| `/ingredients` | GET, POST | 원재료 목록/생성 |
| `/ingredients/<sku>` | GET, PATCH, DELETE | 원재료 관리 |
| `/ingredients/txn` | GET, POST | 원재료 거래 |
| `/menu-recipe/<menu_sku>` | GET | 메뉴 레시피 조회 |
| `/menu-recipe` | POST | 레시피 생성/업데이트 |
| `/analytics/daily/sales` | GET | 일별 판매량 |
| `/analytics/top-sales` | GET | TOP 판매 상품 |
| `/dashboard` | GET | 대시보드 UI |
| `/orders-ui` | GET | 주문 관리 UI |
| `/api-docs` | GET | Swagger UI |

---

## 추가 리소스

- **API 문서**: `http://192.168.0.27:5000/api-docs`
- **API 스펙**: `http://192.168.0.27:5000/apispec.json`
- **프로젝트 README**: `README.md`

---

## 문의 및 지원

문제가 발생하거나 질문이 있으면 팀 채널로 문의하세요.

