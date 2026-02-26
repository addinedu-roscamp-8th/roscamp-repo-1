# Kitchmatic: menus CRUD
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models_kitchmatic import Menu
from ._helpers import row_to_dict

bp = Blueprint("kitchmatic_menus", __name__, url_prefix="/kitchmatic/menus")


@bp.route("", methods=["GET"])
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
      - in: query
        name: available
        type: string
    responses:
      200:
        description: 메뉴 목록
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        q = db.query(Menu)
        if request.args.get("category"):
            q = q.filter(Menu.category == request.args.get("category"))
        if request.args.get("available") is not None:
            q = q.filter(Menu.available == (request.args.get("available").lower() in ("true", "1")))
        rows = q.all()
        return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})
    finally:
        db.close()


@bp.route("/<id>", methods=["GET"])
def get_menu(id):
    """
    Kitchmatic 메뉴 단건 조회
    ---
    tags:
      - Kitchmatic - Menus
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 메뉴 단건
      404:
        description: Not found
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        row = db.query(Menu).filter(Menu.id == id).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        db.close()


@bp.route("", methods=["POST"])
def create_menu():
    """
    Kitchmatic 메뉴 생성
    ---
    tags:
      - Kitchmatic - Menus
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [id, name, price, category]
          properties:
            id: { type: string }
            name: { type: string }
            price: { type: integer }
            category: { type: string }
            available: { type: boolean }
            description: { type: string }
            image_url: { type: string }
    responses:
      201:
        description: 생성됨
      400:
        description: Bad request
      500:
        description: 서버 오류
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    for k in ("id", "name", "price", "category"):
        if k not in data:
            return jsonify({"error": f"Missing required field: {k}"}), 400
    db = get_db()
    try:
        if db.query(Menu).filter(Menu.id == data["id"]).first():
            return jsonify({"error": "Menu id already exists"}), 400
        row = Menu(
            id=data["id"],
            name=data["name"],
            price=int(data["price"]),
            category=data["category"],
            available=data.get("available", True),
            description=data.get("description") or "",
            image_url=data.get("image_url") or "",
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
def update_menu(id):
    """
    Kitchmatic 메뉴 수정
    ---
    tags:
      - Kitchmatic - Menus
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
            name: { type: string }
            price: { type: integer }
            category: { type: string }
            available: { type: boolean }
            description: { type: string }
            image_url: { type: string }
    responses:
      200:
        description: 수정됨
      404:
        description: Not found
      500:
        description: 서버 오류
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    db = get_db()
    try:
        row = db.query(Menu).filter(Menu.id == id).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if "name" in data:
            row.name = data["name"]
        if "price" in data:
            row.price = int(data["price"])
        if "category" in data:
            row.category = data["category"]
        if "available" in data:
            row.available = bool(data["available"])
        if "description" in data:
            row.description = data["description"] or ""
        if "image_url" in data:
            row.image_url = data["image_url"] or ""
        db.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.route("/<id>", methods=["DELETE"])
def delete_menu(id):
    """
    Kitchmatic 메뉴 삭제
    ---
    tags:
      - Kitchmatic - Menus
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      204:
        description: 삭제됨
      404:
        description: Not found
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        row = db.query(Menu).filter(Menu.id == id).first()
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
