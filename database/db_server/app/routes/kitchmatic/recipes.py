# Kitchmatic: recipes + recipe_steps CRUD
import uuid
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models_kitchmatic import Recipe, RecipeStep
from ._helpers import row_to_dict

bp = Blueprint("kitchmatic_recipes", __name__, url_prefix="/kitchmatic/recipes")


def _parse_uuid(s):
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None


@bp.route("", methods=["GET"])
def list_recipes():
    """
    Kitchmatic 레시피 목록 조회
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: query
        name: menu_id
        type: string
    responses:
      200:
        description: 레시피 목록
    """
    db = get_db()
    try:
        q = db.query(Recipe)
        if request.args.get("menu_id"):
            q = q.filter(Recipe.menu_id == request.args.get("menu_id"))
        rows = q.all()
        return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})
    finally:
        db.close()


@bp.route("/<id>", methods=["GET"])
def get_recipe(id):
    """
    Kitchmatic 레시피 단건 조회 (steps 포함)
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 레시피 단건
      400:
        description: Invalid UUID
      404:
        description: Not found
    """
    uid = _parse_uuid(id)
    if not uid:
        return jsonify({"error": "Invalid UUID"}), 400
    db = get_db()
    try:
        row = db.query(Recipe).filter(Recipe.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        out = row_to_dict(row)
        out["steps"] = [row_to_dict(s) for s in row.steps]
        return jsonify(out)
    finally:
        db.close()


@bp.route("", methods=["POST"])
def create_recipe():
    """
    Kitchmatic 레시피 생성
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [menu_id, name, estimated_time_seconds]
          properties:
            menu_id: { type: string }
            name: { type: string }
            estimated_time_seconds: { type: integer }
    responses:
      201:
        description: 생성됨
      400:
        description: Bad request
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    for k in ("menu_id", "name", "estimated_time_seconds"):
        if k not in data:
            return jsonify({"error": f"Missing required field: {k}"}), 400
    db = get_db()
    try:
        row = Recipe(
            menu_id=data["menu_id"],
            name=data["name"],
            estimated_time_seconds=int(data["estimated_time_seconds"]),
        )
        db.add(row)
        db.commit()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.route("/<id>", methods=["PUT"])
def update_recipe(id):
    """
    Kitchmatic 레시피 수정
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: path
        name: id
        type: string
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            menu_id: { type: string }
            name: { type: string }
            estimated_time_seconds: { type: integer }
    responses:
      200:
        description: 수정됨
      400:
        description: Invalid UUID
      404:
        description: Not found
    """
    uid = _parse_uuid(id)
    if not uid:
        return jsonify({"error": "Invalid UUID"}), 400
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    db = get_db()
    try:
        row = db.query(Recipe).filter(Recipe.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if "menu_id" in data:
            row.menu_id = data["menu_id"]
        if "name" in data:
            row.name = data["name"]
        if "estimated_time_seconds" in data:
            row.estimated_time_seconds = int(data["estimated_time_seconds"])
        db.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.route("/<id>", methods=["DELETE"])
def delete_recipe(id):
    """
    Kitchmatic 레시피 삭제
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      204:
        description: 삭제됨
      400:
        description: Invalid UUID
      404:
        description: Not found
    """
    uid = _parse_uuid(id)
    if not uid:
        return jsonify({"error": "Invalid UUID"}), 400
    db = get_db()
    try:
        row = db.query(Recipe).filter(Recipe.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        db.delete(row)
        db.commit()
        return "", 204
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.route("/<id>/steps", methods=["GET"])
def list_recipe_steps(id):
    """
    Kitchmatic 레시피 단계 목록 조회
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 레시피 단계 목록
      400:
        description: Invalid UUID
      404:
        description: Recipe not found
    """
    uid = _parse_uuid(id)
    if not uid:
        return jsonify({"error": "Invalid UUID"}), 400
    db = get_db()
    try:
        recipe = db.query(Recipe).filter(Recipe.id == uid).first()
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404
        return jsonify({"items": [row_to_dict(s) for s in recipe.steps], "count": len(recipe.steps)})
    finally:
        db.close()


@bp.route("/<id>/steps", methods=["POST"])
def create_recipe_step(id):
    """
    Kitchmatic 레시피 단계 추가
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: path
        name: id
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [step_order, action, robot_arm]
          properties:
            step_order: { type: integer }
            action: { type: string }
            ingredient_id: { type: string }
            quantity: { type: integer }
            unit: { type: string }
            robot_arm: { type: string }
            duration_seconds: { type: integer }
    responses:
      201:
        description: 생성됨
      400:
        description: Bad request / Invalid UUID
      404:
        description: Recipe not found
    """
    uid = _parse_uuid(id)
    if not uid:
        return jsonify({"error": "Invalid UUID"}), 400
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    for k in ("step_order", "action", "robot_arm"):
        if k not in data:
            return jsonify({"error": f"Missing required field: {k}"}), 400
    db = get_db()
    try:
        recipe = db.query(Recipe).filter(Recipe.id == uid).first()
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404
        row = RecipeStep(
            recipe_id=uid,
            step_order=int(data["step_order"]),
            action=data["action"],
            ingredient_id=data.get("ingredient_id"),
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            robot_arm=data["robot_arm"],
            duration_seconds=data.get("duration_seconds"),
        )
        db.add(row)
        db.commit()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.route("/<rid>/steps/<sid>", methods=["GET"])
def get_recipe_step(rid, sid):
    """
    Kitchmatic 레시피 단계 단건 조회
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: path
        name: rid
        type: string
        required: true
      - in: path
        name: sid
        type: string
        required: true
    responses:
      200:
        description: 레시피 단계 단건
      400:
        description: Invalid UUID
      404:
        description: Not found
    """
    ruid, suid = _parse_uuid(rid), _parse_uuid(sid)
    if not ruid or not suid:
        return jsonify({"error": "Invalid UUID"}), 400
    db = get_db()
    try:
        row = db.query(RecipeStep).filter(RecipeStep.recipe_id == ruid, RecipeStep.id == suid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        db.close()


@bp.route("/<rid>/steps/<sid>", methods=["PUT"])
def update_recipe_step(rid, sid):
    """
    Kitchmatic 레시피 단계 수정
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: path
        name: rid
        type: string
        required: true
      - in: path
        name: sid
        type: string
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            step_order: { type: integer }
            action: { type: string }
            ingredient_id: { type: string }
            quantity: { type: integer }
            unit: { type: string }
            robot_arm: { type: string }
            duration_seconds: { type: integer }
    responses:
      200:
        description: 수정됨
      400:
        description: Invalid UUID
      404:
        description: Not found
    """
    ruid, suid = _parse_uuid(rid), _parse_uuid(sid)
    if not ruid or not suid:
        return jsonify({"error": "Invalid UUID"}), 400
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    db = get_db()
    try:
        row = db.query(RecipeStep).filter(RecipeStep.recipe_id == ruid, RecipeStep.id == suid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if "step_order" in data:
            row.step_order = int(data["step_order"])
        if "action" in data:
            row.action = data["action"]
        if "ingredient_id" in data:
            row.ingredient_id = data["ingredient_id"]
        if "quantity" in data:
            row.quantity = int(data["quantity"]) if data["quantity"] is not None else None
        if "unit" in data:
            row.unit = data["unit"]
        if "robot_arm" in data:
            row.robot_arm = data["robot_arm"]
        if "duration_seconds" in data:
            row.duration_seconds = int(data["duration_seconds"]) if data["duration_seconds"] is not None else None
        db.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.route("/<rid>/steps/<sid>", methods=["DELETE"])
def delete_recipe_step(rid, sid):
    """
    Kitchmatic 레시피 단계 삭제
    ---
    tags:
      - Kitchmatic - Recipes
    parameters:
      - in: path
        name: rid
        type: string
        required: true
      - in: path
        name: sid
        type: string
        required: true
    responses:
      204:
        description: 삭제됨
      400:
        description: Invalid UUID
      404:
        description: Not found
    """
    ruid, suid = _parse_uuid(rid), _parse_uuid(sid)
    if not ruid or not suid:
        return jsonify({"error": "Invalid UUID"}), 400
    db = get_db()
    try:
        row = db.query(RecipeStep).filter(RecipeStep.recipe_id == ruid, RecipeStep.id == suid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        db.delete(row)
        db.commit()
        return "", 204
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
