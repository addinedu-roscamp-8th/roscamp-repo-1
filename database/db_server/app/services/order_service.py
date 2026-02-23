from app.db import get_db
from app.models import StoreOrder
from sqlalchemy import select
import uuid


class OrderService:
    """주문 서비스 - 상태 업데이트 및 재고 처리"""
    
    def update_order_status(self, order_id: uuid.UUID, new_status: str):
        """
        주문 상태 업데이트
        주의: store_inventory_txn은 예비 테이블이므로 자동 재고 이벤트 생성 기능은 비활성화됨
        """
        db = get_db()
        try:
            # 트랜잭션 시작
            # 주문 row 잠금 (SELECT ... FOR UPDATE)
            stmt = select(StoreOrder).where(StoreOrder.order_id == order_id).with_for_update()
            order = db.execute(stmt).scalar_one_or_none()
            
            if not order:
                raise ValueError('Order not found')
            
            old_status = order.status
            
            # 상태 업데이트
            # updated_at은 모델의 onupdate=func.now()에 의해 자동 갱신됨
            # 명시적으로 설정하지 않음 (DB의 func.now() 사용)
            order.status = new_status
            
            db.commit()
            
            return {
                'order_id': str(order.order_id),
                'old_status': old_status,
                'new_status': new_status,
                'updated_at': order.updated_at.isoformat() if order.updated_at else None
            }
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise Exception(f'Failed to update order status: {str(e)}')
        finally:
            db.close()

