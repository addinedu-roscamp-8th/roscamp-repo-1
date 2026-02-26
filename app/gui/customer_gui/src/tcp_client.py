"""
TCP 클라이언트 - 주문 MS, FMS, 로봇 서비스와 통신
"""
import socket
import json
import sys
import os
import threading
from typing import Optional, List
from PyQt5.QtCore import QObject, pyqtSignal, QThread

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config, MenuItem, Order, OrderStatus


class MessageListenerThread(threading.Thread):
    """비동기 메시지 리스너 스레드"""

    def __init__(self, tcp_client: 'TCPClient'):
        super().__init__(daemon=True)
        self.tcp_client = tcp_client
        self.running = True

    def run(self):
        """스레드 실행: 계속해서 메시지 수신"""
        print('[MessageListener] 리스너 스레드 시작')
        while self.running and self.tcp_client.is_connected:
            try:
                # 메시지 수신 (논블로킹)
                message = self.tcp_client._receive_data_internal()
                if message:
                    # 메시지 타입에 따라 시그널 emit
                    message_type = message.get('type')
                    if message_type == 'delivery_notification':
                        self.tcp_client.delivery_notification_signal.emit(message)
                    else:
                        self.tcp_client.data_received_signal.emit(message)
            except Exception as e:
                if self.running:
                    print(f'[MessageListener] 오류: {e}')
                break

    def stop(self):
        """스레드 종료"""
        self.running = False


class TCPClient(QObject):
    """TCP 클라이언트"""

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    data_received_signal = pyqtSignal(dict)
    delivery_notification_signal = pyqtSignal(dict)

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False
        self.listener_thread = None
        self.listener_lock = threading.Lock()

    def connect(self) -> bool:
        """서버에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # 5초 타임아웃
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            self.connected_signal.emit()
            print(f'[TCPClient] 연결 성공: {self.host}:{self.port}')

            # 메시지 리스너 스레드 시작
            self._start_listener()

            return True
        except Exception as e:
            error_msg = f'연결 실패: {str(e)}'
            print(f'[TCPClient] {error_msg}')
            self.error_signal.emit(error_msg)
            return False

    def disconnect(self):
        """연결 종료"""
        # 리스너 스레드 종료
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
                print('[TCPClient] 연결 종료')

    def send_data(self, data: dict) -> bool:
        """데이터 전송"""
        if not self.is_connected or not self.socket:
            self.error_signal.emit('서버에 연결되지 않음')
            return False

        try:
            # JSON 직렬화
            json_data = json.dumps(data, ensure_ascii=False)
            # 메시지 길이 헤더 추가 (4 bytes)
            message = json_data.encode('utf-8')
            length_header = len(message).to_bytes(4, byteorder='big')

            # 전송
            self.socket.sendall(length_header + message)
            print(f'[TCPClient] 데이터 전송: {json_data[:100]}...')
            return True
        except Exception as e:
            error_msg = f'전송 실패: {str(e)}'
            print(f'[TCPClient] {error_msg}')
            self.error_signal.emit(error_msg)
            return False

    def _start_listener(self):
        """메시지 리스너 스레드 시작"""
        with self.listener_lock:
            if self.listener_thread is None or not self.listener_thread.is_alive():
                self.listener_thread = MessageListenerThread(self)
                self.listener_thread.start()
                print('[TCPClient] 메시지 리스너 스레드 시작됨')

    def _stop_listener(self):
        """메시지 리스너 스레드 종료"""
        with self.listener_lock:
            if self.listener_thread and self.listener_thread.is_alive():
                self.listener_thread.stop()
                self.listener_thread.join(timeout=2.0)
                self.listener_thread = None
                print('[TCPClient] 메시지 리스너 스레드 종료됨')

    def _receive_data_internal(self) -> Optional[dict]:
        """내부용 데이터 수신 (리스너 스레드용)"""
        if not self.is_connected or not self.socket:
            return None

        try:
            # 메시지 길이 헤더 수신 (4 bytes)
            length_header = self.socket.recv(4)
            if not length_header:
                return None

            message_length = int.from_bytes(length_header, byteorder='big')

            # 메시지 수신
            message = b''
            while len(message) < message_length:
                chunk = self.socket.recv(min(4096, message_length - len(message)))
                if not chunk:
                    break
                message += chunk

            # JSON 파싱
            json_data = message.decode('utf-8')
            data = json.loads(json_data)
            print(f'[TCPClient] 메시지 수신: {json_data[:100]}...')
            return data

        except socket.timeout:
            # 타임아웃은 정상 (논블로킹 처리)
            return None
        except Exception as e:
            if self.is_connected:
                error_msg = f'수신 실패: {str(e)}'
                print(f'[TCPClient] {error_msg}')
                self.error_signal.emit(error_msg)
            return None

    def receive_data(self) -> Optional[dict]:
        """데이터 수신 (요청-응답용)"""
        return self._receive_data_internal()


class OrderServiceClient(QObject):
    """주문 서비스 클라이언트 (주문 MS와 통신)"""

    # 시그널 정의
    menus_received_signal = pyqtSignal(list)  # 메뉴 리스트 수신
    order_response_signal = pyqtSignal(dict)  # 주문 응답 수신
    delivery_notification_signal = pyqtSignal(dict)  # 배달 알림 수신
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.client = TCPClient(*Config.get_order_ms_address())
        self.client.error_signal.connect(self.error_signal)
        self.client.delivery_notification_signal.connect(self.delivery_notification_signal)

    def connect(self) -> bool:
        """주문 MS에 연결"""
        return self.client.connect()

    def disconnect(self):
        """연결 종료"""
        self.client.disconnect()

    def fetch_menus(self) -> List[MenuItem]:
        """메뉴 리스트 가져오기 - SR-01: 메뉴 제공"""
        print('[OrderService] 메뉴 리스트 요청')

        # 요청 메시지
        request = {
            'command': 'get_menus',
            'table_number': Config.TABLE_NUMBER
        }

        if not self.client.send_data(request):
            return []

        # 응답 수신
        response = self.client.receive_data()
        if not response or response.get('status') != 'success':
            self.error_signal.emit('메뉴 조회 실패')
            return []

        # MenuItem 객체 리스트로 변환 (data.menus 또는 menus 에서 가져옴)
        menu_items = []
        data = response.get('data', response)  # data 필드가 있으면 그 안에서, 없으면 response에서
        for menu_data in data.get('menus', []):
            menu_item = MenuItem.from_dict(menu_data)
            menu_items.append(menu_item)

        print(f'[OrderService] 메뉴 {len(menu_items)}개 수신')
        self.menus_received_signal.emit(menu_items)
        return menu_items

    def submit_order(self, order: Order) -> Optional[str]:
        """주문 전송 - SR-06: 주문 전송"""
        print(f'[OrderService] 주문 전송 - 테이블 {order.table_number}')

        # 요청 메시지
        request = {
            'command': 'submit_order',
            'order': order.to_dict()
        }

        if not self.client.send_data(request):
            return None

        # 응답 수신
        response = self.client.receive_data()
        if not response or response.get('status') != 'success':
            data = response.get('data', response) if response else {}
            error_msg = data.get('message', '주문 전송 실패')
            self.error_signal.emit(error_msg)
            return None

        # 주문 번호 반환 (data.order_id 또는 order_id에서 가져옴)
        data = response.get('data', response)
        order_id = data.get('order_id')
        print(f'[OrderService] 주문 성공 - 주문 번호: {order_id}')
        self.order_response_signal.emit(response)
        return order_id

    def confirm_delivery(self, order_id: str) -> bool:
        """수령 확인 전송 - SR-16: 음식 수령 확인 / SC-185: 수령 확인 API"""
        print(f'[OrderService] 수령 확인 전송 - 주문 {order_id}')

        request = {
            'type': 'delivery_complete',
            'data': {
                'order_id': order_id,
                'table_number': str(Config.TABLE_NUMBER)
            }
        }

        if not self.client.send_data(request):
            return False

        response = self.client.receive_data()
        if not response or response.get('status') != 'success':
            self.error_signal.emit('수령 확인 실패')
            return False

        print(f'[OrderService] 수령 확인 성공')
        return True


class MockOrderServiceClient(QObject):
    """Mock 주문 서비스 클라이언트 (테스트용)"""

    # 클래스 레벨에서 시그널 정의
    menus_received_signal = pyqtSignal(list)
    order_response_signal = pyqtSignal(dict)
    delivery_notification_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self):
        """Mock 클라이언트 초기화 (실제 TCP 클라이언트 없이)"""
        super().__init__()
        self.client = None
        self.mock_timer = None

    def connect(self) -> bool:
        """가상 연결"""
        print('[MockOrderService] Mock 연결 성공')
        return True

    def disconnect(self):
        """가상 연결 종료"""
        print('[MockOrderService] Mock 연결 종료')

    def fetch_menus(self) -> List[MenuItem]:
        """가상 메뉴 데이터 반환"""
        print('[MockOrderService] Mock 메뉴 리스트 반환')

        mock_menus = [
            MenuItem('M001', '햄치즈 샌드위치', 5000, '재료: 빵, 양상추, 토마토, 치즈, 햄', '', True, '샌드위치'),
            MenuItem('M002', '버섯 샌드위치', 5500, '재료: 빵, 버섯, 토마토, 치즈', '', True, '샌드위치'),
            MenuItem('M003', '올인원 샌드위치', 6500, '재료: 빵, 토마토, 치즈, 햄, 버섯, 양상추', '', True, '샌드위치'),
        ]

        self.menus_received_signal.emit(mock_menus)
        return mock_menus

    def submit_order(self, order: Order) -> Optional[str]:
        """가상 주문 전송"""
        import time
        order_id = f'ORD-{int(time.time())}'
        print(f'[MockOrderService] Mock 주문 전송 성공 - 주문 번호: {order_id}')

        response = {
            'status': 'success',
            'order_id': order_id,
            'message': '주문이 접수되었습니다.'
        }
        self.order_response_signal.emit(response)
        return order_id

    def confirm_delivery(self, order_id: str) -> bool:
        """가상 수령 확인"""
        print(f'[MockOrderService] Mock 수령 확인 - 주문 {order_id}')
        return True


def main():
    """테스트 실행"""
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Mock 클라이언트 테스트
    client = MockOrderServiceClient()
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

    # 수령 확인
    client.confirm_delivery(order_id)

    client.disconnect()


if __name__ == '__main__':
    main()
