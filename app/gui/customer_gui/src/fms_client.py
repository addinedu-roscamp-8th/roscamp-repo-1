"""
FMS Direct TCP Client - Backend 없이 FMS로 직접 통신
Clean Architecture: Infrastructure Layer

Domain Layer: Order, MenuItem (common/models.py)
Application Layer: FMSOrderServiceClient (이 파일)
Infrastructure Layer: TCPClient (tcp_client.py에서 재사용)
Presentation Layer: main.py에서 사용
"""
import socket
import json
import time
import threading
from typing import Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config, MenuItem, Order


class FMSTCPClient:
    """
    FMS TCP 클라이언트 (저수준 TCP 통신)
    Responsibility: FMS 서버와의 TCP 연결 및 메시지 송수신
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.is_connected = False
        self.listener_thread: Optional[threading.Thread] = None
        self.running = False
        self.on_message_received: Optional[Callable] = None

    def connect(self) -> bool:
        """FMS 서버에 연결합니다."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            print(f'[FMSClient] FMS 연결 성공: {self.host}:{self.port}')

            # 메시지 리스너 시작
            self._start_listener()
            return True

        except Exception as e:
            print(f'[FMSClient] FMS 연결 실패: {e}')
            self.is_connected = False
            return False

    def disconnect(self):
        """연결을 종료합니다."""
        self.running = False

        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2.0)

        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None
                self.is_connected = False
                print('[FMSClient] FMS 연결 종료')

    def send_message(self, message: dict) -> bool:
        """메시지를 전송합니다 (4-byte length header + JSON)."""
        if not self.is_connected or not self.socket:
            print('[FMSClient] 오류: FMS 연결되지 않음')
            return False

        try:
            # JSON 직렬화
            json_data = json.dumps(message, ensure_ascii=False)
            message_bytes = json_data.encode('utf-8')

            # 4-byte length header
            length_header = len(message_bytes).to_bytes(4, byteorder='big')

            # 전송
            self.socket.sendall(length_header + message_bytes)
            print(f'[FMSClient] 메시지 전송: {json_data[:200]}...')
            return True

        except Exception as e:
            print(f'[FMSClient] 메시지 전송 실패: {e}')
            self.is_connected = False
            return False

    def _start_listener(self):
        """메시지 리스너 스레드를 시작합니다."""
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen_messages, daemon=True)
        self.listener_thread.start()
        print('[FMSClient] 메시지 리스너 시작')

    def _listen_messages(self):
        """메시지 수신 루프를 실행합니다 (백그라운드 스레드)."""
        while self.running and self.is_connected:
            try:
                message = self._receive_message()
                if message and self.on_message_received:
                    self.on_message_received(message)

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f'[FMSClient] 메시지 수신 오류: {e}')
                break

        print('[FMSClient] 메시지 리스너 종료')

    def _receive_message(self) -> Optional[dict]:
        """메시지를 수신합니다 (4-byte length header + JSON)."""
        if not self.is_connected or not self.socket:
            return None

        try:
            # 4-byte length header 수신
            length_header = self.socket.recv(4)
            if not length_header or len(length_header) < 4:
                return None

            message_length = int.from_bytes(length_header, byteorder='big')

            # 메시지 본문 수신
            message_bytes = b''
            while len(message_bytes) < message_length:
                chunk = self.socket.recv(min(4096, message_length - len(message_bytes)))
                if not chunk:
                    break
                message_bytes += chunk

            # JSON 파싱
            json_data = message_bytes.decode('utf-8')
            message = json.loads(json_data)
            print(f'[FMSClient] 메시지 수신: {json_data[:200]}...')
            return message

        except socket.timeout:
            return None
        except Exception as e:
            if self.is_connected:
                print(f'[FMSClient] 메시지 수신 파싱 오류: {e}')
            return None


class FMSOrderServiceClient(QObject):
    """
    FMS 주문 서비스 클라이언트 (Application Layer)
    Responsibility: FMS로 주문 전송 및 배달 알림 수신 처리

    SOLID Principles:
    - Single Responsibility: FMS 통신 전담
    - Open/Closed: 새로운 메시지 타입 추가 가능 (확장에 열림)
    - Dependency Inversion: QObject 추상화에 의존 (시그널/슬롯)
    """

    # PyQt Signals (이벤트 발행)
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    order_response_signal = pyqtSignal(dict)
    delivery_notification_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        fms_host, fms_port = Config.get_fms_address()
        self.client = FMSTCPClient(fms_host, fms_port)
        self.client.on_message_received = self._handle_message

    def connect(self) -> bool:
        """FMS에 연결합니다."""
        success = self.client.connect()
        if success:
            self.connected_signal.emit()
        else:
            self.error_signal.emit('FMS 연결 실패')
        return success

    def disconnect(self):
        """연결을 종료합니다."""
        self.client.disconnect()
        self.disconnected_signal.emit()

    def submit_order(self, order: Order) -> Optional[str]:
        """
        주문 전송 (FMS로 직접)

        메시지 형식:
        {
            'command': 'new_order',
            'table_number': 1,
            'order': {
                'order_id': 'ORD-XXX',
                'items': [...],
                'table_number': 1
            }
        }
        """
        # order_id 생성 (타임스탬프 기반)
        order_id = f'ORD-{int(time.time())}'
        order.order_id = order_id

        # FMS 주문 메시지 생성
        message = {
            'command': 'new_order',
            'table_number': order.table_number,
            'order': {
                'order_id': order_id,
                'items': [
                    {
                        'menu_id': item.menu_item.menu_id,
                        'name': item.menu_item.name,
                        'quantity': item.quantity,
                        'price': item.menu_item.price
                    }
                    for item in order.items
                ],
                'table_number': order.table_number,
                'total_price': order.calculate_total()
            }
        }

        print(f'[FMSOrderService] 주문 전송 - 테이블 {order.table_number}, 주문 {order_id}')

        # 전송
        if self.client.send_message(message):
            return order_id
        else:
            self.error_signal.emit('주문 전송 실패')
            return None

    def confirm_delivery(self, order_id: str, table_number: int) -> bool:
        """
        수령 확인 전송 (FMS로)

        메시지 형식:
        {
            'type': 'delivery_complete',
            'data': {
                'order_id': 'ORD-XXX',
                'table_number': '1'
            }
        }
        """
        message = {
            'type': 'delivery_complete',
            'data': {
                'order_id': order_id,
                'table_number': str(table_number)
            }
        }

        print(f'[FMSOrderService] 수령 확인 전송 - 주문 {order_id}')

        if self.client.send_message(message):
            return True
        else:
            self.error_signal.emit('수령 확인 전송 실패')
            return False

    def _handle_message(self, message: dict):
        """
        FMS로부터 수신한 메시지 처리

        메시지 타입에 따라 적절한 시그널 발행:
        - delivery_notification: 배달 알림
        - order_response: 주문 응답
        """
        message_type = message.get('type') or message.get('command')

        if message_type == 'delivery_notification':
            print(f'[FMSOrderService] 배달 알림 수신: {message}')
            self.delivery_notification_signal.emit(message)

        elif message_type == 'order_response':
            print(f'[FMSOrderService] 주문 응답 수신: {message}')
            self.order_response_signal.emit(message)

        else:
            print(f'[FMSOrderService] 알 수 없는 메시지 타입: {message_type}')


class MockFMSOrderServiceClient(QObject):
    """
    Mock FMS 클라이언트 (테스트용)
    Responsibility: 실제 FMS 없이 로컬 테스트

    Strategy Pattern: 실제 클라이언트와 동일한 인터페이스 제공
    """

    # 동일한 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    order_response_signal = pyqtSignal(dict)
    delivery_notification_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.is_connected = False

    def connect(self) -> bool:
        """가상으로 연결합니다."""
        print('[MockFMS] Mock FMS 연결 성공')
        self.is_connected = True
        self.connected_signal.emit()
        return True

    def disconnect(self):
        """가상 연결을 종료합니다."""
        print('[MockFMS] Mock FMS 연결 종료')
        self.is_connected = False
        self.disconnected_signal.emit()

    def submit_order(self, order: Order) -> Optional[str]:
        """가상 주문을 전송합니다."""
        order_id = f'ORD-{int(time.time())}'
        order.order_id = order_id
        print(f'[MockFMS] Mock 주문 전송 성공 - 주문 {order_id}')

        # 주문 응답 시그널 발행
        response = {
            'type': 'order_response',
            'status': 'success',
            'order_id': order_id
        }
        self.order_response_signal.emit(response)
        return order_id

    def confirm_delivery(self, order_id: str, table_number: int) -> bool:
        """가상으로 수령을 확인합니다."""
        print(f'[MockFMS] Mock 수령 확인 - 주문 {order_id}')
        return True


def main():
    """테스트를 실행합니다."""
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # FMS 클라이언트 테스트
    print('=== FMS 클라이언트 테스트 ===')
    client = FMSOrderServiceClient()

    # 시그널 연결
    client.connected_signal.connect(lambda: print('[Test] 연결 성공'))
    client.error_signal.connect(lambda msg: print(f'[Test] 오류: {msg}'))
    client.delivery_notification_signal.connect(
        lambda msg: print(f'[Test] 배달 알림: {msg}')
    )

    # 연결 시도
    if client.connect():
        # 테스트 주문
        test_order = Order(table_number=1)
        test_order.add_item(MenuItem('M001', '햄치즈 샌드위치', 5000, '재료: 빵, 양상추, 토마토, 치즈, 햄'), 2)
        test_order.add_item(MenuItem('M002', '버섯 샌드위치', 5500, '재료: 빵, 버섯, 토마토, 치즈'), 1)

        order_id = client.submit_order(test_order)
        print(f'[Test] 주문 전송 완료: {order_id}')

        # 이벤트 루프 실행 (메시지 수신 대기)
        # Ctrl+C로 종료
        try:
            app.exec_()
        except KeyboardInterrupt:
            print('[Test] 종료')
        finally:
            client.disconnect()
    else:
        print('[Test] FMS 연결 실패 - Mock 클라이언트로 테스트')
        mock_client = MockFMSOrderServiceClient()
        mock_client.connect()

        test_order = Order(table_number=1)
        test_order.add_item(MenuItem('M001', '햄치즈 샌드위치', 5000), 1)
        order_id = mock_client.submit_order(test_order)
        print(f'[Test] Mock 주문 전송 완료: {order_id}')

        mock_client.disconnect()


if __name__ == '__main__':
    main()
