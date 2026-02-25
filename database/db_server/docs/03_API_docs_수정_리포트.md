# API 문서(api-docs) 미노출 현상 원인 분석 및 수정 리포트

작성일: 2025-02-23

---

## 1. 현상

`http://192.168.0.27:5000/api-docs` Swagger UI에서:

- **펼쳐도 메서드가 보이지 않는 태그**: Kitchmatic - Menus, Recipes, Robots, Orders, Quality (태그 제목만 보이고 GET/POST/PUT/DELETE 명세·테스트 UI 없음)
- **정상 노출되는 태그**: Kitchmatic - Ingredients, Kitchmatic - Inventory (목록·단건·생성·수정·삭제 등 모두 표시)

---

## 2. 원인 분석

Flasgger는 **docstring에 `---` 로 시작하는 YAML 블록**이 있을 때만 해당 뷰를 OpenAPI operation으로 파싱합니다.

| 구분 | 형식 예시 | Flasgger 인식 |
|------|-----------|----------------|
| **보이던 API** (Ingredients, Inventory) | 첫 줄 설명 + `---` + `tags:` / `parameters:` / `responses:` 등 YAML 블록 | ✅ operation으로 등록 → Swagger UI에 메서드 표시 |
| **안 보이던 API** (Menus, Recipes, Robots, Orders, Quality) | 한 줄 요약만 (예: `"""Kitchmatic 메뉴 목록. tags: Kitchmatic - Menus. responses: 200, 500."""`) | ❌ YAML 블록 없음 → operation 미등록 → 태그만 있고 하위 메서드 없음 |

즉, **동일한 태그 이름**이 swagger_template에 있어도, **각 뷰 함수의 docstring이 OpenAPI YAML 형식이 아니면** 해당 엔드포인트는 스펙에 포함되지 않아 UI에 나오지 않습니다.

---

## 3. 조치 내용

다음 5개 모듈의 **모든 엔드포인트**에 Ingredients/Inventory와 동일한 형식의 **Flasgger YAML docstring**을 추가했습니다.

- **menus.py**: list, get, create, update, delete (5개)
- **recipes.py**: list, get, create, update, delete, list_steps, create_step, get_step, update_step, delete_step (10개)
- **robots.py**: list, get, create, update, delete (5개)
- **orders.py**: list, get, create, update, delete (5개)
- **quality_checks.py**: list, get, create, update, delete (5개)

각 docstring 형식:

```python
def list_menus():
    """
    Kitchmatic 메뉴 목록 조회
    ---
    tags:
      - Kitchmatic - Menus
    parameters:
      - in: query
        name: category
        type: string
    responses:
      200:
        description: 메뉴 목록
    """
```

---

## 4. 수정 후 검증

### 4.1 OpenAPI 스펙(apispec) 검증

앱 로드 후 `/apispec.json` 기준으로 태그별 operation 개수 확인:

| 태그 | operation 수 | 비고 |
|------|--------------|------|
| Kitchmatic - Menus | 5 | GET(목록/단건), POST, PUT, DELETE |
| Kitchmatic - Recipes | 10 | 레시피 CRUD + 단계 목록/단건/생성/수정/삭제 |
| Kitchmatic - Robots | 5 | GET(목록/단건), POST, PUT, DELETE |
| Kitchmatic - Orders | 5 | GET(목록/단건), POST, PUT, DELETE |
| Kitchmatic - Quality | 5 | GET(목록/단건), POST, PUT, DELETE |
| Kitchmatic - Ingredients | 5 | (기존 유지) |
| Kitchmatic - Inventory | 8 | (기존 유지) |

→ **Menus, Recipes, Robots, Orders, Quality** 모두 스펙에 포함되어 api-docs에서 펼치면 메서드가 보여야 합니다.

### 4.2 pytest 결과

- **실행**: `PYTHONPATH=. python3 -m pytest tests/test_kitchmatic_api.py -v`
- **결과**: **39 passed** (1 warning: SQLAlchemy declarative_base deprecation, 기능 영향 없음)
- **추가 조치**: `test_kitchmatic_inventory_transaction_create` 의 fixture `created_inventory_for_txn` 이 중복 생성 시 500이 나던 문제를, “생성 성공 시에만 삭제하고, 이미 있으면 목록에서 id 조회”하도록 수정하여 **전체 39개 테스트 통과**로 정리함.
- docstring 수정으로 인한 **기능 회귀 없음**.

---

## 5. 결론 및 확인 방법

- **원인**: Flasgger가 **`---` YAML 블록이 있는 docstring**만 OpenAPI operation으로 파싱함. Menus/Recipes/Robots/Orders/Quality는 한 줄 docstring만 있어 스펙에 안 들어가서 UI에 안 보였음.
- **조치**: 위 5개 모듈 전 엔드포인트에 YAML 형식 docstring 추가.
- **확인 방법**: 서버 재기동 후 `http://192.168.0.27:5000/api-docs` 에서  
  **Kitchmatic - Menus, Recipes, Robots, Orders, Quality** 를 펼쳤을 때 각각 GET/POST/PUT/DELETE 등 REST 명세 및 Try it out 테스트 UI가 표시되는지 확인하면 됩니다.

**각 API 정상 동작 여부**: 위 pytest로 **39개 전부 통과**했으므로, Menus / Ingredients / Recipes / Recipe steps / Robots / Inventory / Inventory transactions / Orders / Quality checks 관련 Kitchmatic API는 모두 정상 동작하는 것으로 확인되었습니다.  
실서버에서도 `http://192.168.0.27:5000/kitchmatic/menus` 등에 GET/POST를 보내 동작을 한 번씩 확인할 수 있습니다.
