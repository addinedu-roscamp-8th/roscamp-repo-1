from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.db import get_db
from app.models import StoreOrder
from app.services.order_service import OrderService
from sqlalchemy import desc
from datetime import datetime
import uuid

bp = Blueprint('orders_ui', __name__, url_prefix='/orders-ui')


@bp.route('', methods=['GET'])
def orders_page():
    """주문 관리 페이지"""
    return render_template('orders.html')


@bp.route('/api/list', methods=['GET'])
def get_orders_list():
    """주문 목록 API"""
    db = get_db()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status', '')
        search_query = request.args.get('search', '')
        
        query = db.query(StoreOrder)
        
        if status_filter:
            query = query.filter(StoreOrder.status == status_filter)
        
        if search_query:
            query = query.filter(
                (StoreOrder.customer_name.ilike(f'%{search_query}%')) |
                (StoreOrder.customer_phone.ilike(f'%{search_query}%')) |
                (StoreOrder.order_id.cast(str).ilike(f'%{search_query}%'))
            )
        
        query = query.order_by(desc(StoreOrder.ordered_at))
        
        total = query.count()
        orders = query.offset((page - 1) * per_page).limit(per_page).all()
        
        orders_data = []
        for order in orders:
            orders_data.append({
                'order_id': str(order.order_id),
                'channel': order.channel,
                'status': order.status,
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'items': order.items,
                'total_amount': float(order.total_amount) if order.total_amount else 0,
                'payment_status': order.payment_status,
                'ordered_at': order.ordered_at.isoformat() if order.ordered_at else None,
                'updated_at': order.updated_at.isoformat() if order.updated_at else None,
                'meta': order.meta
            })
        
        return jsonify({
            'orders': orders_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/api/detail/<order_id>', methods=['GET'])
def get_order_detail(order_id):
    """주문 상세 API"""
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


@bp.route('/api/create', methods=['POST'])
def create_order():
    """주문 생성 API"""
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
            customer_name=data.get('customer_name'),
            customer_phone=data.get('customer_phone'),
            items=data['items'],
            currency=data.get('currency', 'KRW'),
            total_amount=data.get('total_amount'),
            payment_status=data.get('payment_status', 'unpaid'),
            meta=data.get('meta')
        )
        
        db.add(order)
        db.commit()
        
        return jsonify({
            'success': True,
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


@bp.route('/api/update-status', methods=['POST'])
def update_order_status():
    """주문 상태 업데이트 API"""
    data = request.get_json()
    
    if not data or 'order_id' not in data or 'status' not in data:
        return jsonify({'error': 'order_id and status are required'}), 400
    
    try:
        order_uuid = uuid.UUID(data['order_id'])
    except ValueError:
        return jsonify({'error': 'Invalid order_id format'}), 400
    
    new_status = data['status']
    
    service = OrderService()
    try:
        result = service.update_order_status(order_uuid, new_status)
        return jsonify({
            'success': True,
            **result
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

