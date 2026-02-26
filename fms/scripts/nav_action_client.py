#!/usr/bin/env python3
"""
Nav2 Action Client - NavigateToPose 사용
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
import sys

class Nav2ActionClient(Node):
    def __init__(self):
        super().__init__('nav2_action_client')
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.get_logger().info('Waiting for navigate_to_pose action server...')
        self._action_client.wait_for_server()
        self.get_logger().info('Action server connected!')

    def send_goal(self, x, y, name="target"):
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0
        goal_msg.pose.pose.orientation.w = 1.0

        self.get_logger().info(f'Sending goal: {name} ({x}, {y})')

        send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        send_goal_future.add_done_callback(self.goal_response_callback)
        return send_goal_future

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected!')
            return

        self.get_logger().info('Goal accepted!')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result().result
        status = future.result().status

        if status == 4:  # SUCCEEDED
            self.get_logger().info('Goal reached successfully!')
        elif status == 5:  # CANCELED
            self.get_logger().warn('Goal was canceled')
        elif status == 6:  # ABORTED
            self.get_logger().error('Goal was aborted')
        else:
            self.get_logger().info(f'Goal finished with status: {status}')

        rclpy.shutdown()

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        current = feedback.current_pose.pose.position
        self.get_logger().info(
            f'Current position: ({current.x:.2f}, {current.y:.2f}), '
            f'Distance remaining: {feedback.distance_remaining:.2f}m'
        )


def main():
    rclpy.init()

    # Default target: table2
    x = 1.415
    y = 0.35
    name = "table2"

    if len(sys.argv) >= 3:
        x = float(sys.argv[1])
        y = float(sys.argv[2])
        name = sys.argv[3] if len(sys.argv) > 3 else "custom"

    client = Nav2ActionClient()
    client.send_goal(x, y, name)

    try:
        rclpy.spin(client)
    except KeyboardInterrupt:
        print('\nNavigation canceled')
    finally:
        client.destroy_node()


if __name__ == '__main__':
    main()
