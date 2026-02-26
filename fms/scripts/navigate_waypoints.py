#!/usr/bin/env python3
"""
Navigation Graph 기반 순차 이동 스크립트
point13 → point3 → table8 → table6 → point2 → table6 → table5 → point6 → table2 → table1

Usage:
    ROS_DOMAIN_ID=11 python3 navigate_waypoints.py
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
import time
import math

# Navigation Graph Waypoints
WAYPOINTS = {
    'pickup_spot': (0.47, 0.63),
    'pinky1_spot': (0.585, 0.085),
    'pinky2_spot': (0.585, 0.255),
    'pinky3_spot': (0.585, 0.915),
    'table1': (1.785, 0.35),
    'table2': (1.415, 0.35),
    'table3': (1.785, 0.65),
    'table4': (1.415, 0.65),
    'table5': (1.235, 0.35),
    'table6': (0.865, 0.35),
    'table7': (1.235, 0.65),
    'table8': (0.865, 0.65),
    'point1': (0.78, 0.15),
    'point2': (0.78, 0.35),
    'point3': (0.78, 0.65),
    'point4': (0.78, 0.85),
    'point5': (1.325, 0.15),
    'point6': (1.325, 0.35),
    'point7': (1.325, 0.65),
    'point8': (1.325, 0.85),
    'point9': (1.85, 0.15),
    'point10': (1.85, 0.35),
    'point11': (1.85, 0.65),
    'point12': (1.85, 0.85),
    'point13': (0.585, 0.63),
}

# point13 → table1 경로 (Navigation Graph 기반)
ROUTE_POINT13_TO_TABLE1 = [
    'point13',   # 시작점
    'point3',    # point13 → point3
    'table8',    # point3 → table8
    'point3',    # table8 → point3 (회귀)
    'point7',    # point3 → ... → point7 (실제로는 직접 연결 없음, 중간 경유 필요)
    'table4',    # point7 → table4
    'table3',    # table4 → table3 (같은 y)
    'point11',   # table3 → point11
    'point10',   # point11 → point10
    'table1',    # point10 → table1
]

# 더 간단한 경로 (직접 연결 기준)
SIMPLE_ROUTE = [
    'point13',  # (0.585, 0.63)
    'point3',   # (0.78, 0.65) - point13과 연결됨
    'point2',   # (0.78, 0.35) - point3과 연결됨
    'table6',   # (0.865, 0.35) - point2와 연결됨
    'table5',   # (1.235, 0.35) - table6 옆
    'point6',   # (1.325, 0.35) - table5와 연결됨
    'table2',   # (1.415, 0.35) - point6과 연결됨
    'table1',   # (1.785, 0.35) - table2 옆
]

# 역방향 경로 (table1 근처에서 point13으로, 다시 table1로)
REVERSE_ROUTE = [
    'table2',   # (1.415, 0.35) - 현재 위치에서 가장 가까운 waypoint
    'point6',   # (1.325, 0.35)
    'table5',   # (1.235, 0.35)
    'table6',   # (0.865, 0.35)
    'point2',   # (0.78, 0.35)
    'point3',   # (0.78, 0.65)
    'point13',  # (0.585, 0.63) - 목표 1
    'point3',   # (0.78, 0.65) - 돌아오기
    'point2',   # (0.78, 0.35)
    'table6',   # (0.865, 0.35)
    'table5',   # (1.235, 0.35)
    'point6',   # (1.325, 0.35)
    'table2',   # (1.415, 0.35)
    'table1',   # (1.785, 0.35) - 목표 2
]


class WaypointNavigator(Node):
    def __init__(self):
        super().__init__('waypoint_navigator')

        # Goal pose publisher
        self.goal_pub = self.create_publisher(
            PoseStamped, '/goal_pose', 10)

        # AMCL pose subscriber
        self.current_pose = None
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose',
            self.pose_callback, 10)

        self.get_logger().info('Waypoint Navigator initialized')
        self.get_logger().info(f'Route: {" -> ".join(REVERSE_ROUTE)}')

    def pose_callback(self, msg):
        self.current_pose = (
            msg.pose.pose.position.x,
            msg.pose.pose.position.y
        )

    def distance_to(self, target_x, target_y):
        if self.current_pose is None:
            return float('inf')
        dx = target_x - self.current_pose[0]
        dy = target_y - self.current_pose[1]
        return math.sqrt(dx*dx + dy*dy)

    def send_goal(self, name):
        x, y = WAYPOINTS[name]

        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.position.x = x
        msg.pose.position.y = y
        msg.pose.position.z = 0.0
        msg.pose.orientation.w = 1.0

        self.goal_pub.publish(msg)
        self.get_logger().info(f'Goal sent: {name} ({x}, {y})')

    def wait_for_arrival(self, name, threshold=0.15, timeout=60.0):
        """목표 도착까지 대기"""
        x, y = WAYPOINTS[name]
        start_time = time.time()

        while time.time() - start_time < timeout:
            rclpy.spin_once(self, timeout_sec=0.5)

            dist = self.distance_to(x, y)
            if dist < threshold:
                self.get_logger().info(f'Arrived at {name}! (dist={dist:.3f}m)')
                return True

            if self.current_pose:
                self.get_logger().info(
                    f'Moving to {name}: current=({self.current_pose[0]:.2f}, {self.current_pose[1]:.2f}), '
                    f'target=({x}, {y}), dist={dist:.2f}m')

        self.get_logger().warn(f'Timeout waiting for {name}')
        return False

    def navigate_route(self, route):
        """경로를 따라 순차 이동"""
        self.get_logger().info('='*50)
        self.get_logger().info('Starting navigation along route')
        self.get_logger().info('='*50)

        for i, waypoint in enumerate(route):
            self.get_logger().info(f'\n[{i+1}/{len(route)}] Navigating to: {waypoint}')

            # 목표 전송
            self.send_goal(waypoint)

            # 도착 대기
            if not self.wait_for_arrival(waypoint):
                self.get_logger().error(f'Failed to reach {waypoint}')
                return False

            # 다음 waypoint 전 잠시 대기
            time.sleep(1.0)

        self.get_logger().info('='*50)
        self.get_logger().info('Navigation complete!')
        self.get_logger().info('='*50)
        return True


def main():
    rclpy.init()

    navigator = WaypointNavigator()

    # 잠시 대기하여 pose 수신
    print('Waiting for initial pose...')
    for _ in range(10):
        rclpy.spin_once(navigator, timeout_sec=0.5)

    try:
        # 역방향 경로 따라 이동 (현재 table1 근처에서 시작)
        navigator.navigate_route(REVERSE_ROUTE)
    except KeyboardInterrupt:
        print('\nNavigation interrupted')
    finally:
        navigator.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
