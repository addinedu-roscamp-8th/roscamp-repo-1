# Kitchmatic: inventory + inventory_transactions
import uuid
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models_kitchmatic import Inventory, InventoryTransaction
from ._helpers import row_to_dict

bp = Blueprint("kitchmatic_inventory", __name__, url_prefix="/kitchmatic/inventory")
bp_txn = Blueprint("kitchmatic_inventory_txn", __name__, url_prefix="/kitchmatic/inventory-transactions")

def _parse_uuid(s):
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None

@bp.route("", methods=["GET"])
def list_inventory():
    """
    Kitchmatic 재고 목록 조회
    ---
    tags:
      - Kitchmatic - Inventory
    parameters:
      - in: query
        name: ingredient_id
        type: string
      - in: query
        name: location
        type: string
    responses:
      200:
        description: 재고 목록
    """
    db = get_db()
    try:
        q = db.query(Inventory)
        if request.args.get("ingredient_id"):
            q = q.filter(Inventory.ingredient_id == request.args.get("ingredient_id"))
        if request.args.get("location"):
            q = q.filter(Inventory.location == request.args.get("location"))
        rows = q.all()
        return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})
    finally:
        db.close()

@bp.route("/<id>", methods=["GET"])
def get_inventory(id):
    """
    Kitchmatic 재고 단건 조회
    ---
    tags:
      - Kitchmatic - Inventory
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 재고 단건
      404:
        description: Not found
    """
    uid = _parse_uuid(id)
    if not uid:
        return jsonify({"error": "Invalid UUID"}), 400
    db = get_db()
    try:
        row = db.query(Inventory).filter(Inventory.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        db.close()

@bp.route("", methods=["POST"])
def create_inventory():
    """
    Kitchmatic 재고 생성
    ---
    tags:
      - Kitchmatic - Inventory
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [ingredient_id, location]
          properties:
            ingredient_id: { type: string }
            location: { type: string }
            current_stock: { type: integer }
            min_threshold: { type: integer }
            max_capacity: { type: integer }
    responses:
      201:
        description: 생성됨
      400:
        description: Bad request
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    if "ingredient_id" not in data or "location" not in data:
        return jsonify({"error": "Missing required: ingredient_id, location"}), 400
    db = get_db()
    try:
        row = Inventory(
            ingredient_id=data["ingredient_id"],
            location=data["location"],
            current_stock=int(data.get("current_stock", 0)),
            min_threshold=int(data.get("min_threshold", 2)),
            max_capacity=int(data.get("max_capacity", 10)),
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
def update_inventory(id):
    """
    Kitchmatic 재고 수정
    ---
    tags:
      - Kitchmatic - Inventory
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
            current_stock: { type: integer }
            min_threshold: { type: integer }
            max_capacity: { type: integer }
    responses:
      200:
        description: 수정됨
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
        row = db.query(Inventory).filter(Inventory.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if "current_stock" in data:
            row.current_stock = int(data["current_stock"])
        if "min_threshold" in data:
            row.min_threshold = int(data["min_threshold"])
        if "max_capacity" in data:
            row.max_capacity = int(data["max_capacity"])
        db.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@bp.route("/<id>", methods=["DELETE"])
def delete_inventory(id):
    """
    Kitchmatic 재고 삭제
    ---
    tags:
      - Kitchmatic - Inventory
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
    """
    uid = _parse_uuid(id)
    if not uid:
        return jsonify({"error": "Invalid UUID"}), 400
    db = get_db()
    try:
        row = db.query(Inventory).filter(Inventory.id == uid).first()
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

@bp_txn.route("", methods=["GET"])
def list_transactions():
    """
    Kitchmatic 재고 거래 목록 조회
    ---
    tags:
      - Kitchmatic - Inventory
    parameters:
      - in: query
        name: inventory_id
        type: string
      - in: query
        name: order_id
        type: string
    responses:
      200:
        description: 거래 목록
    """
    db = get_db()
    try:
        q = db.query(InventoryTransaction)
        inv_id = request.args.get("inventory_id")
        if inv_id:
            uid = _parse_uuid(inv_id)
            if uid:
                q = q.filter(InventoryTransaction.inventory_id == uid)
        ord_id = request.args.get("order_id")
        if ord_id:
            uid = _parse_uuid(ord_id)
            if uid:
                q = q.filter(InventoryTransaction.order_id == uid)
        rows = q.order_by(InventoryTransaction.transaction_at.desc()).limit(100).all()
        return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})
    finally:
        db.close()

@bp_txn.route("/<id>", methods=["GET"])
def get_transaction(id):
    """
    Kitchmatic 재고 거래 단건 조회
    ---
    tags:
      - Kitchmatic - Inventory
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 거래 단건
      404:
        description: Not found
    """
    uid = _parse_uuid(id)
    if not uid:
        return jsonify({"error": "Invalid UUID"}), 400
    db = get_db()
    try:
        row = db.query(InventoryTransaction).filter(InventoryTransaction.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        db.close()

@bp_txn.route("", methods=["POST"])
def create_transaction():
    """
    Kitchmatic 재고 거래 생성
    ---
    tags:
      - Kitchmatic - Inventory
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [inventory_id, transaction_type, quantity, before_stock, after_stock]
          properties:
            inventory_id: { type: string }
            transaction_type: { type: string }
            quantity: { type: integer }
            before_stock: { type: integer }
            after_stock: { type: integer }
            order_id: { type: string }
            robot_id: { type: string }
    responses:
      201:
        description: 생성됨
      400:
        description: Bad request
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    for k in ("inventory_id", "transaction_type", "quantity", "before_stock", "after_stock"):
        if k not in data:
            return jsonify({"error": "Missing required: " + k}), 400
    db = get_db()
    try:
        row = InventoryTransaction(
            inventory_id=_parse_uuid(data["inventory_id"]),
            transaction_type=data["transaction_type"],
            quantity=int(data["quantity"]),
            before_stock=int(data["before_stock"]),
            after_stock=int(data["after_stock"]),
            order_id=_parse_uuid(data["order_id"]) if data.get("order_id") else None,
            robot_id=_parse_uuid(data["robot_id"]) if data.get("robot_id") else None,
        )
        db.add(row)
        db.commit()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
