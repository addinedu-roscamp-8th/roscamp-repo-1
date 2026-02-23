"""
Admin GUI용 TCP 클라이언트 - 주문 MS, 레시피 MS, 재고 MS와 통신
"""
import socket
import json
import sys
import os
from typing import Optional, List, Dict
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import (
    Config, Order, OrderStatus, MenuItem,
    Recipe, Stock, Ingredient, RecipeIngredient,
    CookingStep, Supplier
)


class AdminServiceClient(QObject):
    """
    Admin GUI용 실제 TCP 서비스 클라이언트
    주문 MS, 레시피 MS, 재고 MS와 통신
    """

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    order_updated_signal = pyqtSignal(dict)  # 주문 업데이트 알림
    stock_alert_signal = pyqtSignal(dict)  # 재고 부족 알림
    serving_alert_signal = pyqtSignal(dict)  # 서빙 오류 알림

    def __init__(self, host: str = None, port: int = None):
        super().__init__()
        self.host = host or Config.ORDER_MS_HOST
        self.port = port or Config.ORDER_MS_PORT
        self.socket = None
        self.is_connected = False

    def connect(self) -> bool:
        """서버에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            self.connected_signal.emit()
            print(f'[AdminClient] 연결 성공: {self.host}:{self.port}')
            return True
        except Exception as e:
            error_msg = f'연결 실패: {str(e)}'
            print(f'[AdminClient] {error_msg}')
            self.error_signal.emit(error_msg)
            return False

    def disconnect(self):
        """연결 종료"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None
                self.is_connected = False
                self.disconnected_signal.emit()

    def send_request(self, request: dict) -> Optional[dict]:
        """요청 전송 및 응답 수신"""
        if not self.is_connected:
            self.connect()

        if not self.is_connected:
            return None

        try:
            # 요청 전송
            json_data = json.dumps(request, ensure_ascii=False)
            message = json_data.encode('utf-8')
            length_header = len(message).to_bytes(4, byteorder='big')
            self.socket.sendall(length_header + message)

            # 응답 수신
            length_header = self.socket.recv(4)
            if not length_header:
                return None

            message_length = int.from_bytes(length_header, byteorder='big')
            message = b''
            while len(message) < message_length:
                chunk = self.socket.recv(min(4096, message_length - len(message)))
                if not chunk:
                    return None
                message += chunk

            response = json.loads(message.decode('utf-8'))
            return response

        except Exception as e:
            print(f'[AdminClient] 요청 실패: {str(e)}')
            self.error_signal.emit(f'요청 실패: {str(e)}')
            return None

    # ==================== 주문 관련 API ====================

    def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """주문 목록 조회"""
        request = {
            'action': 'get_orders',
            'status': status
        }
        response = self.send_request(request)
        if response and response.get('success'):
            return response.get('orders', [])
        return []

    def get_order(self, order_id: str) -> Optional[Dict]:
        """특정 주문 조회"""
        request = {
            'action': 'get_order',
            'order_id': order_id
        }
        response = self.send_request(request)
        if response and response.get('success'):
            return response.get('order')
        return None

    def update_order_status(self, order_id: str, status: str) -> bool:
        """주문 상태 업데이트"""
        request = {
            'action': 'update_order_status',
            'order_id': order_id,
            'status': status
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    def cancel_order(self, order_id: str, reason: str = "") -> bool:
        """주문 취소"""
        request = {
            'action': 'cancel_order',
            'order_id': order_id,
            'reason': reason
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    def halt_order(self, order_id: str) -> bool:
        """주문 일시중지 (관리자 개입)"""
        request = {
            'action': 'halt_order',
            'order_id': order_id
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    def confirm_inspection(self, order_id: str) -> bool:
        """음식 검수 완료"""
        request = {
            'action': 'confirm_inspection',
            'order_id': order_id
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    def start_serving(self, order_id: str) -> bool:
        """서빙 출발"""
        request = {
            'action': 'start_serving',
            'order_id': order_id
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    # ==================== 레시피 관련 API ====================

    def get_recipes(self) -> List[Dict]:
        """레시피 목록 조회"""
        request = {'action': 'get_recipes'}
        response = self.send_request(request)
        if response and response.get('success'):
            return response.get('recipes', [])
        return []

    def get_recipe(self, recipe_id: str) -> Optional[Dict]:
        """특정 레시피 조회"""
        request = {
            'action': 'get_recipe',
            'recipe_id': recipe_id
        }
        response = self.send_request(request)
        if response and response.get('success'):
            return response.get('recipe')
        return None

    def create_recipe(self, recipe_data: dict) -> bool:
        """레시피 생성"""
        request = {
            'action': 'create_recipe',
            'recipe': recipe_data
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    def update_recipe(self, recipe_id: str, recipe_data: dict) -> bool:
        """레시피 업데이트"""
        request = {
            'action': 'update_recipe',
            'recipe_id': recipe_id,
            'recipe': recipe_data
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    def delete_recipe(self, recipe_id: str) -> bool:
        """레시피 삭제"""
        request = {
            'action': 'delete_recipe',
            'recipe_id': recipe_id
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    # ==================== 재고 관련 API ====================

    def get_stocks(self) -> List[Dict]:
        """재고 목록 조회"""
        request = {'action': 'get_stocks'}
        response = self.send_request(request)
        if response and response.get('success'):
            return response.get('stocks', [])
        return []

    def get_stock(self, stock_id: str) -> Optional[Dict]:
        """특정 재고 조회"""
        request = {
            'action': 'get_stock',
            'stock_id': stock_id
        }
        response = self.send_request(request)
        if response and response.get('success'):
            return response.get('stock')
        return None

    def update_stock(self, stock_id: str, quantity: float) -> bool:
        """재고 수량 업데이트"""
        request = {
            'action': 'update_stock',
            'stock_id': stock_id,
            'quantity': quantity
        }
        response = self.send_request(request)
        return response and response.get('success', False)

    def get_low_stocks(self) -> List[Dict]:
        """재고 부족 항목 조회"""
        request = {'action': 'get_low_stocks'}
        response = self.send_request(request)
        if response and response.get('success'):
            return response.get('stocks', [])
        return []


class MockAdminServiceClient(QObject):
    """
    테스트용 Mock Admin Service Client
    실제 서버 없이 GUI 테스트 가능
    """

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    order_updated_signal = pyqtSignal(dict)
    stock_alert_signal = pyqtSignal(dict)
    serving_alert_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.is_connected = False
        self._init_mock_data()

    def _init_mock_data(self):
        """Mock 데이터 초기화"""
        # Mock 주문 데이터
        self.mock_orders = [
            {
                'order_id': 'ORD001',
                'table_number': 1,
                'items': [
                    {'menu_id': 'M001', 'menu_name': '햄치즈샌드위치', 'price': 5000, 'quantity': 2, 'subtotal': 10000, 'sauce': '마요네즈'}
                ],
                'total_price': 10000,
                'status': 'cooking',
                'created_at': datetime.now().isoformat()
            },
            {
                'order_id': 'ORD002',
                'table_number': 3,
                'items': [
                    {'menu_id': 'M002', 'menu_name': '머쉬룸샌드위치', 'price': 5500, 'quantity': 1, 'subtotal': 5500, 'sauce': '케찹'},
                    {'menu_id': 'M001', 'menu_name': '햄치즈샌드위치', 'price': 5000, 'quantity': 1, 'subtotal': 5000, 'sauce': '머스타드'}
                ],
                'total_price': 10500,
                'status': 'confirmed',
                'created_at': datetime.now().isoformat()
            },
            {
                'order_id': 'ORD003',
                'table_number': 5,
                'items': [
                    {'menu_id': 'M003', 'menu_name': '올인원샌드위치', 'price': 6500, 'quantity': 2, 'subtotal': 13000, 'sauce': '마요네즈'}
                ],
                'total_price': 13000,
                'status': 'ready',
                'created_at': datetime.now().isoformat()
            }
        ]

        # Mock 레시피 데이터
        self.mock_recipes = [
            {
                'recipe_id': 'R001',
                'menu_id': 'M001',
                'menu_name': '햄치즈샌드위치',
                'ingredients': [
                    {'ingredient_id': 'I001', 'ingredient_name': '빵', 'quantity': 2, 'unit': '장'},
                    {'ingredient_id': 'I004', 'ingredient_name': '양상추', 'quantity': 20, 'unit': 'g'},
                    {'ingredient_id': 'I003', 'ingredient_name': '토마토', 'quantity': 30, 'unit': 'g'},
                    {'ingredient_id': 'I002', 'ingredient_name': '치즈', 'quantity': 1, 'unit': '장'},
                    {'ingredient_id': 'I005', 'ingredient_name': '햄', 'quantity': 2, 'unit': '장'}
                ],
                'cooking_steps': [
                    {'step_number': 1, 'description': '빵 토스트하기', 'estimated_time': 120},
                    {'step_number': 2, 'description': '햄 팬에 굽기', 'estimated_time': 180},
                    {'step_number': 3, 'description': '채소 손질 및 준비', 'estimated_time': 60},
                    {'step_number': 4, 'description': '빵 위에 양상추, 토마토, 치즈, 햄 순서로 쌓기', 'estimated_time': 60},
                    {'step_number': 5, 'description': '선택한 소스 추가 및 빵으로 덮기', 'estimated_time': 20}
                ],
                'total_cooking_time': 440,
                'difficulty': 'easy'
            },
            {
                'recipe_id': 'R002',
                'menu_id': 'M002',
                'menu_name': '머쉬룸샌드위치',
                'ingredients': [
                    {'ingredient_id': 'I001', 'ingredient_name': '빵', 'quantity': 2, 'unit': '장'},
                    {'ingredient_id': 'I006', 'ingredient_name': '버섯', 'quantity': 50, 'unit': 'g'},
                    {'ingredient_id': 'I003', 'ingredient_name': '토마토', 'quantity': 30, 'unit': 'g'},
                    {'ingredient_id': 'I002', 'ingredient_name': '치즈', 'quantity': 1, 'unit': '장'},
                    {'ingredient_id': 'I005', 'ingredient_name': '햄', 'quantity': 2, 'unit': '장'}
                ],
                'cooking_steps': [
                    {'step_number': 1, 'description': '빵 토스트하기', 'estimated_time': 120},
                    {'step_number': 2, 'description': '버섯 볶기', 'estimated_time': 240},
                    {'step_number': 3, 'description': '햄 팬에 굽기', 'estimated_time': 180},
                    {'step_number': 4, 'description': '빵 위에 버섯, 토마토, 치즈, 햄 순서로 쌓기', 'estimated_time': 60},
                    {'step_number': 5, 'description': '선택한 소스 추가 및 빵으로 덮기', 'estimated_time': 20}
                ],
                'total_cooking_time': 620,
                'difficulty': 'easy'
            },
            {
                'recipe_id': 'R003',
                'menu_id': 'M003',
                'menu_name': '올인원샌드위치',
                'ingredients': [
                    {'ingredient_id': 'I001', 'ingredient_name': '빵', 'quantity': 2, 'unit': '장'},
                    {'ingredient_id': 'I003', 'ingredient_name': '토마토', 'quantity': 30, 'unit': 'g'},
                    {'ingredient_id': 'I002', 'ingredient_name': '치즈', 'quantity': 1, 'unit': '장'},
                    {'ingredient_id': 'I005', 'ingredient_name': '햄', 'quantity': 2, 'unit': '장'},
                    {'ingredient_id': 'I006', 'ingredient_name': '버섯', 'quantity': 50, 'unit': 'g'},
                    {'ingredient_id': 'I004', 'ingredient_name': '양상추', 'quantity': 20, 'unit': 'g'}
                ],
                'cooking_steps': [
                    {'step_number': 1, 'description': '빵 토스트하기', 'estimated_time': 120},
                    {'step_number': 2, 'description': '햄 팬에 굽기', 'estimated_time': 180},
                    {'step_number': 3, 'description': '버섯 볶기', 'estimated_time': 240},
                    {'step_number': 4, 'description': '채소 손질 및 준비', 'estimated_time': 60},
                    {'step_number': 5, 'description': '빵 위에 토마토, 치즈, 햄, 버섯, 양상추 순서로 쌓기', 'estimated_time': 80},
                    {'step_number': 6, 'description': '선택한 소스 추가 및 빵으로 덮기', 'estimated_time': 20}
                ],
                'total_cooking_time': 700,
                'difficulty': 'medium'
            }
        ]

        # Mock 재고 데이터 (3단계 재고 시스템)
        # 재고 영역: 식재료 박스 보관 (각 박스당 6개)
        # 식재료 밧드: 6종 박스 각 1개씩 배치 (0~6개 잔량)
        self.mock_stocks = [
            {
                'stock_id': 'S001',
                'ingredient': {'ingredient_id': 'I001', 'name': '빵', 'unit': '장', 'allergens': ['wheat']},
                'quantity': 100,
                'threshold': 30,
                'supplier': {'supplier_id': 'SUP001', 'name': '제과점', 'contact': '010-1234-5678'},
                'stock_area_boxes': 15,  # 재고 영역에 15박스
                'bed_remaining': 4,  # 식재료 밧드에 4개 남음
                'box_size': 6,
                'total_quantity': 94,  # 15*6 + 4
                'is_low_stock': False
            },
            {
                'stock_id': 'S002',
                'ingredient': {'ingredient_id': 'I002', 'name': '치즈', 'unit': '장', 'allergens': ['dairy']},
                'quantity': 80,
                'threshold': 20,
                'supplier': {'supplier_id': 'SUP002', 'name': '유제품센터', 'contact': '010-3456-7890'},
                'stock_area_boxes': 12,  # 재고 영역에 12박스
                'bed_remaining': 3,  # 식재료 밧드에 3개 남음
                'box_size': 6,
                'total_quantity': 75,  # 12*6 + 3
                'is_low_stock': False
            },
            {
                'stock_id': 'S003',
                'ingredient': {'ingredient_id': 'I003', 'name': '토마토', 'unit': 'g', 'allergens': []},
                'quantity': 2500,
                'threshold': 500,
                'supplier': {'supplier_id': 'SUP003', 'name': '채소농장', 'contact': '010-5678-9012'},
                'stock_area_boxes': 8,  # 재고 영역에 8박스 (각 박스 180g = 30g*6)
                'bed_remaining': 150,  # 식재료 밧드에 150g (5개분량)
                'box_size': 180,  # 박스당 180g
                'total_quantity': 1590,  # 8*180 + 150
                'is_low_stock': False
            },
            {
                'stock_id': 'S004',
                'ingredient': {'ingredient_id': 'I004', 'name': '양상추', 'unit': 'g', 'allergens': []},
                'quantity': 1500,
                'threshold': 500,
                'supplier': {'supplier_id': 'SUP003', 'name': '채소농장', 'contact': '010-5678-9012'},
                'stock_area_boxes': 6,  # 재고 영역에 6박스 (각 박스 120g = 20g*6)
                'bed_remaining': 80,  # 식재료 밧드에 80g (4개분량)
                'box_size': 120,  # 박스당 120g
                'total_quantity': 800,  # 6*120 + 80
                'is_low_stock': False
            },
            {
                'stock_id': 'S005',
                'ingredient': {'ingredient_id': 'I005', 'name': '햄', 'unit': '장', 'allergens': ['pork']},
                'quantity': 25,
                'threshold': 30,
                'supplier': {'supplier_id': 'SUP004', 'name': '신선육류', 'contact': '010-2345-6789'},
                'stock_area_boxes': 3,  # 재고 영역에 3박스만 남음!
                'bed_remaining': 2,  # 식재료 밧드에 2개 남음
                'box_size': 6,
                'total_quantity': 20,  # 3*6 + 2 (임계값 이하!)
                'is_low_stock': True
            },
            {
                'stock_id': 'S006',
                'ingredient': {'ingredient_id': 'I006', 'name': '버섯', 'unit': 'g', 'allergens': []},
                'quantity': 2000,
                'threshold': 500,
                'supplier': {'supplier_id': 'SUP003', 'name': '채소농장', 'contact': '010-5678-9012'},
                'stock_area_boxes': 10,  # 재고 영역에 10박스 (각 박스 300g = 50g*6)
                'bed_remaining': 250,  # 식재료 밧드에 250g (5개분량)
                'box_size': 300,  # 박스당 300g
                'total_quantity': 3250,  # 10*300 + 250
                'is_low_stock': False
            }
        ]

    def connect(self) -> bool:
        """Mock 연결"""
        self.is_connected = True
        self.connected_signal.emit()
        print('[MockAdminClient] Mock 연결 성공')
        return True

    def disconnect(self):
        """Mock 연결 종료"""
        self.is_connected = False
        self.disconnected_signal.emit()
        print('[MockAdminClient] Mock 연결 종료')

    # ==================== 주문 관련 Mock API ====================

    def get_orders(self, status: Optional[str] = None) -> List[Dict]:
        """주문 목록 조회 (Mock)"""
        if status:
            return [o for o in self.mock_orders if o['status'] == status]
        return self.mock_orders

    def get_order(self, order_id: str) -> Optional[Dict]:
        """특정 주문 조회 (Mock)"""
        for order in self.mock_orders:
            if order['order_id'] == order_id:
                return order
        return None

    def update_order_status(self, order_id: str, status: str) -> bool:
        """주문 상태 업데이트 (Mock)"""
        for order in self.mock_orders:
            if order['order_id'] == order_id:
                order['status'] = status
                print(f'[MockAdminClient] 주문 {order_id} 상태 변경: {status}')
                self.order_updated_signal.emit(order)
                return True
        return False

    def cancel_order(self, order_id: str, reason: str = "") -> bool:
        """주문 취소 (Mock)"""
        return self.update_order_status(order_id, 'cancelled')

    def halt_order(self, order_id: str) -> bool:
        """주문 일시중지 (Mock)"""
        return self.update_order_status(order_id, 'halted')

    def confirm_inspection(self, order_id: str) -> bool:
        """음식 검수 완료 (Mock)"""
        return self.update_order_status(order_id, 'inspected')

    def start_serving(self, order_id: str) -> bool:
        """서빙 출발 (Mock)"""
        return self.update_order_status(order_id, 'delivering')

    # ==================== 레시피 관련 Mock API ====================

    def get_recipes(self) -> List[Dict]:
        """레시피 목록 조회 (Mock)"""
        return self.mock_recipes

    def get_recipe(self, recipe_id: str) -> Optional[Dict]:
        """특정 레시피 조회 (Mock)"""
        for recipe in self.mock_recipes:
            if recipe['recipe_id'] == recipe_id:
                return recipe
        return None

    def create_recipe(self, recipe_data: dict) -> bool:
        """레시피 생성 (Mock)"""
        self.mock_recipes.append(recipe_data)
        print(f'[MockAdminClient] 레시피 생성: {recipe_data.get("menu_name")}')
        return True

    def update_recipe(self, recipe_id: str, recipe_data: dict) -> bool:
        """레시피 업데이트 (Mock)"""
        for i, recipe in enumerate(self.mock_recipes):
            if recipe['recipe_id'] == recipe_id:
                self.mock_recipes[i] = {**recipe, **recipe_data}
                print(f'[MockAdminClient] 레시피 업데이트: {recipe_id}')
                return True
        return False

    def delete_recipe(self, recipe_id: str) -> bool:
        """레시피 삭제 (Mock)"""
        for i, recipe in enumerate(self.mock_recipes):
            if recipe['recipe_id'] == recipe_id:
                del self.mock_recipes[i]
                print(f'[MockAdminClient] 레시피 삭제: {recipe_id}')
                return True
        return False

    # ==================== 재고 관련 Mock API ====================

    def get_stocks(self) -> List[Dict]:
        """재고 목록 조회 (Mock)"""
        return self.mock_stocks

    def get_stock(self, stock_id: str) -> Optional[Dict]:
        """특정 재고 조회 (Mock)"""
        for stock in self.mock_stocks:
            if stock['stock_id'] == stock_id:
                return stock
        return None

    def update_stock(self, stock_id: str, quantity: float) -> bool:
        """재고 수량 업데이트 (Mock)"""
        for stock in self.mock_stocks:
            if stock['stock_id'] == stock_id:
                stock['quantity'] = quantity
                stock['is_low_stock'] = quantity <= stock['threshold']
                print(f'[MockAdminClient] 재고 업데이트: {stock_id} -> {quantity}')
                if stock['is_low_stock']:
                    self.stock_alert_signal.emit(stock)
                return True
        return False

    def get_low_stocks(self) -> List[Dict]:
        """재고 부족 항목 조회 (Mock)"""
        return [s for s in self.mock_stocks if s['is_low_stock']]


# 테스트 코드
if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Mock 클라이언트 테스트
    client = MockAdminServiceClient()
    client.connect()

    print('\n=== 주문 목록 조회 ===')
    orders = client.get_orders()
    for order in orders:
        print(f"주문 {order['order_id']}: 테이블 {order['table_number']}, 상태: {order['status']}, 금액: {order['total_price']}원")

    print('\n=== 레시피 목록 조회 ===')
    recipes = client.get_recipes()
    for recipe in recipes:
        print(f"레시피 {recipe['recipe_id']}: {recipe['menu_name']}, 조리시간: {recipe['total_cooking_time']}초")

    print('\n=== 재고 목록 조회 ===')
    stocks = client.get_stocks()
    for stock in stocks:
        print(f"재고 {stock['stock_id']}: {stock['ingredient']['name']}, 수량: {stock['quantity']}{stock['ingredient']['unit']}, 부족: {stock['is_low_stock']}")

    print('\n=== 재고 부족 항목 조회 ===')
    low_stocks = client.get_low_stocks()
    for stock in low_stocks:
        print(f"⚠️ {stock['ingredient']['name']}: {stock['quantity']}{stock['ingredient']['unit']} (임계값: {stock['threshold']})")

    client.disconnect()
    print('\n테스트 완료')
