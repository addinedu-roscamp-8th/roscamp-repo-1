"""
TCP Server for Kitchmatic Main Server
Handles communication with Kiosks and Admin GUI
"""

import socket
import threading
import json
import logging
from typing import Callable, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# 요청 처리 중인 클라이언트 (broadcast 시 해당 클라이언트 제외 → Voice가 다음 응답을 올바르게 수신)
_current_client_id = threading.local()


class TCPServer:
    """
    TCP Server for handling connections from Kiosks and Admin GUI
    Protocol: JSON-based message exchange
    """

    def __init__(self, host='0.0.0.0', port=9999):
        """
        Initialize TCP Server

        TODO: Configure these values in environment variables or config file:
        - host: Server IP address (default: 0.0.0.0 for all interfaces)
        - port: Server port (default: 9999)
        """
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = {}  # {client_id: socket}
        self.client_lock = threading.Lock()
        self.message_handlers = {}

    def register_handler(self, message_type: str, handler: Callable):
        """
        Register a message handler for specific message type

        Args:
            message_type: Type of message (e.g., 'order_request', 'order_status_query')
            handler: Callback function to handle the message
        """
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type}")

    def start(self):
        """Start TCP server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True

            logger.info(f"TCP Server started on {self.host}:{self.port}")

            # Start accept thread
            accept_thread = threading.Thread(target=self._accept_clients, daemon=True)
            accept_thread.start()

            return True
        except Exception as e:
            logger.error(f"Failed to start TCP server: {e}")
            return False

    def stop(self):
        """Stop TCP server"""
        self.running = False

        # Close all client connections
        with self.client_lock:
            for client_id, client_socket in self.clients.items():
                try:
                    client_socket.close()
                except:
                    pass
            self.clients.clear()

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        logger.info("TCP Server stopped")

    def _accept_clients(self):
        """Accept incoming client connections"""
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                logger.info(f"New client connected from {client_address}")

                # Start client handler thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting client: {e}")

    def _recv_exact(self, client_socket, num_bytes: int) -> bytes:
        """Receive exactly num_bytes from socket"""
        data = b''
        while len(data) < num_bytes:
            chunk = client_socket.recv(num_bytes - len(data))
            if not chunk:
                return b''
            data += chunk
        return data

    def _send_with_header(self, client_socket, message: dict):
        """Send message with 4-byte length header"""
        json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
        length_header = len(json_data).to_bytes(4, byteorder='big')
        client_socket.sendall(length_header + json_data)

    def _handle_client(self, client_socket, client_address):
        """Handle individual client connection"""
        client_id = f"{client_address[0]}:{client_address[1]}"

        # Add to clients dict
        with self.client_lock:
            self.clients[client_id] = client_socket

        try:
            while self.running:
                # Receive 4-byte length header first
                length_header = self._recv_exact(client_socket, 4)
                if not length_header:
                    break

                message_length = int.from_bytes(length_header, byteorder='big')

                # Receive message of specified length
                data = self._recv_exact(client_socket, message_length)
                if not data:
                    break

                try:
                    # Parse JSON message
                    message = json.loads(data.decode('utf-8'))
                    logger.debug(f"Received from {client_id}: {message}")

                    # 요청 처리 중인 클라이언트 기록 (broadcast 시 이 클라이언트 제외 → Voice 클라이언트가 다음 응답을 올바르게 수신)
                    _current_client_id.value = client_id
                    try:
                        response = self._process_message(message)
                        if response:
                            self._send_with_header(client_socket, response)
                    finally:
                        _current_client_id.value = None

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from {client_id}: {e}")
                    error_response = {
                        'status': 'error',
                        'message': 'Invalid JSON format'
                    }
                    self._send_with_header(client_socket, error_response)

                except Exception as e:
                    logger.error(f"Error processing message from {client_id}: {e}")

        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Remove from clients dict
            with self.client_lock:
                if client_id in self.clients:
                    del self.clients[client_id]
            client_socket.close()
            logger.info(f"Client {client_id} disconnected")

    def _process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming message and route to appropriate handler

        Message format:
        {
            "type": "message_type",  # or "command" for legacy clients
            "data": {...}
        }

        Response format:
        {
            "status": "success" or "error",
            "data": {...} or "message": "error message"
        }
        """
        # Support both 'type' and 'command' fields for compatibility
        message_type = message.get('type') or message.get('command')
        message_data = message.get('data', {})

        # For legacy 'command' style, the data might be in other fields
        if not message_data and message.get('command'):
            # Extract data from other fields (e.g., order, table_number)
            message_data = {k: v for k, v in message.items() if k != 'command'}

        if not message_type:
            return {
                'status': 'error',
                'message': 'Missing message type'
            }

        # Route to handler
        handler = self.message_handlers.get(message_type)
        if handler:
            try:
                result = handler(message_data)
                return {
                    'status': 'success',
                    'data': result
                }
            except Exception as e:
                logger.error(f"Handler error for {message_type}: {e}")
                return {
                    'status': 'error',
                    'message': str(e)
                }
        else:
            logger.warning(f"No handler registered for message type: {message_type}")
            return {
                'status': 'error',
                'message': f'Unknown message type: {message_type}'
            }

    def broadcast(self, message: Dict[str, Any], exclude_client_id: str | None = None):
        """
        Broadcast message to all connected clients.
        exclude_client_id: 이 클라이언트에는 전송하지 않음 (요청한 클라이언트가 broadcast를 응답으로 읽지 않도록).

        Args:
            message: Message dict to broadcast
            exclude_client_id: 제외할 client_id (None이면 thread-local에서 요청 처리 중인 클라이언트 자동 제외)
        """
        if exclude_client_id is None:
            exclude_client_id = getattr(_current_client_id, "value", None)

        json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
        length_header = len(json_data).to_bytes(4, byteorder='big')
        message_data = length_header + json_data

        with self.client_lock:
            disconnected = []
            for cid, client_socket in self.clients.items():
                if cid == exclude_client_id:
                    continue
                try:
                    client_socket.sendall(message_data)
                except Exception as e:
                    logger.error(f"Failed to send to {cid}: {e}")
                    disconnected.append(cid)

            for cid in disconnected:
                del self.clients[cid]

    def send_to_client(self, client_id: str, message: Dict[str, Any]):
        """
        Send message to specific client

        Args:
            client_id: Client ID (ip:port)
            message: Message dict to send
        """
        with self.client_lock:
            client_socket = self.clients.get(client_id)
            if client_socket:
                try:
                    json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
                    length_header = len(json_data).to_bytes(4, byteorder='big')
                    client_socket.sendall(length_header + json_data)
                    return True
                except Exception as e:
                    logger.error(f"Failed to send to {client_id}: {e}")
                    return False
            else:
                logger.warning(f"Client {client_id} not found")
                return False


# ========================================
# Message Type Definitions
# ========================================

"""
Supported Message Types:

1. order_request (from Kiosk)
   Request:
   {
       "type": "order_request",
       "data": {
           "table_number": "T01",
           "menu_id": "M001",
           "quantity": 1,
           "sauce_type": "mayo",
           "voice_order": false
       }
   }
   Response:
   {
       "status": "success",
       "data": {
           "order_id": "uuid-string",
           "estimated_time": 120
       }
   }

2. order_status_query (from Kiosk or Admin GUI)
   Request:
   {
       "type": "order_status_query",
       "data": {
           "order_id": "uuid-string"
       }
   }
   Response:
   {
       "status": "success",
       "data": {
           "order_id": "uuid-string",
           "status": "COOKING",
           "table_number": "T01",
           "created_at": "timestamp",
           "updated_at": "timestamp"
       }
   }

3. fleet_status_query (from Admin GUI)
   Request:
   {
       "type": "fleet_status_query",
       "data": {}
   }
   Response:
   {
       "status": "success",
       "data": {
           "robots": [
               {
                   "robot_id": "pinky1",
                   "status": "IDLE",
                   "battery_voltage": 24.5,
                   "current_task": null
               },
               ...
           ],
           "pending_orders": 2,
           "active_orders": 1
       }
   }

4. delivery_complete (from Kiosk)
   Request:
   {
       "type": "delivery_complete",
       "data": {
           "order_id": "uuid-string",
           "table_number": "T01"
       }
   }
   Response:
   {
       "status": "success",
       "data": {
           "message": "Order completed"
       }
   }

5. order_status_update (broadcast from Main Server to all clients)
   Broadcast:
   {
       "type": "order_status_update",
       "data": {
           "order_id": "uuid-string",
           "status": "DELIVERING",
           "table_number": "T01",
           "timestamp": "timestamp"
       }
   }

6. robot_status_update (broadcast from Main Server to Admin GUI)
   Broadcast:
   {
       "type": "robot_status_update",
       "data": {
           "robot_id": "pinky1",
           "status": "BUSY",
           "battery_voltage": 24.3,
           "timestamp": "timestamp"
       }
   }
"""
