# Kitchmatic: ingredients CRUD
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models_kitchmatic import Ingredient
from ._helpers import row_to_dict

bp = Blueprint("kitchmatic_ingredients", __name__, url_prefix="/kitchmatic/ingredients")


@bp.route("", methods=["GET"])
def list_ingredients():
    """
    Kitchmatic 식재료 목록 조회
    ---
    tags:
      - Kitchmatic - Ingredients
    parameters:
      - in: query
        name: category
        type: string
    responses:
      200:
        description: 식재료 목록
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        q = db.query(Ingredient)
        if request.args.get("category"):
            q = q.filter(Ingredient.category == request.args.get("category"))
        rows = q.all()
        return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})
    finally:
        db.close()


@bp.route("/<id>", methods=["GET"])
def get_ingredient(id):
    """
    Kitchmatic 식재료 단건 조회
    ---
    tags:
      - Kitchmatic - Ingredients
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 식재료
      404:
        description: 없음
    """
    db = get_db()
    try:
        row = db.query(Ingredient).filter(Ingredient.id == id).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        db.close()


@bp.route("", methods=["POST"])
def create_ingredient():
    """
    Kitchmatic 식재료 생성
    ---
    tags:
      - Kitchmatic - Ingredients
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [id, name, unit, category]
          properties:
            id: { type: string }
            name: { type: string }
            unit: { type: string }
            category: { type: string }
            items_per_box: { type: integer, default: 5 }
    responses:
      201:
        description: 생성됨
      400:
        description: 잘못된 요청
      500:
        description: 서버 오류
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    for k in ("id", "name", "unit", "category"):
        if k not in data:
            return jsonify({"error": f"Missing required field: {k}"}), 400
    db = get_db()
    try:
        if db.query(Ingredient).filter(Ingredient.id == data["id"]).first():
            return jsonify({"error": "Ingredient id already exists"}), 400
        row = Ingredient(
            id=data["id"],
            name=data["name"],
            unit=data["unit"],
            category=data["category"],
            items_per_box=int(data.get("items_per_box", 5)),
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
def update_ingredient(id):
    """
    Kitchmatic 식재료 수정
    ---
    tags:
      - Kitchmatic - Ingredients
    parameters:
      - in: path
        name: id
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            name: { type: string }
            unit: { type: string }
            category: { type: string }
            items_per_box: { type: integer }
    responses:
      200:
        description: 수정됨
      404:
        description: 없음
      500:
        description: 서버 오류
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    db = get_db()
    try:
        row = db.query(Ingredient).filter(Ingredient.id == id).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if "name" in data:
            row.name = data["name"]
        if "unit" in data:
            row.unit = data["unit"]
        if "category" in data:
            row.category = data["category"]
        if "items_per_box" in data:
            row.items_per_box = int(data["items_per_box"])
        db.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.route("/<id>", methods=["DELETE"])
def delete_ingredient(id):
    """
    Kitchmatic 식재료 삭제
    ---
    tags:
      - Kitchmatic - Ingredients
    parameters:
      - in: path
        name: id
        required: true
    responses:
      204:
        description: 삭제됨
      404:
        description: 없음
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        row = db.query(Ingredient).filter(Ingredient.id == id).first()
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
