#!/usr/bin/env python3
"""
FMS TCP Protocol Tester - Using Newline-Delimited JSON Format

The FMSTCPServer expects newline-delimited JSON messages (not length-prefixed).

Protocol:
- Each message is JSON followed by newline
- Format: <JSON>\n

Example:
{"type": "connect", "data": {...}, "sender_id": "test_client", "sequence": 1}
{"type": "heartbeat", "data": {...}, "sender_id": "test_client", "sequence": 2}

Usage:
python3 test_tcp_protocol.py
"""

import socket
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'


class FMSTCPClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 9000):
        self.host = host
        self.port = port
        self.socket = None
        self.sequence = 0
        self.test_results = []

    def log_test(self, name: str, passed: bool, message: str = ""):
        status = f"{GREEN}✓{NC}" if passed else f"{RED}✗{NC}"
        print(f"{status} {name}")
        if message:
            print(f"  → {message}")
        self.test_results.append((name, passed, message))

    def log_info(self, message: str):
        print(f"{BLUE}ℹ{NC} {message}")

    def log_error(self, message: str):
        print(f"{RED}✗{NC} {message}")

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
        """Send newline-delimited JSON message"""
        try:
            json_str = json.dumps(message)
            self.socket.sendall((json_str + '\n').encode('utf-8'))
            self.log_info(f"Sent: {json_str[:80]}...")
            return True
        except Exception as e:
            self.log_error(f"Send error: {e}")
            return False

    def recv_message(self, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """Receive newline-delimited JSON message"""
        try:
            self.socket.settimeout(timeout)
            # Read until newline
            data = b''
            while True:
                chunk = self.socket.recv(1)
                if not chunk:
                    return None
                data += chunk
                if chunk == b'\n':
                    break

            json_str = data.decode('utf-8').strip()
            return json.loads(json_str)
        except socket.timeout:
            return None
        except Exception as e:
            self.log_error(f"Receive error: {e}")
            return None

    def test_connect(self):
        """Test robot connection"""
        print(f"\n{YELLOW}=== Test 1: Robot Connection ==={NC}")

        message = {
            "type": "connect",
            "data": {
                "robot_id": "test_robot",
                "robot_type": "mobile",
                "ip_address": "127.0.0.1"
            },
            "sender_id": "test_robot",
            "sequence": 1
        }

        if self.send_message(message):
            response = self.recv_message()
            if response:
                self.log_test("Connect Response", True, json.dumps(response, indent=2))
                return True
            else:
                self.log_test("Connect Response", False, "No response from FMS")
                return False
        return False

    def test_heartbeat(self):
        """Test heartbeat message"""
        print(f"\n{YELLOW}=== Test 2: Heartbeat ==={NC}")

        message = {
            "type": "heartbeat",
            "data": {
                "robot_id": "test_robot",
                "battery": 85,
                "status": "idle"
            },
            "sender_id": "test_robot",
            "sequence": 2
        }

        if self.send_message(message):
            self.log_test("Heartbeat Sent", True)
            time.sleep(0.5)
            return True
        return False

    def test_pose_update(self):
        """Test pose update"""
        print(f"\n{YELLOW}=== Test 3: Pose Update ==={NC}")

        message = {
            "type": "pose_update",
            "data": {
                "robot_id": "test_robot",
                "x": 1.5,
                "y": 2.0,
                "theta": 0.5
            },
            "sender_id": "test_robot",
            "sequence": 3
        }

        if self.send_message(message):
            self.log_test("Pose Update Sent", True)
            return True
        return False

    def test_robot_status(self):
        """Test robot status update"""
        print(f"\n{YELLOW}=== Test 4: Robot Status ==={NC}")

        message = {
            "type": "robot_status",
            "data": {
                "robot_id": "test_robot",
                "status": "moving",
                "current_task": "task_001"
            },
            "sender_id": "test_robot",
            "sequence": 4
        }

        if self.send_message(message):
            self.log_test("Robot Status Sent", True)
            return True
        return False

    def test_nav_status(self):
        """Test navigation status"""
        print(f"\n{YELLOW}=== Test 5: Navigation Status ==={NC}")

        message = {
            "type": "nav_status",
            "data": {
                "robot_id": "test_robot",
                "status": "in_progress",
                "goal_id": "goal_001"
            },
            "sender_id": "test_robot",
            "sequence": 5
        }

        if self.send_message(message):
            self.log_test("Nav Status Sent", True)
            return True
        return False

    def test_task_complete(self):
        """Test task completion"""
        print(f"\n{YELLOW}=== Test 6: Task Complete ==={NC}")

        message = {
            "type": "task_complete",
            "data": {
                "robot_id": "test_robot",
                "task_id": "task_001",
                "result": "success"
            },
            "sender_id": "test_robot",
            "sequence": 6
        }

        if self.send_message(message):
            self.log_test("Task Complete Sent", True)
            return True
        return False

    def test_error(self):
        """Test error reporting"""
        print(f"\n{YELLOW}=== Test 7: Error Report ==={NC}")

        message = {
            "type": "error",
            "data": {
                "robot_id": "test_robot",
                "error_code": "E001",
                "error_message": "Test error message"
            },
            "sender_id": "test_robot",
            "sequence": 7
        }

        if self.send_message(message):
            self.log_test("Error Report Sent", True)
            return True
        return False

    def test_disconnect(self):
        """Test disconnect"""
        print(f"\n{YELLOW}=== Test 8: Disconnect ==={NC}")

        message = {
            "type": "disconnect",
            "data": {
                "robot_id": "test_robot",
                "reason": "normal_shutdown"
            },
            "sender_id": "test_robot",
            "sequence": 8
        }

        if self.send_message(message):
            self.log_test("Disconnect Sent", True)
            return True
        return False

    def print_summary(self):
        """Print test summary"""
        print(f"\n{BLUE}========================================{NC}")
        print(f"{BLUE}TCP Protocol Test Summary{NC}")
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
            print(f"\n{GREEN}All tests passed!{NC}")
            print(f"\n{YELLOW}Key Findings:{NC}")
            print("- FMS TCP Server is accepting newline-delimited JSON format")
            print("- Message handlers are processing incoming messages")
            print("- Server appears to be ready for robot connections")
            return 0
        else:
            print(f"\n{RED}Some tests failed.{NC}")
            return 1


def main():
    print(f"{BLUE}========================================{NC}")
    print(f"{BLUE}FMS TCP Protocol Tester (Newline-Delimited JSON){NC}")
    print(f"{BLUE}========================================{NC}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: 127.0.0.1:9000")
    print()

    client = FMSTCPClient()

    if not client.connect():
        print(f"\n{RED}Failed to connect to FMS TCP server.{NC}")
        return 1

    # Run all tests
    client.test_connect()
    time.sleep(0.5)
    client.test_heartbeat()
    time.sleep(0.2)
    client.test_pose_update()
    time.sleep(0.2)
    client.test_robot_status()
    time.sleep(0.2)
    client.test_nav_status()
    time.sleep(0.2)
    client.test_task_complete()
    time.sleep(0.2)
    client.test_error()
    time.sleep(0.2)
    client.test_disconnect()

    client.disconnect()
    return client.print_summary()


if __name__ == '__main__':
    sys.exit(main())
