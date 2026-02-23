from flask import Blueprint, render_template, jsonify
from app.db import get_db
from app.models import StoreOrder, StoreIngredientTxn, StoreIngredientMst
from app.services.analytics_service import AnalyticsService
from sqlalchemy import func, desc
from datetime import datetime, timedelta

bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@bp.route('', methods=['GET'])
def dashboard():
    """대시보드 메인 페이지"""
    return render_template('dashboard.html')


@bp.route('/api/stats', methods=['GET'])
def get_stats():
    """대시보드 통계 데이터"""
    db = get_db()
    try:
        # 오늘 날짜
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        # 총 주문 수
        total_orders = db.query(func.count(StoreOrder.order_id)).scalar()
        
        # 오늘 주문 수
        today_orders = db.query(func.count(StoreOrder.order_id)).filter(
            func.date(StoreOrder.ordered_at) == today
        ).scalar()
        
        # 오늘 매출
        today_revenue = db.query(func.coalesce(func.sum(StoreOrder.total_amount), 0)).filter(
            func.date(StoreOrder.ordered_at) == today,
            StoreOrder.status == 'completed'
        ).scalar()
        
        # 주문 상태별 통계
        status_stats = db.query(
            StoreOrder.status,
            func.count(StoreOrder.order_id).label('count')
        ).group_by(StoreOrder.status).all()
        
        status_dict = {status: count for status, count in status_stats}
        
        # 최근 주문 (최근 10개)
        recent_orders = db.query(StoreOrder).order_by(
            desc(StoreOrder.ordered_at)
        ).limit(10).all()
        
        orders_data = []
        for order in recent_orders:
            orders_data.append({
                'order_id': str(order.order_id),
                'channel': order.channel,
                'status': order.status,
                'customer_name': order.customer_name,
                'total_amount': float(order.total_amount) if order.total_amount else 0,
                'ordered_at': order.ordered_at.isoformat() if order.ordered_at else None,
                'items_count': len(order.items) if order.items else 0
            })
        
        return jsonify({
            'total_orders': total_orders,
            'today_orders': today_orders,
            'today_revenue': float(today_revenue) if today_revenue else 0,
            'status_stats': status_dict,
            'recent_orders': orders_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/api/orders', methods=['GET'])
def get_orders():
    """주문 목록 (페이징)"""
    from flask import request
    
    db = get_db()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status')
        
        query = db.query(StoreOrder)
        
        if status_filter:
            query = query.filter(StoreOrder.status == status_filter)
        
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


@bp.route('/api/inventory', methods=['GET'])
def get_inventory_summary():
    """원재료 재고 요약 (원재료 거래 기준)"""
    db = get_db()
    try:
        # 최근 30일 원재료 거래 변동
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # 원재료별 최근 입고량
        recent_in = db.query(
            StoreIngredientTxn.ingredient_sku,
            func.sum(StoreIngredientTxn.qty_delta).label('total_in')
        ).filter(
            StoreIngredientTxn.txn_type == 'in',
            StoreIngredientTxn.occurred_at >= thirty_days_ago
        ).group_by(StoreIngredientTxn.ingredient_sku).all()
        
        # 원재료별 최근 사용량
        recent_out = db.query(
            StoreIngredientTxn.ingredient_sku,
            func.sum(func.abs(StoreIngredientTxn.qty_delta)).label('total_out')
        ).filter(
            StoreIngredientTxn.txn_type == 'out',
            StoreIngredientTxn.occurred_at >= thirty_days_ago
        ).group_by(StoreIngredientTxn.ingredient_sku).all()
        
        in_dict = {sku: float(total) for sku, total in recent_in}
        out_dict = {sku: float(total) for sku, total in recent_out}
        
        # 모든 원재료 정보 조회
        all_ingredients = db.query(StoreIngredientMst).filter(
            StoreIngredientMst.is_active == True
        ).all()
        
        inventory_data = []
        for ing in all_ingredients:
            inventory_data.append({
                'ingredient_sku': ing.ingredient_sku,
                'ingredient_name': ing.ingredient_name,
                'category': ing.category,
                'base_unit': ing.base_unit,
                'total_in': in_dict.get(ing.ingredient_sku, 0),
                'total_out': out_dict.get(ing.ingredient_sku, 0)
            })
        
        return jsonify({
            'inventory': inventory_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@bp.route('/api/analytics', methods=['GET'])
def get_analytics():
    """분석 데이터"""
    try:
        service = AnalyticsService()
        
        # 최근 7일 판매량
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=7)
        
        sales_data = service.get_daily_sales(
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat()
        )
        
        # TOP 판매 상품
        top_sales = service.get_top_sales(days=30, limit=5)
        
        return jsonify({
            'daily_sales': sales_data.get('data', []),
            'top_products': top_sales.get('top_products', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

