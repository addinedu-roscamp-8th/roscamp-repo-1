# Kitchmatic: quality_check_results CRUD
import uuid
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models_kitchmatic import QualityCheckResult
from ._helpers import row_to_dict

bp = Blueprint("kitchmatic_quality_checks", __name__, url_prefix="/kitchmatic/quality-check-results")


def _parse_uuid(s):
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError):
        return None


@bp.route("", methods=["GET"])
def list_quality_checks():
    """
    Kitchmatic 품질검사 목록 조회
    ---
    tags:
      - Kitchmatic - Quality
    parameters:
      - in: query
        name: order_id
        type: string
      - in: query
        name: status
        type: string
    responses:
      200:
        description: 품질검사 목록
    """
    db = get_db()
    try:
        q = db.query(QualityCheckResult)
        if request.args.get("order_id"):
            uid = _parse_uuid(request.args.get("order_id"))
            if uid:
                q = q.filter(QualityCheckResult.order_id == uid)
        if request.args.get("status"):
            q = q.filter(QualityCheckResult.status == request.args.get("status"))
        rows = q.order_by(QualityCheckResult.checked_at.desc()).limit(100).all()
        return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})
    finally:
        db.close()


@bp.route("/<id>", methods=["GET"])
def get_quality_check(id):
    """
    Kitchmatic 품질검사 단건 조회
    ---
    tags:
      - Kitchmatic - Quality
    parameters:
      - in: path
        name: id
        type: string
        required: true
    responses:
      200:
        description: 품질검사 단건
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
        row = db.query(QualityCheckResult).filter(QualityCheckResult.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        db.close()


@bp.route("", methods=["POST"])
def create_quality_check():
    """
    Kitchmatic 품질검사 생성
    ---
    tags:
      - Kitchmatic - Quality
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [order_id, status]
          properties:
            order_id: { type: string }
            status: { type: string }
            confidence_score: { type: number }
            attempt_number: { type: integer }
            robot_arm_id: { type: string }
    responses:
      201:
        description: 생성됨
      400:
        description: Bad request
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    if "order_id" not in data or "status" not in data:
        return jsonify({"error": "Missing required field: order_id, status"}), 400
    db = get_db()
    try:
        row = QualityCheckResult(
            order_id=_parse_uuid(data["order_id"]),
            status=data["status"],
            confidence_score=float(data["confidence_score"]) if data.get("confidence_score") is not None else None,
            attempt_number=int(data.get("attempt_number", 1)),
            robot_arm_id=_parse_uuid(data["robot_arm_id"]) if data.get("robot_arm_id") else None,
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
def update_quality_check(id):
    """
    Kitchmatic 품질검사 수정
    ---
    tags:
      - Kitchmatic - Quality
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
            status: { type: string }
            confidence_score: { type: number }
            attempt_number: { type: integer }
            robot_arm_id: { type: string }
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
        row = db.query(QualityCheckResult).filter(QualityCheckResult.id == uid).first()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if "status" in data:
            row.status = data["status"]
        if "confidence_score" in data:
            row.confidence_score = float(data["confidence_score"]) if data["confidence_score"] is not None else None
        if "attempt_number" in data:
            row.attempt_number = int(data["attempt_number"])
        if "robot_arm_id" in data:
            row.robot_arm_id = _parse_uuid(data["robot_arm_id"]) if data["robot_arm_id"] else None
        db.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@bp.route("/<id>", methods=["DELETE"])
def delete_quality_check(id):
    """
    Kitchmatic 품질검사 삭제
    ---
    tags:
      - Kitchmatic - Quality
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
        row = db.query(QualityCheckResult).filter(QualityCheckResult.id == uid).first()
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
