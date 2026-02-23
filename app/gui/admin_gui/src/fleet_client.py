"""
Fleet Management System용 TCP 클라이언트
Main Server와 통신하여 서빙 로봇 상태 모니터링
"""
import socket
import json
import threading
from typing import Optional, Dict, List
from PyQt5.QtCore import QObject, pyqtSignal


class FleetClient(QObject):
    """
    FMS Main Server와 통신하는 TCP 클라이언트

    Main Server 포트: 9999 (기본값)
    프로토콜: JSON 기반 메시지 교환
    """

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    fleet_status_updated = pyqtSignal(dict)  # Fleet 상태 업데이트
    robot_status_updated = pyqtSignal(dict)  # 개별 로봇 상태 업데이트
    order_status_updated = pyqtSignal(dict)  # 주문 상태 업데이트

    def __init__(self, host: str = 'localhost', port: int = 9999):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False
        self.receive_thread = None
        self.running = False

    def connect(self) -> bool:
        """Main Server에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            self.running = True

            # 수신 스레드 시작
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            self.connected_signal.emit()
            print(f'[FleetClient] Main Server 연결 성공: {self.host}:{self.port}')
            return True
        except Exception as e:
            error_msg = f'Main Server 연결 실패: {str(e)}'
            print(f'[FleetClient] {error_msg}')
            self.error_signal.emit(error_msg)
            return False

    def disconnect(self):
        """연결 종료"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None
                self.is_connected = False
                self.disconnected_signal.emit()
                print('[FleetClient] Main Server 연결 종료')

    def send_request(self, message_type: str, data: dict) -> bool:
        """
        Main Server에 요청 전송

        Args:
            message_type: 메시지 타입 (fleet_status_query, order_status_query 등)
            data: 메시지 데이터

        Returns:
            전송 성공 여부
        """
        if not self.is_connected:
            print('[FleetClient] 연결되지 않음')
            return False

        try:
            message = {
                'type': message_type,
                'data': data
            }
            json_data = json.dumps(message, ensure_ascii=False)
            self.socket.sendall(json_data.encode('utf-8'))
            return True
        except Exception as e:
            print(f'[FleetClient] 요청 전송 실패: {str(e)}')
            self.error_signal.emit(f'요청 전송 실패: {str(e)}')
            return False

    def _receive_loop(self):
        """메시지 수신 루프 (별도 스레드)"""
        buffer = b''

        while self.running:
            try:
                # 데이터 수신
                data = self.socket.recv(4096)
                if not data:
                    print('[FleetClient] 서버 연결 끊김')
                    break

                buffer += data

                # JSON 메시지 파싱 (버퍼에서 완전한 JSON 추출)
                while buffer:
                    try:
                        # JSON 디코딩 시도
                        message_str = buffer.decode('utf-8')
                        message = json.loads(message_str)
                        buffer = b''  # 성공하면 버퍼 비우기

                        # 메시지 처리
                        self._handle_message(message)

                    except json.JSONDecodeError:
                        # 불완전한 JSON이면 더 받기
                        break
                    except Exception as e:
                        print(f'[FleetClient] 메시지 처리 오류: {str(e)}')
                        buffer = b''
                        break

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f'[FleetClient] 수신 오류: {str(e)}')
                break

        # 연결 종료
        self.disconnect()

    def _handle_message(self, message: dict):
        """
        수신한 메시지 처리

        메시지 타입:
        - fleet_status_update: Fleet 전체 상태
        - robot_status_update: 개별 로봇 상태
        - order_status_update: 주문 상태
        """
        message_type = message.get('type')
        data = message.get('data', {})

        if message_type == 'fleet_status_update':
            # Fleet 상태 업데이트
            self.fleet_status_updated.emit(data)

        elif message_type == 'robot_status_update':
            # 개별 로봇 상태 업데이트
            self.robot_status_updated.emit(data)

        elif message_type == 'order_status_update':
            # 주문 상태 업데이트
            self.order_status_updated.emit(data)

        else:
            print(f'[FleetClient] 알 수 없는 메시지 타입: {message_type}')

    # ==================== API 메서드 ====================

    def query_fleet_status(self):
        """Fleet 상태 조회"""
        return self.send_request('fleet_status_query', {})

    def query_order_status(self, order_id: str):
        """주문 상태 조회"""
        return self.send_request('order_status_query', {'order_id': order_id})

    def send_delivery_complete(self, order_id: str, table_number: str):
        """배달 완료 신호 전송"""
        return self.send_request('delivery_complete', {
            'order_id': order_id,
            'table_number': table_number
        })


class MockFleetClient(QObject):
    """
    테스트용 Mock Fleet Client
    실제 서버 없이 GUI 테스트 가능
    """

    # 시그널 정의
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    fleet_status_updated = pyqtSignal(dict)
    robot_status_updated = pyqtSignal(dict)
    order_status_updated = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.is_connected = False
        self._init_mock_data()
        self._timer = None

    def _init_mock_data(self):
        """Mock 데이터 초기화"""
        self.mock_fleet_status = {
            'robots': [
                {
                    'robot_id': 'pinky1',
                    'status': 'IDLE',
                    'battery_voltage': 24.5,
                    'battery_present': True
                },
                {
                    'robot_id': 'pinky2',
                    'status': 'MOVING_TO_TABLE',
                    'battery_voltage': 23.8,
                    'battery_present': True
                },
                {
                    'robot_id': 'pinky3',
                    'status': 'DELIVERING',
                    'battery_voltage': 22.1,
                    'battery_present': True
                }
            ],
            'pending_orders': 2,
            'active_orders': 1
        }

    def connect(self) -> bool:
        """Mock 연결"""
        self.is_connected = True
        self.connected_signal.emit()
        print('[MockFleetClient] Mock 연결 성공')

        # 주기적으로 Mock 데이터 전송 (2초마다)
        from PyQt5.QtCore import QTimer
        self._timer = QTimer()
        self._timer.timeout.connect(self._send_mock_updates)
        self._timer.start(2000)

        return True

    def disconnect(self):
        """Mock 연결 종료"""
        if self._timer:
            self._timer.stop()
        self.is_connected = False
        self.disconnected_signal.emit()
        print('[MockFleetClient] Mock 연결 종료')

    def send_request(self, message_type: str, data: dict) -> bool:
        """Mock 요청 전송"""
        print(f'[MockFleetClient] 요청: {message_type}, 데이터: {data}')
        return True

    def query_fleet_status(self):
        """Fleet 상태 조회 (Mock)"""
        self.fleet_status_updated.emit(self.mock_fleet_status)
        return True

    def query_order_status(self, order_id: str):
        """주문 상태 조회 (Mock)"""
        return True

    def send_delivery_complete(self, order_id: str, table_number: str):
        """배달 완료 신호 (Mock)"""
        print(f'[MockFleetClient] 배달 완료: {order_id}, {table_number}')
        return True

    def _send_mock_updates(self):
        """주기적으로 Mock 업데이트 전송"""
        # Fleet 상태 업데이트
        self.fleet_status_updated.emit(self.mock_fleet_status)

        # 로봇 배터리 소모 시뮬레이션
        import random
        for robot in self.mock_fleet_status['robots']:
            robot['battery_voltage'] -= random.uniform(0.01, 0.05)
            if robot['battery_voltage'] < 20.0:
                robot['battery_voltage'] = 25.0  # 재충전
