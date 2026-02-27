"""
FMS Direct Client - Backend 없이 FMS와 직접 TCP 통신
Customer GUI -> FMS (192.168.1.3:9000)
"""
import socket
import json
import sys
import os
import threading
import time
from typing import Optional, List
from PyQt5.QtCore import QObject, pyqtSignal

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config, MenuItem, Order, OrderItem


class FMSMessageListener(threading.Thread):
    """FMS 메시지 리스너 스레드 - 배달 알림 수신"""

    def __init__(self, client: 'FMSDirectClient'):
        super().__init__(daemon=True)
        self.client = client
        self.running = True

    def run(self):
        """스레드 실행: 계속해서 메시지 수신"""
        print('[FMSListener] 리스너 스레드 시작')
        while self.running and self.client.is_connected:
            try:
                message = self.client._receive_message_internal()
                if message:
                    message_type = message.get('type')
                    if message_type == 'delivery_notification':
                        print(f'[FMSListener] 배달 알림 수신: {message}')
                        self.client.delivery_notification_signal.emit(message)
                    else:
                        print(f'[FMSListener] 일반 메시지 수신: {message}')
                        self.client.data_received_signal.emit(message)
            except Exception as e:
                if self.running:
                    print(f'[FMSListener] 오류: {e}')
                break

    def stop(self):
        """스레드 종료"""
        self.running = False


class FMSDirectClient(QObject):
    """
    FMS 직접 통신 클라이언트

    Features:
    - Mock 메뉴 데이터 (햄버거, 피자, 샌드위치)
    - FMS로 직접 주문 전송
    - 배달 알림 수신 대기
    - 수령 확인 전송
    """

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    data_received_signal = pyqtSignal(dict)
    delivery_notification_signal = pyqtSignal(dict)
    menus_received_signal = pyqtSignal(list)
    order_response_signal = pyqtSignal(dict)

    def __init__(self, host: str = None, port: int = None):
        super().__init__()
        # FMS 주소 설정 (기본값: Config에서 가져오기)
        self.host = host or Config.FMS_HOST
        self.port = port or Config.FMS_PORT
        self.socket: Optional[socket.socket] = None
        self.is_connected = False
        self.listener_thread: Optional[FMSMessageListener] = None
        self.listener_lock = threading.Lock()
        self.send_lock = threading.Lock()  # 송신 락

        print(f'[FMSDirectClient] 초기화 - FMS 주소: {self.host}:{self.port}')

    def connect(self) -> bool:
        """FMS에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(Config.CONNECTION_TIMEOUT)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            self.connected_signal.emit()
            print(f'[FMSDirectClient] FMS 연결 성공: {self.host}:{self.port}')

            # 메시지 리스너 스레드 시작
            self._start_listener()

            return True
        except Exception as e:
            error_msg = f'FMS 연결 실패: {str(e)}'
            print(f'[FMSDirectClient] {error_msg}')
            self.error_signal.emit(error_msg)
            return False

    def disconnect(self):
        """연결 종료"""
        self._stop_listener()

        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None
                self.is_connected = False
                self.disconnected_signal.emit()
                print('[FMSDirectClient] 연결 종료')

    def _start_listener(self):
        """메시지 리스너 스레드 시작"""
        with self.listener_lock:
            if self.listener_thread is None or not self.listener_thread.is_alive():
                self.listener_thread = FMSMessageListener(self)
                self.listener_thread.start()
                print('[FMSDirectClient] 메시지 리스너 시작됨')

    def _stop_listener(self):
        """메시지 리스너 스레드 종료"""
        with self.listener_lock:
            if self.listener_thread and self.listener_thread.is_alive():
                self.listener_thread.stop()
                self.listener_thread.join(timeout=2.0)
                self.listener_thread = None
                print('[FMSDirectClient] 메시지 리스너 종료됨')

    def _send_message(self, message: dict) -> bool:
        """메시지 전송 (4바이트 길이 헤더 포함)"""
        if not self.is_connected or not self.socket:
            self.error_signal.emit('FMS에 연결되지 않음')
            return False

        try:
            with self.send_lock:
                json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
                length_header = len(json_data).to_bytes(4, byteorder='big')
                self.socket.sendall(length_header + json_data)
                print(f'[FMSDirectClient] 메시지 전송: {json_data[:100].decode()}...')
                return True
        except Exception as e:
            error_msg = f'전송 실패: {str(e)}'
            print(f'[FMSDirectClient] {error_msg}')
            self.error_signal.emit(error_msg)
            return False

    def _receive_message_internal(self) -> Optional[dict]:
        """내부용 메시지 수신 (리스너 스레드용)"""
        if not self.is_connected or not self.socket:
            return None

        try:
            # 4바이트 길이 헤더 수신
            length_header = self._recv_exact(4)
            if not length_header:
                return None

            message_length = int.from_bytes(length_header, byteorder='big')

            # 메시지 수신
            message_data = self._recv_exact(message_length)
            if not message_data:
                return None

            # JSON 파싱
            json_data = message_data.decode('utf-8')
            data = json.loads(json_data)
            return data

        except socket.timeout:
            return None
        except Exception as e:
            if self.is_connected:
                print(f'[FMSDirectClient] 수신 오류: {e}')
            return None

    def _recv_exact(self, num_bytes: int) -> bytes:
        """정확히 num_bytes 바이트 수신"""
        data = b''
        while len(data) < num_bytes:
            chunk = self.socket.recv(num_bytes - len(data))
            if not chunk:
                return b''
            data += chunk
        return data

    def _receive_response(self) -> Optional[dict]:
        """요청-응답용 메시지 수신"""
        return self._receive_message_internal()

    # ==================== Mock 메뉴 데이터 ====================

    def fetch_menus(self) -> List[MenuItem]:
        """
        메뉴 데이터 반환
        샌드위치 메뉴: 햄치즈, 버섯, 올인원
        """
        print('[FMSDirectClient] 메뉴 데이터 반환')

        mock_menus = [
            MenuItem(
                menu_id='M001',
                name='햄치즈 샌드위치',
                price=5000,
                description='재료: 빵, 양상추, 토마토, 치즈, 햄',
                image_url='',
                available=True,
                category='샌드위치'
            ),
            MenuItem(
                menu_id='M002',
                name='버섯 샌드위치',
                price=5500,
                description='재료: 빵, 버섯, 토마토, 치즈',
                image_url='',
                available=True,
                category='샌드위치'
            ),
            MenuItem(
                menu_id='M003',
                name='올인원 샌드위치',
                price=6500,
                description='재료: 빵, 토마토, 치즈, 햄, 버섯, 양상추',
                image_url='',
                available=True,
                category='샌드위치'
            ),
        ]

        self.menus_received_signal.emit(mock_menus)
        return mock_menus

    # ==================== FMS 주문 전송 ====================

    def submit_order(self, order: Order) -> Optional[str]:
        """
        FMS로 직접 주문 전송

        FMS 메시지 포맷:
        {
            "command": "new_order",
            "table_number": 1,
            "order": {
                "items": [
                    {"menu_id": "M001", "quantity": 1}
                ]
            }
        }
        """
        print(f'[FMSDirectClient] 주문 전송 - 테이블 {order.table_number}')

        # FMS 메시지 포맷으로 변환
        order_items = []
        for item in order.items:
            # sauce 이름 변환: 마요네즈 -> mayo, 케찹 -> ketchup, 머스타드 -> mustard
            sauce_map = {
                '마요네즈': 'mayo',
                '케찹': 'ketchup',
                '머스타드': 'mustard',
                '소스선택x': '',
                '': ''
            }
            sauce_value = sauce_map.get(item.sauce, item.sauce) if item.sauce else ''

            order_items.append({
                'menu_id': item.menu_item.menu_id,
                'menu_name': item.menu_item.name,
                'quantity': item.quantity,
                'price': item.menu_item.price,
                'subtotal': item.get_subtotal(),
                'sauce': sauce_value
            })

        request = {
            'command': 'new_order',
            'table_number': order.table_number,
            'order': {
                'items': order_items,
                'total_price': order.total_price
            }
        }

        if not self._send_message(request):
            return None

        # 응답 수신
        response = self._receive_response()
        if not response:
            self.error_signal.emit('FMS 응답 없음')
            return None

        if response.get('status') != 'success':
            error_msg = response.get('message', '주문 전송 실패')
            self.error_signal.emit(error_msg)
            return None

        # 주문 번호 추출
        data = response.get('data', response)
        order_id = data.get('order_id')
        print(f'[FMSDirectClient] 주문 성공 - 주문 번호: {order_id}')

        self.order_response_signal.emit(response)
        return order_id

    # ==================== 수령 확인 전송 ====================

    def confirm_delivery(self, order_id: str) -> bool:
        """
        수령 확인 전송

        FMS 메시지 포맷:
        {
            "command": "delivery_complete",
            "order_id": "ORD-XXX",
            "table_number": 1
        }
        """
        print(f'[FMSDirectClient] 수령 확인 전송 - 주문 {order_id}')

        request = {
            'command': 'delivery_complete',
            'order_id': order_id,
            'table_number': Config.TABLE_NUMBER
        }

        if not self._send_message(request):
            return False

        # 응답 수신
        response = self._receive_response()
        if not response or response.get('status') != 'success':
            self.error_signal.emit('수령 확인 실패')
            return False

        print(f'[FMSDirectClient] 수령 확인 성공')
        return True


class MockFMSDirectClient(QObject):
    """
    Mock FMS Direct Client - 실제 FMS 연결 없이 테스트용
    배달 알림 시뮬레이션 포함
    """

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    data_received_signal = pyqtSignal(dict)
    delivery_notification_signal = pyqtSignal(dict)
    menus_received_signal = pyqtSignal(list)
    order_response_signal = pyqtSignal(dict)

    def __init__(self, host: str = None, port: int = None):
        super().__init__()
        self.host = host or Config.FMS_HOST
        self.port = port or Config.FMS_PORT
        self.is_connected = False
        self._simulate_delivery = True
        self._delivery_delay = 10  # 배달 시뮬레이션 지연 (초)
        self._pending_order_id = None
        self._delivery_timer = None

        print(f'[MockFMSDirectClient] 초기화 (Mock 모드)')

    def connect(self) -> bool:
        """가상 연결"""
        print('[MockFMSDirectClient] Mock 연결 성공')
        self.is_connected = True
        self.connected_signal.emit()
        return True

    def disconnect(self):
        """가상 연결 종료"""
        self.is_connected = False
        if self._delivery_timer:
            self._delivery_timer.cancel()
        self.disconnected_signal.emit()
        print('[MockFMSDirectClient] Mock 연결 종료')

    def fetch_menus(self) -> List[MenuItem]:
        """Mock 메뉴 데이터 반환"""
        print('[MockFMSDirectClient] Mock 메뉴 데이터 반환')

        mock_menus = [
            MenuItem(
                menu_id='M001',
                name='햄치즈 샌드위치',
                price=5000,
                description='재료: 빵, 양상추, 토마토, 치즈, 햄',
                image_url='',
                available=True,
                category='샌드위치'
            ),
            MenuItem(
                menu_id='M002',
                name='버섯 샌드위치',
                price=5500,
                description='재료: 빵, 버섯, 토마토, 치즈',
                image_url='',
                available=True,
                category='샌드위치'
            ),
            MenuItem(
                menu_id='M003',
                name='올인원 샌드위치',
                price=6500,
                description='재료: 빵, 토마토, 치즈, 햄, 버섯, 양상추',
                image_url='',
                available=True,
                category='샌드위치'
            ),
        ]

        self.menus_received_signal.emit(mock_menus)
        return mock_menus

    def submit_order(self, order: Order) -> Optional[str]:
        """가상 주문 전송 + 배달 시뮬레이션"""
        order_id = f'ORD-{int(time.time())}'
        print(f'[MockFMSDirectClient] Mock 주문 전송 성공 - 주문 번호: {order_id}')

        response = {
            'status': 'success',
            'data': {
                'order_id': order_id,
                'message': '주문이 접수되었습니다.'
            }
        }
        self.order_response_signal.emit(response)

        # 배달 시뮬레이션 (설정된 시간 후 배달 알림 발생)
        if self._simulate_delivery:
            self._pending_order_id = order_id
            self._delivery_timer = threading.Timer(
                self._delivery_delay,
                self._simulate_delivery_notification,
                args=[order_id, order.table_number]
            )
            self._delivery_timer.start()
            print(f'[MockFMSDirectClient] {self._delivery_delay}초 후 배달 알림 시뮬레이션 예약됨')

        return order_id

    def _simulate_delivery_notification(self, order_id: str, table_number: int):
        """배달 알림 시뮬레이션"""
        print(f'[MockFMSDirectClient] 배달 알림 시뮬레이션 - 주문 {order_id}')

        notification = {
            'type': 'delivery_notification',
            'data': {
                'order_id': order_id,
                'table_number': table_number,
                'robot_id': 'pinky1',
                'status': 'arrived'
            }
        }
        self.delivery_notification_signal.emit(notification)

    def confirm_delivery(self, order_id: str) -> bool:
        """가상 수령 확인"""
        print(f'[MockFMSDirectClient] Mock 수령 확인 - 주문 {order_id}')
        return True

    def set_delivery_delay(self, seconds: int):
        """배달 시뮬레이션 지연 시간 설정"""
        self._delivery_delay = seconds

    def enable_delivery_simulation(self, enabled: bool):
        """배달 시뮬레이션 활성화/비활성화"""
        self._simulate_delivery = enabled


def main():
    """테스트 실행"""
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Mock 클라이언트 테스트
    print("=== Mock FMS Direct Client 테스트 ===")
    client = MockFMSDirectClient()
    client.set_delivery_delay(5)  # 5초 후 배달 알림

    # 배달 알림 시그널 연결
    def on_delivery(notification):
        print(f'[테스트] 배달 알림 수신: {notification}')

    client.delivery_notification_signal.connect(on_delivery)

    client.connect()

    # 메뉴 조회
    menus = client.fetch_menus()
    print(f'메뉴 {len(menus)}개 조회됨')

    # 주문 전송
    test_order = Order(table_number=1)
    test_order.add_item(menus[0], 2)
    test_order.add_item(menus[2], 1)

    order_id = client.submit_order(test_order)
    print(f'주문 번호: {order_id}')

    # 5초 대기 (배달 시뮬레이션)
    import time
    print("배달 알림 대기 중...")
    time.sleep(6)

    # 수령 확인
    client.confirm_delivery(order_id)

    client.disconnect()
    print("=== 테스트 완료 ===")


if __name__ == '__main__':
    main()
