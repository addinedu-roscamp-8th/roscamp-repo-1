"""
Fleet Controller for Fleet Management System
Manages serving robot fleet (3 robots) and their status
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from geometry_msgs.msg import Pose
import math

logger = logging.getLogger(__name__)


class RobotState:
    """
    Represents the state of a serving robot
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
        """Update robot pose"""
        self.current_pose = pose
        self.last_update = datetime.utcnow()

    def update_battery(self, voltage: float, present: bool):
        """Update battery status"""
        self.battery_voltage = voltage
        self.battery_present = present
        self.last_update = datetime.utcnow()

    def update_status(self, status: str):
        """Update robot status"""
        self.status = status
        self.last_update = datetime.utcnow()
        logger.debug(f"Robot {self.robot_id} status updated to {status}")

    def assign_task(self, task_id: str, order_id: str):
        """Assign task to robot"""
        self.current_task_id = task_id
        self.current_order_id = order_id
        logger.info(f"Robot {self.robot_id} assigned task {task_id}")

    def clear_task(self):
        """Clear current task"""
        self.current_task_id = None
        self.current_order_id = None
        self.target_location = None

    def is_available(self) -> bool:
        """Check if robot is available for new task"""
        return self.status == self.STATUS_IDLE and self.current_task_id is None

    def is_low_battery(self, threshold: float = 0.0) -> bool:
        """Check if battery is low"""
        return self.battery_present and self.battery_voltage < threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert robot state to dictionary"""
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
    Manages serving robot fleet

    Responsibilities:
    - Track status of 3 serving robots (pinky1, pinky2, pinky3)
    - Select best robot for task assignment
    - Monitor robot health (battery, connectivity)
    - Handle robot errors and recovery
    """

    def __init__(self, robot_configs: List[Dict]):
        """
        Initialize fleet controller

        Args:
            robot_configs: List of robot configurations
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
        self.pickup_spot = 'pickup_spot'

        logger.info(f"FleetController initialized with {len(self.robots)} robots")

    def update_robot_pose(self, robot_id: str, pose: Pose):
        """
        Update robot pose

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
        Update robot battery status

        Args:
            robot_id: Robot ID
            voltage: Battery voltage
            present: Battery present flag
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
        Update robot status

        Args:
            robot_id: Robot ID
            status: Robot status
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(status)
        else:
            logger.warning(f"Robot {robot_id} not found")

    def get_available_robot(self) -> Optional[RobotState]:
        """
        Get best available robot for task assignment

        Selection criteria (in priority order):
        1. Robot must be IDLE and have no current task
        2. Robot must not have low battery
        3. Prefer robot closest to pickup spot (TODO: implement distance calculation)

        Returns:
            RobotState object if available, None otherwise
        """
        available_robots = []

        for robot in self.robots.values():
            if robot.is_available() and not robot.is_low_battery():
                available_robots.append(robot)

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
        Assign task to specific robot

        Args:
            robot_id: Robot ID
            task_id: Task ID
            order_id: Order ID

        Returns:
            True if assignment successful, False otherwise
        """
        robot = self.robots.get(robot_id)
        if robot and robot.is_available():
            robot.assign_task(task_id, order_id)
            robot.update_status(RobotState.STATUS_MOVING_TO_PICKUP)
            robot.target_location = self.pickup_spot
            logger.info(f"Assigned task {task_id} to robot {robot_id}")
            return True
        else:
            logger.warning(f"Cannot assign task to robot {robot_id} (not available)")
            return False

    def robot_reached_pickup(self, robot_id: str):
        """
        Mark that robot reached pickup spot

        Args:
            robot_id: Robot ID
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_LOADED)
            logger.info(f"Robot {robot_id} reached pickup spot")

    def robot_start_delivery(self, robot_id: str, table_number: str):
        """
        Mark that robot started delivery to table

        Args:
            robot_id: Robot ID
            table_number: Target table number (T01-T08)
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_MOVING_TO_TABLE)
            robot.target_location = table_number.lower().replace('t', 'table')  # T01 -> table1
            logger.info(f"Robot {robot_id} started delivery to {table_number}")

    def robot_reached_table(self, robot_id: str):
        """
        Mark that robot reached table

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

        Args:
            robot_id: Robot ID
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_RETURNING)
            parking_spot = self.parking_spots.get(robot_id)
            robot.target_location = parking_spot
            logger.info(f"Robot {robot_id} completed delivery, returning to {parking_spot}")

    def robot_returned_home(self, robot_id: str):
        """
        Mark that robot returned to parking spot

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
        Handle robot error

        Args:
            robot_id: Robot ID
            error_message: Error message
        """
        robot = self.robots.get(robot_id)
        if robot:
            robot.update_status(RobotState.STATUS_ERROR)
            logger.error(f"Robot {robot_id} encountered error: {error_message}")

    def get_robot(self, robot_id: str) -> Optional[RobotState]:
        """
        Get robot state by ID

        Args:
            robot_id: Robot ID

        Returns:
            RobotState object if found, None otherwise
        """
        return self.robots.get(robot_id)

    def get_all_robots(self) -> List[RobotState]:
        """
        Get all robot states

        Returns:
            List of RobotState objects
        """
        return list(self.robots.values())

    def get_fleet_status_summary(self) -> Dict[str, Any]:
        """
        Get fleet status summary

        Returns:
            Dictionary with fleet status information
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
        Calculate Euclidean distance between two poses

        Args:
            pose1: First pose
            pose2: Second pose

        Returns:
            Distance in meters
        """
        dx = pose2.position.x - pose1.position.x
        dy = pose2.position.y - pose1.position.y
        return math.sqrt(dx * dx + dy * dy)
