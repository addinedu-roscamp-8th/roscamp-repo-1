# Kitchmatic: robots CRUD
import uuid
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models_kitchmatic import Robot
from ._helpers import row_to_dict

bp = Blueprint("kitchmatic_robots", __name__, url_prefix="/kitchmatic/robots")

def _parse_uuid(s):
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None

@bp.route("", methods=["GET"])
def list_robots():
    """
    Kitchmatic 로봇 목록 조회
    ---
    tags:
      - Kitchmatic - Robots
    parameters:
      - in: query
        name: type
        type: string
      - in: query
        name: status
        type: string
    responses:
      200:
        description: 로봇 목록
    """
    db = get_db()
    try:
        q = db.query(Robot)
        if request.args.get("type"):
            q = q.filter(Robot.type == request.args.get("type"))
        if request.args.get("status"):
            q = q.filter(Robot.status == request.args.get("status"))
        rows = q.all()
        return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})
    finally:
        db.close()

@bp.route("/<id>", methods=["GET"])
def get_robot(id):
    """
    Kitchmatic 로봇 단건 조회
    ---
    tags:
      - Kitchmatic - Robots
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 로봇 단건
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
        row = db.query(Robot).filter(Robot.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        db.close()

@bp.route("", methods=["POST"])
def create_robot():
    """
    Kitchmatic 로봇 생성
    ---
    tags:
      - Kitchmatic - Robots
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [name, type, ip_address, port]
          properties:
            name: { type: string }
            type: { type: string }
            ip_address: { type: string }
            port: { type: integer }
            status: { type: string }
    responses:
      201:
        description: 생성됨
      400:
        description: Bad request
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    for k in ("name", "type", "ip_address", "port"):
        if k not in data:
            return jsonify({"error": f"Missing required field: {k}"}), 400
    db = get_db()
    try:
        if db.query(Robot).filter(Robot.name == data["name"]).first():
            return jsonify({"error": "Robot name already exists"}), 400
        row = Robot(name=data["name"], type=data["type"], ip_address=data["ip_address"], port=int(data["port"]), status=data.get("status", "IDLE"))
        db.add(row)
        db.commit()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@bp.route("/<id>", methods=["PUT"])
def update_robot(id):
    """
    Kitchmatic 로봇 수정
    ---
    tags:
      - Kitchmatic - Robots
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
            type: { type: string }
            status: { type: string }
            ip_address: { type: string }
            port: { type: integer }
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
        row = db.query(Robot).filter(Robot.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        for k in ("name", "type", "status", "ip_address", "port", "last_heartbeat"):
            if k in data:
                v = data[k]
                if k == "port":
                    v = int(v)
                setattr(row, k, v)
        db.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@bp.route("/<id>", methods=["DELETE"])
def delete_robot(id):
    """
    Kitchmatic 로봇 삭제
    ---
    tags:
      - Kitchmatic - Robots
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
        row = db.query(Robot).filter(Robot.id == uid).first()
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
