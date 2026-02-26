#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Navigate Pinky1 Script

pinky1 로봇을 point13에서 table1으로 순차 이동시키는 스크립트입니다.

Architecture:
- Main PC (ROS_DOMAIN_ID=25)에서 실행
- Domain Bridge를 통해 /pinky1/navigate_to_pose action 사용
- 순차 이동: point13 (x=0.585, y=0.63) -> table1 (x=1.785, y=0.35)

Usage:
    # Domain Bridge 먼저 실행 (별도 터미널)
    ros2 run domain_bridge domain_bridge \
        /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml

    # 이 스크립트 실행 (ROS_DOMAIN_ID=25)
    ROS_DOMAIN_ID=25 python3 navigate_pinky1.py

Author: Kitchmatics FMS Team
Date: 2026-02-25
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.action.client import ClientGoalHandle, GoalStatus
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from action_msgs.msg import GoalStatus as GoalStatusMsg
import math
import time
from typing import List, Tuple, Optional


class NavigatePinky1Node(Node):
    """
    pinky1 로봇을 순차적으로 이동시키는 ROS 2 노드

    waypoints:
        1. point13: (x=0.585, y=0.63, theta=0.0)
        2. table1:  (x=1.785, y=0.35, theta=0.0)
    """

    def __init__(self):
        super().__init__('navigate_pinky1_node')

        self.get_logger().info('='*60)
        self.get_logger().info('Navigate Pinky1 Node Initializing...')
        self.get_logger().info('='*60)

        # Navigation waypoints: (name, x, y, theta)
        self.waypoints: List[Tuple[str, float, float, float]] = [
            ('point13', 0.585, 0.63, 0.0),
            ('table1', 1.785, 0.35, 0.0),
        ]

        self.current_waypoint_index = 0
        self.navigation_complete = False
        self.goal_handle: Optional[ClientGoalHandle] = None

        # Action client for /pinky1/navigate_to_pose
        # Domain Bridge가 Main PC (DOMAIN_ID=25)에서 pinky1 (DOMAIN_ID=11)로 전달
        self._action_client = ActionClient(
            self,
            NavigateToPose,
            '/pinky1/navigate_to_pose'
        )

        self.get_logger().info('Waiting for /pinky1/navigate_to_pose action server...')

        # Action server 연결 대기
        if not self._action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('Action server not available!')
            self.get_logger().error('Domain Bridge가 실행 중인지 확인하세요:')
            self.get_logger().error('  ros2 run domain_bridge domain_bridge \\')
            self.get_logger().error('    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml')
            return

        self.get_logger().info('Action server connected!')
        self.get_logger().info('')
        self.get_logger().info('Navigation Plan:')
        for i, (name, x, y, theta) in enumerate(self.waypoints):
            self.get_logger().info(f'  {i+1}. {name}: (x={x}, y={y}, theta={theta})')
        self.get_logger().info('')

        # 첫 번째 목표로 이동 시작
        self.send_next_goal()

    def theta_to_quaternion(self, theta: float) -> Tuple[float, float, float, float]:
        """
        theta (yaw angle in radians)를 quaternion으로 변환

        theta=0.0일 때:
            - z = sin(0/2) = 0.0
            - w = cos(0/2) = 1.0

        Args:
            theta: Yaw angle in radians

        Returns:
            Tuple of (x, y, z, w) quaternion values
        """
        # 2D navigation에서는 x, y 회전 없음
        qx = 0.0
        qy = 0.0
        qz = math.sin(theta / 2.0)
        qw = math.cos(theta / 2.0)
        return (qx, qy, qz, qw)

    def send_next_goal(self):
        """다음 waypoint로 이동 목표 전송"""
        if self.current_waypoint_index >= len(self.waypoints):
            self.get_logger().info('='*60)
            self.get_logger().info('All waypoints reached! Navigation complete.')
            self.get_logger().info('='*60)
            self.navigation_complete = True
            return

        name, x, y, theta = self.waypoints[self.current_waypoint_index]

        self.get_logger().info('-'*60)
        self.get_logger().info(f'Sending goal [{self.current_waypoint_index + 1}/{len(self.waypoints)}]: {name}')
        self.get_logger().info(f'  Position: x={x}, y={y}')
        self.get_logger().info(f'  Orientation: theta={theta} rad')

        # Create goal message
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()

        # Set position
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0

        # Set orientation (theta=0.0 -> z=0, w=1)
        qx, qy, qz, qw = self.theta_to_quaternion(theta)
        goal_msg.pose.pose.orientation.x = qx
        goal_msg.pose.pose.orientation.y = qy
        goal_msg.pose.pose.orientation.z = qz
        goal_msg.pose.pose.orientation.w = qw

        self.get_logger().info(f'  Quaternion: (x={qx}, y={qy}, z={qz}, w={qw})')

        # Send goal with callbacks
        send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        """Goal이 수락되었는지 확인하는 콜백"""
        self.goal_handle = future.result()

        if not self.goal_handle.accepted:
            self.get_logger().error('Goal rejected!')
            return

        self.get_logger().info('Goal accepted!')

        # Result 콜백 등록
        result_future = self.goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def feedback_callback(self, feedback_msg):
        """Navigation 진행 상황 피드백 콜백"""
        feedback = feedback_msg.feedback

        # Current pose from feedback
        current_pose = feedback.current_pose.pose
        x = current_pose.position.x
        y = current_pose.position.y

        # Distance remaining (if available)
        distance_remaining = feedback.distance_remaining if hasattr(feedback, 'distance_remaining') else 0.0

        # Navigation time (if available)
        nav_time = feedback.navigation_time.sec if hasattr(feedback, 'navigation_time') else 0

        name = self.waypoints[self.current_waypoint_index][0]
        self.get_logger().info(
            f'[Feedback] {name}: pos=({x:.3f}, {y:.3f}), '
            f'dist_remaining={distance_remaining:.3f}m, time={nav_time}s'
        )

    def result_callback(self, future):
        """Navigation 결과 콜백"""
        result = future.result()
        status = result.status

        name = self.waypoints[self.current_waypoint_index][0]

        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f'[Result] {name}: SUCCEEDED!')
            self.get_logger().info(f'  Waypoint {self.current_waypoint_index + 1}/{len(self.waypoints)} reached.')

            # 다음 waypoint로 이동
            self.current_waypoint_index += 1

            # 잠시 대기 후 다음 목표 전송
            time.sleep(1.0)
            self.send_next_goal()

        elif status == GoalStatus.STATUS_ABORTED:
            self.get_logger().error(f'[Result] {name}: ABORTED!')
            self.get_logger().error('Navigation was aborted. Check for obstacles or path planning issues.')

        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().warn(f'[Result] {name}: CANCELED!')
            self.get_logger().warn('Navigation was canceled.')

        else:
            self.get_logger().error(f'[Result] {name}: Unknown status {status}')


def main(args=None):
    """Main entry point"""
    rclpy.init(args=args)

    print('='*60)
    print('Pinky1 Sequential Navigation Script')
    print('='*60)
    print('')
    print('Prerequisites:')
    print('  1. Domain Bridge must be running:')
    print('     ros2 run domain_bridge domain_bridge \\')
    print('       /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml')
    print('')
    print('  2. pinky1 robot must be running with Nav2 stack (DOMAIN_ID=11)')
    print('')
    print('  3. This script runs on Main PC (DOMAIN_ID=25)')
    print('='*60)
    print('')

    try:
        node = NavigatePinky1Node()

        # Spin until navigation is complete
        while rclpy.ok() and not node.navigation_complete:
            rclpy.spin_once(node, timeout_sec=0.1)

        # Final spin to process remaining callbacks
        for _ in range(10):
            rclpy.spin_once(node, timeout_sec=0.1)

        node.get_logger().info('Node shutting down.')
        node.destroy_node()

    except KeyboardInterrupt:
        print('\nNavigation interrupted by user.')
    except Exception as e:
        print(f'Error: {e}')
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
