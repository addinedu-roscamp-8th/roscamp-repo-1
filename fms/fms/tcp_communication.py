#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kitchmatics FMS - TCP Communication Module
Based on: /home/gw/Downloads/통신/TCP_Server.py, TCP_Client.py

Fleet Management System을 위한 폐쇄형 네트워크 TCP Server/Client
WiFi: kitchmatics
"""

import socket
import threading
import json
import time
import logging
from typing import Dict, Callable, Optional, Any, List
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue
import yaml
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s: %(message)s'
)
logger = logging.getLogger("FMS_TCP")


class MessageType(Enum):
    """FMS 통신을 위한 TCP Message 타입"""
    # Connection Management
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    HEARTBEAT = "heartbeat"
    ACK = "ack"

    # Robot Status
    ROBOT_STATUS = "robot_status"
    FLEET_STATUS = "fleet_status"
    BATTERY_STATUS = "battery_status"
    POSE_UPDATE = "pose_update"

    # Task Commands
    TASK_ASSIGN = "task_assign"
    TASK_STATUS = "task_status"
    TASK_COMPLETE = "task_complete"
    TASK_CANCEL = "task_cancel"

    # Navigation Commands
    NAV_GOAL = "nav_goal"
    NAV_CANCEL = "nav_cancel"
    NAV_STATUS = "nav_status"

    # System Commands
    EMERGENCY_STOP = "emergency_stop"
    SYSTEM_RESET = "system_reset"
    PARAM_UPDATE = "param_update"

    # Error/Alert
    ERROR = "error"
    ALERT = "alert"


@dataclass
class TCPMessage:
    """TCP 메시지 구조"""
    msg_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    sender_id: str = ""
    sequence: int = 0

    def to_json(self) -> str:
        return json.dumps({
            "type": self.msg_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "sender_id": self.sender_id,
            "sequence": self.sequence
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'TCPMessage':
        data = json.loads(json_str)
        return cls(
            msg_type=data.get("type", ""),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time.time()),
            sender_id=data.get("sender_id", ""),
            sequence=data.get("sequence", 0)
        )


@dataclass
class RobotConnection:
    """Robot 연결 정보"""
    robot_id: str
    ip_address: str
    port: int
    client_socket: Optional["socket.socket"] = None
    connected: bool = False
    last_heartbeat: float = 0.0
    reconnect_attempts: int = 0


class FMSTCPServer:
    """
    FMS TCP Server - Master Control Station
    여러 robot의 연결을 처리
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 9000,
                 config_path: Optional[str] = None):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.clients: Dict[str, RobotConnection] = {}
        self.handlers: Dict[str, Callable] = {}
        self.running = False
        self.lock = threading.Lock()
        self.sequence = 0

        # Load config
        self.config = self._load_config(config_path)

        # Message queue for GUI updates
        self.message_queue: Queue = Queue()

        # Register default handlers
        self._register_default_handlers()

    def _load_config(self, config_path: Optional[str]) -> dict:
        """네트워크 설정 로드"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        return {}

    def _register_default_handlers(self):
        """기본 메시지 handler 등록"""
        self.register_handler(MessageType.CONNECT.value, self._handle_connect)
        self.register_handler(MessageType.DISCONNECT.value, self._handle_disconnect)
        self.register_handler(MessageType.HEARTBEAT.value, self._handle_heartbeat)
        self.register_handler(MessageType.ROBOT_STATUS.value, self._handle_robot_status)
        self.register_handler(MessageType.POSE_UPDATE.value, self._handle_pose_update)
        self.register_handler(MessageType.NAV_STATUS.value, self._handle_nav_status)
        self.register_handler(MessageType.ERROR.value, self._handle_error)

    def register_handler(self, msg_type: str, handler: Callable):
        """메시지 handler 등록"""
        self.handlers[msg_type] = handler
        logger.info(f"Registered handler for: {msg_type}")

    def start(self):
        """TCP server 시작"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True

            logger.info(f"FMS TCP Server started on {self.host}:{self.port}")

            # Start accept thread
            accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            accept_thread.start()

            # Start heartbeat monitor thread
            heartbeat_thread = threading.Thread(target=self._monitor_heartbeats, daemon=True)
            heartbeat_thread.start()

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise

    def stop(self):
        """TCP server 중지"""
        self.running = False

        # Close all client connections
        with self.lock:
            for robot_id, conn in self.clients.items():
                if conn.client_socket:
                    try:
                        conn.client_socket.close()
                    except:
                        pass
            self.clients.clear()

        # Close server socket
        if self.server_socket:
            self.server_socket.close()

        logger.info("FMS TCP Server stopped")

    def _accept_connections(self):
        """들어오는 연결 수락"""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, addr = self.server_socket.accept()
                logger.info(f"New connection from {addr}")

                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, addr),
                    daemon=True
                )
                client_thread.start()

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Accept error: {e}")

    def _handle_client(self, client_socket: socket.socket, addr):
        """client 연결 처리"""
        robot_id = None
        file_wrapper = client_socket.makefile("rwb")

        try:
            while self.running:
                try:
                    line = file_wrapper.readline()
                    if not line:
                        break

                    message_str = line.decode(self.config.get('tcp', {}).get('encoding', 'utf-8')).strip()
                    if not message_str:
                        continue

                    message = TCPMessage.from_json(message_str)
                    robot_id = message.sender_id

                    # Update connection info
                    with self.lock:
                        if robot_id and robot_id in self.clients:
                            self.clients[robot_id].last_heartbeat = time.time()

                    # Handle message
                    handler = self.handlers.get(message.msg_type)
                    if handler:
                        response = handler(message, client_socket)
                        if response:
                            self._send_message(client_socket, response)
                    else:
                        logger.warning(f"No handler for message type: {message.msg_type}")

                    # Put message in queue for GUI
                    self.message_queue.put(message)

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                except socket.timeout:
                    continue

        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            # Clean up connection
            if robot_id:
                with self.lock:
                    if robot_id in self.clients:
                        self.clients[robot_id].connected = False
                        self.clients[robot_id].client_socket = None
            file_wrapper.close()
            client_socket.close()
            logger.info(f"Connection closed: {addr}")

    def _send_message(self, client_socket: socket.socket, message: TCPMessage):
        """client에 메시지 전송"""
        try:
            msg_bytes = (message.to_json() + "\n").encode('utf-8')
            client_socket.sendall(msg_bytes)
        except Exception as e:
            logger.error(f"Send error: {e}")

    def broadcast(self, message: TCPMessage):
        """연결된 모든 client에 메시지 broadcast"""
        with self.lock:
            for robot_id, conn in self.clients.items():
                if conn.connected and conn.client_socket:
                    try:
                        self._send_message(conn.client_socket, message)
                    except Exception as e:
                        logger.error(f"Broadcast to {robot_id} failed: {e}")

    def send_to_robot(self, robot_id: str, message: TCPMessage):
        """특정 robot에 메시지 전송"""
        with self.lock:
            if robot_id in self.clients:
                conn = self.clients[robot_id]
                if conn.connected and conn.client_socket:
                    self._send_message(conn.client_socket, message)
                    return True
        return False

    def _monitor_heartbeats(self):
        """heartbeat 모니터링 및 연결 끊김 감지"""
        heartbeat_timeout = self.config.get('network', {}).get('heartbeat_interval', 1.0) * 3

        while self.running:
            current_time = time.time()

            with self.lock:
                for robot_id, conn in list(self.clients.items()):
                    if conn.connected:
                        if current_time - conn.last_heartbeat > heartbeat_timeout:
                            logger.warning(f"Heartbeat timeout for {robot_id}")
                            conn.connected = False
                            # Notify GUI
                            self.message_queue.put(TCPMessage(
                                msg_type=MessageType.DISCONNECT.value,
                                data={"robot_id": robot_id, "reason": "heartbeat_timeout"},
                                sender_id="server"
                            ))

            time.sleep(1.0)

    # Default message handlers
    def _handle_connect(self, message: TCPMessage, client_socket: socket.socket) -> TCPMessage:
        """robot 연결 처리"""
        robot_id = message.data.get("robot_id", "")
        robot_type = message.data.get("robot_type", "")
        ip_address = message.data.get("ip_address", "")

        with self.lock:
            self.clients[robot_id] = RobotConnection(
                robot_id=robot_id,
                ip_address=ip_address,
                port=self.port,
                client_socket=client_socket,
                connected=True,
                last_heartbeat=time.time()
            )

        logger.info(f"Robot connected: {robot_id} ({robot_type}) from {ip_address}")

        return TCPMessage(
            msg_type=MessageType.ACK.value,
            data={"status": "connected", "robot_id": robot_id},
            sender_id="server"
        )

    def _handle_disconnect(self, message: TCPMessage, client_socket: socket.socket) -> Optional[TCPMessage]:
        """robot 연결 해제 처리"""
        robot_id = message.sender_id

        with self.lock:
            if robot_id in self.clients:
                self.clients[robot_id].connected = False

        logger.info(f"Robot disconnected: {robot_id}")
        return None

    def _handle_heartbeat(self, message: TCPMessage, client_socket: socket.socket) -> TCPMessage:
        """heartbeat 처리"""
        return TCPMessage(
            msg_type=MessageType.ACK.value,
            data={"status": "alive"},
            sender_id="server"
        )

    def _handle_robot_status(self, message: TCPMessage, client_socket: socket.socket) -> None:
        """robot 상태 업데이트 처리"""
        robot_id = message.sender_id
        logger.debug(f"Robot status from {robot_id}: {message.data}")
        return None

    def _handle_pose_update(self, message: TCPMessage, client_socket: socket.socket) -> None:
        """pose 업데이트 처리"""
        robot_id = message.sender_id
        logger.debug(f"Pose update from {robot_id}: {message.data}")
        return None

    def _handle_nav_status(self, message: TCPMessage, client_socket: socket.socket) -> None:
        """navigation 상태 처리"""
        robot_id = message.sender_id
        logger.debug(f"Nav status from {robot_id}: {message.data}")
        return None

    def _handle_error(self, message: TCPMessage, client_socket: socket.socket) -> None:
        """에러 메시지 처리"""
        robot_id = message.sender_id
        logger.error(f"Error from {robot_id}: {message.data}")
        return None

    def get_connected_robots(self) -> List[str]:
        """연결된 robot 목록 반환"""
        with self.lock:
            return [rid for rid, conn in self.clients.items() if conn.connected]

    def get_fleet_status(self) -> Dict[str, Any]:
        """fleet 상태 요약 반환"""
        with self.lock:
            return {
                "total_robots": len(self.clients),
                "connected": sum(1 for c in self.clients.values() if c.connected),
                "disconnected": sum(1 for c in self.clients.values() if not c.connected),
                "robots": {
                    rid: {
                        "connected": conn.connected,
                        "ip_address": conn.ip_address,
                        "last_heartbeat": conn.last_heartbeat
                    }
                    for rid, conn in self.clients.items()
                }
            }


class FMSTCPClient:
    """
    FMS TCP Client - Robot 측
    master control station에 연결
    """

    def __init__(self, robot_id: str, server_host: str, server_port: int = 9000,
                 robot_type: str = "PINKYPRO"):
        self.robot_id = robot_id
        self.robot_type = robot_type
        self.server_host = server_host
        self.server_port = server_port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.running = False
        self.handlers: Dict[str, Callable] = {}
        self.lock = threading.Lock()
        self.sequence = 0

        # Reconnection settings
        self.reconnect_interval = 3.0
        self.max_reconnect_attempts = 10

    def connect(self) -> bool:
        """FMS server에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.server_host, self.server_port))
            self.connected = True
            self.running = True

            # Send connection message
            connect_msg = TCPMessage(
                msg_type=MessageType.CONNECT.value,
                data={
                    "robot_id": self.robot_id,
                    "robot_type": self.robot_type,
                    "ip_address": self._get_local_ip()
                },
                sender_id=self.robot_id
            )
            self.send_message(connect_msg)

            # Start receive thread
            recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            recv_thread.start()

            # Start heartbeat thread
            heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            heartbeat_thread.start()

            logger.info(f"Connected to FMS server at {self.server_host}:{self.server_port}")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """FMS server 연결 해제"""
        self.running = False

        if self.connected:
            # Send disconnect message
            disconnect_msg = TCPMessage(
                msg_type=MessageType.DISCONNECT.value,
                data={"reason": "normal"},
                sender_id=self.robot_id
            )
            self.send_message(disconnect_msg)

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        self.connected = False
        logger.info("Disconnected from FMS server")

    def send_message(self, message: TCPMessage) -> bool:
        """server에 메시지 전송"""
        if not self.connected or not self.socket:
            return False

        try:
            message.sender_id = self.robot_id
            message.sequence = self._next_sequence()
            msg_bytes = (message.to_json() + "\n").encode('utf-8')
            self.socket.sendall(msg_bytes)
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self.connected = False
            return False

    def register_handler(self, msg_type: str, handler: Callable):
        """메시지 handler 등록"""
        self.handlers[msg_type] = handler

    def _receive_loop(self):
        """server로부터 메시지 수신"""
        file_wrapper = self.socket.makefile("rwb")

        try:
            while self.running and self.connected:
                try:
                    line = file_wrapper.readline()
                    if not line:
                        break

                    message_str = line.decode('utf-8').strip()
                    if not message_str:
                        continue

                    message = TCPMessage.from_json(message_str)

                    # Call handler
                    handler = self.handlers.get(message.msg_type)
                    if handler:
                        handler(message)

                except socket.timeout:
                    continue
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")

        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self.connected = False
            file_wrapper.close()

            # Attempt reconnection
            if self.running:
                self._reconnect()

    def _heartbeat_loop(self):
        """주기적으로 heartbeat 전송"""
        while self.running:
            if self.connected:
                heartbeat_msg = TCPMessage(
                    msg_type=MessageType.HEARTBEAT.value,
                    data={"timestamp": time.time()},
                    sender_id=self.robot_id
                )
                self.send_message(heartbeat_msg)
            time.sleep(1.0)

    def _reconnect(self):
        """server 재연결 시도"""
        attempt = 0
        while self.running and attempt < self.max_reconnect_attempts:
            attempt += 1
            logger.info(f"Reconnection attempt {attempt}/{self.max_reconnect_attempts}")

            time.sleep(self.reconnect_interval)

            if self.connect():
                return

        logger.error("Max reconnection attempts reached")

    def _next_sequence(self) -> int:
        """다음 sequence 번호 반환"""
        with self.lock:
            self.sequence += 1
            return self.sequence

    def _get_local_ip(self) -> str:
        """로컬 IP 주소 반환"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((self.server_host, self.server_port))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    # Convenience methods for sending specific messages
    def send_status(self, status: str, battery: float = 0.0,
                    pose: Optional[Dict] = None):
        """robot 상태 업데이트 전송"""
        msg = TCPMessage(
            msg_type=MessageType.ROBOT_STATUS.value,
            data={
                "status": status,
                "battery_voltage": battery,
                "pose": pose or {}
            },
            sender_id=self.robot_id
        )
        return self.send_message(msg)

    def send_pose(self, x: float, y: float, theta: float):
        """pose 업데이트 전송"""
        msg = TCPMessage(
            msg_type=MessageType.POSE_UPDATE.value,
            data={"x": x, "y": y, "theta": theta},
            sender_id=self.robot_id
        )
        return self.send_message(msg)

    def send_nav_status(self, status: str, goal: Optional[Dict] = None):
        """navigation 상태 전송"""
        msg = TCPMessage(
            msg_type=MessageType.NAV_STATUS.value,
            data={"status": status, "goal": goal or {}},
            sender_id=self.robot_id
        )
        return self.send_message(msg)

    def send_task_complete(self, task_id: str, success: bool, message: str = ""):
        """task 완료 전송"""
        msg = TCPMessage(
            msg_type=MessageType.TASK_COMPLETE.value,
            data={"task_id": task_id, "success": success, "message": message},
            sender_id=self.robot_id
        )
        return self.send_message(msg)

    def send_error(self, error_code: str, error_message: str):
        """에러 메시지 전송"""
        msg = TCPMessage(
            msg_type=MessageType.ERROR.value,
            data={"code": error_code, "message": error_message},
            sender_id=self.robot_id
        )
        return self.send_message(msg)


# Test code
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FMS TCP Communication Test")
    parser.add_argument("--mode", choices=["server", "client"], required=True)
    parser.add_argument("--host", default="192.168.1.3")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--robot-id", default="test_robot")
    args = parser.parse_args()

    if args.mode == "server":
        server = FMSTCPServer(host="0.0.0.0", port=args.port)
        server.start()

        try:
            while True:
                time.sleep(1)
                status = server.get_fleet_status()
                print(f"Connected robots: {status['connected']}")
        except KeyboardInterrupt:
            server.stop()

    else:
        client = FMSTCPClient(
            robot_id=args.robot_id,
            server_host=args.host,
            server_port=args.port
        )

        if client.connect():
            try:
                while True:
                    client.send_status("IDLE", battery=12.5)
                    time.sleep(2)
            except KeyboardInterrupt:
                client.disconnect()
        else:
            print("Failed to connect")
