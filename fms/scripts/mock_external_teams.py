#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kitchmatics FMS - Mock External Teams Script

This script mocks external team messages for testing the FMS without
depending on external teams:

1. Precision Control Team:
   - Mocks precision_parked message after robot reaches point13

2. Robot Arm Team:
   - Mocks food_loaded message after receiving food load request

This enables full end-to-end testing in skip mode without external
team dependencies.

Usage:
  # Run mock servers in background
  python3 mock_external_teams.py --start-all

  # Run precision control mock only
  python3 mock_external_teams.py --mock-precision

  # Run robot arm mock only
  python3 mock_external_teams.py --mock-arm

  # Run with custom delay parameters
  python3 mock_external_teams.py --start-all --precision-delay 3 --arm-delay 4

  # Interactive mode with controls
  python3 mock_external_teams.py --interactive
"""

import sys
import os
import argparse
import time
import json
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import signal

# ROS 2 imports
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import MultiThreadedExecutor
    from std_msgs.msg import String
    from builtin_interfaces.msg import Time as ROS2Time
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    print("[ERROR] ROS 2 is not available. Please install ROS 2 Jazzy.")
    sys.exit(1)

# FMS imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fms'))

try:
    from fleet_interfaces.msg import OrderRequest
    HAS_FLEET_INTERFACES = True
except ImportError:
    HAS_FLEET_INTERFACES = False
    print("[WARN] Fleet interfaces not available")

from tcp_communication import TCPMessage, MessageType


class MockEvent(Enum):
    """Mock events that can be simulated"""
    PRECISION_PARKED = "precision_parked"
    FOOD_LOADED = "food_loaded"
    DELIVERY_COMPLETE = "delivery_complete"


@dataclass
class PrecisionParkedMessage:
    """Precision control team: Robot successfully parked at pickup spot"""
    robot_id: str
    location: str = "pickup_spot"
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'robot_id': self.robot_id,
            'location': self.location,
            'timestamp': self.timestamp
        }


@dataclass
class FoodLoadedMessage:
    """Robot arm team: Food successfully loaded onto robot"""
    robot_id: str
    order_id: str
    menu_id: str
    quantity: int
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'robot_id': self.robot_id,
            'order_id': self.order_id,
            'menu_id': self.menu_id,
            'quantity': self.quantity,
            'timestamp': self.timestamp
        }


class PrecisionControlMock(Node):
    """Mock Precision Control Team

    Simulates the precision control team that:
    1. Receives goal_arrived message from FMS (robot at point13)
    2. Performs precision parking (point13 -> pickup_spot)
    3. Sends precision_parked message back to FMS
    """

    def __init__(self, delay: float = 2.0):
        super().__init__('precision_control_mock')

        self.logger = self.get_logger()
        self.delay = delay
        self.parked_robots = set()
        self.goal_arrived_count = 0
        self.precision_parked_count = 0

        # Publishers
        self.precision_parked_pub = self.create_publisher(
            String,
            '/fms/precision_parked',
            10
        )
        self.logger.info(f"Precision Control Mock initialized (delay={delay}s)")
        self.logger.info("Created publisher: /fms/precision_parked")

        # Subscribers
        self.goal_arrived_sub = self.create_subscription(
            String,
            '/fms/goal_arrived',
            self.goal_arrived_callback,
            10
        )
        self.logger.info("Subscribed to: /fms/goal_arrived")

        # Timer for processing goal arrivals
        self.create_timer(0.5, self.timer_callback)
        self.pending_parkings = {}  # {robot_id: arrival_time}

    def goal_arrived_callback(self, msg: String):
        """Handle goal_arrived message from FMS"""
        try:
            data = json.loads(msg.data)
            robot_id = data.get('robot_id')
            location = data.get('location', 'point13')

            self.goal_arrived_count += 1
            self.logger.info(f"[GOAL_ARRIVED] Received from {robot_id} at {location}")

            if location == 'point13':
                # Schedule precision parking for this robot
                self.pending_parkings[robot_id] = time.time()
                self.logger.info(f"  -> Precision parking scheduled ({self.delay}s delay)")

        except json.JSONDecodeError as e:
            self.logger.warn(f"Failed to parse goal_arrived message: {e}")

    def timer_callback(self):
        """Process scheduled precision parkings"""
        current_time = time.time()
        completed = []

        for robot_id, arrival_time in self.pending_parkings.items():
            if current_time - arrival_time >= self.delay:
                # Time to publish precision_parked
                self.publish_precision_parked(robot_id)
                completed.append(robot_id)

        # Remove completed parkings
        for robot_id in completed:
            del self.pending_parkings[robot_id]

    def publish_precision_parked(self, robot_id: str):
        """Publish precision_parked message"""
        try:
            msg_data = PrecisionParkedMessage(
                robot_id=robot_id,
                location='pickup_spot'
            )

            msg = String()
            msg.data = json.dumps(msg_data.to_dict())

            self.precision_parked_pub.publish(msg)
            self.precision_parked_count += 1

            self.logger.info(f"[PRECISION_PARKED] Published: {robot_id} parked at pickup_spot")

        except Exception as e:
            self.logger.error(f"Failed to publish precision_parked: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get mock statistics"""
        return {
            'goal_arrived_received': self.goal_arrived_count,
            'precision_parked_published': self.precision_parked_count,
            'pending_parkings': len(self.pending_parkings)
        }


class RobotArmMock(Node):
    """Mock Robot Arm Team

    Simulates the robot arm team that:
    1. Receives food_load_request message from FMS
    2. Loads food onto robot (simulated)
    3. Sends food_loaded message back to FMS
    """

    def __init__(self, delay: float = 3.0):
        super().__init__('robot_arm_mock')

        self.logger = self.get_logger()
        self.delay = delay
        self.loading_robots = {}
        self.load_request_count = 0
        self.food_loaded_count = 0

        # Publishers
        self.food_loaded_pub = self.create_publisher(
            String,
            '/fms/food_loaded',
            10
        )
        self.logger.info(f"Robot Arm Mock initialized (delay={delay}s)")
        self.logger.info("Created publisher: /fms/food_loaded")

        # Subscribers
        self.load_request_sub = self.create_subscription(
            String,
            '/fms/food_load_request',
            self.load_request_callback,
            10
        )
        self.logger.info("Subscribed to: /fms/food_load_request")

        # Timer for processing load requests
        self.create_timer(0.5, self.timer_callback)
        self.pending_loads = {}  # {robot_id: (start_time, load_data)}

    def load_request_callback(self, msg: String):
        """Handle food_load_request message from FMS"""
        try:
            data = json.loads(msg.data)
            robot_id = data.get('robot_id')
            order_id = data.get('order_id')
            menu_id = data.get('menu_id', 'M001')
            quantity = data.get('quantity', 1)

            self.load_request_count += 1
            self.logger.info(f"[FOOD_LOAD_REQUEST] Received for {robot_id}")
            self.logger.info(f"  Order ID: {order_id}, Menu: {menu_id}, Qty: {quantity}")

            # Schedule food loading
            self.pending_loads[robot_id] = {
                'order_id': order_id,
                'menu_id': menu_id,
                'quantity': quantity,
                'start_time': time.time()
            }
            self.logger.info(f"  -> Food loading scheduled ({self.delay}s delay)")

        except json.JSONDecodeError as e:
            self.logger.warn(f"Failed to parse food_load_request message: {e}")

    def timer_callback(self):
        """Process scheduled food loadings"""
        current_time = time.time()
        completed = []

        for robot_id, load_data in self.pending_loads.items():
            if current_time - load_data['start_time'] >= self.delay:
                # Time to publish food_loaded
                self.publish_food_loaded(
                    robot_id,
                    load_data['order_id'],
                    load_data['menu_id'],
                    load_data['quantity']
                )
                completed.append(robot_id)

        # Remove completed loads
        for robot_id in completed:
            del self.pending_loads[robot_id]

    def publish_food_loaded(self, robot_id: str, order_id: str,
                            menu_id: str, quantity: int):
        """Publish food_loaded message"""
        try:
            msg_data = FoodLoadedMessage(
                robot_id=robot_id,
                order_id=order_id,
                menu_id=menu_id,
                quantity=quantity
            )

            msg = String()
            msg.data = json.dumps(msg_data.to_dict())

            self.food_loaded_pub.publish(msg)
            self.food_loaded_count += 1

            self.logger.info(f"[FOOD_LOADED] Published: {robot_id} loaded with {order_id}")

        except Exception as e:
            self.logger.error(f"Failed to publish food_loaded: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get mock statistics"""
        return {
            'load_requests_received': self.load_request_count,
            'food_loaded_published': self.food_loaded_count,
            'pending_loads': len(self.pending_loads)
        }


class MockControlServer:
    """Control interface for mock servers"""

    def __init__(self, precision_mock: Optional[PrecisionControlMock] = None,
                 arm_mock: Optional[RobotArmMock] = None):
        self.precision_mock = precision_mock
        self.arm_mock = arm_mock
        self.running = False

    def start_precision_mock(self, delay: float = 2.0):
        """Start precision control mock"""
        if self.precision_mock:
            self.precision_mock.logger.info(f"Precision mock already running")
            return False
        self.precision_mock = PrecisionControlMock(delay=delay)
        return True

    def start_arm_mock(self, delay: float = 3.0):
        """Start robot arm mock"""
        if self.arm_mock:
            self.arm_mock.logger.info(f"Arm mock already running")
            return False
        self.arm_mock = RobotArmMock(delay=delay)
        return True

    def stop_precision_mock(self):
        """Stop precision control mock"""
        if self.precision_mock:
            self.precision_mock.destroy_node()
            self.precision_mock = None
            return True
        return False

    def stop_arm_mock(self):
        """Stop robot arm mock"""
        if self.arm_mock:
            self.arm_mock.destroy_node()
            self.arm_mock = None
            return True
        return False

    def print_stats(self):
        """Print statistics from active mocks"""
        print("\n" + "="*60)
        print("MOCK STATISTICS")
        print("="*60)

        if self.precision_mock:
            stats = self.precision_mock.get_stats()
            print("Precision Control Mock:")
            print(f"  goal_arrived received:     {stats['goal_arrived_received']}")
            print(f"  precision_parked sent:     {stats['precision_parked_published']}")
            print(f"  pending parkings:          {stats['pending_parkings']}")

        if self.arm_mock:
            stats = self.arm_mock.get_stats()
            print("Robot Arm Mock:")
            print(f"  food_load_request received: {stats['load_requests_received']}")
            print(f"  food_loaded sent:           {stats['food_loaded_published']}")
            print(f"  pending loads:              {stats['pending_loads']}")

        print()


def run_mocks(precision_mock: Optional[PrecisionControlMock] = None,
              arm_mock: Optional[RobotArmMock] = None,
              duration: Optional[float] = None):
    """Run mock servers with optional duration limit"""
    executor = MultiThreadedExecutor(num_threads=2)

    if precision_mock:
        executor.add_node(precision_mock)
    if arm_mock:
        executor.add_node(arm_mock)

    if not (precision_mock or arm_mock):
        print("[ERROR] No mocks to run!")
        return

    print("\n" + "="*60)
    print("Mock External Teams Running")
    print("="*60)

    if precision_mock:
        print("- Precision Control Mock: ACTIVE")
    if arm_mock:
        print("- Robot Arm Mock: ACTIVE")

    print("\nPress Ctrl+C to stop")
    print()

    try:
        if duration:
            start_time = time.time()
            while (time.time() - start_time) < duration:
                executor.spin_once(timeout_sec=1)
        else:
            while True:
                executor.spin_once(timeout_sec=1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping mocks...")
    finally:
        executor.shutdown()


def interactive_mode(server: MockControlServer):
    """Interactive mode for controlling mocks"""
    print("\n" + "="*60)
    print("Mock External Teams - Interactive Mode")
    print("="*60)
    print("\nAvailable commands:")
    print("  start precision [delay]    - Start precision control mock")
    print("  start arm [delay]          - Start robot arm mock")
    print("  start all [p-delay] [a-delay] - Start both mocks")
    print("  stop precision             - Stop precision control mock")
    print("  stop arm                   - Stop robot arm mock")
    print("  stop all                   - Stop all mocks")
    print("  stats                      - Show statistics")
    print("  quit                       - Exit")
    print()

    # Start executor in background
    executor = MultiThreadedExecutor(num_threads=4)

    def add_to_executor(node):
        if node:
            executor.add_node(node)

    executor_thread = threading.Thread(
        target=lambda: executor.spin(),
        daemon=True
    )
    executor_thread.start()

    try:
        while True:
            try:
                cmd = input("MOCK> ").strip()

                if not cmd:
                    continue

                parts = cmd.split()

                if parts[0] == 'quit' or parts[0] == 'exit':
                    break

                elif parts[0] == 'start':
                    if len(parts) < 2:
                        print("Usage: start [precision|arm|all] [delay]")
                        continue

                    if parts[1] == 'precision':
                        delay = float(parts[2]) if len(parts) > 2 else 2.0
                        if server.start_precision_mock(delay):
                            add_to_executor(server.precision_mock)
                            print(f"[OK] Precision mock started ({delay}s delay)")
                        else:
                            print("[WARN] Precision mock already running")

                    elif parts[1] == 'arm':
                        delay = float(parts[2]) if len(parts) > 2 else 3.0
                        if server.start_arm_mock(delay):
                            add_to_executor(server.arm_mock)
                            print(f"[OK] Arm mock started ({delay}s delay)")
                        else:
                            print("[WARN] Arm mock already running")

                    elif parts[1] == 'all':
                        p_delay = float(parts[2]) if len(parts) > 2 else 2.0
                        a_delay = float(parts[3]) if len(parts) > 3 else 3.0
                        p_ok = server.start_precision_mock(p_delay)
                        a_ok = server.start_arm_mock(a_delay)
                        if p_ok:
                            add_to_executor(server.precision_mock)
                        if a_ok:
                            add_to_executor(server.arm_mock)
                        print(f"[OK] Mocks started (precision: {p_delay}s, arm: {a_delay}s)")

                elif parts[0] == 'stop':
                    if len(parts) < 2:
                        print("Usage: stop [precision|arm|all]")
                        continue

                    if parts[1] == 'precision':
                        if server.stop_precision_mock():
                            print("[OK] Precision mock stopped")
                        else:
                            print("[WARN] Precision mock not running")

                    elif parts[1] == 'arm':
                        if server.stop_arm_mock():
                            print("[OK] Arm mock stopped")
                        else:
                            print("[WARN] Arm mock not running")

                    elif parts[1] == 'all':
                        p_ok = server.stop_precision_mock()
                        a_ok = server.stop_arm_mock()
                        print("[OK] Mocks stopped")

                elif parts[0] == 'stats':
                    server.print_stats()

                else:
                    print(f"Unknown command: {parts[0]}")

                # Brief spin to process messages
                executor.spin_once(timeout_sec=0.1)

            except KeyboardInterrupt:
                break
            except ValueError as e:
                print(f"Invalid value: {e}")
            except Exception as e:
                print(f"Error: {e}")

    finally:
        print("\n[INFO] Shutting down...")
        executor.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description="Mock External Teams for FMS Testing"
    )
    parser.add_argument('--mock-precision', action='store_true',
                       help='Start precision control mock only')
    parser.add_argument('--mock-arm', action='store_true',
                       help='Start robot arm mock only')
    parser.add_argument('--start-all', action='store_true',
                       help='Start all mocks')
    parser.add_argument('--precision-delay', type=float, default=2.0,
                       help='Delay for precision control mock (seconds)')
    parser.add_argument('--arm-delay', type=float, default=3.0,
                       help='Delay for robot arm mock (seconds)')
    parser.add_argument('--duration', type=float, default=None,
                       help='Run for specified duration (seconds)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interactive control mode')

    args = parser.parse_args()

    # Initialize ROS 2
    rclpy.init()

    try:
        # Determine which mocks to start
        start_precision = args.mock_precision or args.start_all
        start_arm = args.mock_arm or args.start_all

        if args.interactive:
            server = MockControlServer()
            interactive_mode(server)
        else:
            precision_mock = None
            arm_mock = None

            if start_precision:
                precision_mock = PrecisionControlMock(delay=args.precision_delay)

            if start_arm:
                arm_mock = RobotArmMock(delay=args.arm_delay)

            if precision_mock or arm_mock:
                run_mocks(precision_mock, arm_mock, args.duration)
            else:
                print("[INFO] No mocks specified. Use --start-all, --mock-precision, or --mock-arm")
                print("[INFO] Or use --interactive for interactive mode")

    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
