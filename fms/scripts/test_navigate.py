#!/usr/bin/env python3
"""
Test script for NavigateToPose action
"""
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
import sys

class NavigateTestNode(Node):
    def __init__(self):
        super().__init__('navigate_test_node')
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.get_logger().info("Waiting for NavigateToPose action server...")

    def send_goal(self, x, y, theta=0.0):
        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("NavigateToPose action server not available!")
            return False

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0
        goal_msg.pose.pose.orientation.w = 1.0

        self.get_logger().info(f"Sending goal: x={x}, y={y}")

        send_goal_future = self.nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        send_goal_future.add_done_callback(self.goal_response_callback)
        return True

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(f"Distance remaining: {feedback.distance_remaining:.2f}m")

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Goal rejected!")
            return
        self.get_logger().info("Goal accepted!")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def result_callback(self, future):
        result = future.result().result
        self.get_logger().info(f"Navigation result: {result}")
        rclpy.shutdown()

def main():
    rclpy.init()

    # Default to point13
    x = float(sys.argv[1]) if len(sys.argv) > 1 else 0.585
    y = float(sys.argv[2]) if len(sys.argv) > 2 else 0.63

    node = NavigateTestNode()

    if node.send_goal(x, y):
        rclpy.spin(node)
    else:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
