#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kitchmatics FMS - Robot TCP Client
This script runs on the robot to connect to the FMS server

Usage on robot:
  python3 robot_client.py --robot-id pinky1 --server 192.168.1.3
  python3 robot_client.py --robot-id cobot1 --server 192.168.1.3 --type JETCOBOT
"""

import sys
import os
import argparse
import time
import threading
import signal

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fms'))

from tcp_communication import FMSTCPClient, TCPMessage, MessageType


class RobotTCPClient:
    """
    Robot-side TCP Client for FMS communication

    This client:
    1. Connects to FMS server
    2. Sends periodic status updates
    3. Receives and executes commands
    """

    def __init__(self, robot_id: str, server_host: str, server_port: int = 9000,
                 robot_type: str = "PINKYPRO"):
        self.robot_id = robot_id
        self.robot_type = robot_type
        self.client = FMSTCPClient(
            robot_id=robot_id,
            server_host=server_host,
            server_port=server_port,
            robot_type=robot_type
        )

        # Robot state
        self.status = "IDLE"
        self.battery_voltage = 24.0
        self.pose = {"x": 0.0, "y": 0.0, "theta": 0.0}
        self.current_task = None

        # ROS 2 integration (optional)
        self.ros_node = None
        self.running = False

        # Register handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register message handlers"""
        self.client.register_handler(MessageType.NAV_GOAL.value, self._handle_nav_goal)
        self.client.register_handler(MessageType.NAV_CANCEL.value, self._handle_nav_cancel)
        self.client.register_handler(MessageType.TASK_ASSIGN.value, self._handle_task_assign)
        self.client.register_handler(MessageType.EMERGENCY_STOP.value, self._handle_emergency)
        self.client.register_handler(MessageType.PARAM_UPDATE.value, self._handle_param_update)
        self.client.register_handler(MessageType.ACK.value, self._handle_ack)

    def _handle_nav_goal(self, message: TCPMessage):
        """Handle navigation goal command"""
        x = message.data.get('x', 0.0)
        y = message.data.get('y', 0.0)
        theta = message.data.get('theta', 0.0)
        print(f"[NAV] Received goal: ({x}, {y}, {theta})")

        self.status = "MOVING_TO_GOAL"

        # TODO: Send to Nav2 via ROS 2
        # self.ros_node.send_nav_goal(x, y, theta)

    def _handle_nav_cancel(self, message: TCPMessage):
        """Handle navigation cancel command"""
        print("[NAV] Cancel received")
        self.status = "IDLE"

        # TODO: Cancel Nav2 goal via ROS 2

    def _handle_task_assign(self, message: TCPMessage):
        """Handle task assignment"""
        task_id = message.data.get('task_id', '')
        task_type = message.data.get('task_type', '')
        print(f"[TASK] Assigned: {task_id} ({task_type})")

        self.current_task = {
            'task_id': task_id,
            'task_type': task_type,
            'data': message.data
        }
        self.status = "ASSIGNED"

    def _handle_emergency(self, message: TCPMessage):
        """Handle emergency stop"""
        print("[EMERGENCY] STOP received!")
        self.status = "EMERGENCY_STOP"

        # TODO: Emergency stop robot
        # self.ros_node.emergency_stop()

    def _handle_param_update(self, message: TCPMessage):
        """Handle parameter update"""
        params = message.data.get('params', {})
        print(f"[PARAM] Update received: {params}")

    def _handle_ack(self, message: TCPMessage):
        """Handle acknowledgement"""
        print(f"[ACK] {message.data}")

    def start(self):
        """Start the client"""
        self.running = True

        print(f"\n{'='*60}")
        print(f"  Robot TCP Client: {self.robot_id} ({self.robot_type})")
        print(f"  Server: {self.client.server_host}:{self.client.server_port}")
        print(f"{'='*60}\n")

        # Connect to server
        if not self.client.connect():
            print("Failed to connect to server")
            return False

        print("Connected to FMS server")

        # Start status update thread
        status_thread = threading.Thread(target=self._status_loop, daemon=True)
        status_thread.start()

        return True

    def stop(self):
        """Stop the client"""
        self.running = False
        self.client.disconnect()
        print("Client stopped")

    def _status_loop(self):
        """Send periodic status updates"""
        while self.running:
            try:
                self.client.send_status(
                    status=self.status,
                    battery=self.battery_voltage,
                    pose=self.pose
                )

                # Simulate battery drain
                self.battery_voltage -= 0.001
                if self.battery_voltage < 20.0:
                    self.battery_voltage = 24.0  # Simulated recharge

            except Exception as e:
                print(f"Status send error: {e}")

            time.sleep(1.0)

    def report_task_complete(self, success: bool = True, message: str = ""):
        """Report task completion to server"""
        if self.current_task:
            self.client.send_task_complete(
                task_id=self.current_task['task_id'],
                success=success,
                message=message
            )
            self.current_task = None
            self.status = "IDLE"

    def update_pose(self, x: float, y: float, theta: float):
        """Update robot pose"""
        self.pose = {"x": x, "y": y, "theta": theta}
        self.client.send_pose(x, y, theta)


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\nShutting down...")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Robot TCP Client for FMS")
    parser.add_argument('--robot-id', '-r', required=True,
                        help='Robot ID (e.g., pinky1, cobot1)')
    parser.add_argument('--server', '-s', default='192.168.1.3',
                        help='FMS server IP address')
    parser.add_argument('--port', '-p', type=int, default=9000,
                        help='FMS server port')
    parser.add_argument('--type', '-t', default='PINKYPRO',
                        choices=['PINKYPRO', 'JETCOBOT'],
                        help='Robot type')

    args = parser.parse_args()

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create and start client
    client = RobotTCPClient(
        robot_id=args.robot_id,
        server_host=args.server,
        server_port=args.port,
        robot_type=args.type
    )

    if client.start():
        try:
            # Keep running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            client.stop()
    else:
        print("Failed to start client")
        sys.exit(1)


if __name__ == "__main__":
    main()
