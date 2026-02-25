# Kitchmatic REST API tests (schema.sql tables, prefix /kitchmatic)
# Test DB: test_sandwich_db with schema.sql tables (menus, ingredients, etc.)
import pytest
import uuid

BASE = "/kitchmatic"


# ---------- Menus ----------
def test_kitchmatic_menus_list(client):
    r = client.get(f"{BASE}/menus")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data
    assert isinstance(data["items"], list)


def test_kitchmatic_menus_get_existing(client):
    r = client.get(f"{BASE}/menus/M001")
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == "M001"
    assert "name" in data and "price" in data


def test_kitchmatic_menus_get_not_found(client):
    r = client.get(f"{BASE}/menus/NONE")
    assert r.status_code == 404


def test_kitchmatic_menus_create(client):
    payload = {"id": "M099", "name": "테스트메뉴", "price": 1000, "category": "테스트"}
    r = client.post(f"{BASE}/menus", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["id"] == "M099"
    assert data["name"] == "테스트메뉴"


def test_kitchmatic_menus_create_dup_id(client):
    client.post(f"{BASE}/menus", json={"id": "M098", "name": "dup", "price": 1, "category": "c"})
    r = client.post(f"{BASE}/menus", json={"id": "M098", "name": "dup2", "price": 1, "category": "c"})
    assert r.status_code == 400


def test_kitchmatic_menus_update(client):
    r = client.put(f"{BASE}/menus/M099", json={"name": "업데이트메뉴", "price": 2000})
    assert r.status_code == 200
    data = r.get_json()
    assert data["name"] == "업데이트메뉴"
    assert data["price"] == 2000


def test_kitchmatic_menus_delete(client):
    r = client.delete(f"{BASE}/menus/M099")
    assert r.status_code == 204
    r2 = client.get(f"{BASE}/menus/M099")
    assert r2.status_code == 404


# ---------- Ingredients ----------
def test_kitchmatic_ingredients_list(client):
    r = client.get(f"{BASE}/ingredients")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data


def test_kitchmatic_ingredients_get_existing(client):
    r = client.get(f"{BASE}/ingredients/I001")
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == "I001"


def test_kitchmatic_ingredients_get_not_found(client):
    r = client.get(f"{BASE}/ingredients/INONE")
    assert r.status_code == 404


def test_kitchmatic_ingredients_create(client):
    payload = {"id": "I099", "name": "테스트재료", "unit": "개", "category": "테스트", "items_per_box": 10}
    r = client.post(f"{BASE}/ingredients", json=payload)
    assert r.status_code == 201
    assert r.get_json()["id"] == "I099"


def test_kitchmatic_ingredients_update(client):
    r = client.put(f"{BASE}/ingredients/I099", json={"name": "업데이트재료"})
    assert r.status_code == 200
    assert r.get_json()["name"] == "업데이트재료"


def test_kitchmatic_ingredients_delete(client):
    r = client.delete(f"{BASE}/ingredients/I099")
    assert r.status_code == 204


# ---------- Recipes (UUID) ----------
def test_kitchmatic_recipes_list(client):
    r = client.get(f"{BASE}/recipes")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data


def test_kitchmatic_recipes_create(client):
    payload = {"menu_id": "M001", "name": "테스트레시피", "estimated_time_seconds": 60}
    r = client.post(f"{BASE}/recipes", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["menu_id"] == "M001"
    assert "id" in data
    try:
        uuid.UUID(data["id"])
    except ValueError:
        pytest.fail("recipe id should be UUID")


def test_kitchmatic_recipes_get_invalid_uuid(client):
    r = client.get(f"{BASE}/recipes/not-a-uuid")
    assert r.status_code == 400


@pytest.fixture
def created_recipe_id(client):
    r = client.post(f"{BASE}/recipes", json={"menu_id": "M001", "name": "fixture recipe", "estimated_time_seconds": 30})
    assert r.status_code == 201
    return r.get_json()["id"]


def test_kitchmatic_recipes_get(client, created_recipe_id):
    r = client.get(f"{BASE}/recipes/{created_recipe_id}")
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == created_recipe_id
    assert "steps" in data


def test_kitchmatic_recipes_update(client, created_recipe_id):
    r = client.put(f"{BASE}/recipes/{created_recipe_id}", json={"name": "updated recipe", "estimated_time_seconds": 90})
    assert r.status_code == 200
    assert r.get_json()["name"] == "updated recipe"


# ---------- Recipe steps ----------
def test_kitchmatic_recipe_steps_list(client, created_recipe_id):
    r = client.get(f"{BASE}/recipes/{created_recipe_id}/steps")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data
    assert data["count"] == 0


def test_kitchmatic_recipe_step_create(client, created_recipe_id):
    payload = {"step_order": 1, "action": "TAKE", "robot_arm": "ARM_1"}
    r = client.post(f"{BASE}/recipes/{created_recipe_id}/steps", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["step_order"] == 1
    assert data["action"] == "TAKE"
    assert "id" in data


@pytest.fixture
def created_step_id(client, created_recipe_id):
    r = client.post(f"{BASE}/recipes/{created_recipe_id}/steps", json={"step_order": 2, "action": "PLACE", "robot_arm": "ARM_2"})
    assert r.status_code == 201
    return created_recipe_id, r.get_json()["id"]


def test_kitchmatic_recipe_step_get(client, created_step_id):
    rid, sid = created_step_id
    r = client.get(f"{BASE}/recipes/{rid}/steps/{sid}")
    assert r.status_code == 200
    assert r.get_json()["action"] == "PLACE"


def test_kitchmatic_recipe_step_update(client, created_step_id):
    rid, sid = created_step_id
    r = client.put(f"{BASE}/recipes/{rid}/steps/{sid}", json={"action": "REPLACE"})
    assert r.status_code == 200
    assert r.get_json()["action"] == "REPLACE"


def test_kitchmatic_recipe_step_delete(client, created_step_id):
    rid, sid = created_step_id
    r = client.delete(f"{BASE}/recipes/{rid}/steps/{sid}")
    assert r.status_code == 204


def test_kitchmatic_recipes_delete(client, created_recipe_id):
    r = client.delete(f"{BASE}/recipes/{created_recipe_id}")
    assert r.status_code == 204


# ---------- Robots (UUID) ----------
def test_kitchmatic_robots_list(client):
    r = client.get(f"{BASE}/robots")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data


def test_kitchmatic_robots_create(client):
    name = f"테스트로봇_{uuid.uuid4().hex[:8]}"
    payload = {"name": name, "type": "ARM_1", "ip_address": "192.168.1.99", "port": 5999}
    r = client.post(f"{BASE}/robots", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["name"] == name
    robot_id = data["id"]
    r2 = client.get(f"{BASE}/robots/{robot_id}")
    assert r2.status_code == 200
    client.delete(f"{BASE}/robots/{robot_id}")


def test_kitchmatic_robots_get_invalid_uuid(client):
    r = client.get(f"{BASE}/robots/not-a-uuid")
    assert r.status_code == 400


# ---------- Inventory (UUID, needs ingredient_id) ----------
def test_kitchmatic_inventory_list(client):
    r = client.get(f"{BASE}/inventory")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data


def test_kitchmatic_inventory_create(client):
    payload = {"ingredient_id": "I001", "location": "STOCK_AREA", "current_stock": 5, "min_threshold": 2, "max_capacity": 10}
    r = client.post(f"{BASE}/inventory", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["ingredient_id"] == "I001"
    assert data["location"] == "STOCK_AREA"
    inv_id = data["id"]
    r2 = client.get(f"{BASE}/inventory/{inv_id}")
    assert r2.status_code == 200
    client.delete(f"{BASE}/inventory/{inv_id}")


# ---------- Orders (UUID, needs menu_id) ----------
def test_kitchmatic_orders_list(client):
    r = client.get(f"{BASE}/orders")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data


def test_kitchmatic_orders_create(client):
    payload = {"table_number": "T1", "menu_id": "M001", "quantity": 2}
    r = client.post(f"{BASE}/orders", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["menu_id"] == "M001"
    assert data["table_number"] == "T1"
    order_id = data["id"]
    r2 = client.get(f"{BASE}/orders/{order_id}")
    assert r2.status_code == 200
    client.delete(f"{BASE}/orders/{order_id}")


def test_kitchmatic_orders_create_missing_field(client):
    r = client.post(f"{BASE}/orders", json={"table_number": "T1"})
    assert r.status_code == 400


# ---------- Inventory transactions (UUID, needs inventory_id) ----------
@pytest.fixture
def created_inventory_for_txn(client):
    # Use a pair unlikely to exist from other tests; create or reuse existing
    payload = {"ingredient_id": "I004", "location": "INGREDIENT_BED", "current_stock": 3}
    r = client.post(f"{BASE}/inventory", json=payload)
    if r.status_code == 201:
        inv = r.get_json()
        yield inv["id"]
        client.delete(f"{BASE}/inventory/{inv['id']}")
    else:
        # already exists (e.g. from prior run): get id from list
        r2 = client.get(f"{BASE}/inventory?ingredient_id=I004&location=INGREDIENT_BED")
        assert r2.status_code == 200
        items = r2.get_json().get("items", [])
        assert items, "need at least one inventory row for I004/INGREDIENT_BED"
        yield items[0]["id"]


def test_kitchmatic_inventory_transactions_list(client):
    r = client.get(f"{BASE}/inventory-transactions")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data


def test_kitchmatic_inventory_transaction_create(client, created_inventory_for_txn):
    payload = {
        "inventory_id": created_inventory_for_txn,
        "transaction_type": "REPLENISHMENT",
        "quantity": 2,
        "before_stock": 3,
        "after_stock": 5,
    }
    r = client.post(f"{BASE}/inventory-transactions", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["transaction_type"] == "REPLENISHMENT"
    assert data["after_stock"] == 5


# ---------- Quality check results (UUID, needs order_id) ----------
@pytest.fixture
def created_order_for_qc(client):
    r = client.post(f"{BASE}/orders", json={"table_number": "Q1", "menu_id": "M002", "quantity": 1})
    assert r.status_code == 201
    order_id = r.get_json()["id"]
    yield order_id
    client.delete(f"{BASE}/orders/{order_id}")


def test_kitchmatic_quality_checks_list(client):
    r = client.get(f"{BASE}/quality-check-results")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data and "count" in data


def test_kitchmatic_quality_check_create(client, created_order_for_qc):
    payload = {"order_id": created_order_for_qc, "status": "NORMAL", "confidence_score": 95.5}
    r = client.post(f"{BASE}/quality-check-results", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["order_id"] == created_order_for_qc
    assert data["status"] == "NORMAL"
    qc_id = data["id"]
    r2 = client.get(f"{BASE}/quality-check-results/{qc_id}")
    assert r2.status_code == 200
    client.delete(f"{BASE}/quality-check-results/{qc_id}")


def test_kitchmatic_quality_check_create_missing_order(client):
    r = client.post(f"{BASE}/quality-check-results", json={"status": "NORMAL"})
    assert r.status_code == 400


# ---------- 400 on invalid UUID for UUID resources ----------
def test_kitchmatic_orders_get_invalid_uuid(client):
    r = client.get(f"{BASE}/orders/not-a-uuid")
    assert r.status_code == 400


def test_kitchmatic_inventory_get_invalid_uuid(client):
    r = client.get(f"{BASE}/inventory/not-a-uuid")
    assert r.status_code == 400
