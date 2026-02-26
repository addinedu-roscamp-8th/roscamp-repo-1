#!/usr/bin/env python3
"""
Pinky Navigation Test Script
Usage: python3 test_navigation.py `pinky1` `table1`

Sends a navigation command to move the specified pinky robot to the target waypoint.
Requires: Domain Bridge running, pinky robot bringup and Nav2 running.
"""

import sys
import time
import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped

# Waypoint coordinates from navigation_graph.yaml
WAYPOINTS = {
    # Pickup zone
    "pickup_spot": (0.47, 0.63),

    # Robot parking spots
    "pinky1_spot": (0.585, 0.085),
    "pinky2_spot": (0.585, 0.255),
    "pinky3_spot": (0.585, 0.915),

    # Tables
    "table1": (1.785, 0.35),
    "table2": (1.415, 0.35),
    "table3": (1.785, 0.65),
    "table4": (1.415, 0.65),
    "table5": (1.235, 0.35),
    "table6": (0.865, 0.35),
    "table7": (1.235, 0.65),
    "table8": (0.865, 0.65),

    # Navigation points
    "point1": (0.78, 0.15),
    "point2": (0.78, 0.35),
    "point3": (0.78, 0.65),
    "point4": (0.78, 0.85),
    "point5": (1.325, 0.15),
    "point6": (1.325, 0.35),
    "point7": (1.325, 0.65),
    "point8": (1.325, 0.85),
    "point9": (1.85, 0.15),
    "point10": (1.85, 0.35),
    "point11": (1.85, 0.65),
    "point12": (1.85, 0.85),
    "point13": (0.585, 0.63),
}

# Robot Domain IDs
ROBOT_DOMAINS = {
    "pinky1": 11,
    "pinky2": 12,
    "pinky3": 13,
}


class NavigationClient(Node):
    def __init__(self, robot_name: str):
        super().__init__(f'{robot_name}_nav_client')
        self.robot_name = robot_name

        # Action client for NavigateToPose
        # When using domain bridge, the topic is /{robot}/navigate_to_pose on domain 25
        action_name = f'/{robot_name}/navigate_to_pose'
        self._action_client = ActionClient(self, NavigateToPose, action_name)

        self.get_logger().info(f'Navigation client created for {robot_name}')
        self.get_logger().info(f'Action: {action_name}')

    def send_goal(self, x: float, y: float, theta: float = 0.0):
        """Send navigation goal to robot"""
        self.get_logger().info(f'Waiting for action server...')

        if not self._action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('Action server not available!')
            self.get_logger().error('Make sure Domain Bridge and robot Nav2 are running.')
            return False

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0

        # Convert theta to quaternion (rotation around z-axis)
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = math.sin(theta / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(theta / 2.0)

        self.get_logger().info(f'Sending goal: x={x:.3f}, y={y:.3f}, theta={theta:.3f}')

        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        self._send_goal_future.add_done_callback(self.goal_response_callback)
        return True

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected!')
            return

        self.get_logger().info('Goal accepted!')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result()
        status = result.status

        if status == 4:  # SUCCEEDED
            self.get_logger().info('Navigation SUCCEEDED!')
        elif status == 5:  # CANCELED
            self.get_logger().warn('Navigation CANCELED')
        elif status == 6:  # ABORTED
            self.get_logger().error('Navigation ABORTED')
        else:
            self.get_logger().info(f'Navigation finished with status: {status}')

        rclpy.shutdown()

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        current_pose = feedback.current_pose.pose
        distance = feedback.distance_remaining
        self.get_logger().info(
            f'Position: ({current_pose.position.x:.2f}, {current_pose.position.y:.2f}), '
            f'Distance remaining: {distance:.2f}m'
        )


def print_usage():
    print("Usage: python3 test_navigation.py `<robot>` `<waypoint>`")
    print("")
    print("Robots: pinky1, pinky2, pinky3")
    print("")
    print("Waypoints:")
    print("  Spots: pickup_spot, pinky1_spot, pinky2_spot, pinky3_spot")
    print("  Tables: table1~table8")
    print("  Points: point1~point13")
    print("")
    print("Example: python3 test_navigation.py `pinky1` `table1`")
    print("")
    print("Prerequisites:")
    print("  1. Domain Bridge running (all bridges)")
    print("  2. Robot bringup running (ros2 launch pinky_bringup bringup_robot.launch.xml)")
    print("  3. Nav2 running (ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml)")


def main():
    if len(sys.argv) != 3:
        print_usage()
        sys.exit(1)

    # Parse arguments (remove backticks if present)
    robot_name = sys.argv[1].strip('`')
    waypoint_name = sys.argv[2].strip('`')

    # Validate robot
    if robot_name not in ROBOT_DOMAINS:
        print(f"Error: Unknown robot '{robot_name}'")
        print(f"Available robots: {list(ROBOT_DOMAINS.keys())}")
        sys.exit(1)

    # Validate waypoint
    if waypoint_name not in WAYPOINTS:
        print(f"Error: Unknown waypoint '{waypoint_name}'")
        print(f"Available waypoints: {list(WAYPOINTS.keys())}")
        sys.exit(1)

    x, y = WAYPOINTS[waypoint_name]

    print(f"=== Navigation Test ===")
    print(f"Robot: {robot_name} (Domain ID: {ROBOT_DOMAINS[robot_name]})")
    print(f"Target: {waypoint_name} ({x}, {y})")
    print(f"=======================")

    # Initialize ROS2 with domain 25 (FMS domain, via domain bridge)
    rclpy.init()

    nav_client = NavigationClient(robot_name)

    if nav_client.send_goal(x, y, theta=0.0):
        rclpy.spin(nav_client)
    else:
        nav_client.destroy_node()
        rclpy.shutdown()
        sys.exit(1)


if __name__ == '__main__':
    main()
