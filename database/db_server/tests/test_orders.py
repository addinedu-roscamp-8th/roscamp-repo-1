import pytest
import uuid
from datetime import datetime
from app.services.order_service import OrderService
from app.models import StoreOrder, StoreInventoryTxn


def test_order_completion_creates_inventory_out(client, db_session):
    """주문 완료 시 재고 OUT 이벤트 생성 테스트"""
    # 주문 생성
    order = StoreOrder(
        order_id=uuid.uuid4(),
        channel='online',
        status='placed',
        customer_name='테스트 고객',
        items=[
            {
                'sku': 'TEST-SKU-001',
                'name': '테스트 상품',
                'qty': 3,
                'unit': '개',
                'unit_price': 1000
            }
        ],
        total_amount=3000,
        payment_status='paid'
    )
    db_session.add(order)
    db_session.commit()
    order_id = order.order_id
    
    # 주문 완료 처리
    service = OrderService()
    result = service.update_order_status(order_id, 'completed')
    
    # 검증
    assert result['new_status'] == 'completed'
    assert len(result['inventory_txns_created']) > 0
    
    # 재고 OUT 이벤트 확인
    out_txn = db_session.query(StoreInventoryTxn).filter(
        StoreInventoryTxn.order_id == order_id,
        StoreInventoryTxn.txn_type == 'out'
    ).first()
    
    assert out_txn is not None
    assert out_txn.sku == 'TEST-SKU-001'
    assert float(out_txn.qty_delta) == -3.0  # 음수여야 함


def test_order_completion_idempotency(client, db_session):
    """주문 완료 처리 멱등성 테스트 - 중복 OUT 이벤트 생성 방지"""
    # 주문 생성
    order = StoreOrder(
        order_id=uuid.uuid4(),
        channel='online',
        status='placed',
        customer_name='테스트 고객',
        items=[
            {
                'sku': 'TEST-SKU-002',
                'name': '테스트 상품 2',
                'qty': 2,
                'unit': '개'
            }
        ],
        total_amount=2000,
        payment_status='paid'
    )
    db_session.add(order)
    db_session.commit()
    order_id = order.order_id
    
    # 첫 번째 완료 처리
    service = OrderService()
    result1 = service.update_order_status(order_id, 'completed')
    
    # 두 번째 완료 처리 (중복 요청 시뮬레이션)
    result2 = service.update_order_status(order_id, 'completed')
    
    # 검증: 두 번째 요청에서는 새 이벤트가 생성되지 않아야 함
    assert 'already exist' in result2['inventory_txns_created'][0].get('message', '')
    
    # DB에서 OUT 이벤트 개수 확인 (1개만 있어야 함)
    out_txns = db_session.query(StoreInventoryTxn).filter(
        StoreInventoryTxn.order_id == order_id,
        StoreInventoryTxn.txn_type == 'out'
    ).all()
    
    assert len(out_txns) == 1


def test_create_order_api(client):
    """주문 생성 API 테스트"""
    response = client.post('/orders', json={
        'channel': 'online',
        'customer_name': 'API 테스트',
        'items': [
            {
                'sku': 'API-SKU-001',
                'name': 'API 테스트 상품',
                'qty': 1,
                'unit': '개',
                'unit_price': 5000
            }
        ],
        'total_amount': 5000,
        'payment_status': 'paid'
    })
    
    assert response.status_code == 201
    data = response.get_json()
    assert 'order_id' in data
    assert data['status'] == 'placed'


def test_get_order_api(client, db_session):
    """주문 조회 API 테스트"""
    # 주문 생성
    order = StoreOrder(
        order_id=uuid.uuid4(),
        channel='online',
        status='placed',
        customer_name='조회 테스트',
        items=[{'sku': 'GET-SKU-001', 'qty': 1}],
        total_amount=1000
    )
    db_session.add(order)
    db_session.commit()
    order_id = str(order.order_id)
    
    # 조회
    response = client.get(f'/orders/{order_id}')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['order_id'] == order_id
    assert data['customer_name'] == '조회 테스트'

