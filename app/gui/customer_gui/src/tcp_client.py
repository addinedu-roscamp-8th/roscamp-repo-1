"""
TCP 클라이언트 - 주문 MS, FMS, 로봇 서비스와 통신
"""
import socket
import json
import sys
import os
from typing import Optional, List
from PyQt5.QtCore import QObject, pyqtSignal, QThread

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config, MenuItem, Order, OrderStatus


class TCPClient(QObject):
    """TCP 클라이언트"""

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    data_received_signal = pyqtSignal(dict)
    push_message_signal = pyqtSignal(dict)  # 서버 푸시 메시지 수신용

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False
        self._listener_thread = None
        self._stop_listener = False

    def connect(self) -> bool:
        """서버에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # 5초 타임아웃
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            self.connected_signal.emit()
            print(f'[TCPClient] 연결 성공: {self.host}:{self.port}')
            return True
        except Exception as e:
            error_msg = f'연결 실패: {str(e)}'
            print(f'[TCPClient] {error_msg}')
            self.error_signal.emit(error_msg)
            return False

    def disconnect(self):
        """연결 종료"""
        self._stop_listener = True
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=1.0)
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

    def start_push_listener(self):
        """서버 푸시 메시지 리스너 스레드 시작"""
        if not self.is_connected:
            print('[TCPClient] 연결되지 않아 리스너 시작 불가')
            return

        self._stop_listener = False
        import threading
        self._listener_thread = threading.Thread(target=self._push_listener_loop, daemon=True)
        self._listener_thread.start()
        print('[TCPClient] 푸시 메시지 리스너 시작')

    def _push_listener_loop(self):
        """푸시 메시지 수신 루프"""
        while not self._stop_listener and self.is_connected and self.socket:
            try:
                # 데이터 대기
                self.socket.settimeout(1.0)  # 1초 타임아웃
                data = self.socket.recv(4096)
                if not data:
                    continue

                # JSON 파싱
                json_data = data.decode('utf-8')
                message = json.loads(json_data)
                print(f'[TCPClient] 푸시 메시지 수신: {json_data[:100]}...')
                self.push_message_signal.emit(message)

            except socket.timeout:
                # 타임아웃은 정상 (대기 중)
                continue
            except json.JSONDecodeError as e:
                print(f'[TCPClient] JSON 파싱 오류: {e}')
                continue
            except Exception as e:
                if not self._stop_listener:
                    print(f'[TCPClient] 리스너 오류: {e}')
                break

        print('[TCPClient] 푸시 메시지 리스너 종료')

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

    def receive_data(self) -> Optional[dict]:
        """데이터 수신"""
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
            print(f'[TCPClient] 데이터 수신: {json_data[:100]}...')
            self.data_received_signal.emit(data)
            return data

        except Exception as e:
            error_msg = f'수신 실패: {str(e)}'
            print(f'[TCPClient] {error_msg}')
            self.error_signal.emit(error_msg)
            return None


class OrderServiceClient(QObject):
    """주문 서비스 클라이언트 (주문 MS와 통신)"""

    # 시그널 정의
    menus_received_signal = pyqtSignal(list)  # 메뉴 리스트 수신
    order_response_signal = pyqtSignal(dict)  # 주문 응답 수신
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.client = TCPClient(*Config.get_order_ms_address())
        self.client.error_signal.connect(self.error_signal)

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

        # MenuItem 객체 리스트로 변환
        menu_items = []
        for menu_data in response.get('menus', []):
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
            error_msg = response.get('message', '주문 전송 실패') if response else '주문 전송 실패'
            self.error_signal.emit(error_msg)
            return None

        # 주문 번호 반환
        order_id = response.get('order_id')
        print(f'[OrderService] 주문 성공 - 주문 번호: {order_id}')
        self.order_response_signal.emit(response)
        return order_id

    def confirm_delivery(self, order_id: str) -> bool:
        """수령 확인 전송 - SR-16: 음식 수령 확인"""
        print(f'[OrderService] 수령 확인 전송 - 주문 {order_id}')

        request = {
            'command': 'confirm_delivery',
            'order_id': order_id,
            'table_number': Config.TABLE_NUMBER
        }

        if not self.client.send_data(request):
            return False

        response = self.client.receive_data()
        if not response or response.get('status') != 'success':
            self.error_signal.emit('수령 확인 실패')
            return False

        print(f'[OrderService] 수령 확인 성공')
        return True


class MockOrderServiceClient(OrderServiceClient):
    """Mock 주문 서비스 클라이언트 (테스트용)"""

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
            MenuItem('M001', '햄치즈샌드위치', 5000, '재료: 빵, 양상추, 토마토, 치즈, 햄', '', True, '샌드위치'),
            MenuItem('M002', '머쉬룸샌드위치', 5500, '재료: 빵, 버섯, 토마토, 치즈, 햄', '', True, '샌드위치'),
            MenuItem('M003', '올인원샌드위치', 6500, '재료: 빵, 토마토, 치즈, 햄, 버섯, 양상추', '', True, '샌드위치'),
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


class FMSClient(QObject):
    """
    FMS 클라이언트 - Main Server와 통신하여 주문, 배달 알림 등을 처리

    서버에서 푸시되는 메시지(delivery_notification 등)를 수신하여
    Customer GUI에 전달합니다.
    """

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    order_response_signal = pyqtSignal(dict)  # 주문 응답
    delivery_notification_signal = pyqtSignal(dict)  # 배달 도착 알림
    order_status_update_signal = pyqtSignal(dict)  # 주문 상태 업데이트

    def __init__(self, table_number: int = None):
        super().__init__()
        self.table_number = table_number or Config.TABLE_NUMBER
        self.client = TCPClient(*Config.get_fms_address())
        self.client.error_signal.connect(self.error_signal)
        self.client.push_message_signal.connect(self._handle_push_message)

    def connect(self) -> bool:
        """Main Server에 연결"""
        if self.client.connect():
            self.client.start_push_listener()
            self.connected_signal.emit()
            return True
        return False

    def disconnect(self):
        """연결 종료"""
        self.client.disconnect()
        self.disconnected_signal.emit()

    def _handle_push_message(self, message: dict):
        """
        서버에서 푸시된 메시지 처리

        메시지 타입에 따라 적절한 시그널 발생
        """
        msg_type = message.get('type')
        data = message.get('data', {})

        print(f'[FMSClient] 푸시 메시지 수신: type={msg_type}')

        if msg_type == 'delivery_notification':
            # 배달 도착 알림 - 해당 테이블인지 확인
            table = data.get('table_number', '')
            # T01 형식과 1 형식 모두 처리
            table_num = int(table.replace('T', '').replace('0', '')) if isinstance(table, str) else table
            if table_num == self.table_number:
                print(f'[FMSClient] 배달 도착 알림 (테이블 {self.table_number})')
                self.delivery_notification_signal.emit(data)

        elif msg_type == 'order_status_update':
            # 주문 상태 업데이트
            self.order_status_update_signal.emit(data)

    def submit_order(self, order: Order) -> Optional[str]:
        """주문 전송"""
        print(f'[FMSClient] 주문 전송 - 테이블 {order.table_number}')

        # Table number를 T0X 형식으로 변환
        table_str = f'T{order.table_number:02d}'

        # 첫 번째 아이템 기준으로 주문 정보 구성 (단일 주문)
        first_item = order.items[0] if order.items else None
        if not first_item:
            self.error_signal.emit('주문 항목이 없습니다')
            return None

        request = {
            'type': 'order_request',
            'data': {
                'table_number': table_str,
                'menu_id': first_item.menu_item.menu_id,
                'quantity': first_item.quantity,
                'sauce_type': first_item.sauce or 'mayo',
                'voice_order': False
            }
        }

        # JSON 인코딩하여 전송 (Main Server TCP 프로토콜)
        if not self.client.is_connected:
            self.error_signal.emit('서버에 연결되지 않음')
            return None

        try:
            json_data = json.dumps(request).encode('utf-8')
            self.client.socket.sendall(json_data)

            # 응답 수신
            self.client.socket.settimeout(10.0)
            response_data = self.client.socket.recv(4096)
            response = json.loads(response_data.decode('utf-8'))

            if response.get('status') == 'success':
                order_id = response.get('data', {}).get('order_id')
                print(f'[FMSClient] 주문 성공: {order_id}')
                self.order_response_signal.emit(response)
                return order_id
            else:
                error_msg = response.get('message', '주문 실패')
                self.error_signal.emit(error_msg)
                return None

        except Exception as e:
            self.error_signal.emit(f'주문 전송 오류: {str(e)}')
            return None

    def confirm_delivery(self, order_id: str) -> bool:
        """수령 완료 전송"""
        print(f'[FMSClient] 수령 완료 전송 - 주문 {order_id}')

        table_str = f'T{self.table_number:02d}'

        request = {
            'type': 'delivery_complete',
            'data': {
                'order_id': order_id,
                'table_number': table_str
            }
        }

        if not self.client.is_connected:
            self.error_signal.emit('서버에 연결되지 않음')
            return False

        try:
            json_data = json.dumps(request).encode('utf-8')
            self.client.socket.sendall(json_data)

            # 응답 수신
            self.client.socket.settimeout(5.0)
            response_data = self.client.socket.recv(4096)
            response = json.loads(response_data.decode('utf-8'))

            if response.get('status') == 'success':
                print(f'[FMSClient] 수령 완료 성공')
                return True
            else:
                error_msg = response.get('message', '수령 완료 실패')
                self.error_signal.emit(error_msg)
                return False

        except Exception as e:
            self.error_signal.emit(f'수령 완료 전송 오류: {str(e)}')
            return False


class MockFMSClient(FMSClient):
    """Mock FMS 클라이언트 (테스트용)"""

    def __init__(self, table_number: int = None):
        QObject.__init__(self)
        self.table_number = table_number or Config.TABLE_NUMBER
        self._delivery_timer = None

    def connect(self) -> bool:
        """가상 연결"""
        print('[MockFMSClient] Mock 연결 성공')
        self.connected_signal.emit()
        return True

    def disconnect(self):
        """가상 연결 종료"""
        if self._delivery_timer:
            self._delivery_timer.stop()
        print('[MockFMSClient] Mock 연결 종료')
        self.disconnected_signal.emit()

    def submit_order(self, order: Order) -> Optional[str]:
        """가상 주문 전송"""
        import time
        order_id = f'ORD-{int(time.time())}'
        print(f'[MockFMSClient] Mock 주문 전송 성공 - 주문 번호: {order_id}')

        response = {
            'status': 'success',
            'data': {
                'order_id': order_id,
                'estimated_time': 120
            }
        }
        self.order_response_signal.emit(response)

        # 5초 후 배달 도착 알림 시뮬레이션
        from PyQt5.QtCore import QTimer
        self._delivery_timer = QTimer()
        self._delivery_timer.setSingleShot(True)
        self._delivery_timer.timeout.connect(
            lambda: self._simulate_delivery_arrival(order_id)
        )
        self._delivery_timer.start(5000)  # 5초 후

        return order_id

    def _simulate_delivery_arrival(self, order_id: str):
        """배달 도착 시뮬레이션"""
        print(f'[MockFMSClient] 배달 도착 알림 시뮬레이션 - 주문 {order_id}')
        self.delivery_notification_signal.emit({
            'order_id': order_id,
            'robot_id': 'pinky1',
            'table_number': f'T{self.table_number:02d}'
        })

    def confirm_delivery(self, order_id: str) -> bool:
        """가상 수령 확인"""
        print(f'[MockFMSClient] Mock 수령 완료 - 주문 {order_id}')
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
