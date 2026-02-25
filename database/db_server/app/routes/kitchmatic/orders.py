# Kitchmatic: orders CRUD
import uuid
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models_kitchmatic import Order
from ._helpers import row_to_dict

bp = Blueprint("kitchmatic_orders", __name__, url_prefix="/kitchmatic/orders")

def _parse_uuid(s):
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None

@bp.route("", methods=["GET"])
def list_orders():
    """
    Kitchmatic 주문 목록 조회
    ---
    tags:
      - Kitchmatic - Orders
    parameters:
      - in: query
        name: status
        type: string
      - in: query
        name: table_number
        type: string
    responses:
      200:
        description: 주문 목록
    """
    db = get_db()
    try:
        q = db.query(Order)
        if request.args.get("status"):
            q = q.filter(Order.status == request.args.get("status"))
        if request.args.get("table_number"):
            q = q.filter(Order.table_number == request.args.get("table_number"))
        rows = q.order_by(Order.created_at.desc()).limit(100).all()
        return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})
    finally:
        db.close()

@bp.route("/<id>", methods=["GET"])
def get_order(id):
    """
    Kitchmatic 주문 단건 조회
    ---
    tags:
      - Kitchmatic - Orders
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 주문 단건
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
        row = db.query(Order).filter(Order.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        db.close()

@bp.route("", methods=["POST"])
def create_order():
    """
    Kitchmatic 주문 생성
    ---
    tags:
      - Kitchmatic - Orders
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [table_number, menu_id, quantity]
          properties:
            table_number: { type: string }
            menu_id: { type: string }
            quantity: { type: integer }
            status: { type: string }
            voice_order: { type: boolean }
            assigned_robot_arm_id: { type: string }
            assigned_serving_bot_id: { type: string }
    responses:
      201:
        description: 생성됨
      400:
        description: Bad request
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    for k in ("table_number", "menu_id", "quantity"):
        if k not in data:
            return jsonify({"error": f"Missing required: {k}"}), 400
    db = get_db()
    try:
        row = Order(table_number=data["table_number"], menu_id=data["menu_id"], quantity=int(data["quantity"]),
            status=data.get("status", "PENDING"), voice_order=data.get("voice_order", False),
            assigned_robot_arm_id=_parse_uuid(data["assigned_robot_arm_id"]) if data.get("assigned_robot_arm_id") else None,
            assigned_serving_bot_id=_parse_uuid(data["assigned_serving_bot_id"]) if data.get("assigned_serving_bot_id") else None)
        db.add(row)
        db.commit()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@bp.route("/<id>", methods=["PUT"])
def update_order(id):
    """
    Kitchmatic 주문 수정
    ---
    tags:
      - Kitchmatic - Orders
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
            table_number: { type: string }
            menu_id: { type: string }
            quantity: { type: integer }
            status: { type: string }
            assigned_robot_arm_id: { type: string }
            assigned_serving_bot_id: { type: string }
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
        row = db.query(Order).filter(Order.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if "table_number" in data:
            row.table_number = data["table_number"]
        if "menu_id" in data:
            row.menu_id = data["menu_id"]
        if "quantity" in data:
            row.quantity = int(data["quantity"])
        if "status" in data:
            row.status = data["status"]
        if "completed_at" in data:
            row.completed_at = data["completed_at"]
        if "assigned_robot_arm_id" in data:
            row.assigned_robot_arm_id = _parse_uuid(data["assigned_robot_arm_id"]) if data["assigned_robot_arm_id"] else None
        if "assigned_serving_bot_id" in data:
            row.assigned_serving_bot_id = _parse_uuid(data["assigned_serving_bot_id"]) if data["assigned_serving_bot_id"] else None
        db.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@bp.route("/<id>", methods=["DELETE"])
def delete_order(id):
    """
    Kitchmatic 주문 삭제
    ---
    tags:
      - Kitchmatic - Orders
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
        row = db.query(Order).filter(Order.id == uid).first()
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
