"""
Error Handler TCP Client for Admin GUI
Communicates with Main Server to send operator commands and receive error alerts

Protocol:
- Receive: {"type": "error_alert", "data": {"robot_id": "...", "error_type": "...", ...}}
- Send: {"type": "operator_command", "data": {"robot_id": "...", "command": "...", ...}}
"""

import socket
import json
import threading
import logging
from typing import Callable, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorClient:
    """에러 처리용 TCP client"""

    def __init__(self, host: str = 'localhost', port: int = 9999):
        """
        error client 초기화

        Args:
            host: Server host address
            port: Server port
        """
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.receive_thread = None
        self.running = False

        # Callbacks
        self.on_error_alert: Optional[Callable] = None
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None

        logger.info(f"ErrorClient initialized: {host}:{port}")

    def connect(self) -> bool:
        """
        server에 연결

        Returns:
            연결 성공 시 True, 실패 시 False
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.running = True

            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            logger.info(f"Connected to error server at {self.host}:{self.port}")

            if self.on_connected:
                self.on_connected()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to error server: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """server 연결 해제"""
        self.running = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        self.connected = False

        if self.on_disconnected:
            self.on_disconnected()

        logger.info("Disconnected from error server")

    def send_operator_command(self, robot_id: str, command: str, order_id: str = None,
                             reason: str = None) -> bool:
        """
        server로 운영자 명령 전송

        Args:
            robot_id: 대상 robot ID
            command: 운영자 명령 (RETRY, RETURN_HOME, EMERGENCY_STOP, CLEAR_ERROR)
            order_id: 관련 order ID (선택사항)
            reason: 명령 사유

        Returns:
            전송 성공 시 True, 실패 시 False
        """
        if not self.connected:
            logger.warning("Not connected to error server")
            return False

        try:
            message = {
                'type': 'operator_command',
                'data': {
                    'robot_id': robot_id,
                    'command': command,
                    'order_id': order_id or '',
                    'reason': reason or '',
                    'timestamp': datetime.utcnow().isoformat()
                }
            }

            json_str = json.dumps(message)
            self.socket.sendall(json_str.encode() + b'\n')

            logger.info(f"Sent operator command: {robot_id} - {command}")
            return True

        except Exception as e:
            logger.error(f"Failed to send operator command: {e}")
            self.connected = False
            return False

    def _receive_loop(self):
        """server로부터 메시지 수신 (별도 thread에서 실행)"""
        buffer = ""

        while self.running:
            try:
                data = self.socket.recv(4096).decode('utf-8')

                if not data:
                    logger.warning("Server disconnected")
                    self.connected = False
                    break

                buffer += data

                # Process complete messages (separated by newlines)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._process_message(line.strip())

            except Exception as e:
                if self.running:
                    logger.error(f"Error receiving from server: {e}")
                self.connected = False
                break

        if self.on_disconnected:
            self.on_disconnected()

    def _process_message(self, message_str: str):
        """
        수신된 메시지 처리

        Args:
            message_str: JSON 메시지 문자열
        """
        try:
            message = json.loads(message_str)
            msg_type = message.get('type')

            if msg_type == 'error_alert':
                self._handle_error_alert(message.get('data', {}))
            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse message: {message_str}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _handle_error_alert(self, data: Dict):
        """
        에러 alert 메시지 처리

        Args:
            data: 에러 alert 데이터
        """
        robot_id = data.get('robot_id', '')
        error_type = data.get('error_type', '')
        error_message = data.get('error_message', '')
        battery_voltage = data.get('battery_voltage', 0.0)
        pose = data.get('pose', {})

        logger.warning(f"Received error alert: {robot_id} - {error_type}")

        if self.on_error_alert:
            self.on_error_alert(robot_id, error_type, error_message, battery_voltage, pose)


class MockErrorClient:
    """server 없이 테스트용 Mock error client"""

    def __init__(self, host: str = 'localhost', port: int = 9999):
        """Mock error client 초기화"""
        self.host = host
        self.port = port
        self.connected = False

        self.on_error_alert: Optional[Callable] = None
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None

        logger.info("MockErrorClient initialized (testing mode)")

    def connect(self) -> bool:
        """연결 (mock)"""
        self.connected = True
        if self.on_connected:
            self.on_connected()
        logger.info("MockErrorClient connected")
        return True

    def disconnect(self):
        """연결 해제 (mock)"""
        self.connected = False
        if self.on_disconnected:
            self.on_disconnected()
        logger.info("MockErrorClient disconnected")

    def send_operator_command(self, robot_id: str, command: str, order_id: str = None,
                             reason: str = None) -> bool:
        """운영자 명령 전송 (mock)"""
        logger.info(f"[MOCK] Operator command: {robot_id} - {command}")
        return True

    def simulate_error(self, robot_id: str, error_type: str, message: str,
                      battery: float = 0.0, pose: Dict = None):
        """
        테스트용 에러 alert 시뮬레이션

        Args:
            robot_id: Robot ID
            error_type: 에러 타입
            message: 에러 메시지
            battery: Battery 전압
            pose: Robot pose
        """
        logger.info(f"[MOCK] Simulating error: {robot_id} - {error_type}")

        if self.on_error_alert:
            self.on_error_alert(robot_id, error_type, message, battery, pose or {})
