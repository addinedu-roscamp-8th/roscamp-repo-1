# 서버 사용 가이드

Sandwich Server의 서버 실행 및 운영 가이드입니다.

## 환경 설정

### 1. 의존성 설치

```bash
# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 데이터베이스 연결 정보를 설정:

```bash
cp env.example .env
nano .env  # 또는 원하는 에디터 사용
```

**.env 파일 내용:**
```bash
DB_HOST=192.168.0.27
DB_PORT=5432
DB_NAME=pinky_robot_store
DB_USER=deepdive
DB_PASSWORD=your_password_here
FLASK_ENV=development
FLASK_DEBUG=True
```

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

## 웹 UI 접속

### 대시보드

```
http://192.168.0.27:5000/dashboard
```

**기능:**
- 📊 실시간 통계 (집계 카드 - 토글 가능, 기본 숨김)
- 📋 최근 주문 목록
- 📦 원재료 재고 현황 (토글 가능, 기본 숨김)
- 🏆 인기 상품 TOP 5
- 🔄 자동 새로고침 (30초)

**토글 기능:**
- 상단 우측의 "집계 카드 보기" 버튼으로 통계 카드 표시/숨김
- 상단 우측의 "재고 현황 보기" 버튼으로 재고 현황 표시/숨김
- 선택한 상태는 브라우저에 저장되어 다음 접속 시에도 유지

### 주문 관리 UI

```
http://192.168.0.27:5000/orders-ui
```

**기능:**
- 📋 주문 목록 조회 (테이블 형태)
- 🔍 검색 기능 (고객명, 전화번호, 주문ID)
- 🏷️ 상태별 필터링
- ➕ 새 주문 생성 (모달 폼)
- 👁️ 주문 상세 보기
- ✅ 주문 상태 변경
- 📄 페이징 지원

## API 문서 (Swagger)

### Swagger UI

```
http://192.168.0.27:5000/api-docs
```

Swagger UI에서:
- 모든 API 엔드포인트 확인
- 요청/응답 스키마 확인
- "Try it out" 기능으로 직접 테스트

### API 스펙 (JSON)

```
http://192.168.0.27:5000/apispec.json
```

## 주요 엔드포인트

### 헬스체크

```bash
# 서버 상태 확인
curl http://192.168.0.27:5000/health

# 데이터베이스 상태 확인
curl http://192.168.0.27:5000/db/status
```

### 주문 API

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

# 주문 목록 조회
curl "http://192.168.0.27:5000/orders?status=completed&limit=10"

# 주문 상태 변경
curl -X PATCH http://192.168.0.27:5000/orders/<order_id>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

### 원재료 API

```bash
# 원재료 생성
curl -X POST http://192.168.0.27:5000/ingredients \
  -H "Content-Type: application/json" \
  -d '{
    "ingredient_sku": "ING-BREAD-WHEAT",
    "ingredient_name": "Wheat Bread",
    "category": "bread",
    "base_unit": "g"
  }'

# 원재료 거래 이벤트 생성
curl -X POST http://192.168.0.27:5000/ingredients/txn \
  -H "Content-Type: application/json" \
  -d '{
    "ingredient_sku": "ING-BREAD-WHEAT",
    "qty_delta": -100,
    "txn_type": "out",
    "reason": "주문 생산 사용"
  }'
```

## 로그 확인

### 개발 모드

서버 콘솔에서 실시간 로그 확인

### 프로덕션 모드

```bash
# gunicorn 로그
tail -f /var/log/gunicorn/error.log

# 애플리케이션 로그
tail -f /var/log/sandwich_server/app.log
```

## 성능 모니터링

### 데이터베이스 연결 확인

```bash
# 연결 상태 확인
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -c "SELECT count(*) FROM pg_stat_activity;"
```

### 서버 리소스 확인

```bash
# CPU 및 메모리 사용량
top
# 또는
htop

# 네트워크 연결
netstat -an | grep 5000
```

## 문제 해결

### 포트 충돌

```bash
# 포트 사용 중인 프로세스 확인
lsof -i :5000
# 또는
netstat -tulpn | grep 5000

# 프로세스 종료
kill -9 <PID>
```

### 데이터베이스 연결 오류

```bash
# 연결 테스트
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -c "SELECT 1;"

# .env 파일 확인
cat .env | grep DB_
```

### 서버가 시작되지 않음

```bash
# 에러 로그 확인
python run.py 2>&1 | tee error.log

# 의존성 확인
pip list | grep -E "flask|sqlalchemy|psycopg2"
```

## 배포 체크리스트

- [ ] `.env` 파일 설정 완료
- [ ] 데이터베이스 연결 테스트 완료
- [ ] Continuous Aggregates 뷰 생성 (선택사항)
- [ ] 권한 설정 완료
- [ ] 방화벽 포트 열기 (5000)
- [ ] 로그 디렉토리 생성
- [ ] 백업 스크립트 설정

## 참고 자료

- [인프라 가이드](./infrastructure.md)
- [데이터베이스 가이드](./database-guide.md)
- [API 레퍼런스](./api-reference.md)

