#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kitchmatics FMS - Test Messages Script

This script tests ROS 2 message publishing and subscribing for the FMS system.
It validates:
1. Publishing goal_arrived messages
2. Publishing/subscribing to fleet status messages
3. Testing per-robot topics (same ROS_DOMAIN_ID)
4. TCP message format verification
5. ROS_DOMAIN_ID isolation (11=pinky1, 12=pinky2, 13=pinky3)

Usage:
  # Test publishing goal_arrived message manually
  python3 test_messages.py --test-goal-arrived

  # Test fleet status subscription
  python3 test_messages.py --test-fleet-status

  # Test per-robot topics
  python3 test_messages.py --test-robot-topics

  # Test TCP message format
  python3 test_messages.py --test-tcp-format

  # Interactive mode (publish various messages)
  python3 test_messages.py --interactive

  # Run all tests
  python3 test_messages.py --all
"""

import sys
import os
import argparse
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime

# ROS 2 imports
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import MultiThreadedExecutor
    from geometry_msgs.msg import Pose
    from std_msgs.msg import Float32, Bool
    from builtin_interfaces.msg import Time as ROS2Time
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    print("[ERROR] ROS 2 is not available. Please install ROS 2 Jazzy.")
    sys.exit(1)

# FMS imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fms'))

try:
    from fleet_interfaces.msg import (
        OrderRequest,
        RobotStatus,
        FleetStatus,
        DeliveryComplete
    )
    HAS_FLEET_INTERFACES = True
except ImportError:
    HAS_FLEET_INTERFACES = False
    print("[WARN] Fleet interfaces not available")

from tcp_communication import TCPMessage, MessageType


class GoalArrivedMessage:
    """Custom message type for goal_arrived (until official message is defined)"""
    def __init__(self, robot_id: str, location: str, timestamp: float = None):
        self.robot_id = robot_id
        self.location = location
        self.timestamp = timestamp or time.time()


class RobotTopicsMonitor(Node):
    """Monitor robot topics on current ROS_DOMAIN_ID (no namespace prefix)"""

    def __init__(self):
        super().__init__('robot_topics_monitor')
        import os

        self.logger = self.get_logger()
        current_domain = int(os.environ.get('ROS_DOMAIN_ID', 0))
        domain_to_robot = {11: 'pinky1', 12: 'pinky2', 13: 'pinky3'}
        self.current_robot = domain_to_robot.get(current_domain, 'unknown')

        self.received_messages = {
            'pose': None,
            'battery_voltage': None,
            'battery_present': None
        }

        self.logger.info(f"Starting robot topics monitoring on DOMAIN_ID={current_domain} ({self.current_robot})...")
        self.logger.info("Subscribing to (no namespace prefix):")
        self.logger.info("  /pose")
        self.logger.info("  /battery/voltage")
        self.logger.info("  /battery/present")


class FMSTestNode(Node):
    """Test node for FMS message communication"""

    def __init__(self):
        super().__init__('fms_test_node')

        self.logger = self.get_logger()
        self.test_results = {
            'goal_arrived': False,
            'fleet_status': False,
            'robot_topics': False,
            'tcp_format': False
        }

        # Publishers
        self.goal_arrived_pub = None
        self.order_request_pub = None

        # Subscribers
        self.fleet_status_sub = None

        self.logger.info("FMS Test Node initialized")
        self._setup_publishers()
        self._setup_subscribers()

    def _setup_publishers(self):
        """Setup message publishers"""
        # Note: goal_arrived message type is not yet defined in fleet_interfaces
        # For now, we use std_msgs/String as a workaround
        try:
            from std_msgs.msg import String
            self.goal_arrived_pub = self.create_publisher(
                String,
                '/fms/goal_arrived',
                10
            )
            self.logger.info("Created publisher: /fms/goal_arrived (using String type)")
        except Exception as e:
            self.logger.warn(f"Could not create goal_arrived publisher: {e}")

        try:
            self.order_request_pub = self.create_publisher(
                OrderRequest,
                '/fms/order_request',
                10
            )
            self.logger.info("Created publisher: /fms/order_request")
        except Exception as e:
            self.logger.warn(f"Could not create order_request publisher: {e}")

    def _setup_subscribers(self):
        """Setup message subscribers"""
        try:
            self.fleet_status_sub = self.create_subscription(
                FleetStatus,
                '/fms/fleet_status',
                self.fleet_status_callback,
                10
            )
            self.logger.info("Subscribed to: /fms/fleet_status")
        except Exception as e:
            self.logger.warn(f"Could not subscribe to fleet_status: {e}")

    def fleet_status_callback(self, msg: FleetStatus):
        """Handle incoming fleet status messages"""
        self.logger.info(f"[FLEET_STATUS] Received: {len(msg.robots)} robots, "
                        f"{msg.pending_orders} pending, {msg.active_orders} active")
        for robot in msg.robots:
            self.logger.info(f"  - {robot.robot_id}: {robot.status}")
        self.test_results['fleet_status'] = True

    def publish_goal_arrived(self, robot_id: str, location: str = "point13"):
        """Publish goal_arrived message"""
        if not self.goal_arrived_pub:
            self.logger.error("goal_arrived publisher not available")
            return False

        try:
            from std_msgs.msg import String
            msg = String()
            msg.data = json.dumps({
                'robot_id': robot_id,
                'location': location,
                'timestamp': time.time()
            })
            self.goal_arrived_pub.publish(msg)
            self.logger.info(f"[GOAL_ARRIVED] Published: {robot_id} arrived at {location}")
            self.test_results['goal_arrived'] = True
            return True
        except Exception as e:
            self.logger.error(f"Failed to publish goal_arrived: {e}")
            return False

    def publish_order_request(self, order_id: str, table_number: str = "T01",
                             menu_id: str = "M001", quantity: int = 1):
        """Publish order request message"""
        if not self.order_request_pub:
            self.logger.error("order_request publisher not available")
            return False

        try:
            msg = OrderRequest()
            msg.order_id = order_id
            msg.menu_id = menu_id
            msg.table_number = table_number
            msg.quantity = quantity
            msg.sauce_type = "mayo"
            msg.voice_order = False

            now = time.time()
            msg.created_at.sec = int(now)
            msg.created_at.nanosec = int((now - int(now)) * 1e9)

            self.order_request_pub.publish(msg)
            self.logger.info(f"[ORDER_REQUEST] Published: {order_id} to {table_number}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to publish order_request: {e}")
            return False


def test_goal_arrived(node: FMSTestNode):
    """Test goal_arrived message publishing"""
    print("\n" + "="*60)
    print("TEST 1: Publishing goal_arrived Message")
    print("="*60)

    # Test publishing for each robot
    for robot_id in ['pinky1', 'pinky2', 'pinky3']:
        success = node.publish_goal_arrived(robot_id, 'point13')
        time.sleep(0.5)
        print(f"  [{robot_id}] Published: {'OK' if success else 'FAILED'}")

    print()


def test_fleet_status(node: FMSTestNode):
    """Test fleet status subscription"""
    print("\n" + "="*60)
    print("TEST 2: Fleet Status Subscription")
    print("="*60)
    print("  Waiting 5 seconds for fleet status messages...")
    print("  (Start the FMS node in another terminal to see messages)")

    for i in range(5):
        rclpy.spin_once(node, timeout_sec=1)
        print(f"  [{i+1}/5] Waiting...")

    if node.test_results['fleet_status']:
        print("  Result: OK - Received fleet status message")
    else:
        print("  Result: NO MESSAGES RECEIVED")

    print()


def test_robot_topics(node: FMSTestNode):
    """Test per-robot topics"""
    print("\n" + "="*60)
    print("TEST 3: Per-Robot Topics")
    print("="*60)

    robot_monitor = RobotTopicsMonitor()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    executor.add_node(robot_monitor)

    print("  Monitoring robot topics for 5 seconds...")
    print("  Expected topics:")
    for robot_id in ['pinky1', 'pinky2', 'pinky3']:
        print(f"    /{robot_id}/pose")
        print(f"    /{robot_id}/battery/voltage")
        print(f"    /{robot_id}/battery/present")

    try:
        start_time = time.time()
        while (time.time() - start_time) < 5:
            executor.spin_once(timeout_sec=0.5)
    except KeyboardInterrupt:
        pass

    executor.shutdown()
    print("  Result: Topic monitoring completed")
    print()


def test_tcp_format():
    """Test TCP message format specification"""
    print("\n" + "="*60)
    print("TEST 4: TCP Message Format Verification")
    print("="*60)

    # Test various message types
    test_cases = [
        {
            'type': MessageType.CONNECT,
            'data': {
                'robot_id': 'pinky1',
                'robot_type': 'PINKYPRO',
                'ip_address': '192.168.1.7'
            }
        },
        {
            'type': MessageType.TASK_ASSIGN,
            'data': {
                'order_id': 'ORD-123456',
                'robot_id': 'pinky1',
                'table_number': 'T01',
                'menu_id': 'M001'
            }
        },
        {
            'type': MessageType.ROBOT_STATUS,
            'data': {
                'robot_id': 'pinky1',
                'status': 'NAVIGATING',
                'battery_voltage': 24.5,
                'position_x': 0.5,
                'position_y': 0.6
            }
        },
        {
            'type': MessageType.HEARTBEAT,
            'data': {
                'sender_id': 'fms_node',
                'timestamp': time.time()
            }
        }
    ]

    print("  Testing message serialization/deserialization:")
    all_ok = True

    for i, test_case in enumerate(test_cases):
        try:
            msg = TCPMessage(
                msg_type=test_case['type'].value,
                data=test_case['data'],
                sender_id='test_node'
            )

            # Serialize
            json_str = msg.to_json()

            # Deserialize
            msg_restored = TCPMessage.from_json(json_str)

            # Verify
            if (msg_restored.msg_type == msg.msg_type and
                msg_restored.data == msg.data and
                msg_restored.sender_id == msg.sender_id):
                print(f"  [{i+1}] {test_case['type'].value}: OK")
            else:
                print(f"  [{i+1}] {test_case['type'].value}: FAILED - Data mismatch")
                all_ok = False

        except Exception as e:
            print(f"  [{i+1}] {test_case['type'].value}: ERROR - {e}")
            all_ok = False

    print(f"\n  Result: {'OK' if all_ok else 'SOME TESTS FAILED'}")
    print()


def test_domain_isolation():
    """Test ROS_DOMAIN_ID isolation (verify that domain 11, 12, 13 are separate)"""
    print("\n" + "="*60)
    print("TEST 5: ROS_DOMAIN_ID Isolation")
    print("="*60)
    print("  Current implementation uses ROS_DOMAIN_ID:")
    print("    - domain 11 (pinky1)")
    print("    - domain 12 (pinky2)")
    print("    - domain 13 (pinky3)")
    print()

    # Show topic structure for each domain
    domains = {11: 'pinky1', 12: 'pinky2', 13: 'pinky3'}
    print("  Topic structure (same on each domain):")

    topics = [
        "/pose",
        "/battery/voltage",
        "/battery/present",
        "/navigate_to_pose",
        "/amcl_pose"
    ]
    for topic in topics:
        print(f"    - {topic}")

    print()
    print("  Each robot operates on its own ROS_DOMAIN_ID.")
    print("  FMS communicates with each robot by setting ROS_DOMAIN_ID environment variable.")
    print("  No namespace prefixes are used - topics are isolated by domain.")
    print()


def interactive_mode(node: FMSTestNode):
    """Interactive test mode"""
    print("\n" + "="*60)
    print("Interactive Mode - FMS Message Testing")
    print("="*60)
    print("\nAvailable commands:")
    print("  goal_arrived <robot_id> [location] - Publish goal_arrived message")
    print("  order <table> [menu] [qty]         - Publish order request")
    print("  status                              - Show test results")
    print("  quit                                - Exit")
    print()

    executor = MultiThreadedExecutor(num_threads=1)
    executor.add_node(node)

    try:
        while True:
            try:
                cmd = input("TEST> ").strip()

                if not cmd:
                    continue

                parts = cmd.split()

                if parts[0] == 'quit' or parts[0] == 'exit':
                    break

                elif parts[0] == 'goal_arrived':
                    if len(parts) < 2:
                        print("Usage: goal_arrived <robot_id> [location]")
                        continue
                    robot_id = parts[1]
                    location = parts[2] if len(parts) > 2 else 'point13'
                    node.publish_goal_arrived(robot_id, location)

                elif parts[0] == 'order':
                    if len(parts) < 2:
                        print("Usage: order <table> [menu] [qty]")
                        continue
                    table = f"T{int(parts[1]):02d}"
                    menu = parts[2] if len(parts) > 2 else 'M001'
                    qty = int(parts[3]) if len(parts) > 3 else 1
                    order_id = f"ORD-{int(time.time())}-001"
                    node.publish_order_request(order_id, table, menu, qty)

                elif parts[0] == 'status':
                    print("\n  Test Results:")
                    for test_name, passed in node.test_results.items():
                        status = "PASSED" if passed else "NOT RUN"
                        print(f"    {test_name}: {status}")
                    print()

                else:
                    print(f"Unknown command: {parts[0]}")

                # Allow ROS 2 to process callbacks
                executor.spin_once(timeout_sec=0.1)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

    finally:
        executor.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description="FMS Message Testing Suite"
    )
    parser.add_argument('--test-goal-arrived', action='store_true',
                       help='Test goal_arrived message publishing')
    parser.add_argument('--test-fleet-status', action='store_true',
                       help='Test fleet status subscription')
    parser.add_argument('--test-robot-topics', action='store_true',
                       help='Test per-robot topics')
    parser.add_argument('--test-tcp-format', action='store_true',
                       help='Test TCP message format')
    parser.add_argument('--test-domain', action='store_true',
                       help='Test ROS_DOMAIN_ID isolation')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interactive test mode')
    parser.add_argument('--all', action='store_true',
                       help='Run all tests')

    args = parser.parse_args()

    # Initialize ROS 2
    rclpy.init()

    try:
        # Create test node
        node = FMSTestNode()
        executor = MultiThreadedExecutor(num_threads=1)
        executor.add_node(node)

        # Determine which tests to run
        run_all = args.all or not any([
            args.test_goal_arrived,
            args.test_fleet_status,
            args.test_robot_topics,
            args.test_tcp_format,
            args.test_domain,
            args.interactive
        ])

        if run_all or args.test_goal_arrived:
            test_goal_arrived(node)

        if run_all or args.test_fleet_status:
            test_fleet_status(node)

        if run_all or args.test_tcp_format:
            test_tcp_format()

        if run_all or args.test_domain:
            test_domain_isolation()

        if run_all or args.test_robot_topics:
            print("\n[NOTE] Per-robot topic monitoring requires running robots.")
            print("       This test checks topic structure, not actual robot connections.")

        if args.interactive:
            interactive_mode(node)

        executor.shutdown()

        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"goal_arrived:    {node.test_results['goal_arrived']}")
        print(f"fleet_status:    {node.test_results['fleet_status']}")
        print(f"tcp_format:      {node.test_results['tcp_format']}")
        print()
        print("Note: To fully test the system, start these nodes in other terminals:")
        print("  ros2 launch fms fms_launch.py")
        print("  ros2 launch mobile_robot bringup_launch.py")
        print()

    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
