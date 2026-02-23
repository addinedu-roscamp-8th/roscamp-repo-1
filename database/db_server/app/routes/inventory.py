from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models import StoreInventoryTxn
from sqlalchemy import desc
from datetime import datetime
import uuid

bp = Blueprint('inventory', __name__, url_prefix='/inventory')


@bp.route('/txn', methods=['POST'])
def create_inventory_txn():
    """
    재고 이벤트 생성
    재고 입/출/조정/폐기 등의 이벤트를 기록합니다.
    ---
    tags:
      - Inventory
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - sku
            - qty_delta
            - txn_type
          properties:
            sku:
              type: string
              description: 상품 SKU
              example: SANDWICH-001
            display_name:
              type: string
              description: 상품 표시명
              example: 치킨 샌드위치
            unit:
              type: string
              description: 단위
              example: 개
            qty_delta:
              type: number
              description: "수량 변동 (양수: 입고/조정 증가, 음수: 출고/폐기/조정 감소)"
              example: -5
            txn_type:
              type: string
              enum: [in, out, adjust, waste, return]
              description: "거래 유형 (out/waste는 양수 입력 시 자동으로 음수로 변환)"
              example: out
            reason:
              type: string
              description: 사유
              example: 판매 출고
            occurred_at:
              type: string
              format: date-time
              description: "발생 시각 (ISO 8601, 선택사항, 기본값: 현재 시각)"
              example: 2024-01-01T00:00:00Z
            order_id:
              type: string
              format: uuid
              description: "관련 주문 ID (선택사항)"
            meta:
              type: object
              description: 추가 메타데이터
    responses:
      201:
        description: 재고 이벤트가 성공적으로 생성되었습니다
        schema:
          type: object
          properties:
            inventory_txn_id:
              type: string
              format: uuid
            sku:
              type: string
            txn_type:
              type: string
            qty_delta:
              type: number
            occurred_at:
              type: string
              format: date-time
      400:
        description: 잘못된 요청
      500:
        description: 서버 오류
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    # 필수 필드 검증
    required_fields = ['sku', 'qty_delta', 'txn_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    txn_type = data['txn_type']
    qty_delta = float(data['qty_delta'])
    
    # txn_type에 따른 qty_delta 검증 및 변환
    if txn_type in ('out', 'waste'):
        if qty_delta > 0:
            qty_delta = -abs(qty_delta)  # 양수면 음수로 변환
    elif txn_type == 'in':
        if qty_delta < 0:
            qty_delta = abs(qty_delta)  # 음수면 양수로 변환
    
    db = get_db()
    try:
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
        
        txn = StoreInventoryTxn(
            inventory_txn_id=uuid.uuid4(),
            occurred_at=occurred_at,
            sku=data['sku'],
            display_name=data.get('display_name'),
            unit=data.get('unit'),
            qty_delta=qty_delta,
            txn_type=txn_type,
            reason=data.get('reason'),
            order_id=order_id,
            meta=data.get('meta')
        )
        
        db.add(txn)
        db.commit()
        
        return jsonify({
            'inventory_txn_id': str(txn.inventory_txn_id),
            'sku': txn.sku,
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
def list_inventory_txn():
    """
    재고 이벤트 목록 조회
    재고 이벤트 목록을 조회합니다. 필터링 및 페이징을 지원합니다.
    ---
    tags:
      - Inventory
    parameters:
      - in: query
        name: sku
        type: string
        description: SKU 필터
      - in: query
        name: txn_type
        type: string
        enum: [in, out, adjust, waste, return]
        description: 거래 유형 필터
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
        description: 페이지 크기
      - in: query
        name: offset
        type: integer
        default: 0
        description: 오프셋
    responses:
      200:
        description: 재고 이벤트 목록
        schema:
          type: object
          properties:
            total:
              type: integer
            limit:
              type: integer
            offset:
              type: integer
            transactions:
              type: array
              items:
                type: object
      400:
        description: 잘못된 날짜 형식
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        query = db.query(StoreInventoryTxn)
        
        # 필터링
        sku = request.args.get('sku')
        if sku:
            query = query.filter(StoreInventoryTxn.sku == sku)
        
        txn_type = request.args.get('txn_type')
        if txn_type:
            query = query.filter(StoreInventoryTxn.txn_type == txn_type)
        
        from_date = request.args.get('from')
        to_date = request.args.get('to')
        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                query = query.filter(StoreInventoryTxn.occurred_at >= from_dt)
            except ValueError:
                return jsonify({'error': 'Invalid from date format. Use ISO 8601'}), 400
        
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                query = query.filter(StoreInventoryTxn.occurred_at <= to_dt)
            except ValueError:
                return jsonify({'error': 'Invalid to date format. Use ISO 8601'}), 400
        
        # 정렬 및 페이징
        query = query.order_by(desc(StoreInventoryTxn.occurred_at))
        
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        total = query.count()
        txns = query.limit(limit).offset(offset).all()
        
        return jsonify({
            'total': total,
            'limit': limit,
            'offset': offset,
            'transactions': [{
                'inventory_txn_id': str(t.inventory_txn_id),
                'occurred_at': t.occurred_at.isoformat() if t.occurred_at else None,
                'sku': t.sku,
                'display_name': t.display_name,
                'unit': t.unit,
                'qty_delta': float(t.qty_delta),
                'txn_type': t.txn_type,
                'reason': t.reason,
                'order_id': str(t.order_id) if t.order_id else None,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'meta': t.meta
            } for t in txns]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

