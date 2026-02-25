#!/usr/bin/env python3
"""
TCP Test Client for Kitchmatics Main Server

This script tests TCP communication with the Main Server.
It can send order requests and query status.
"""

import socket
import json
import sys
import argparse
from typing import Dict, Any


class TCPTestClient:
    """TCP Test Client for Main Server"""

    def __init__(self, host: str = 'localhost', port: int = 9999):
        """
        Initialize TCP test client

        Args:
            host: Main Server host
            port: Main Server TCP port
        """
        self.host = host
        self.port = port
        self.socket = None

    def connect(self) -> bool:
        """
        Connect to Main Server

        Returns:
            True if connection succeeded
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"Connected to Main Server at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send message to Main Server and receive response

        Args:
            message: Message dict to send

        Returns:
            Response dict from server
        """
        try:
            # Send message
            message_json = json.dumps(message)
            self.socket.sendall(message_json.encode('utf-8'))
            self.socket.sendall(b'\n')  # Message delimiter

            # Receive response
            response_data = b''
            while True:
                chunk = self.socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                if b'\n' in chunk:
                    break

            # Parse response
            response_json = response_data.decode('utf-8').strip()
            response = json.loads(response_json)
            return response

        except Exception as e:
            print(f"Error sending message: {e}")
            return {'error': str(e)}

    def close(self):
        """Close connection"""
        if self.socket:
            self.socket.close()
            print("Connection closed")

    def send_order_request(self, table_number: str, menu_id: str = 'M001',
                          quantity: int = 1, sauce_type: str = 'mayo',
                          voice_order: bool = False) -> Dict[str, Any]:
        """
        Send order request to Main Server

        Args:
            table_number: Table number (T01-T08)
            menu_id: Menu ID (M001, M002)
            quantity: Order quantity
            sauce_type: Sauce type (mayo, mustard, ketchup)
            voice_order: Whether order was placed via voice

        Returns:
            Server response
        """
        message = {
            'type': 'order_request',
            'data': {
                'table_number': table_number,
                'menu_id': menu_id,
                'quantity': quantity,
                'sauce_type': sauce_type,
                'voice_order': voice_order
            }
        }

        print(f"\nSending order request:")
        print(json.dumps(message, indent=2))

        response = self.send_message(message)

        print(f"\nReceived response:")
        print(json.dumps(response, indent=2))

        return response

    def query_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Query order status

        Args:
            order_id: Order UUID

        Returns:
            Server response
        """
        message = {
            'type': 'order_status_query',
            'data': {
                'order_id': order_id
            }
        }

        print(f"\nQuerying order status:")
        print(json.dumps(message, indent=2))

        response = self.send_message(message)

        print(f"\nReceived response:")
        print(json.dumps(response, indent=2))

        return response

    def query_fleet_status(self) -> Dict[str, Any]:
        """
        Query fleet status

        Returns:
            Server response
        """
        message = {
            'type': 'fleet_status_query',
            'data': {}
        }

        print(f"\nQuerying fleet status:")
        print(json.dumps(message, indent=2))

        response = self.send_message(message)

        print(f"\nReceived response:")
        print(json.dumps(response, indent=2))

        return response

    def send_delivery_complete(self, order_id: str, table_number: str) -> Dict[str, Any]:
        """
        Send delivery complete signal

        Args:
            order_id: Order UUID
            table_number: Table number

        Returns:
            Server response
        """
        message = {
            'type': 'delivery_complete',
            'data': {
                'order_id': order_id,
                'table_number': table_number
            }
        }

        print(f"\nSending delivery complete:")
        print(json.dumps(message, indent=2))

        response = self.send_message(message)

        print(f"\nReceived response:")
        print(json.dumps(response, indent=2))

        return response


def main():
    """Main function for TCP test client"""
    parser = argparse.ArgumentParser(description='TCP Test Client for Kitchmatics Main Server')
    parser.add_argument('--host', default='localhost', help='Main Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=9999, help='Main Server port (default: 9999)')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Order request command
    order_parser = subparsers.add_parser('order', help='Send order request')
    order_parser.add_argument('--table', required=True, help='Table number (T01-T08)')
    order_parser.add_argument('--menu', default='M001', help='Menu ID (default: M001)')
    order_parser.add_argument('--quantity', type=int, default=1, help='Quantity (default: 1)')
    order_parser.add_argument('--sauce', default='mayo', help='Sauce type (default: mayo)')
    order_parser.add_argument('--voice', action='store_true', help='Voice order flag')

    # Order status query command
    status_parser = subparsers.add_parser('status', help='Query order status')
    status_parser.add_argument('--order-id', required=True, help='Order UUID')

    # Fleet status query command
    subparsers.add_parser('fleet', help='Query fleet status')

    # Delivery complete command
    complete_parser = subparsers.add_parser('complete', help='Send delivery complete')
    complete_parser.add_argument('--order-id', required=True, help='Order UUID')
    complete_parser.add_argument('--table', required=True, help='Table number')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Create client and connect
    client = TCPTestClient(host=args.host, port=args.port)
    if not client.connect():
        sys.exit(1)

    try:
        # Execute command
        if args.command == 'order':
            client.send_order_request(
                table_number=args.table,
                menu_id=args.menu,
                quantity=args.quantity,
                sauce_type=args.sauce,
                voice_order=args.voice
            )

        elif args.command == 'status':
            client.query_order_status(order_id=args.order_id)

        elif args.command == 'fleet':
            client.query_fleet_status()

        elif args.command == 'complete':
            client.send_delivery_complete(
                order_id=args.order_id,
                table_number=args.table
            )

    finally:
        client.close()


if __name__ == '__main__':
    main()
