from app.db import get_db
from app.models import StoreOrder, StoreIngredientTxn, StoreIngredientMst
from sqlalchemy import text, func, desc
from datetime import datetime, timedelta


class AnalyticsService:
    """분석 서비스 - TimescaleDB continuous aggregates 활용"""
    
    def get_daily_inventory_change(self, sku=None, from_date=None, to_date=None):
        """일별 재고 변동량 조회"""
        db = get_db()
        try:
            # 기본 날짜 범위 설정
            if not to_date:
                to_date = datetime.utcnow()
            else:
                if isinstance(to_date, str):
                    to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            
            if not from_date:
                from_date = to_date - timedelta(days=30)
            else:
                if isinstance(from_date, str):
                    from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            
            # 쿼리 구성 (public 스키마 명시)
            query = """
                SELECT day, sku, display_name, unit, net_qty_change
                FROM public.cagg_daily_inventory_change
                WHERE day >= :from_date AND day <= :to_date
            """
            params = {
                'from_date': from_date,
                'to_date': to_date
            }
            
            if sku:
                query += " AND sku = :sku"
                params['sku'] = sku
            
            query += " ORDER BY day DESC, sku"
            
            result = db.execute(text(query), params)
            
            data = []
            for row in result:
                data.append({
                    'day': row.day.isoformat() if row.day else None,
                    'sku': row.sku,
                    'display_name': row.display_name,
                    'unit': row.unit,
                    'net_qty_change': float(row.net_qty_change) if row.net_qty_change else 0.0
                })
            
            return {
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'sku': sku,
                'data': data
            }
        except Exception as e:
            error_msg = str(e)
            # 뷰가 없는 경우 - store_ingredient_txn에서 직접 계산 (fallback)
            if 'does not exist' in error_msg.lower() or 'undefinedtable' in error_msg.lower():
                db.close()
                return self._get_daily_inventory_change_from_ingredients(sku, from_date, to_date)
            # 권한 오류인 경우 더 명확한 메시지 제공
            if 'permission denied' in error_msg.lower() or 'insufficientprivilege' in error_msg.lower():
                raise Exception(
                    f'Permission denied: Database user does not have SELECT permission on cagg_daily_inventory_change view. '
                    f'To fix this, run as the view owner or superuser: '
                    f'1. Check view owner: SELECT view_owner FROM timescaledb_information.continuous_aggregates WHERE view_name = \'cagg_daily_inventory_change\'; '
                    f'2. Grant permission as owner/superuser: GRANT SELECT ON public.cagg_daily_inventory_change TO deepdive; '
                    f'Original error: {error_msg}'
                )
            raise Exception(f'Failed to get daily inventory change: {error_msg}')
        finally:
            db.close()
    
    def _get_daily_inventory_change_from_ingredients(self, sku=None, from_date=None, to_date=None):
        """store_ingredient_txn에서 직접 일별 재고 변동량 계산 (fallback)"""
        db = get_db()
        try:
            # 기본 날짜 범위 설정
            if not to_date:
                to_date = datetime.utcnow()
            else:
                if isinstance(to_date, str):
                    to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            
            if not from_date:
                from_date = to_date - timedelta(days=30)
            else:
                if isinstance(from_date, str):
                    from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            
            # store_ingredient_txn에서 원재료 거래 조회
            query = db.query(
                func.date(StoreIngredientTxn.occurred_at).label('day'),
                StoreIngredientTxn.ingredient_sku,
                StoreIngredientMst.ingredient_name,
                StoreIngredientTxn.unit,
                func.sum(StoreIngredientTxn.qty_delta).label('net_qty_change')
            ).join(
                StoreIngredientMst,
                StoreIngredientTxn.ingredient_sku == StoreIngredientMst.ingredient_sku
            ).filter(
                func.date(StoreIngredientTxn.occurred_at) >= from_date.date(),
                func.date(StoreIngredientTxn.occurred_at) <= to_date.date()
            )
            
            if sku:
                query = query.filter(StoreIngredientTxn.ingredient_sku == sku)
            
            query = query.group_by(
                func.date(StoreIngredientTxn.occurred_at),
                StoreIngredientTxn.ingredient_sku,
                StoreIngredientMst.ingredient_name,
                StoreIngredientTxn.unit
            ).order_by(
                desc(func.date(StoreIngredientTxn.occurred_at)),
                StoreIngredientTxn.ingredient_sku
            )
            
            results = query.all()
            
            # 데이터 포맷팅
            data = []
            for row in results:
                data.append({
                    'day': row.day.isoformat() if row.day else None,
                    'sku': row.ingredient_sku,
                    'display_name': row.ingredient_name or row.ingredient_sku,
                    'unit': row.unit,
                    'net_qty_change': float(row.net_qty_change) if row.net_qty_change else 0.0
                })
            
            return {
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'sku': sku,
                'data': data,
                'note': 'Calculated from store_ingredient_txn (fallback, view not available)'
            }
        finally:
            db.close()
    
    def get_daily_sales(self, sku=None, from_date=None, to_date=None):
        """일별 판매량 조회"""
        db = get_db()
        try:
            # 기본 날짜 범위 설정
            if not to_date:
                to_date = datetime.utcnow()
            else:
                if isinstance(to_date, str):
                    to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            
            if not from_date:
                from_date = to_date - timedelta(days=30)
            else:
                if isinstance(from_date, str):
                    from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            
            # 쿼리 구성 (public 스키마 명시)
            query = """
                SELECT day, sku, display_name, unit, sold_qty
                FROM public.cagg_daily_sales_qty
                WHERE day >= :from_date AND day <= :to_date
            """
            params = {
                'from_date': from_date,
                'to_date': to_date
            }
            
            if sku:
                query += " AND sku = :sku"
                params['sku'] = sku
            
            query += " ORDER BY day DESC, sku"
            
            result = db.execute(text(query), params)
            
            data = []
            for row in result:
                data.append({
                    'day': row.day.isoformat() if row.day else None,
                    'sku': row.sku,
                    'display_name': row.display_name,
                    'unit': row.unit,
                    'sold_qty': float(row.sold_qty) if row.sold_qty else 0.0
                })
            
            return {
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'sku': sku,
                'data': data
            }
        except Exception as e:
            error_msg = str(e)
            # 뷰가 없는 경우 - store_order에서 직접 계산 (fallback)
            if 'does not exist' in error_msg.lower() or 'undefinedtable' in error_msg.lower():
                db.close()
                return self._get_daily_sales_from_orders(sku, from_date, to_date)
            # 권한 오류인 경우 더 명확한 메시지 제공
            if 'permission denied' in error_msg.lower() or 'insufficientprivilege' in error_msg.lower():
                raise Exception(
                    f'Permission denied: Database user does not have SELECT permission on cagg_daily_sales_qty view. '
                    f'To fix this, run as the view owner or superuser: '
                    f'1. Check view owner: SELECT view_owner FROM timescaledb_information.continuous_aggregates WHERE view_name = \'cagg_daily_sales_qty\'; '
                    f'2. Grant permission as owner/superuser: GRANT SELECT ON public.cagg_daily_sales_qty TO deepdive; '
                    f'Original error: {error_msg}'
                )
            raise Exception(f'Failed to get daily sales: {error_msg}')
        finally:
            db.close()
    
    def _get_daily_sales_from_orders(self, sku=None, from_date=None, to_date=None):
        """store_order에서 직접 일별 판매량 계산 (fallback)"""
        db = get_db()
        try:
            # 기본 날짜 범위 설정
            if not to_date:
                to_date = datetime.utcnow()
            else:
                if isinstance(to_date, str):
                    to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            
            if not from_date:
                from_date = to_date - timedelta(days=30)
            else:
                if isinstance(from_date, str):
                    from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            
            # store_order에서 완료된 주문만 조회
            query = db.query(StoreOrder).filter(
                StoreOrder.status == 'completed',
                func.date(StoreOrder.ordered_at) >= from_date.date(),
                func.date(StoreOrder.ordered_at) <= to_date.date()
            )
            
            orders = query.all()
            
            # 일별 판매량 집계
            sales_dict = {}
            for order in orders:
                if not order.items or not isinstance(order.items, list):
                    continue
                
                order_date = order.ordered_at.date() if order.ordered_at else None
                if not order_date:
                    continue
                
                for item in order.items:
                    if not isinstance(item, dict):
                        continue
                    
                    item_sku = item.get('sku')
                    item_name = item.get('name', item_sku)
                    item_unit = item.get('unit', 'ea')
                    item_qty = float(item.get('qty', 0))
                    
                    if not item_sku or item_qty <= 0:
                        continue
                    
                    if sku and item_sku != sku:
                        continue
                    
                    key = (order_date, item_sku, item_name, item_unit)
                    if key not in sales_dict:
                        sales_dict[key] = 0
                    sales_dict[key] += item_qty
            
            # 데이터 포맷팅
            data = []
            for (day, item_sku, item_name, item_unit), qty in sales_dict.items():
                data.append({
                    'day': day.isoformat() if day else None,
                    'sku': item_sku,
                    'display_name': item_name,
                    'unit': item_unit,
                    'sold_qty': qty
                })
            
            # 날짜, SKU 순으로 정렬
            data.sort(key=lambda x: (x['day'], x['sku']), reverse=True)
            
            return {
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'sku': sku,
                'data': data,
                'note': 'Calculated from store_order (fallback, view not available)'
            }
        finally:
            db.close()
    
    def get_top_sales(self, days=30, limit=20):
        """TOP 판매 상품 조회"""
        db = get_db()
        try:
            to_date = datetime.utcnow()
            from_date = to_date - timedelta(days=days)
            
            query = text("""
                SELECT sku, display_name, unit, SUM(sold_qty) as total_sold_qty
                FROM public.cagg_daily_sales_qty
                WHERE day >= :from_date AND day <= :to_date
                GROUP BY sku, display_name, unit
                ORDER BY total_sold_qty DESC
                LIMIT :limit
            """)
            
            result = db.execute(query, {
                'from_date': from_date,
                'to_date': to_date,
                'limit': limit
            })
            
            data = []
            for row in result:
                data.append({
                    'sku': row.sku,
                    'display_name': row.display_name,
                    'unit': row.unit,
                    'total_sold_qty': float(row.total_sold_qty) if row.total_sold_qty else 0.0
                })
            
            return {
                'days': days,
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'top_products': data
            }
        except Exception as e:
            error_msg = str(e)
            # 뷰가 없는 경우 - store_order에서 직접 계산 (fallback)
            if 'does not exist' in error_msg.lower() or 'undefinedtable' in error_msg.lower():
                db.close()
                return self._get_top_sales_from_orders(days, limit)
            # 권한 오류인 경우 더 명확한 메시지 제공
            if 'permission denied' in error_msg.lower() or 'insufficientprivilege' in error_msg.lower():
                raise Exception(
                    f'Permission denied: Database user does not have SELECT permission on cagg_daily_sales_qty view. '
                    f'To fix this, run as the view owner or superuser: '
                    f'1. Check view owner: SELECT view_owner FROM timescaledb_information.continuous_aggregates WHERE view_name = \'cagg_daily_sales_qty\'; '
                    f'2. Grant permission as owner/superuser: GRANT SELECT ON public.cagg_daily_sales_qty TO deepdive; '
                    f'Original error: {error_msg}'
                )
            raise Exception(f'Failed to get top sales: {error_msg}')
        finally:
            db.close()
    
    def _get_top_sales_from_orders(self, days=30, limit=20):
        """store_order에서 직접 TOP 판매 상품 계산 (fallback)"""
        db = get_db()
        try:
            to_date = datetime.utcnow()
            from_date = to_date - timedelta(days=days)
            
            # store_order에서 완료된 주문만 조회
            orders = db.query(StoreOrder).filter(
                StoreOrder.status == 'completed',
                func.date(StoreOrder.ordered_at) >= from_date.date(),
                func.date(StoreOrder.ordered_at) <= to_date.date()
            ).all()
            
            # SKU별 판매량 집계
            sales_dict = {}
            for order in orders:
                if not order.items or not isinstance(order.items, list):
                    continue
                
                for item in order.items:
                    if not isinstance(item, dict):
                        continue
                    
                    item_sku = item.get('sku')
                    item_name = item.get('name', item_sku)
                    item_unit = item.get('unit', 'ea')
                    item_qty = float(item.get('qty', 0))
                    
                    if not item_sku or item_qty <= 0:
                        continue
                    
                    key = (item_sku, item_name, item_unit)
                    if key not in sales_dict:
                        sales_dict[key] = 0
                    sales_dict[key] += item_qty
            
            # 판매량 순으로 정렬
            data = []
            for (item_sku, item_name, item_unit), total_qty in sorted(
                sales_dict.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:limit]:
                data.append({
                    'sku': item_sku,
                    'display_name': item_name,
                    'unit': item_unit,
                    'total_sold_qty': total_qty
                })
            
            return {
                'days': days,
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'top_products': data,
                'note': 'Calculated from store_order (fallback, view not available)'
            }
        finally:
            db.close()

