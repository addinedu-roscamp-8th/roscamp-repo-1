#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kitchmatics FMS - TCP Node
ROS 2 Node that integrates FMS with TCP communication for closed network

This node:
1. Runs the FMS TCP Server for robot communication
2. Bridges TCP messages to/from ROS 2 topics
3. Manages the closed network fleet
"""

import os
import sys
import yaml
import threading
from pathlib import Path
from typing import Dict, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import PoseStamped, Pose

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from tcp_communication import (
    FMSTCPServer, TCPMessage, MessageType, RobotConnection
)

# Try to import fleet_interfaces
try:
    from fleet_interfaces.msg import (
        FleetStatus, RobotStatus, OrderRequest,
        DeliveryComplete, LoadingComplete
    )
    HAS_FLEET_INTERFACES = True
except ImportError:
    HAS_FLEET_INTERFACES = False
    print("[WARN] fleet_interfaces not found, using basic messages")


class FMSTCPNode(Node):
    """
    FMS TCP Node - Integrates TCP communication with ROS 2

    Responsibilities:
    1. Start and manage FMS TCP Server
    2. Translate TCP messages to ROS 2 messages
    3. Translate ROS 2 messages to TCP messages
    4. Monitor robot connections and status
    """

    def __init__(self):
        super().__init__('fms_tcp_node')

        # Declare parameters
        self.declare_parameter('tcp_port', 9000)
        self.declare_parameter('config_file', '')
        self.declare_parameter('network_config_file', '')

        # Get parameters
        self.tcp_port = self.get_parameter('tcp_port').value
        config_file = self.get_parameter('config_file').value
        network_config_file = self.get_parameter('network_config_file').value

        # Load configurations
        self.fms_config = self._load_yaml(config_file) if config_file else {}
        self.network_config = self._load_yaml(network_config_file) if network_config_file else {}

        # Override port from network config if available
        if self.network_config:
            self.tcp_port = self.network_config.get('master', {}).get('tcp_port', self.tcp_port)

        # Initialize TCP Server
        self.tcp_server = FMSTCPServer(
            host="0.0.0.0",
            port=self.tcp_port,
            config_path=network_config_file
        )

        # Register custom TCP handlers
        self._register_tcp_handlers()

        # QoS profile for reliable communication
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Create ROS 2 publishers
        if HAS_FLEET_INTERFACES:
            self.fleet_status_pub = self.create_publisher(
                FleetStatus, '/fms/fleet_status', qos_profile)
            self.order_request_pub = self.create_publisher(
                OrderRequest, '/fms/order_request', qos_profile)
        else:
            self.get_logger().warn("Using basic publishers (no fleet_interfaces)")

        # Create ROS 2 subscribers
        if HAS_FLEET_INTERFACES:
            self.delivery_complete_sub = self.create_subscription(
                DeliveryComplete, '/fms/delivery_complete',
                self.delivery_complete_callback, qos_profile)

        # Robot pose subscribers (per robot)
        self.pose_subscribers = {}
        self._setup_robot_pose_subscribers()

        # Timer for periodic status publishing
        self.status_timer = self.create_timer(1.0, self.publish_fleet_status)

        # Timer for processing TCP message queue
        self.queue_timer = self.create_timer(0.1, self.process_tcp_queue)

        # Start TCP server
        self.tcp_server.start()
        self.get_logger().info(f'FMS TCP Node started on port {self.tcp_port}')

        # Log configured robots
        self._log_configured_robots()

    def _load_yaml(self, file_path: str) -> dict:
        """Load YAML configuration file"""
        if file_path and os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return yaml.safe_load(f)
        return {}

    def _register_tcp_handlers(self):
        """Register custom TCP message handlers"""
        self.tcp_server.register_handler(
            MessageType.TASK_COMPLETE.value,
            self._handle_task_complete
        )
        self.tcp_server.register_handler(
            MessageType.NAV_STATUS.value,
            self._handle_nav_status
        )
        self.tcp_server.register_handler(
            MessageType.EMERGENCY_STOP.value,
            self._handle_emergency_stop
        )

    def _setup_robot_pose_subscribers(self):
        """Setup pose subscribers for each configured robot"""
        mobile_robots = self.network_config.get('mobile_robots', {})

        for robot_name, robot_cfg in mobile_robots.items():
            if robot_cfg.get('enabled', False):
                namespace = robot_cfg.get('namespace', f'/{robot_cfg.get("robot_id", robot_name)}')

                # Subscribe to robot pose
                topic = f'{namespace}/pose'
                self.pose_subscribers[robot_name] = self.create_subscription(
                    PoseStamped, topic,
                    lambda msg, rn=robot_name: self.robot_pose_callback(rn, msg),
                    10
                )
                self.get_logger().info(f'Subscribed to {topic}')

    def _log_configured_robots(self):
        """Log all configured robots"""
        self.get_logger().info('=== Configured Robots ===')

        mobile_robots = self.network_config.get('mobile_robots', {})
        for name, cfg in mobile_robots.items():
            status = "ENABLED" if cfg.get('enabled', False) else "DISABLED"
            ip = cfg.get('ip_address', 'N/A')
            self.get_logger().info(f'  Mobile: {name} ({ip}) [{status}]')

        cobot_arms = self.network_config.get('cobot_arms', {})
        for name, cfg in cobot_arms.items():
            status = "ENABLED" if cfg.get('enabled', False) else "DISABLED"
            ip = cfg.get('ip_address', 'N/A')
            self.get_logger().info(f'  Cobot:  {name} ({ip}) [{status}]')

    # ========== TCP Message Handlers ==========

    def _handle_task_complete(self, message: TCPMessage, client_socket) -> Optional[TCPMessage]:
        """Handle task completion from robot"""
        robot_id = message.sender_id
        task_id = message.data.get('task_id', '')
        success = message.data.get('success', False)

        self.get_logger().info(f'Task complete from {robot_id}: {task_id} (success={success})')

        # Publish to ROS 2 if available
        if HAS_FLEET_INTERFACES and success:
            # Create delivery complete message
            pass  # Implement as needed

        return TCPMessage(
            msg_type=MessageType.ACK.value,
            data={"status": "received", "task_id": task_id},
            sender_id="server"
        )

    def _handle_nav_status(self, message: TCPMessage, client_socket) -> None:
        """Handle navigation status from robot"""
        robot_id = message.sender_id
        status = message.data.get('status', '')
        self.get_logger().debug(f'Nav status from {robot_id}: {status}')
        return None

    def _handle_emergency_stop(self, message: TCPMessage, client_socket) -> TCPMessage:
        """Handle emergency stop command"""
        robot_id = message.sender_id
        self.get_logger().error(f'EMERGENCY STOP from {robot_id}!')

        # Broadcast emergency to all robots
        emergency_msg = TCPMessage(
            msg_type=MessageType.EMERGENCY_STOP.value,
            data={"source": robot_id},
            sender_id="server"
        )
        self.tcp_server.broadcast(emergency_msg)

        return TCPMessage(
            msg_type=MessageType.ACK.value,
            data={"status": "emergency_acknowledged"},
            sender_id="server"
        )

    # ========== ROS 2 Callbacks ==========

    def robot_pose_callback(self, robot_name: str, msg: PoseStamped):
        """Handle robot pose update from ROS 2"""
        # Forward pose to TCP clients if needed
        pose_data = {
            'x': msg.pose.position.x,
            'y': msg.pose.position.y,
            'z': msg.pose.position.z,
            'orientation': {
                'x': msg.pose.orientation.x,
                'y': msg.pose.orientation.y,
                'z': msg.pose.orientation.z,
                'w': msg.pose.orientation.w
            }
        }

        # Broadcast pose update
        pose_msg = TCPMessage(
            msg_type=MessageType.POSE_UPDATE.value,
            data={'robot_name': robot_name, 'pose': pose_data},
            sender_id="server"
        )
        self.tcp_server.broadcast(pose_msg)

    def delivery_complete_callback(self, msg):
        """Handle delivery complete from ROS 2"""
        # Forward to TCP clients
        delivery_msg = TCPMessage(
            msg_type=MessageType.TASK_COMPLETE.value,
            data={
                'order_id': msg.order_id,
                'table_number': msg.table_number,
                'success': True
            },
            sender_id="server"
        )
        self.tcp_server.broadcast(delivery_msg)

    # ========== Timer Callbacks ==========

    def publish_fleet_status(self):
        """Publish fleet status to ROS 2"""
        fleet_status = self.tcp_server.get_fleet_status()

        # Log status periodically
        connected = fleet_status.get('connected', 0)
        total = fleet_status.get('total_robots', 0)
        self.get_logger().debug(f'Fleet status: {connected}/{total} robots connected')

        # Publish to ROS 2 if available
        if HAS_FLEET_INTERFACES:
            # Build FleetStatus message
            pass  # Implement as needed

        # Broadcast to TCP clients
        status_msg = TCPMessage(
            msg_type=MessageType.FLEET_STATUS.value,
            data=fleet_status,
            sender_id="server"
        )
        self.tcp_server.broadcast(status_msg)

    def process_tcp_queue(self):
        """Process messages from TCP queue"""
        while not self.tcp_server.message_queue.empty():
            try:
                message = self.tcp_server.message_queue.get_nowait()
                self._process_tcp_message(message)
            except:
                break

    def _process_tcp_message(self, message: TCPMessage):
        """Process a TCP message from the queue"""
        # Log connection events
        if message.msg_type == MessageType.CONNECT.value:
            robot_id = message.data.get('robot_id', 'unknown')
            ip = message.data.get('ip_address', 'unknown')
            self.get_logger().info(f'Robot connected: {robot_id} from {ip}')

        elif message.msg_type == MessageType.DISCONNECT.value:
            robot_id = message.data.get('robot_id', 'unknown')
            reason = message.data.get('reason', 'unknown')
            self.get_logger().warn(f'Robot disconnected: {robot_id} ({reason})')

    # ========== Navigation Commands ==========

    def send_nav_goal(self, robot_id: str, x: float, y: float, theta: float) -> bool:
        """Send navigation goal to a robot via TCP"""
        nav_msg = TCPMessage(
            msg_type=MessageType.NAV_GOAL.value,
            data={'x': x, 'y': y, 'theta': theta},
            sender_id="server"
        )
        return self.tcp_server.send_to_robot(robot_id, nav_msg)

    def cancel_nav(self, robot_id: str) -> bool:
        """Cancel navigation for a robot"""
        cancel_msg = TCPMessage(
            msg_type=MessageType.NAV_CANCEL.value,
            data={},
            sender_id="server"
        )
        return self.tcp_server.send_to_robot(robot_id, cancel_msg)

    # ========== Lifecycle ==========

    def destroy_node(self):
        """Clean up resources"""
        self.tcp_server.stop()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    try:
        node = FMSTCPNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
