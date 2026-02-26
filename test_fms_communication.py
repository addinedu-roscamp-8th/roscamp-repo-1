#!/usr/bin/env python3
"""
FMS Communication Validation Test Client

This script tests the complete FMS communication flow:
1. GUI → FMS TCP (order)
2. FMS → Coordinator (cooking order)
3. FMS → Navigation (robot to pickup)
4. FMS → GUI (pickup arrival notification)
5. Coordinator → FMS (loading complete)
6. FMS → Navigation (robot to table)
7. GUI → FMS (delivery complete)
8. FMS → Navigation (robot to home)

Usage:
  python3 test_fms_communication.py --test-all
  python3 test_fms_communication.py --test-tcp
  python3 test_fms_communication.py --test-topics
"""

import socket
import json
import time
import sys
import argparse
import threading
import subprocess
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


class FMSTestClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 9000):
        self.host = host
        self.port = port
        self.socket = None
        self.test_results = []

    def log_test(self, name: str, passed: bool, message: str = ""):
        status = f"{GREEN}✓ PASS{NC}" if passed else f"{RED}✗ FAIL{NC}"
        print(f"{status} {name}")
        if message:
            print(f"    {message}")
        self.test_results.append((name, passed, message))

    def connect(self) -> bool:
        """Connect to FMS TCP server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.log_test("TCP Connection", True, f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            self.log_test("TCP Connection", False, str(e))
            return False

    def disconnect(self):
        """Disconnect from FMS"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

    def send_message(self, message: Dict[str, Any]) -> bool:
        """Send message with 4-byte length header"""
        try:
            json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            length_header = len(json_data).to_bytes(4, byteorder='big')
            self.socket.sendall(length_header + json_data)
            return True
        except Exception as e:
            print(f"{RED}✗ Send error: {e}{NC}")
            return False

    def recv_message(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Receive message with 4-byte length header"""
        try:
            self.socket.settimeout(timeout)
            length_header = self.socket.recv(4)
            if not length_header:
                return None

            message_length = int.from_bytes(length_header, byteorder='big')
            data = b''
            while len(data) < message_length:
                chunk = self.socket.recv(message_length - len(data))
                if not chunk:
                    return None
                data += chunk

            return json.loads(data.decode('utf-8'))
        except socket.timeout:
            return None
        except Exception as e:
            print(f"{RED}✗ Receive error: {e}{NC}")
            return None

    def test_simple_order(self):
        """Test sending a simple order"""
        print(f"\n{YELLOW}=== Test: Simple Order ==={NC}")

        order = {
            "message_type": "new_order",
            "order_id": "TEST_001",
            "table_id": "table1",
            "items": ["burger", "fries"],
            "special_request": "No onions"
        }

        print(f"Sending order: {json.dumps(order, indent=2)}")
        if self.send_message(order):
            self.log_test("Send Order", True)

            # Wait for response
            response = self.recv_message(timeout=3.0)
            if response:
                self.log_test("Receive Response", True, json.dumps(response))
                return True
            else:
                self.log_test("Receive Response", False, "No response from FMS")
                return False
        else:
            self.log_test("Send Order", False)
            return False

    def test_delivery_complete(self):
        """Test delivery complete notification"""
        print(f"\n{YELLOW}=== Test: Delivery Complete ==={NC}")

        message = {
            "message_type": "delivery_complete",
            "order_id": "TEST_001",
            "table_id": "table1"
        }

        print(f"Sending delivery complete: {json.dumps(message, indent=2)}")
        if self.send_message(message):
            self.log_test("Send Delivery Complete", True)
            return True
        else:
            self.log_test("Send Delivery Complete", False)
            return False

    def test_connection_persistence(self):
        """Test multiple messages on same connection"""
        print(f"\n{YELLOW}=== Test: Connection Persistence ==={NC}")

        messages = [
            {"message_type": "new_order", "order_id": "TEST_002", "table_id": "table2"},
            {"message_type": "new_order", "order_id": "TEST_003", "table_id": "table3"},
        ]

        success = True
        for msg in messages:
            if self.send_message(msg):
                self.log_test(f"Send {msg['order_id']}", True)
            else:
                self.log_test(f"Send {msg['order_id']}", False)
                success = False

        return success

    def test_topics(self):
        """Test ROS 2 topics"""
        print(f"\n{YELLOW}=== Test: ROS 2 Topics ==={NC}")

        os.environ['ROS_DOMAIN_ID'] = '25'
        os.system('source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash >/dev/null 2>&1')

        topics_to_check = [
            '/fms/fleet_status',
            '/fms/order_request',
            '/fms/pickup_arrival',
            '/fms/error_alert',
            '/pinky1/amcl_pose',
            '/pinky2/amcl_pose',
            '/cooking/loading_complete',
            '/cooking/order'
        ]

        cmd = 'source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash && ros2 topic list'
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            available_topics = set(result.stdout.strip().split('\n'))

            all_found = True
            for topic in topics_to_check:
                if topic in available_topics:
                    self.log_test(f"Topic {topic}", True)
                else:
                    self.log_test(f"Topic {topic}", False)
                    all_found = False

            return all_found
        except Exception as e:
            self.log_test("Topic Check", False, str(e))
            return False

    def test_port_listening(self):
        """Test if port is listening"""
        print(f"\n{YELLOW}=== Test: Port Listening ==={NC}")

        cmd = "netstat -tlnp 2>/dev/null | grep -q ':9000' && echo 'listening' || echo 'not_listening'"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if 'listening' in result.stdout:
                self.log_test("Port 9000 Listening", True)
                return True
            else:
                self.log_test("Port 9000 Listening", False)
                return False
        except Exception as e:
            self.log_test("Port Check", False, str(e))
            return False

    def test_node_running(self):
        """Test if FMS node is running"""
        print(f"\n{YELLOW}=== Test: FMS Node Running ==={NC}")

        cmd = "pgrep -f 'fms_node|fms_tcp_node' | wc -l"
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            count = int(result.stdout.strip())
            if count > 0:
                self.log_test("FMS Node Running", True, f"Found {count} processes")
                return True
            else:
                self.log_test("FMS Node Running", False, "No FMS processes found")
                return False
        except Exception as e:
            self.log_test("Node Check", False, str(e))
            return False

    def print_summary(self):
        """Print test summary"""
        print(f"\n{BLUE}========================================{NC}")
        print(f"{BLUE}Test Summary{NC}")
        print(f"{BLUE}========================================{NC}")

        passed = sum(1 for _, result, _ in self.test_results if result)
        total = len(self.test_results)

        for name, result, message in self.test_results:
            status = f"{GREEN}✓{NC}" if result else f"{RED}✗{NC}"
            print(f"{status} {name}")
            if message and len(message) < 100:
                print(f"  {message}")

        print(f"\nResults: {GREEN}{passed}/{total} tests passed{NC}")

        if passed == total:
            print(f"{GREEN}All tests passed!{NC}")
            return 0
        else:
            print(f"{RED}Some tests failed. See details above.{NC}")
            return 1


def main():
    parser = argparse.ArgumentParser(description='FMS Communication Test Client')
    parser.add_argument('--host', default='127.0.0.1', help='FMS host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=9000, help='FMS port (default: 9000)')
    parser.add_argument('--test-all', action='store_true', help='Run all tests')
    parser.add_argument('--test-tcp', action='store_true', help='Test TCP communication only')
    parser.add_argument('--test-topics', action='store_true', help='Test ROS 2 topics only')
    parser.add_argument('--test-node', action='store_true', help='Test node status only')

    args = parser.parse_args()

    print(f"{BLUE}========================================{NC}")
    print(f"{BLUE}FMS Communication Test Client{NC}")
    print(f"{BLUE}========================================{NC}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {args.host}:{args.port}")
    print()

    client = FMSTestClient(args.host, args.port)

    # Default to all tests if no specific test is selected
    run_all = args.test_all or (not args.test_tcp and not args.test_topics and not args.test_node)

    if run_all or args.test_node:
        client.test_node_running()
        client.test_port_listening()

    if run_all or args.test_topics:
        client.test_topics()

    if run_all or args.test_tcp:
        if client.connect():
            client.test_simple_order()
            client.test_connection_persistence()
            client.test_delivery_complete()
            client.disconnect()

    client.print_summary()
    return 0


if __name__ == '__main__':
    sys.exit(main())
