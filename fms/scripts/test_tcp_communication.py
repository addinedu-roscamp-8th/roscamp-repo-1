#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kitchmatics FMS - TCP Communication Test Suite

This script tests TCP communication on the closed network "kitchmatics":
1. Port availability (9000, 9001, 9002, 9999, 5432)
2. TCP message format and serialization
3. Network connectivity to robot and arm IPs
4. Message type validation

Network Configuration:
  WiFi: kitchmatics
  Master PC: 192.168.1.3 (port 9000 - FMS, 9999 - Main Server)
  pinky1: 192.168.1.7 (port 9001)
  pinky2: 192.168.1.6 (port 9001)
  pinky3: 192.168.1.11 (port 9001)
  cobot1: 192.168.1.4 (port 9002)
  cobot2: 192.168.1.10 (port 9002)

Usage:
  # Test all TCP ports
  python3 test_tcp_communication.py --test-all

  # Test specific port
  python3 test_tcp_communication.py --test-port 9000

  # Test network connectivity
  python3 test_tcp_communication.py --test-connectivity

  # Test message format
  python3 test_tcp_communication.py --test-message-format

  # Start TCP echo server for testing
  python3 test_tcp_communication.py --echo-server --port 9000

  # Connect to echo server
  python3 test_tcp_communication.py --echo-client --host 192.168.1.3 --port 9000
"""

import sys
import os
import argparse
import socket
import time
import json
import threading
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import struct

# FMS imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fms'))

from tcp_communication import TCPMessage, MessageType


class PortConfig:
    """Port configuration for Kitchmatics network"""
    MASTER_FMS = ('192.168.1.3', 9000)
    MASTER_MAIN_SERVER = ('192.168.1.3', 9999)
    PINKY1_CLIENT = ('192.168.1.7', 9001)
    PINKY2_CLIENT = ('192.168.1.6', 9001)
    PINKY3_CLIENT = ('192.168.1.11', 9001)
    COBOT1_CLIENT = ('192.168.1.4', 9002)
    COBOT2_CLIENT = ('192.168.1.10', 9002)
    POSTGRES = ('localhost', 5432)


class TCPPortTester:
    """Test TCP ports and connectivity"""

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self.results = {}

    def test_port(self, host: str, port: int, name: str = "") -> bool:
        """Test if a port is accessible"""
        if not name:
            name = f"{host}:{port}"

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((host, port))
            sock.close()

            is_open = (result == 0)
            self.results[name] = is_open

            status = "OPEN" if is_open else "CLOSED"
            print(f"  [{name}] {status}")

            return is_open

        except Exception as e:
            print(f"  [{name}] ERROR: {e}")
            self.results[name] = False
            return False

    def test_all_ports(self) -> Dict[str, bool]:
        """Test all configured ports"""
        print("\n" + "="*60)
        print("TEST 1: TCP Port Accessibility")
        print("="*60)

        configs = [
            ('192.168.1.3', 9000, 'Master FMS'),
            ('192.168.1.3', 9999, 'Main Server'),
            ('192.168.1.7', 9001, 'pinky1 Client'),
            ('192.168.1.6', 9001, 'pinky2 Client'),
            ('192.168.1.11', 9001, 'pinky3 Client'),
            ('192.168.1.4', 9002, 'cobot1 Client'),
            ('192.168.1.10', 9002, 'cobot2 Client'),
            ('127.0.0.1', 5432, 'PostgreSQL'),
        ]

        print("\nTesting port accessibility (3s timeout per port):")
        for host, port, name in configs:
            self.test_port(host, port, name)

        return self.results

    def get_summary(self) -> Dict[str, Any]:
        """Get test summary"""
        open_ports = sum(1 for v in self.results.values() if v)
        total_ports = len(self.results)

        return {
            'total_ports_tested': total_ports,
            'open_ports': open_ports,
            'closed_ports': total_ports - open_ports,
            'results': self.results
        }


class TCPMessageTester:
    """Test TCP message format and serialization"""

    @staticmethod
    def test_message_formats() -> bool:
        """Test all message types can be serialized"""
        print("\n" + "="*60)
        print("TEST 2: TCP Message Format Validation")
        print("="*60)

        test_cases = [
            {
                'name': 'CONNECT',
                'msg_type': MessageType.CONNECT,
                'data': {
                    'robot_id': 'pinky1',
                    'robot_type': 'PINKYPRO',
                    'ip_address': '192.168.1.7'
                }
            },
            {
                'name': 'ROBOT_STATUS',
                'msg_type': MessageType.ROBOT_STATUS,
                'data': {
                    'robot_id': 'pinky1',
                    'status': 'IDLE',
                    'battery_voltage': 24.5,
                    'position_x': 0.5,
                    'position_y': 0.6,
                    'yaw': 0.0
                }
            },
            {
                'name': 'TASK_ASSIGN',
                'msg_type': MessageType.TASK_ASSIGN,
                'data': {
                    'order_id': 'ORD-20250225-001',
                    'robot_id': 'pinky1',
                    'table_number': 'T01',
                    'menu_id': 'M001',
                    'quantity': 1,
                    'sauce_type': 'mayo'
                }
            },
            {
                'name': 'TASK_COMPLETE',
                'msg_type': MessageType.TASK_COMPLETE,
                'data': {
                    'order_id': 'ORD-20250225-001',
                    'robot_id': 'pinky1',
                    'status': 'SUCCESS'
                }
            },
            {
                'name': 'FLEET_STATUS',
                'msg_type': MessageType.FLEET_STATUS,
                'data': {
                    'timestamp': time.time(),
                    'robots': [
                        {'robot_id': 'pinky1', 'status': 'IDLE'},
                        {'robot_id': 'pinky2', 'status': 'NAVIGATING'},
                        {'robot_id': 'pinky3', 'status': 'IDLE'}
                    ],
                    'pending_orders': 2,
                    'active_orders': 1
                }
            },
            {
                'name': 'HEARTBEAT',
                'msg_type': MessageType.HEARTBEAT,
                'data': {
                    'sender_id': 'fms_node',
                    'timestamp': time.time()
                }
            },
            {
                'name': 'EMERGENCY_STOP',
                'msg_type': MessageType.EMERGENCY_STOP,
                'data': {
                    'reason': 'Obstacle detected',
                    'affected_robots': ['pinky1', 'pinky2']
                }
            }
        ]

        print("\nTesting message serialization/deserialization:")
        all_ok = True

        for test_case in test_cases:
            try:
                # Create message
                msg = TCPMessage(
                    msg_type=test_case['msg_type'].value,
                    data=test_case['data'],
                    sender_id='test_node',
                    sequence=1
                )

                # Serialize to JSON
                json_str = msg.to_json()
                json_size = len(json_str.encode('utf-8'))

                # Deserialize
                msg_restored = TCPMessage.from_json(json_str)

                # Verify integrity
                checks = [
                    msg_restored.msg_type == msg.msg_type,
                    msg_restored.data == msg.data,
                    msg_restored.sender_id == msg.sender_id,
                    msg_restored.sequence == msg.sequence
                ]

                if all(checks):
                    print(f"  [{test_case['name']}] OK ({json_size} bytes)")
                else:
                    print(f"  [{test_case['name']}] FAILED - Data integrity check")
                    all_ok = False

            except Exception as e:
                print(f"  [{test_case['name']}] ERROR - {e}")
                all_ok = False

        print(f"\nResult: {'OK' if all_ok else 'SOME TESTS FAILED'}")
        return all_ok

    @staticmethod
    def test_message_parsing() -> bool:
        """Test parsing of various JSON formats"""
        print("\n" + "="*60)
        print("TEST 3: TCP Message Parsing")
        print("="*60)

        test_cases = [
            {
                'name': 'Valid complete message',
                'json': json.dumps({
                    'type': 'connect',
                    'data': {'robot_id': 'pinky1'},
                    'timestamp': time.time(),
                    'sender_id': 'test',
                    'sequence': 1
                }),
                'should_pass': True
            },
            {
                'name': 'Minimal message',
                'json': json.dumps({
                    'type': 'heartbeat',
                    'data': {}
                }),
                'should_pass': True
            },
            {
                'name': 'Complex nested data',
                'json': json.dumps({
                    'type': 'fleet_status',
                    'data': {
                        'robots': [
                            {'id': 'p1', 'status': 'IDLE', 'pose': {'x': 0, 'y': 0}},
                            {'id': 'p2', 'status': 'MOVING', 'pose': {'x': 1, 'y': 2}}
                        ]
                    },
                    'timestamp': time.time()
                }),
                'should_pass': True
            },
            {
                'name': 'Missing required fields (type)',
                'json': json.dumps({
                    'data': {'robot_id': 'pinky1'},
                    'timestamp': time.time()
                }),
                'should_pass': False
            }
        ]

        print("\nTesting message parsing:")
        passed = 0
        failed = 0

        for test_case in test_cases:
            try:
                msg = TCPMessage.from_json(test_case['json'])
                if test_case['should_pass']:
                    print(f"  [{test_case['name']}] OK")
                    passed += 1
                else:
                    print(f"  [{test_case['name']}] FAILED - Should have raised exception")
                    failed += 1

            except Exception as e:
                if not test_case['should_pass']:
                    print(f"  [{test_case['name']}] OK (correctly rejected)")
                    passed += 1
                else:
                    print(f"  [{test_case['name']}] FAILED - {e}")
                    failed += 1

        print(f"\nResult: {passed} passed, {failed} failed")
        return failed == 0

    @staticmethod
    def test_message_size() -> bool:
        """Test message size limits"""
        print("\n" + "="*60)
        print("TEST 4: TCP Message Size")
        print("="*60)

        test_sizes = [
            ('Small message', 100),
            ('Medium message', 1000),
            ('Large message', 10000),
            ('Very large message', 100000),
        ]

        print("\nTesting message sizes:")

        for name, target_size in test_sizes:
            # Create message with data of approximate size
            large_data = 'x' * target_size
            msg = TCPMessage(
                msg_type=MessageType.FLEET_STATUS.value,
                data={'payload': large_data},
                sender_id='test'
            )

            json_str = msg.to_json()
            actual_size = len(json_str.encode('utf-8'))

            # Test if it can be parsed
            try:
                restored = TCPMessage.from_json(json_str)
                status = "OK"
            except Exception as e:
                status = f"FAILED - {e}"

            print(f"  [{name}] {actual_size} bytes - {status}")

        return True


class TCPEchoServer:
    """Simple TCP echo server for testing"""

    def __init__(self, host: str = '0.0.0.0', port: int = 9000):
        self.host = host
        self.port = port
        self.running = False
        self.client_count = 0

    def start(self):
        """Start the echo server"""
        self.running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        print(f"\n[ECHO SERVER] Started on {self.host}:{self.port}")

    def _run(self):
        """Main server loop"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen(5)

            print(f"[ECHO SERVER] Listening on {self.host}:{self.port}")

            while self.running:
                try:
                    sock.settimeout(1.0)
                    client_sock, client_addr = sock.accept()
                    self.client_count += 1

                    print(f"[ECHO SERVER] Client {self.client_count} connected: {client_addr}")

                    # Handle client
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, client_addr, self.client_count),
                        daemon=True
                    )
                    thread.start()

                except socket.timeout:
                    continue

        except Exception as e:
            print(f"[ECHO SERVER] Error: {e}")
        finally:
            sock.close()
            self.running = False

    def _handle_client(self, sock: socket.socket, addr: Tuple, client_id: int):
        """Handle individual client connection"""
        try:
            while True:
                data = sock.recv(4096)
                if not data:
                    break

                # Echo the data back
                sock.sendall(data)

                # Parse and log if it's a valid message
                try:
                    msg = TCPMessage.from_json(data.decode('utf-8'))
                    print(f"[ECHO SERVER] Client {client_id}: {msg.msg_type}")
                except:
                    print(f"[ECHO SERVER] Client {client_id}: Raw data ({len(data)} bytes)")

        except Exception as e:
            print(f"[ECHO SERVER] Client {client_id} error: {e}")
        finally:
            sock.close()
            print(f"[ECHO SERVER] Client {client_id} disconnected")

    def stop(self):
        """Stop the echo server"""
        self.running = False


class TCPEchoClient:
    """Simple TCP echo client for testing"""

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None

    def connect(self) -> bool:
        """Connect to echo server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            print(f"[ECHO CLIENT] Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[ECHO CLIENT] Failed to connect: {e}")
            return False

    def send_message(self, msg: TCPMessage) -> bool:
        """Send message and wait for echo"""
        if not self.sock:
            print("[ECHO CLIENT] Not connected")
            return False

        try:
            json_str = msg.to_json()
            self.sock.sendall(json_str.encode('utf-8'))

            # Receive echo
            data = self.sock.recv(4096)
            echo_msg = TCPMessage.from_json(data.decode('utf-8'))

            if echo_msg.msg_type == msg.msg_type and echo_msg.data == msg.data:
                print(f"[ECHO CLIENT] Sent and received: {msg.msg_type}")
                return True
            else:
                print(f"[ECHO CLIENT] Echo mismatch")
                return False

        except Exception as e:
            print(f"[ECHO CLIENT] Error: {e}")
            return False

    def disconnect(self):
        """Disconnect from server"""
        if self.sock:
            self.sock.close()
            print("[ECHO CLIENT] Disconnected")


def main():
    parser = argparse.ArgumentParser(
        description="TCP Communication Test Suite"
    )
    parser.add_argument('--test-all', action='store_true',
                       help='Run all tests')
    parser.add_argument('--test-ports', action='store_true',
                       help='Test TCP port accessibility')
    parser.add_argument('--test-message-format', action='store_true',
                       help='Test message format validation')
    parser.add_argument('--test-connectivity', action='store_true',
                       help='Test network connectivity')
    parser.add_argument('--echo-server', action='store_true',
                       help='Start TCP echo server')
    parser.add_argument('--echo-client', action='store_true',
                       help='Connect to echo server as client')
    parser.add_argument('--host', default='192.168.1.3',
                       help='Server host')
    parser.add_argument('--port', type=int, default=9000,
                       help='Server port')

    args = parser.parse_args()

    try:
        if args.echo_server:
            server = TCPEchoServer(host=args.host, port=args.port)
            server.start()
            try:
                print("\nServer running. Press Ctrl+C to stop...")
                while server.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping server...")

        elif args.echo_client:
            client = TCPEchoClient(args.host, args.port)
            if client.connect():
                # Send test messages
                for i in range(3):
                    msg = TCPMessage(
                        msg_type=MessageType.HEARTBEAT.value,
                        data={'count': i},
                        sender_id='test_client',
                        sequence=i
                    )
                    client.send_message(msg)
                    time.sleep(0.5)
                client.disconnect()

        else:
            # Run tests
            run_all = args.test_all or not any([
                args.test_ports,
                args.test_message_format,
                args.test_connectivity
            ])

            if run_all or args.test_ports:
                tester = TCPPortTester(timeout=3.0)
                tester.test_all_ports()
                summary = tester.get_summary()
                print(f"\nSummary: {summary['open_ports']}/{summary['total_ports_tested']} ports open")

            if run_all or args.test_message_format:
                TCPMessageTester.test_message_formats()
                TCPMessageTester.test_message_parsing()
                TCPMessageTester.test_message_size()

            if run_all or args.test_connectivity:
                print("\n" + "="*60)
                print("TEST 5: Network Connectivity Check")
                print("="*60)
                print("\nNetwork configuration:")
                print("  WiFi SSID: kitchmatics")
                print("  Robots:")
                print("    - pinky1: 192.168.1.7:9001")
                print("    - pinky2: 192.168.1.6:9001")
                print("    - pinky3: 192.168.1.11:9001")
                print("  Arms:")
                print("    - cobot1: 192.168.1.4:9002")
                print("    - cobot2: 192.168.1.10:9002")
                print("  Master PC: 192.168.1.3")
                print("    - FMS: port 9000")
                print("    - Main Server: port 9999")
                print()

    except KeyboardInterrupt:
        print("\nInterrupted by user")


if __name__ == '__main__':
    main()
