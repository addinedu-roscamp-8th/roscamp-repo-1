from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models import StoreIngredientMst, StoreIngredientTxn
from sqlalchemy import desc
from datetime import datetime
import uuid

bp = Blueprint('ingredients', __name__, url_prefix='/ingredients')


@bp.route('', methods=['GET'])
def list_ingredients():
    """
    원재료 마스터 목록 조회
    ---
    tags:
      - Ingredients
    parameters:
      - in: query
        name: category
        type: string
        description: "카테고리 필터 (bread/cheese/veg/meat/sauce/etc)"
      - in: query
        name: is_active
        type: boolean
        description: "활성 상태 필터"
      - in: query
        name: limit
        type: integer
        default: 50
        description: 페이지 크기
      - in: query
        name: offset
        type: integer
        default: 0
        description: 오프셋
    responses:
      200:
        description: 원재료 목록
        schema:
          type: object
          properties:
            total:
              type: integer
            ingredients:
              type: array
              items:
                type: object
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        query = db.query(StoreIngredientMst)
        
        category = request.args.get('category')
        if category:
            query = query.filter(StoreIngredientMst.category == category)
        
        is_active = request.args.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() in ('true', '1', 'yes')
            query = query.filter(StoreIngredientMst.is_active == is_active_bool)
        
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        total = query.count()
        ingredients = query.limit(limit).offset(offset).all()
        
        return jsonify({
            'total': total,
            'limit': limit,
            'offset': offset,
            'ingredients': [{
                'ingredient_id': str(ing.ingredient_id),
                'ingredient_sku': ing.ingredient_sku,
                'ingredient_name': ing.ingredient_name,
                'category': ing.category,
                'base_unit': ing.base_unit,
                'is_active': ing.is_active,
                'meta': ing.meta,
                'created_at': ing.created_at.isoformat() if ing.created_at else None,
                'updated_at': ing.updated_at.isoformat() if ing.updated_at else None
            } for ing in ingredients]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/<ingredient_sku>', methods=['GET'])
def get_ingredient(ingredient_sku):
    """
    원재료 상세 조회
    ---
    tags:
      - Ingredients
    parameters:
      - in: path
        name: ingredient_sku
        type: string
        required: true
        description: 원재료 SKU
    responses:
      200:
        description: 원재료 상세 정보
      404:
        description: 원재료를 찾을 수 없음
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        ingredient = db.query(StoreIngredientMst).filter(
            StoreIngredientMst.ingredient_sku == ingredient_sku
        ).first()
        
        if not ingredient:
            return jsonify({'error': 'Ingredient not found'}), 404
        
        return jsonify({
            'ingredient_id': str(ingredient.ingredient_id),
            'ingredient_sku': ingredient.ingredient_sku,
            'ingredient_name': ingredient.ingredient_name,
            'category': ingredient.category,
            'base_unit': ingredient.base_unit,
            'is_active': ingredient.is_active,
            'meta': ingredient.meta,
            'created_at': ingredient.created_at.isoformat() if ingredient.created_at else None,
            'updated_at': ingredient.updated_at.isoformat() if ingredient.updated_at else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('', methods=['POST'])
def create_ingredient():
    """
    원재료 생성
    ---
    tags:
      - Ingredients
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - ingredient_sku
            - ingredient_name
            - category
          properties:
            ingredient_sku:
              type: string
              description: "원재료 SKU (고유)"
              example: ING-BREAD-WHEAT
            ingredient_name:
              type: string
              description: "원재료명"
              example: Wheat Bread
            category:
              type: string
              description: "카테고리"
              example: bread
            base_unit:
              type: string
              description: "기본 단위 (기본값: g)"
              example: g
            is_active:
              type: boolean
              description: "활성 상태 (기본값: true)"
              example: true
            meta:
              type: object
              description: "추가 메타데이터"
    responses:
      201:
        description: 원재료가 성공적으로 생성되었습니다
      400:
        description: 잘못된 요청
      500:
        description: 서버 오류
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    required_fields = ['ingredient_sku', 'ingredient_name', 'category']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    db = get_db()
    try:
        # 중복 체크
        existing = db.query(StoreIngredientMst).filter(
            StoreIngredientMst.ingredient_sku == data['ingredient_sku']
        ).first()
        
        if existing:
            return jsonify({'error': 'Ingredient SKU already exists'}), 400
        
        ingredient = StoreIngredientMst(
            ingredient_sku=data['ingredient_sku'],
            ingredient_name=data['ingredient_name'],
            category=data['category'],
            base_unit=data.get('base_unit', 'g'),
            is_active=data.get('is_active', True),
            meta=data.get('meta', {})
        )
        
        db.add(ingredient)
        db.commit()
        
        return jsonify({
            'ingredient_id': str(ingredient.ingredient_id),
            'ingredient_sku': ingredient.ingredient_sku,
            'ingredient_name': ingredient.ingredient_name,
            'category': ingredient.category,
            'base_unit': ingredient.base_unit,
            'is_active': ingredient.is_active,
            'created_at': ingredient.created_at.isoformat() if ingredient.created_at else None
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/<ingredient_sku>', methods=['PATCH'])
def update_ingredient(ingredient_sku):
    """
    원재료 수정
    ---
    tags:
      - Ingredients
    parameters:
      - in: path
        name: ingredient_sku
        type: string
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            ingredient_name:
              type: string
            category:
              type: string
            base_unit:
              type: string
            is_active:
              type: boolean
            meta:
              type: object
    responses:
      200:
        description: 원재료가 성공적으로 수정되었습니다
      404:
        description: 원재료를 찾을 수 없음
      500:
        description: 서버 오류
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    db = get_db()
    try:
        ingredient = db.query(StoreIngredientMst).filter(
            StoreIngredientMst.ingredient_sku == ingredient_sku
        ).first()
        
        if not ingredient:
            return jsonify({'error': 'Ingredient not found'}), 404
        
        # 업데이트 가능한 필드만 수정
        if 'ingredient_name' in data:
            ingredient.ingredient_name = data['ingredient_name']
        if 'category' in data:
            ingredient.category = data['category']
        if 'base_unit' in data:
            ingredient.base_unit = data['base_unit']
        if 'is_active' in data:
            ingredient.is_active = data['is_active']
        if 'meta' in data:
            ingredient.meta = data['meta']
        
        # updated_at은 모델의 onupdate=func.now()에 의해 자동 갱신됨
        # 명시적으로 설정하지 않음 (DB의 func.now() 사용)
        
        db.commit()
        
        return jsonify({
            'ingredient_id': str(ingredient.ingredient_id),
            'ingredient_sku': ingredient.ingredient_sku,
            'ingredient_name': ingredient.ingredient_name,
            'category': ingredient.category,
            'base_unit': ingredient.base_unit,
            'is_active': ingredient.is_active,
            'meta': ingredient.meta,
            'updated_at': ingredient.updated_at.isoformat() if ingredient.updated_at else None
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/<ingredient_sku>', methods=['DELETE'])
def delete_ingredient(ingredient_sku):
    """
    원재료 삭제 (또는 비활성화)
    ---
    tags:
      - Ingredients
    parameters:
      - in: path
        name: ingredient_sku
        type: string
        required: true
      - in: query
        name: hard_delete
        type: boolean
        default: false
        description: "true면 실제 삭제, false면 is_active=false로 설정"
    responses:
      200:
        description: 원재료가 삭제되었습니다
      404:
        description: 원재료를 찾을 수 없음
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        ingredient = db.query(StoreIngredientMst).filter(
            StoreIngredientMst.ingredient_sku == ingredient_sku
        ).first()
        
        if not ingredient:
            return jsonify({'error': 'Ingredient not found'}), 404
        
        hard_delete = request.args.get('hard_delete', 'false').lower() == 'true'
        
        if hard_delete:
            db.delete(ingredient)
        else:
            ingredient.is_active = False
            # updated_at은 모델의 onupdate=func.now()에 의해 자동 갱신됨
            # 명시적으로 설정하지 않음 (DB의 func.now() 사용)
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Ingredient deleted' if hard_delete else 'Ingredient deactivated'
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/txn', methods=['POST'])
def create_ingredient_txn():
    """
    원재료 거래 이벤트 생성
    ---
    tags:
      - Ingredients
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - ingredient_sku
            - qty_delta
            - txn_type
          properties:
            ingredient_sku:
              type: string
              description: "원재료 SKU"
            unit:
              type: string
              description: "단위 (기본값: g)"
            qty_delta:
              type: number
              description: "수량 변동 (양수: 입고, 음수: 사용/폐기)"
            txn_type:
              type: string
              enum: [in, out, waste, adjust]
              description: "거래 유형"
            reason:
              type: string
              description: "사유"
            order_id:
              type: string
              format: uuid
              description: "관련 주문 ID"
            occurred_at:
              type: string
              format: date-time
              description: "발생 시각 (ISO 8601)"
            meta:
              type: object
    responses:
      201:
        description: 거래 이벤트가 생성되었습니다
      400:
        description: 잘못된 요청
      500:
        description: 서버 오류
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    required_fields = ['ingredient_sku', 'qty_delta', 'txn_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    db = get_db()
    try:
        # 원재료 존재 확인
        ingredient = db.query(StoreIngredientMst).filter(
            StoreIngredientMst.ingredient_sku == data['ingredient_sku']
        ).first()
        
        if not ingredient:
            return jsonify({'error': 'Ingredient not found'}), 404
        
        txn_type = data['txn_type']
        qty_delta = float(data['qty_delta'])
        
        # txn_type에 따른 qty_delta 검증 및 변환
        if txn_type in ('out', 'waste'):
            if qty_delta > 0:
                qty_delta = -abs(qty_delta)
        elif txn_type == 'in':
            if qty_delta < 0:
                qty_delta = abs(qty_delta)
        
        # occurred_at 파싱
        occurred_at = datetime.utcnow()
        if 'occurred_at' in data and data['occurred_at']:
            try:
                occurred_at = datetime.fromisoformat(data['occurred_at'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid occurred_at format. Use ISO 8601'}), 400
        
        # order_id 파싱
        order_id = None
        if 'order_id' in data and data['order_id']:
            try:
                order_id = uuid.UUID(data['order_id'])
            except ValueError:
                return jsonify({'error': 'Invalid order_id format'}), 400
        
        txn = StoreIngredientTxn(
            ingredient_txn_id=uuid.uuid4(),
            ingredient_sku=data['ingredient_sku'],
            unit=data.get('unit', ingredient.base_unit),
            qty_delta=qty_delta,
            txn_type=txn_type,
            reason=data.get('reason'),
            order_id=order_id,
            occurred_at=occurred_at,
            meta=data.get('meta', {})
        )
        
        db.add(txn)
        db.commit()
        
        return jsonify({
            'ingredient_txn_id': str(txn.ingredient_txn_id),
            'ingredient_sku': txn.ingredient_sku,
            'txn_type': txn.txn_type,
            'qty_delta': float(txn.qty_delta),
            'occurred_at': txn.occurred_at.isoformat() if txn.occurred_at else None
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/txn', methods=['GET'])
def list_ingredient_txn():
    """
    원재료 거래 이벤트 목록 조회
    ---
    tags:
      - Ingredients
    parameters:
      - in: query
        name: ingredient_sku
        type: string
        description: "원재료 SKU 필터"
      - in: query
        name: txn_type
        type: string
        enum: [in, out, waste, adjust]
        description: "거래 유형 필터"
      - in: query
        name: from
        type: string
        format: date-time
        description: "시작 날짜 (ISO 8601)"
      - in: query
        name: to
        type: string
        format: date-time
        description: "종료 날짜 (ISO 8601)"
      - in: query
        name: limit
        type: integer
        default: 50
      - in: query
        name: offset
        type: integer
        default: 0
    responses:
      200:
        description: 거래 이벤트 목록
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        query = db.query(StoreIngredientTxn)
        
        ingredient_sku = request.args.get('ingredient_sku')
        if ingredient_sku:
            query = query.filter(StoreIngredientTxn.ingredient_sku == ingredient_sku)
        
        txn_type = request.args.get('txn_type')
        if txn_type:
            query = query.filter(StoreIngredientTxn.txn_type == txn_type)
        
        from_date = request.args.get('from')
        to_date = request.args.get('to')
        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                query = query.filter(StoreIngredientTxn.occurred_at >= from_dt)
            except ValueError:
                return jsonify({'error': 'Invalid from date format. Use ISO 8601'}), 400
        
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                query = query.filter(StoreIngredientTxn.occurred_at <= to_dt)
            except ValueError:
                return jsonify({'error': 'Invalid to date format. Use ISO 8601'}), 400
        
        query = query.order_by(desc(StoreIngredientTxn.occurred_at))
        
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        total = query.count()
        txns = query.limit(limit).offset(offset).all()
        
        return jsonify({
            'total': total,
            'limit': limit,
            'offset': offset,
            'transactions': [{
                'ingredient_txn_id': str(t.ingredient_txn_id),
                'ingredient_sku': t.ingredient_sku,
                'unit': t.unit,
                'qty_delta': float(t.qty_delta),
                'txn_type': t.txn_type,
                'reason': t.reason,
                'order_id': str(t.order_id) if t.order_id else None,
                'occurred_at': t.occurred_at.isoformat() if t.occurred_at else None,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'meta': t.meta
            } for t in txns]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

