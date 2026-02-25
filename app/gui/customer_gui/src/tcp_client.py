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

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False

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
