from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models import StoreOrder
from app.services.order_service import OrderService
from sqlalchemy import desc
from datetime import datetime
import uuid

bp = Blueprint('orders', __name__, url_prefix='/orders')


@bp.route('', methods=['POST'])
def create_order():
    """
    주문 생성
    새로운 주문을 생성합니다.
    ---
    tags:
      - Orders
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - channel
            - items
          properties:
            channel:
              type: string
              description: "주문 채널 (예: online, offline)"
              example: online
            status:
              type: string
              description: "주문 상태 (기본값: placed)"
              enum: [placed, preparing, ready, completed, canceled, refunded]
              example: placed
            customer_name:
              type: string
              description: 고객 이름
              example: 홍길동
            customer_phone:
              type: string
              description: 고객 전화번호
              example: 010-1234-5678
            items:
              type: array
              description: 주문 항목 목록
              items:
                type: object
                required:
                  - sku
                  - qty
                properties:
                  sku:
                    type: string
                    example: SANDWICH-001
                  name:
                    type: string
                    example: 치킨 샌드위치
                  qty:
                    type: number
                    example: 2
                  unit:
                    type: string
                    example: 개
                  unit_price:
                    type: number
                    example: 5000
            currency:
              type: string
              description: "통화 (기본값: KRW)"
              example: KRW
            total_amount:
              type: number
              description: 총 금액
              example: 10000
            payment_status:
              type: string
              description: 결제 상태
              example: paid
            meta:
              type: object
              description: 추가 메타데이터
    responses:
      201:
        description: 주문이 성공적으로 생성되었습니다
        schema:
          type: object
          properties:
            order_id:
              type: string
              format: uuid
            status:
              type: string
            channel:
              type: string
            ordered_at:
              type: string
              format: date-time
      400:
        description: 잘못된 요청
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: 서버 오류
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body is required'}), 400
    
    # 필수 필드 검증
    required_fields = ['channel', 'items']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # items 검증
    if not isinstance(data['items'], list) or len(data['items']) == 0:
        return jsonify({'error': 'items must be a non-empty array'}), 400
    
    for item in data['items']:
        if not isinstance(item, dict) or 'sku' not in item or 'qty' not in item:
            return jsonify({'error': 'Each item must have sku and qty'}), 400
    
    db = get_db()
    try:
        order = StoreOrder(
            order_id=uuid.uuid4(),
            channel=data['channel'],
            status=data.get('status', 'placed'),
            customer_name=data.get('customer', {}).get('name') if isinstance(data.get('customer'), dict) else data.get('customer_name'),
            customer_phone=data.get('customer', {}).get('phone') if isinstance(data.get('customer'), dict) else data.get('customer_phone'),
            items=data['items'],
            currency=data.get('currency', 'KRW'),
            total_amount=data.get('total_amount'),
            payment_status=data.get('payment_status'),
            meta=data.get('meta')
        )
        
        db.add(order)
        db.commit()
        
        return jsonify({
            'order_id': str(order.order_id),
            'status': order.status,
            'channel': order.channel,
            'ordered_at': order.ordered_at.isoformat() if order.ordered_at else None
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('', methods=['GET'])
def list_orders():
    """
    주문 목록 조회
    주문 목록을 조회합니다. 필터링 및 페이징을 지원합니다.
    ---
    tags:
      - Orders
    parameters:
      - in: query
        name: status
        type: string
        description: 주문 상태 필터
        enum: [placed, preparing, ready, completed, canceled, refunded]
      - in: query
        name: from
        type: string
        format: date-time
        description: "시작 날짜 (ISO 8601)"
        example: 2024-01-01T00:00:00Z
      - in: query
        name: to
        type: string
        format: date-time
        description: "종료 날짜 (ISO 8601)"
        example: 2024-01-31T23:59:59Z
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
        description: 주문 목록
        schema:
          type: object
          properties:
            total:
              type: integer
            limit:
              type: integer
            offset:
              type: integer
            orders:
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
        query = db.query(StoreOrder)
        
        # 필터링
        status = request.args.get('status')
        if status:
            query = query.filter(StoreOrder.status == status)
        
        from_date = request.args.get('from')
        to_date = request.args.get('to')
        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                query = query.filter(StoreOrder.ordered_at >= from_dt)
            except ValueError:
                return jsonify({'error': 'Invalid from date format. Use ISO 8601'}), 400
        
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
                query = query.filter(StoreOrder.ordered_at <= to_dt)
            except ValueError:
                return jsonify({'error': 'Invalid to date format. Use ISO 8601'}), 400
        
        # 정렬 및 페이징
        query = query.order_by(desc(StoreOrder.ordered_at))
        
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        total = query.count()
        orders = query.limit(limit).offset(offset).all()
        
        return jsonify({
            'total': total,
            'limit': limit,
            'offset': offset,
            'orders': [{
                'order_id': str(o.order_id),
                'channel': o.channel,
                'status': o.status,
                'customer_name': o.customer_name,
                'customer_phone': o.customer_phone,
                'items': o.items,
                'currency': o.currency,
                'total_amount': float(o.total_amount) if o.total_amount else None,
                'payment_status': o.payment_status,
                'ordered_at': o.ordered_at.isoformat() if o.ordered_at else None,
                'updated_at': o.updated_at.isoformat() if o.updated_at else None,
                'meta': o.meta
            } for o in orders]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/<order_id>', methods=['GET'])
def get_order(order_id):
    """
    주문 상세 조회
    특정 주문의 상세 정보를 조회합니다.
    ---
    tags:
      - Orders
    parameters:
      - in: path
        name: order_id
        type: string
        format: uuid
        required: true
        description: 주문 ID
    responses:
      200:
        description: 주문 상세 정보
        schema:
          type: object
          properties:
            order_id:
              type: string
              format: uuid
            channel:
              type: string
            status:
              type: string
            customer_name:
              type: string
            customer_phone:
              type: string
            items:
              type: array
            currency:
              type: string
            total_amount:
              type: number
            payment_status:
              type: string
            ordered_at:
              type: string
              format: date-time
            updated_at:
              type: string
              format: date-time
            meta:
              type: object
      400:
        description: 잘못된 order_id 형식
      404:
        description: 주문을 찾을 수 없음
      500:
        description: 서버 오류
    """
    db = get_db()
    try:
        try:
            order_uuid = uuid.UUID(order_id)
        except ValueError:
            return jsonify({'error': 'Invalid order_id format'}), 400
        
        order = db.query(StoreOrder).filter(StoreOrder.order_id == order_uuid).first()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        return jsonify({
            'order_id': str(order.order_id),
            'channel': order.channel,
            'status': order.status,
            'customer_name': order.customer_name,
            'customer_phone': order.customer_phone,
            'items': order.items,
            'currency': order.currency,
            'total_amount': float(order.total_amount) if order.total_amount else None,
            'payment_status': order.payment_status,
            'ordered_at': order.ordered_at.isoformat() if order.ordered_at else None,
            'updated_at': order.updated_at.isoformat() if order.updated_at else None,
            'meta': order.meta
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/<order_id>/status', methods=['PATCH'])
def update_order_status(order_id):
    """
    주문 상태 업데이트
    주문 상태를 업데이트합니다. completed로 변경 시 자동으로 재고 OUT 이벤트가 생성됩니다 (멱등성 보장).
    ---
    tags:
      - Orders
    parameters:
      - in: path
        name: order_id
        type: string
        format: uuid
        required: true
        description: 주문 ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - status
          properties:
            status:
              type: string
              enum: [placed, preparing, ready, completed, canceled, refunded]
              description: 새로운 주문 상태
              example: completed
    responses:
      200:
        description: 주문 상태가 성공적으로 업데이트되었습니다
        schema:
          type: object
          properties:
            order_id:
              type: string
              format: uuid
            old_status:
              type: string
            new_status:
              type: string
            updated_at:
              type: string
              format: date-time
            updated_at:
              type: string
              format: date-time
      400:
        description: 잘못된 요청
      404:
        description: 주문을 찾을 수 없음
      500:
        description: 서버 오류
    """
    data = request.get_json()
    
    if not data or 'status' not in data:
        return jsonify({'error': 'status field is required'}), 400
    
    new_status = data['status']
    
    try:
        order_uuid = uuid.UUID(order_id)
    except ValueError:
        return jsonify({'error': 'Invalid order_id format'}), 400
    
    service = OrderService()
    try:
        result = service.update_order_status(order_uuid, new_status)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

