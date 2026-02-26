#!/usr/bin/env python3
"""
GUI에서 FMS로 직접 주문 전송 테스트
GUI 없이 FMS TCP 통신만 테스트

Usage:
    python test_gui_to_fms.py              # 실제 FMS로 테스트
    python test_gui_to_fms.py --mock       # Mock 모드로 테스트
"""
import sys
import os
import time
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common import Config, Order, MenuItem
from src.fms_client import FMSOrderServiceClient, MockFMSOrderServiceClient


def test_fms_order_flow(use_mock: bool = False):
    """
    FMS 주문 플로우 테스트

    1. FMS 연결
    2. 주문 전송
    3. 수령 확인 전송
    4. 연결 종료
    """
    print('=' * 60)
    print('FMS 주문 플로우 테스트')
    print('=' * 60)

    # 클라이언트 생성
    if use_mock:
        print('[Test] Mock FMS 클라이언트 사용')
        client = MockFMSOrderServiceClient()
    else:
        print(f'[Test] 실제 FMS 클라이언트 사용: {Config.FMS_HOST}:{Config.FMS_PORT}')
        client = FMSOrderServiceClient()

    # 1. FMS 연결
    print('\n[Step 1] FMS 연결 중...')
    if not client.connect():
        print('[Error] FMS 연결 실패')
        print('FMS 서버가 실행 중인지 확인하세요.')
        return False

    print('[Success] FMS 연결 성공')

    # 2. 테스트 주문 생성
    print('\n[Step 2] 테스트 주문 생성')
    test_order = Order(table_number=1)
    test_order.add_item(MenuItem('M001', '햄버거', 8000, '신선한 소고기 패티'), 2)
    test_order.add_item(MenuItem('M002', '피자', 15000, '마르게리타 피자'), 1)

    print(f'테이블 번호: {test_order.table_number}')
    print(f'주문 항목:')
    for item in test_order.items:
        print(f'  - {item.menu_item.name} x {item.quantity} ({item.menu_item.price}원)')
    print(f'총 금액: {test_order.calculate_total()}원')

    # 3. 주문 전송
    print('\n[Step 3] FMS로 주문 전송 중...')
    order_id = client.submit_order(test_order)

    if not order_id:
        print('[Error] 주문 전송 실패')
        client.disconnect()
        return False

    print(f'[Success] 주문 전송 성공')
    print(f'주문 번호: {order_id}')

    # 4. 배달 알림 대기 시뮬레이션 (실제로는 FMS가 푸시)
    if not use_mock:
        print('\n[Step 4] 배달 알림 대기 중... (시뮬레이션)')
        print('실제 환경에서는 FMS가 배달 완료 시 푸시 알림을 보냅니다.')
        print('테스트를 위해 5초 대기...')
        time.sleep(5)
    else:
        print('\n[Step 4] Mock 모드 - 배달 알림 시뮬레이션 스킵')
        time.sleep(1)

    # 5. 수령 확인 전송
    print('\n[Step 5] 수령 확인 전송 중...')
    if client.confirm_delivery(order_id, test_order.table_number):
        print('[Success] 수령 확인 전송 성공')
    else:
        print('[Error] 수령 확인 전송 실패')

    # 6. 연결 종료
    print('\n[Step 6] FMS 연결 종료')
    client.disconnect()
    print('[Success] 연결 종료 완료')

    print('\n' + '=' * 60)
    print('테스트 완료')
    print('=' * 60)
    return True


def test_fms_message_format():
    """FMS 메시지 형식 테스트"""
    print('=' * 60)
    print('FMS 메시지 형식 테스트')
    print('=' * 60)

    test_order = Order(table_number=1)
    test_order.order_id = 'ORD-1234567890'
    test_order.add_item(MenuItem('M001', '햄버거', 8000), 2)

    # 주문 메시지 형식
    order_message = {
        'command': 'new_order',
        'table_number': test_order.table_number,
        'order': {
            'order_id': test_order.order_id,
            'items': [
                {
                    'menu_id': item.menu_item.menu_id,
                    'name': item.menu_item.name,
                    'quantity': item.quantity,
                    'price': item.menu_item.price
                }
                for item in test_order.items
            ],
            'table_number': test_order.table_number,
            'total_price': test_order.calculate_total()
        }
    }

    print('\n[주문 메시지]')
    import json
    print(json.dumps(order_message, ensure_ascii=False, indent=2))

    # 수령 확인 메시지 형식
    confirm_message = {
        'type': 'delivery_complete',
        'data': {
            'order_id': test_order.order_id,
            'table_number': str(test_order.table_number)
        }
    }

    print('\n[수령 확인 메시지]')
    print(json.dumps(confirm_message, ensure_ascii=False, indent=2))

    print('\n' + '=' * 60)
    print('메시지 형식 테스트 완료')
    print('=' * 60)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='FMS 주문 테스트')
    parser.add_argument('--mock', action='store_true', help='Mock 모드 사용')
    parser.add_argument('--format', action='store_true', help='메시지 형식만 테스트')
    args = parser.parse_args()

    if args.format:
        # 메시지 형식만 테스트
        test_fms_message_format()
    else:
        # 실제 주문 플로우 테스트
        success = test_fms_order_flow(use_mock=args.mock)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
