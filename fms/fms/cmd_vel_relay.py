#!/usr/bin/env python3
"""
cmd_vel Relay Node

Relays velocity commands from namespaced topics to the global /cmd_vel topic
that the robot driver subscribes to.

This is necessary because:
- Nav2 publishes to /pinky1/cmd_vel (namespaced)
- Robot driver (pinky_bringup) subscribes to /cmd_vel (global)
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from rclpy.qos import QoSProfile, ReliabilityPolicy


class CmdVelRelay(Node):
    def __init__(self):
        super().__init__('cmd_vel_relay')

        # Declare parameters
        self.declare_parameter('robot_namespaces', ['pinky1', 'pinky2', 'pinky3'])
        self.declare_parameter('active_robot', 'pinky1')

        robot_namespaces = self.get_parameter('robot_namespaces').get_parameter_value().string_array_value
        active_robot = self.get_parameter('active_robot').get_parameter_value().string_value

        # QoS profile for cmd_vel
        qos = QoSProfile(depth=10)
        qos.reliability = ReliabilityPolicy.RELIABLE

        # Publisher to global /cmd_vel
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', qos)

        # Track active robot
        self.active_robot = active_robot
        self.last_cmd_time = {}

        # Subscribe to each robot's cmd_vel
        self.subscriptions_dict = {}
        for ns in robot_namespaces:
            topic = f'/{ns}/cmd_vel'
            sub = self.create_subscription(
                Twist,
                topic,
                lambda msg, robot=ns: self.cmd_vel_callback(msg, robot),
                qos
            )
            self.subscriptions_dict[ns] = sub
            self.last_cmd_time[ns] = self.get_clock().now()
            self.get_logger().info(f'Subscribed to {topic}')

        self.get_logger().info(f'CmdVelRelay started. Active robot: {active_robot}')

    def cmd_vel_callback(self, msg: Twist, robot: str):
        """Forward cmd_vel from active robot to global topic"""
        # For now, just forward from the active robot
        # Later can add priority/conflict resolution
        if robot == self.active_robot:
            self.cmd_vel_pub.publish(msg)
            self.last_cmd_time[robot] = self.get_clock().now()


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelRelay()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
