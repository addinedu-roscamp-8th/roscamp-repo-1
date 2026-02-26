# Backend ↔ pinky_robot_store DB 호환성 점검 계획

작성일: 2025-02-23  
참고: [backend_개발_분석_리포트.md](./backend_개발_분석_리포트.md), database/db_server/.env

---

## 1. 목표

- **db_server**가 바라보는 DB: `database/db_server/.env`에 정의된 **pinky_robot_store**
- **backend(Main Server)**가 동일한 **pinky_robot_store** DB에 연결하여 Kitchmatic 테이블(orders, robots, menus 등)을 사용할 수 있도록 하고, 연결 검증 테스트를 수행한다.

---

## 2. 현재 설정 정리

### 2.1 db_server (.env)

| 항목 | 값 |
|------|-----|
| DB_HOST | 192.168.0.27 |
| DB_PORT | 5432 |
| DB_NAME | **pinky_robot_store** |
| DB_USER | deepdive |
| DB_PASSWORD | deepdive_team123!# |

### 2.2 backend (현재)

- **설정 경로**: `app/backend/config/database.env` (gitignore) 또는 환경 변수
- **우선순위**: 환경 변수 > `config/database.env` > 기본값
- **기본값**: db_name=`kitchmatic`, db_user=`kitchmatic_user`, db_password=`your_password_here`
- **로드 위치**: `main_server_node.py` → `_load_db_config()` → `DatabaseManager(**db_config)`

### 2.3 backend가 사용하는 테이블 (database_manager.py ORM)

| 순번 | 테이블명 | 용도 |
|------|----------|------|
| 1 | menus | 메뉴 마스터 |
| 2 | ingredients | 식재료 마스터 |
| 3 | recipes | 레시피 |
| 4 | recipe_steps | 레시피 단계 |
| 5 | inventory | 재고 |
| 6 | inventory_transactions | 재고 거래 |
| 7 | robots | 로봇 |
| 8 | orders | 주문 |
| 9 | quality_check_results | 품질검사 결과 |

→ `database/schema.sql`(Kitchmatic)과 동일한 9개 테이블.

---

## 3. 수행 전략

1. **DB 연결 가능 여부 점검**  
   - db_server .env 값(host, port, db_name, user, password)으로 pinky_robot_store에 접속 시도.  
   - 도구: Python 스크립트 또는 `psql`로 연결 테스트. (실제 접속 가능한 환경에서 실행)

2. **필요 테이블 존재 여부 확인**  
   - pinky_robot_store DB에 위 9개 테이블이 모두 있는지 조회.  
   - 방법: `information_schema.tables` 또는 `SELECT tablename FROM pg_tables WHERE schemaname = 'public'` 등으로 확인.

3. **backend를 pinky_robot_store에 연결**  
   - backend가 db_server와 동일한 DB를 쓰도록 설정.  
   - 방법 (택일 또는 병행):  
     - **A)** `app/backend/config/database.env`에 db_server .env와 동일한 값 작성 (DB_NAME=pinky_robot_store, DB_USER=deepdive, DB_PASSWORD=..., DB_HOST=192.168.0.27, DB_PORT=5432)  
     - **B)** backend 실행 전에 환경 변수로 동일 값 export  
   - `main_server_node._load_db_config()`는 이미 env 파일·환경 변수를 읽으므로, 위 값이 적용되면 pinky_robot_store로 연결됨.

4. **연결 검증 테스트**  
   - backend 시작 시 `DatabaseManager.connect()` 성공 여부 확인.  
   - 추가로: `get_session()` 후 단순 SELECT(예: `SELECT 1`, 또는 `menus`/`orders` count) 등 최소 쿼리로 접근 가능 여부 확인.  
   - 가능하면 기존 backend 테스트 스크립트나 TCP 테스트 클라이언트로 주문 생성·조회 등 한 번 수행해 보는 것 권장.

---

## 4. 실행 계획 (단계별)

| 단계 | 내용 | 산출물/확인 |
|------|------|-------------|
| **1** | db_server .env 기준으로 pinky_robot_store **연결 테스트** (Python/psql) | 연결 성공/실패 및 오류 메시지 |
| **2** | pinky_robot_store 내 **9개 테이블 존재 여부** 조회 (스크립트 또는 수동 쿼리) | 테이블 목록·누락 테이블 유무 |
| **3** | 테이블이 모두 있으면: backend **config를 pinky_robot_store로 설정** (database.env 또는 env) | app/backend/config/database.env 또는 설정 가이드 |
| **4** | backend 서버 기동 후 **DB 연결 및 최소 쿼리 검증** (connect + 세션·쿼리) | 검증 스크립트 또는 실행 로그 |
| **5** | (선택) TCP 테스트 클라이언트 등으로 **주문 생성/조회** 등 동작 확인 | 테스트 결과 요약 |

---

## 5. 주의사항

- **database.env**는 gitignore이므로, db_server .env 내용을 backend용으로 **복사·작성**할 때 비밀번호 등이 저장소에 올라가지 않도록 유지.
- **orders.status**: backend ORM에는 `AT_POINT13` 등이 CheckConstraint에 없을 수 있음(CRITICAL_FIXES.md 참고). 테이블 존재 여부 점검과는 별도로, 실제 주문 상태 업데이트 시 DB 제약과 맞출지 여부는 이후 수정 과제로 둘 수 있음.
- DB 서버(192.168.0.27)가 실행 중이며, 방화벽·네트워크에서 backend 실행 환경 → 5432 접근이 허용되어 있어야 함.

---

## 6. 진행 여부 피드백 요청

위 **1~5 단계**대로 진행해도 될지 알려 주세요.

- **진행 가능**  
  → 1) 연결 점검, 2) 테이블 존재 확인, 3) backend 설정, 4) 연결 검증 테스트 순으로 수행하고, 결과를 정리해 보고드리겠습니다.

- **조건/변경**  
  - 예: "backend는 database.env만 수정하고, 환경 변수는 쓰지 않는다", "테이블이 없으면 schema.sql 적용 방법까지 포함해 달라" 등  
  → 요청하신 조건에 맞춰 계획을 수정한 뒤 진행하겠습니다.

- **보류**  
  → 현재는 계획만 반영하고, 실제 연결·설정·테스트는 하지 않겠습니다.

**기본 가정**: 1~4는 수행하고, 5(주문 생성 등)는 선택적으로 수행하는 방향으로 하겠습니다. 피드백 주시면 그에 맞춰 진행하겠습니다.

---

## 7. 수행 결과 (2025-02-23)

| 단계 | 결과 | 비고 |
|------|------|------|
| **1** | ✅ 완료 | `psql`로 pinky_robot_store(192.168.0.27:5432) 접속 성공 |
| **2** | ✅ 완료 | public 스키마에 필수 9개 테이블 모두 존재 (menus, ingredients, recipes, recipe_steps, inventory, inventory_transactions, robots, orders, quality_check_results) |
| **3** | ✅ 완료 | `app/backend/config/database.env`에 pinky_robot_store 설정 반영 (db_server .env와 동일) |
| **4** | ✅ 완료 | 프로젝트 루트 `docs/scripts/verify_backend_db.py`로 DatabaseManager connect + get_session + `SELECT COUNT(*) FROM menus` 검증 통과 (menus count = 4) |
| **5** | 미수행 | TCP 테스트 클라이언트 주문 생성/조회는 선택 항목으로 보류 |

- **연결 검증 스크립트**: 프로젝트 루트의 `docs/scripts/` 에 있음. repo 루트에서  
  `PYTHONPATH=app/backend .venv/bin/python docs/scripts/verify_backend_db.py`  
  (`.venv`에 sqlalchemy, psycopg2-binary 필요. 또는 `database_manager`만 로드하므로 해당 의존성만 있으면 됨.)
- **테이블 점검 스크립트**: 프로젝트 루트 `docs/scripts/check_pinky_robot_store_db.py` (실행 시 psycopg2 필요. 동일 접속 정보로 `psql` 사용 가능.)
