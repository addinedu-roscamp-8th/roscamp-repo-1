"""
GUI TCP Server - Infrastructure Layer
TCP server for receiving orders from GUI and sending notifications
Port: 9000
"""

import socket
import threading
import json
import logging
from typing import Dict, Any, Callable, Optional, List

logger = logging.getLogger(__name__)


class GUITCPServer:
    """
    TCP Server for GUI Communication

    Handles:
    - Order reception from Customer GUI (port 9000)
    - Delivery notifications to Customer GUI
    - Delivery confirmation from Customer GUI
    """

    def __init__(self, host: str = '0.0.0.0', port: int = 9000):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.clients: Dict[str, socket.socket] = {}  # {client_id: socket}
        self.client_lock = threading.Lock()

        # Message handlers (registered by application layer)
        self.message_handlers: Dict[str, Callable] = {}

        logger.info(f"GUITCPServer initialized on {host}:{port}")

    def register_handler(self, message_type: str, handler: Callable):
        """
        Register message handler for specific message type

        Args:
            message_type: Message type (e.g., 'new_order', 'delivery_complete')
            handler: Callback function
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

            logger.info(f"GUI TCP Server started on {self.host}:{self.port}")

            # Start accept thread
            accept_thread = threading.Thread(target=self._accept_clients, daemon=True)
            accept_thread.start()

            return True
        except Exception as e:
            logger.error(f"Failed to start GUI TCP server: {e}")
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

        logger.info("GUI TCP Server stopped")

    def _accept_clients(self):
        """Accept incoming client connections"""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                client_socket, client_address = self.server_socket.accept()
                logger.info(f"New GUI client connected from {client_address}")

                # Start client handler thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting client: {e}")

    def _recv_exact(self, client_socket: socket.socket, num_bytes: int) -> bytes:
        """Receive exactly num_bytes from socket"""
        data = b''
        while len(data) < num_bytes:
            chunk = client_socket.recv(num_bytes - len(data))
            if not chunk:
                return b''
            data += chunk
        return data

    def _send_with_header(self, client_socket: socket.socket, message: dict):
        """Send message with 4-byte length header"""
        json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
        length_header = len(json_data).to_bytes(4, byteorder='big')
        client_socket.sendall(length_header + json_data)

    def _handle_client(self, client_socket: socket.socket, client_address):
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
                    logger.info(f"Received from GUI {client_id}: {message}")

                    # Handle message
                    response = self._process_message(message)

                    # Send response with length header
                    if response:
                        self._send_with_header(client_socket, response)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from {client_id}: {e}")
                    error_response = {
                        'status': 'error',
                        'message': 'Invalid JSON format'
                    }
                    self._send_with_header(client_socket, error_response)

                except Exception as e:
                    logger.error(f"Error processing message from {client_id}: {e}")
                    error_response = {
                        'status': 'error',
                        'message': str(e)
                    }
                    self._send_with_header(client_socket, error_response)

        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Remove from clients dict
            with self.client_lock:
                if client_id in self.clients:
                    del self.clients[client_id]
            client_socket.close()
            logger.info(f"GUI client {client_id} disconnected")

    def _process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming message from GUI

        Message format (supports both styles):
        Style 1 (command-based):
        {
            "command": "new_order" | "delivery_complete",
            "table_number": 1,
            "order": {...} | "order_id": "ORD-XXX"
        }

        Style 2 (type-based):
        {
            "type": "delivery_complete",
            "data": {"order_id": "ORD-XXX", "table_number": "1"}
        }

        Response format:
        {
            "status": "success" | "error",
            "data": {...} or "message": "error message"
        }
        """
        # Support both 'command' and 'type' fields
        command = message.get('command') or message.get('type')

        if not command:
            return {
                'status': 'error',
                'message': 'Missing command or type field'
            }

        # Route to handler
        handler = self.message_handlers.get(command)
        if handler:
            try:
                result = handler(message)
                return {
                    'status': 'success',
                    'data': result
                }
            except Exception as e:
                logger.error(f"Handler error for {command}: {e}")
                return {
                    'status': 'error',
                    'message': str(e)
                }
        else:
            logger.warning(f"No handler registered for command: {command}")
            return {
                'status': 'error',
                'message': f'Unknown command: {command}'
            }

    def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast message to all connected GUI clients

        Args:
            message: Message dict to broadcast
        """
        json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
        length_header = len(json_data).to_bytes(4, byteorder='big')
        message_data = length_header + json_data

        with self.client_lock:
            disconnected = []
            for client_id, client_socket in self.clients.items():
                try:
                    client_socket.sendall(message_data)
                    logger.debug(f"Sent notification to GUI client {client_id}")
                except Exception as e:
                    logger.error(f"Failed to send to {client_id}: {e}")
                    disconnected.append(client_id)

            # Remove disconnected clients
            for client_id in disconnected:
                del self.clients[client_id]

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

    def get_connected_clients(self) -> List[str]:
        """Get list of connected client IDs"""
        with self.client_lock:
            return list(self.clients.keys())


# Message format documentation
"""
Supported Message Types:

1. new_order (from GUI to FMS)
   Request:
   {
       "command": "new_order",
       "table_number": 1,
       "order": {
           "items": [
               {"menu_id": "M001", "quantity": 1}
           ]
       }
   }
   Response:
   {
       "status": "success",
       "data": {
           "order_id": "ORD-20260225123456-0001",
           "message": "Order accepted"
       }
   }

2. delivery_complete (from GUI to FMS)
   Request:
   {
       "command": "delivery_complete",
       "order_id": "ORD-20260225123456-0001",
       "table_number": 1
   }
   Response:
   {
       "status": "success",
       "data": {
           "message": "Delivery confirmed"
       }
   }

3. delivery_notification (from FMS to GUI) - Push notification
   Broadcast:
   {
       "type": "delivery_notification",
       "data": {
           "order_id": "ORD-20260225123456-0001",
           "table_number": 1,
           "robot_id": "pinky1",
           "status": "arrived"
       }
   }
"""
