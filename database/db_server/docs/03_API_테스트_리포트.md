# 03 API 테스트 리포트 (Kitchmatic)

작성일: 2025-02-23  
대상: `/kitchmatic` prefix REST API 전부

---

## 1. 테스트 환경

| 항목 | 내용 |
|------|------|
| 테스트 파일 | `tests/test_kitchmatic_api.py` |
| 테스트 프레임워크 | pytest 7.4.3, pytest-flask |
| DB | **.env에 설정된 DB** (schema.sql 테이블 + 기존 테이블 공존) |
| conftest | `TestConfig`가 `Config` 상속으로 **동일 DB** 사용 (별도 test_sandwich_db 미사용) |

---

## 2. 실행 결과 요약

| 결과 | 개수 |
|------|------|
| **PASSED** | 39 |
| FAILED | 0 |
| ERROR | 0 |

**전체 39개 테스트 통과.**

---

## 3. 테스트 대상 리소스 및 케이스

| 리소스 | 테스트 내용 |
|--------|-------------|
| **Menus** | 목록, 기존 단건(M001), 404, 생성(M099), 중복 ID 400, 수정, 삭제 |
| **Ingredients** | 목록, 기존 단건(I001), 404, 생성(I099), 수정, 삭제 |
| **Recipes** | 목록, 생성(menu_id=M001), 잘못된 UUID 400, 단건 조회, 수정, 삭제 |
| **Recipe steps** | 목록, 단계 생성(step_order, action, robot_arm), 단건 조회, 수정, 삭제 |
| **Robots** | 목록, 생성(고유 name), 잘못된 UUID 400, 생성 후 조회·삭제 |
| **Inventory** | 목록, 생성(ingredient_id, location), 단건 조회, 삭제 |
| **Orders** | 목록, 생성(table_number, menu_id, quantity), 필수 필드 누락 400, 잘못된 UUID 400 |
| **Inventory transactions** | 목록, 생성(inventory_id, transaction_type, quantity, before/after_stock) |
| **Quality check results** | 목록, 생성(order_id, status), order_id 누락 400 |
| **공통** | Invalid UUID 시 400 (recipes, robots, orders, inventory) |

---

## 4. 수정·적용 사항 (개발 완료까지 반복)

### 4.1 conftest.py

- **문제**: `TestConfig` 내부에서 `TestConfig.DB_NAME` 참조 시 Python 3.12에서 `NameError: cannot access free variable 'TestConfig'` 발생.
- **조치**: `SQLALCHEMY_DATABASE_URI`에 리터럴 `test_sandwich_db` 사용하도록 수정.

- **문제**: 사용자 요청대로 “아래 정보의 DB에 기존 테이블들과 같이 있어” 반영 필요. 즉 **별도 test_sandwich_db가 아닌, .env에 설정된 DB**에서 테스트 실행.
- **조치**: `TestConfig`에서 `DB_NAME`/`SQLALCHEMY_DATABASE_URI` 오버라이드 제거 → `Config`(.env)와 동일 DB 사용. 테스트 실행 시 해당 DB에 schema.sql 테이블이 있어야 함.

### 4.2 테스트 코드

- 별도 수정 없이 39개 전부 통과.

---

## 5. 실행 방법

```bash
cd database/db_server
# .env에 DB 연결 정보 설정 후
PYTHONPATH=. python3 -m pytest tests/test_kitchmatic_api.py -v --tb=short
```

가상환경 사용 시:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_kitchmatic_api.py -v --tb=short
```

ROS 등 외부 플러그인 충돌 시:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_kitchmatic_api.py -v --tb=short -p no:launch_testing
```

---

## 6. 결론 및 완료 전략

- **결론**: Kitchmatic REST API 39개 테스트가 현재 환경에서 **전부 통과**했으며, 수정 후 재테스트를 반복해 **개발 완료** 상태까지 반영함.
- **완료 전략**:  
  - 테스트 DB는 .env 기준 단일 DB 사용.  
  - 신규 리소스/엔드포인트 추가 시 `test_kitchmatic_api.py`에 동일 스타일로 케이스 추가 후 pytest 재실행으로 회귀 확인.
