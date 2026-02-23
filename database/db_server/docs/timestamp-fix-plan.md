# Timestamp 문제 분석 및 수정 계획

## 문제 상황

데이터베이스에서 `ordered_at`이 `updated_at`보다 늦게 기록되는 경우가 발생하고 있습니다.

### 요구사항
1. **ordered_at**: 최초 생성 이후 절대 변경 금지
2. **updated_at**: 항상 `now()`로 자동 갱신

## 현재 코드 분석

### 1. 모델 정의 (app/models.py)

```python
ordered_at = Column(DateTime(timezone=True), server_default=func.now())
updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**현재 상태:**
- ✅ `ordered_at`: `server_default=func.now()` - DB 레벨에서만 설정 (생성 시)
- ✅ `updated_at`: `server_default=func.now(), onupdate=func.now()` - DB 레벨에서 자동 갱신

### 2. 주문 생성 (app/routes/orders.py, app/routes/orders_ui.py)

```python
order = StoreOrder(
    order_id=uuid.uuid4(),
    channel=data['channel'],
    # ... 다른 필드들
    # ordered_at과 updated_at은 명시적으로 설정하지 않음
)
```

**현재 상태:**
- ✅ `ordered_at`: 명시적으로 설정하지 않음 → `server_default`에 의존 (정상)
- ✅ `updated_at`: 명시적으로 설정하지 않음 → `server_default`에 의존 (정상)

### 3. 주문 업데이트 (app/services/order_service.py)

```python
order.status = new_status
order.updated_at = datetime.utcnow()  # ⚠️ 문제!
```

**문제점:**
- ❌ `datetime.utcnow()`를 사용하여 Python 레벨에서 명시적으로 설정
- ❌ Python 서버 시간과 PostgreSQL 서버 시간이 다를 수 있음
- ❌ `onupdate=func.now()`가 있지만, 명시적으로 설정하면 그것이 우선됨
- ❌ 네트워크 지연, 서버 시간 동기화 문제 등으로 인해 시간 불일치 발생 가능

## 문제 원인

### 시나리오 1: 서버 시간 불일치
```
1. 주문 생성: ordered_at = DB.now() = 2026-01-06 22:00:00 (UTC)
2. 주문 업데이트: updated_at = Python.utcnow() = 2026-01-06 22:05:00 (UTC)
3. 하지만 Python 서버 시간이 DB보다 빠르면:
   - updated_at = Python.utcnow() = 2026-01-06 21:55:00 (UTC)
   - 결과: updated_at < ordered_at (문제!)
```

### 시나리오 2: 명시적 설정으로 인한 onupdate 무시
```
1. 주문 생성: ordered_at = DB.now() = 2026-01-06 22:00:00
2. 주문 업데이트: order.updated_at = datetime.utcnow() 명시적 설정
3. onupdate=func.now()가 무시되고 Python 시간이 사용됨
4. Python 시간이 DB 시간보다 느리면 문제 발생
```

## 수정 계획

### 목표
1. `ordered_at`: 생성 시에만 DB의 `func.now()`로 설정, 이후 절대 변경 금지
2. `updated_at`: 항상 DB의 `func.now()`로 자동 갱신 (Python 레벨에서 명시적 설정 제거)

### 수정 사항

#### 1. 모델 정의 강화
- `ordered_at`에 `onupdate` 제거 (이미 없음, 확인)
- `updated_at`의 `onupdate=func.now()` 유지

#### 2. 주문 생성 로직
- `ordered_at`을 명시적으로 설정하지 않음 (현재 상태 유지)
- `updated_at`을 명시적으로 설정하지 않음 (현재 상태 유지)

#### 3. 주문 업데이트 로직 (핵심 수정)
- `order.updated_at = datetime.utcnow()` 제거
- DB의 `onupdate=func.now()`에 의존하도록 변경
- SQLAlchemy가 자동으로 `updated_at`을 갱신하도록 함

#### 4. 추가 보호 장치
- `ordered_at` 변경 시도 시 에러 발생하도록 검증 추가 (선택사항)

## 수정 코드

### app/services/order_service.py

**수정 전:**
```python
order.status = new_status
order.updated_at = datetime.utcnow()  # 제거 필요
```

**수정 후:**
```python
order.status = new_status
# updated_at은 onupdate=func.now()에 의해 자동 갱신됨
# 명시적으로 설정하지 않음
```

### app/models.py (확인)

**현재 상태 (이미 올바름):**
```python
ordered_at = Column(DateTime(timezone=True), server_default=func.now())
# onupdate 없음 → 생성 후 변경 불가

updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
# onupdate 있음 → 업데이트 시 자동 갱신
```

## 검증 방법

### 1. 주문 생성 테스트
```sql
-- 주문 생성 후
SELECT order_id, ordered_at, updated_at 
FROM store_order 
WHERE order_id = '...';

-- 검증: ordered_at ≈ updated_at (거의 동일해야 함)
```

### 2. 주문 업데이트 테스트
```sql
-- 주문 업데이트 전
SELECT order_id, ordered_at, updated_at FROM store_order WHERE order_id = '...';

-- 주문 상태 변경 (API 호출)

-- 주문 업데이트 후
SELECT order_id, ordered_at, updated_at FROM store_order WHERE order_id = '...';

-- 검증: 
-- - ordered_at은 변경되지 않아야 함
-- - updated_at은 현재 시간으로 갱신되어야 함
-- - updated_at >= ordered_at 이어야 함
```

## 예상 효과

### 수정 전
- Python 서버 시간과 DB 서버 시간 불일치 가능
- `ordered_at` > `updated_at` 상황 발생 가능

### 수정 후
- 모든 시간이 DB의 `func.now()`로 통일
- `ordered_at`은 생성 시에만 설정, 이후 변경 불가
- `updated_at`은 업데이트 시마다 DB의 현재 시간으로 자동 갱신
- `updated_at` >= `ordered_at` 보장

## 추가 고려사항

### 1. 기존 데이터 정리 (선택사항)
```sql
-- ordered_at > updated_at인 데이터 수정
UPDATE store_order 
SET updated_at = ordered_at 
WHERE updated_at < ordered_at;
```

### 2. 데이터베이스 트리거 (선택사항)
```sql
-- 추가 보호를 위한 트리거 생성
CREATE OR REPLACE FUNCTION prevent_ordered_at_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.ordered_at IS DISTINCT FROM NEW.ordered_at THEN
        RAISE EXCEPTION 'ordered_at cannot be modified after creation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_ordered_at_update
BEFORE UPDATE ON store_order
FOR EACH ROW
EXECUTE FUNCTION prevent_ordered_at_update();
```

## 수정 완료 내역

✅ **모든 수정이 완료되었습니다!**

1. ✅ `app/services/order_service.py`에서 `order.updated_at = datetime.utcnow()` 제거 완료
2. ✅ `app/routes/ingredients.py`에서 `ingredient.updated_at = datetime.utcnow()` 제거 완료 (2곳)
3. ✅ 기존 잘못된 데이터 정리 SQL 스크립트 생성: `scripts/fix_timestamp_data.sql`
4. ✅ 데이터베이스 트리거 생성 스크립트: `scripts/create_timestamp_triggers.sql`
5. ✅ 통합 실행 스크립트: `scripts/apply_timestamp_fixes.sh`

## 실행 방법

### 방법 1: 통합 스크립트 실행 (권장)

```bash
./scripts/apply_timestamp_fixes.sh
```

### 방법 2: 개별 실행

```bash
# 1. 데이터 정리
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -f scripts/fix_timestamp_data.sql

# 2. 트리거 생성
psql -h 192.168.0.27 -U deepdive -d pinky_robot_store -f scripts/create_timestamp_triggers.sql
```

