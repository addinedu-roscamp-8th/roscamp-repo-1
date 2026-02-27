"""
Fleet Management System용 Fleet Controller
서빙 로봇 함대(3대)와 그들의 상태를 관리합니다
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from geometry_msgs.msg import Pose
import math

logger = logging.getLogger(__name__)


class RobotState:
    """
    서빙 로봇의 상태를 나타냅니다
    """

    # Robot status states
    STATUS_IDLE = 'IDLE'
    STATUS_MOVING_TO_PICKUP = 'MOVING_TO_PICKUP'
    STATUS_LOADED = 'LOADED'
    STATUS_MOVING_TO_TABLE = 'MOVING_TO_TABLE'
    STATUS_DELIVERING = 'DELIVERING'
    STATUS_RETURNING = 'RETURNING'
    STATUS_ERROR = 'ERROR'

    def __init__(self, robot_id: str, domain_id: int):
        self.robot_id = robot_id  # pinky1, pinky2, pinky3
        self.domain_id = domain_id  # ROS_DOMAIN_ID: 11, 12, 13
        self.status = self.STATUS_IDLE
        self.current_pose = None
        self.battery_voltage = 0.0
        self.battery_present = False
        self.current_task_id = None
        self.current_order_id = None
        self.target_location = None  # pickup_spot, table1-8, or parking spot
        self.last_update = datetime.utcnow()

    def update_pose(self, pose: Pose):
        """로봇 pose를 업데이트합니다"""
        self.current_pose = pose
        self.last_update = datetime.utcnow()

    def update_battery(self, voltage: float, present: bool):
        """배터리 상태를 업데이트합니다"""
        self.battery_voltage = voltage
        self.battery_present = present
        self.last_update = datetime.utcnow()

    def update_status(self, status: str):
        """로봇 상태를 업데이트합니다"""
        self.status = status
        self.last_update = datetime.utcnow()
        logger.debug(f"Robot {self.robot_id} status updated to {status}")

    def assign_task(self, task_id: str, order_id: str):
        """로봇에 task를 할당합니다"""
        self.current_task_id = task_id
        self.current_order_id = order_id
        logger.info(f"Robot {self.robot_id} assigned task {task_id}")

    def clear_task(self):
        """현재 task를 클리어합니다"""
        self.current_task_id = None
        self.current_order_id = None
        self.target_location = None

    def is_available(self) -> bool:
        """로봇이 새로운 task를 수행할 수 있는지 확인합니다

        로봇이 가용한 조건:
        - 최근에 POSE 데이터를 수신함 (10초 이내)
        - 상태가 IDLE (오류 또는 작업 중 상태가 아님)
        - 현재 할당된 task가 없음
        - 현재 할당된 order가 없음
        """
        # Check if robot is online (received POSE data within last 10 seconds)
        POSE_TIMEOUT_SECONDS = 10.0
        time_since_update = (datetime.utcnow() - self.last_update).total_seconds()
        if time_since_update > POSE_TIMEOUT_SECONDS:
            logger.debug(f"Robot {self.robot_id} offline (no POSE for {time_since_update:.1f}s)")
            return False
        if self.status == self.STATUS_ERROR:
            return False
        if self.status != self.STATUS_IDLE:
            return False
        if self.current_task_id is not None:
            return False
        if self.current_order_id is not None:
            return False
        return True

    def is_low_battery(self, threshold: float = 0.0) -> bool:
        """배터리가 낮은지 확인합니다"""
        return self.battery_present and self.battery_voltage < threshold

    def to_dict(self) -> Dict[str, Any]:
        """로봇 상태를 dictionary로 변환합니다"""
        return {
            'robot_id': self.robot_id,
            'domain_id': self.domain_id,
            'status': self.status,
            'current_pose': {
                'position': {
                    'x': self.current_pose.position.x if self.current_pose else 0.0,
                    'y': self.current_pose.position.y if self.current_pose else 0.0,
                    'z': self.current_pose.position.z if self.current_pose else 0.0
                },
                'orientation': {
                    'x': self.current_pose.orientation.x if self.current_pose else 0.0,
                    'y': self.current_pose.orientation.y if self.current_pose else 0.0,
                    'z': self.current_pose.orientation.z if self.current_pose else 0.0,
                    'w': self.current_pose.orientation.w if self.current_pose else 1.0
                }
            } if self.current_pose else None,
            'battery_voltage': self.battery_voltage,
            'battery_present': self.battery_present,
            'current_task_id': self.current_task_id,
            'current_order_id': self.current_order_id,
            'target_location': self.target_location,
            'last_update': self.last_update.isoformat()
        }


class FleetController:
    """
    서빙 로봇 함대를 관리합니다

    책임:
    - 3대의 서빙 로봇 (pinky1, pinky2, pinky3) 상태 추적
    - task 할당을 위한 최적 로봇 선택
    - 로봇 상태 모니터링 (배터리, 연결성)
    - 로봇 오류 처리 및 복구
    """

    def __init__(self, robot_configs: List[Dict]):
        """
        Fleet controller를 초기화합니다

        Args:
            robot_configs: 로봇 설정 목록
                [{
                    'robot_id': 'pinky1',
                    'domain_id': 11
                }, ...]
        """
        self.robots = {}  # {robot_id: RobotState}

        # Initialize robot states
        for config in robot_configs:
            robot_id = config['robot_id']
            domain_id = config.get('domain_id', 0)
            # Skip disabled robots
            if config.get('enabled', True) is False:
                logger.info(f"Skipping disabled robot {robot_id}")
                continue
            self.robots[robot_id] = RobotState(robot_id, domain_id)
            logger.info(f"Initialized robot {robot_id} with DOMAIN_ID={domain_id}")

        # Parking spot positions (TODO: Load from config file)
        self.parking_spots = {
            'pinky1': 'pinky1_spot',
            'pinky2': 'pinky2_spot',
            'pinky3': 'pinky3_spot'
        }

        # Pickup spot position
        # Robot moves directly to pickup_spot for food loading
        self.pickup_spot = 'pickup_spot'

        logger.info(f"FleetController initialized with {len(self.robots)} robots")

    def update_robot_pose(self, robot_id: str, pose: Pose):
        """
        로봇 pose를 업데이트합니다

        Args:
            robot_id: Robot ID
            pose: Robot pose
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_pose(pose)
        else:
            logger.warning(f"Robot {robot_id} not found")

    def update_robot_battery(self, robot_id: str, voltage: float, present: bool):
        """
        로봇 배터리 상태를 업데이트합니다

        Args:
            robot_id: Robot ID
            voltage: 배터리 전압
            present: 배터리 존재 여부 flag
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_battery(voltage, present)

            # Check for low battery
            if robot.is_low_battery():
                logger.warning(f"Robot {robot_id} has low battery: {voltage}V")
        else:
            logger.warning(f"Robot {robot_id} not found")

    def update_robot_status(self, robot_id: str, status: str):
        """
        로봇 상태를 업데이트합니다

        Args:
            robot_id: Robot ID
            status: 로봇 상태
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(status)
        else:
            logger.warning(f"Robot {robot_id} not found")

    def get_available_robots(self) -> List[RobotState]:
        """
        모든 가용 로봇 목록을 가져옵니다

        가용성 기준:
        - status == STATUS_IDLE
        - current_task_id가 None
        - current_order_id가 None
        - 오류 상태가 아님
        - 배터리가 충분함 (선택적 threshold)

        Returns:
            가용한 RobotState 객체 목록
        """
        available = []
        for robot in self.robots.values():
            if self._is_robot_available(robot):
                available.append(robot)

        logger.debug(f"Available robots: {[r.robot_id for r in available]}")
        return available

    def _is_robot_available(self, robot: RobotState) -> bool:
        """
        특정 로봇이 새로운 task 할당을 받을 수 있는지 확인합니다

        Args:
            robot: 확인할 RobotState 객체

        Returns:
            로봇이 새로운 task를 받을 수 있으면 True, 아니면 False
        """
        # Check basic availability (status and task assignment)
        if not robot.is_available():
            return False

        # Check battery level
        if robot.is_low_battery():
            logger.debug(f"Robot {robot.robot_id} has low battery, not available")
            return False

        return True

    def get_available_robot(self) -> Optional[RobotState]:
        """
        task 할당을 위한 최적의 가용 로봇을 가져옵니다

        선택 기준 (우선순위 순):
        1. 로봇이 IDLE 상태이고 현재 task가 없어야 함
        2. 배터리가 충분해야 함
        3. pickup spot에 가장 가까운 로봇 우선 (TODO: 거리 계산 구현)

        Returns:
            가용한 경우 RobotState 객체, 아니면 None
        """
        available_robots = self.get_available_robots()

        if not available_robots:
            logger.debug("No available robots")
            return None

        # For now, return first available robot
        # TODO: Implement distance-based selection
        selected_robot = available_robots[0]
        logger.info(f"Selected robot {selected_robot.robot_id} for task assignment")
        return selected_robot

    def assign_task_to_robot(self, robot_id: str, task_id: str, order_id: str) -> bool:
        """
        특정 로봇에 task를 할당합니다

        Args:
            robot_id: Robot ID
            task_id: Task ID
            order_id: Order ID

        Returns:
            할당 성공 시 True, 실패 시 False
        """
        robot = self.robots.get(robot_id)
        if robot and self._is_robot_available(robot):
            robot.assign_task(task_id, order_id)
            robot.update_status(RobotState.STATUS_MOVING_TO_PICKUP)
            robot.target_location = self.pickup_spot
            logger.info(f"Assigned task {task_id} to robot {robot_id}")
            return True
        else:
            logger.warning(f"Cannot assign task to robot {robot_id} (not available)")
            return False

    def mark_robot_busy(self, robot_id: str, status: str = None) -> bool:
        """
        로봇을 사용 중으로 표시합니다

        Args:
            robot_id: Robot ID
            status: 선택적 특정 상태 (기본값: STATUS_MOVING_TO_PICKUP)

        Returns:
            성공 시 True, 로봇을 찾지 못한 경우 False
        """
        robot = self.robots.get(robot_id)
        if robot:
            new_status = status if status else RobotState.STATUS_MOVING_TO_PICKUP
            robot.update_status(new_status)
            logger.info(f"Robot {robot_id} marked as busy ({new_status})")
            return True
        else:
            logger.warning(f"Robot {robot_id} not found for mark_robot_busy")
            return False

    def mark_robot_available(self, robot_id: str) -> bool:
        """
        로봇을 가용(idle) 상태로 표시합니다

        현재 task를 클리어하고 상태를 IDLE로 설정합니다.

        Args:
            robot_id: Robot ID

        Returns:
            성공 시 True, 로봇을 찾지 못한 경우 False
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_IDLE)
            robot.clear_task()
            logger.info(f"Robot {robot_id} marked as available (IDLE)")
            return True
        else:
            logger.warning(f"Robot {robot_id} not found for mark_robot_available")
            return False

    def robot_reached_pickup(self, robot_id: str):
        """
        로봇이 pickup spot에 도달했음을 표시합니다

        Args:
            robot_id: Robot ID
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_LOADED)
            logger.info(f"Robot {robot_id} reached pickup spot")

    def robot_start_delivery(self, robot_id: str, table_number: str):
        """
        로봇이 테이블로 배달을 시작했음을 표시합니다

        Args:
            robot_id: Robot ID
            table_number: 목표 테이블 번호 (T01-T08)
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_MOVING_TO_TABLE)
            robot.target_location = table_number.lower().replace('t', 'table')  # T01 -> table1
            logger.info(f"Robot {robot_id} started delivery to {table_number}")

    def robot_reached_table(self, robot_id: str):
        """
        로봇이 테이블에 도달했음을 표시합니다

        Args:
            robot_id: Robot ID
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_DELIVERING)
            logger.info(f"Robot {robot_id} reached table")

    def robot_complete_delivery(self, robot_id: str):
        """
        Mark that robot completed delivery
        수령 확인 시 pinky1 home으로 복귀

        Args:
            robot_id: Robot ID
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_RETURNING)
            parking_spot = self.parking_spots.get(robot_id)
            robot.target_location = parking_spot
            logger.info(f"Robot {robot_id} delivery confirmed, returning to home ({parking_spot})")

    def get_home_location(self, robot_id: str) -> str:
        """
        로봇의 home (parking) 위치를 가져옵니다

        Args:
            robot_id: Robot ID

        Returns:
            Home 위치 이름 (예: 'pinky1_spot')
        """
        return self.parking_spots.get(robot_id, f"{robot_id}_spot")

    def robot_returned_home(self, robot_id: str):
        """
        로봇이 parking spot으로 복귀했음을 표시합니다

        Args:
            robot_id: Robot ID
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_IDLE)
            robot.clear_task()
            logger.info(f"Robot {robot_id} returned to parking spot, now IDLE")

    def robot_error(self, robot_id: str, error_message: str = None):
        """
        로봇 오류를 처리합니다

        Args:
            robot_id: Robot ID
            error_message: 오류 메시지
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_ERROR)
            logger.error(f"Robot {robot_id} encountered error: {error_message}")

    def get_robot(self, robot_id: str) -> Optional[RobotState]:
        """
        ID로 로봇 상태를 가져옵니다

        Args:
            robot_id: Robot ID

        Returns:
            찾으면 RobotState 객체, 아니면 None
        """
        return self.robots.get(robot_id)

    def get_all_robots(self) -> List[RobotState]:
        """
        모든 로봇 상태를 가져옵니다

        Returns:
            RobotState 객체 목록
        """
        return list(self.robots.values())

    def get_fleet_status_summary(self) -> Dict[str, Any]:
        """
        함대 상태 요약을 가져옵니다

        Returns:
            함대 상태 정보를 담은 dictionary
        """
        return {
            'total_robots': len(self.robots),
            'idle_robots': sum(1 for r in self.robots.values() if r.status == RobotState.STATUS_IDLE),
            'busy_robots': sum(1 for r in self.robots.values() if r.status != RobotState.STATUS_IDLE and r.status != RobotState.STATUS_ERROR),
            'error_robots': sum(1 for r in self.robots.values() if r.status == RobotState.STATUS_ERROR),
            'low_battery_robots': sum(1 for r in self.robots.values() if r.is_low_battery()),
            'robots': [r.to_dict() for r in self.robots.values()]
        }

    def calculate_distance(self, pose1: Pose, pose2: Pose) -> float:
        """
        두 pose 간의 유클리드 거리를 계산합니다

        Args:
            pose1: 첫 번째 pose
            pose2: 두 번째 pose

        Returns:
            미터 단위 거리
        """
        dx = pose2.position.x - pose1.position.x
        dy = pose2.position.y - pose1.position.y
        return math.sqrt(dx * dx + dy * dy)
