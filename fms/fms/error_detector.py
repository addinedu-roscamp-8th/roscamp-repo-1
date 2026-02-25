"""
Error Detection and Monitoring System for FMS
Detects serving errors and triggers appropriate responses

Error Types:
- NAV_FAILED: Navigation action failed (ABORTED, CANCELED)
- COMM_LOST: Robot communication heartbeat timeout
- LOW_BATTERY: Battery voltage below threshold
- TIMEOUT: Task execution timeout (pickup or delivery)
- OBSTACLE: Persistent obstacle blocking navigation
"""

import logging
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
from geometry_msgs.msg import Pose

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Error types for robot serving"""
    NAV_FAILED = 'NAV_FAILED'          # Navigation action failed
    COMM_LOST = 'COMM_LOST'            # Communication lost (heartbeat timeout)
    LOW_BATTERY = 'LOW_BATTERY'        # Battery below threshold
    TIMEOUT = 'TIMEOUT'                # Task timeout
    OBSTACLE = 'OBSTACLE'              # Obstacle blocking path


class RobotError:
    """Represents a robot error"""

    def __init__(self, robot_id: str, error_type: ErrorType, error_message: str,
                 current_pose: Optional[Pose] = None, battery_voltage: float = 0.0):
        """
        Initialize robot error

        Args:
            robot_id: Robot ID
            error_type: Type of error
            error_message: Human-readable error message
            current_pose: Robot's position when error occurred
            battery_voltage: Battery voltage at time of error
        """
        self.robot_id = robot_id
        self.error_type = error_type
        self.error_message = error_message
        self.current_pose = current_pose
        self.battery_voltage = battery_voltage
        self.created_at = datetime.utcnow()
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3

    def can_retry(self) -> bool:
        """Check if error can be retried"""
        return self.recovery_attempts < self.max_recovery_attempts

    def increment_retry(self):
        """Increment recovery attempt counter"""
        self.recovery_attempts += 1

    def to_dict(self):
        """Convert to dictionary for message"""
        return {
            'robot_id': self.robot_id,
            'error_type': self.error_type.value,
            'error_message': self.error_message,
            'battery_voltage': self.battery_voltage,
            'recovery_attempts': self.recovery_attempts,
            'created_at': self.created_at.isoformat(),
            'pose': {
                'x': self.current_pose.position.x if self.current_pose else 0.0,
                'y': self.current_pose.position.y if self.current_pose else 0.0,
                'z': self.current_pose.position.z if self.current_pose else 0.0,
            } if self.current_pose else None
        }


class ErrorDetector:
    """
    Detects and tracks robot serving errors

    Monitors:
    - Navigation failures (action ABORTED/CANCELED)
    - Communication loss (heartbeat timeout)
    - Low battery conditions
    - Task timeouts (pickup and delivery)
    - Obstacles blocking navigation
    """

    def __init__(self):
        """Initialize error detector"""
        self.active_errors: Dict[str, RobotError] = {}  # {robot_id: RobotError}
        self.error_history: Dict[str, list] = {}  # {robot_id: [RobotError]}
        self.heartbeat_timestamps: Dict[str, datetime] = {}  # {robot_id: last_heartbeat}

        # Configuration
        self.heartbeat_timeout = 5.0  # seconds
        self.battery_low_threshold = 0.0  # voltage
        self.pickup_timeout = 60.0  # seconds
        self.delivery_timeout = 120.0  # seconds
        self.nav_retry_timeout = 10.0  # seconds before considering nav failed

        logger.info("ErrorDetector initialized")

    def register_heartbeat(self, robot_id: str):
        """
        Register robot heartbeat (pose update)

        Args:
            robot_id: Robot ID
        """
        self.heartbeat_timestamps[robot_id] = datetime.utcnow()

        # Clear COMM_LOST error if robot comes back online
        if robot_id in self.active_errors:
            error = self.active_errors[robot_id]
            if error.error_type == ErrorType.COMM_LOST:
                logger.info(f"Robot {robot_id} heartbeat restored, clearing COMM_LOST error")
                self._clear_error(robot_id)

    def check_communication_loss(self, robot_id: str) -> Optional[RobotError]:
        """
        Check if robot has lost communication (heartbeat timeout)

        Args:
            robot_id: Robot ID

        Returns:
            RobotError if communication lost, None otherwise
        """
        last_heartbeat = self.heartbeat_timestamps.get(robot_id)
        if not last_heartbeat:
            return None

        elapsed = (datetime.utcnow() - last_heartbeat).total_seconds()

        if elapsed > self.heartbeat_timeout:
            if robot_id not in self.active_errors or \
               self.active_errors[robot_id].error_type != ErrorType.COMM_LOST:
                error = RobotError(
                    robot_id=robot_id,
                    error_type=ErrorType.COMM_LOST,
                    error_message=f"No heartbeat for {elapsed:.1f}s (threshold: {self.heartbeat_timeout}s)"
                )
                logger.error(f"Communication lost with robot {robot_id}: {error.error_message}")
                return error

        return None

    def check_low_battery(self, robot_id: str, battery_voltage: float,
                          current_pose: Optional[Pose] = None) -> Optional[RobotError]:
        """
        Check if robot battery is low

        Args:
            robot_id: Robot ID
            battery_voltage: Current battery voltage
            current_pose: Robot's current position

        Returns:
            RobotError if battery low, None otherwise
        """
        if battery_voltage < self.battery_low_threshold:
            if robot_id not in self.active_errors or \
               self.active_errors[robot_id].error_type != ErrorType.LOW_BATTERY:
                error = RobotError(
                    robot_id=robot_id,
                    error_type=ErrorType.LOW_BATTERY,
                    error_message=f"Battery low: {battery_voltage:.1f}V (threshold: {self.battery_low_threshold}V)",
                    current_pose=current_pose,
                    battery_voltage=battery_voltage
                )
                logger.warning(f"Low battery detected on robot {robot_id}: {error.error_message}")
                return error

        return None

    def check_navigation_failure(self, robot_id: str, nav_goal_state: str,
                                  current_pose: Optional[Pose] = None) -> Optional[RobotError]:
        """
        Check if navigation action failed

        Args:
            robot_id: Robot ID
            nav_goal_state: Navigation goal state (SUCCEEDED, ABORTED, CANCELED, etc.)
            current_pose: Robot's current position

        Returns:
            RobotError if navigation failed, None otherwise
        """
        if nav_goal_state in ['ABORTED', 'CANCELED', 'FAILED']:
            error = RobotError(
                robot_id=robot_id,
                error_type=ErrorType.NAV_FAILED,
                error_message=f"Navigation failed: {nav_goal_state}",
                current_pose=current_pose
            )
            logger.error(f"Navigation failure for robot {robot_id}: {error.error_message}")
            return error

        return None

    def check_task_timeout(self, robot_id: str, task_start_time: datetime,
                          task_type: str, current_pose: Optional[Pose] = None) -> Optional[RobotError]:
        """
        Check if task has timed out

        Args:
            robot_id: Robot ID
            task_start_time: When task started
            task_type: Type of task ('pickup' or 'delivery')
            current_pose: Robot's current position

        Returns:
            RobotError if task timed out, None otherwise
        """
        # Determine timeout threshold
        timeout_threshold = self.pickup_timeout if task_type == 'pickup' else self.delivery_timeout

        elapsed = (datetime.utcnow() - task_start_time).total_seconds()

        if elapsed > timeout_threshold:
            error = RobotError(
                robot_id=robot_id,
                error_type=ErrorType.TIMEOUT,
                error_message=f"Task timeout ({task_type}): {elapsed:.0f}s > {timeout_threshold}s",
                current_pose=current_pose
            )
            logger.error(f"Task timeout for robot {robot_id}: {error.error_message}")
            return error

        return None

    def register_error(self, error: RobotError) -> bool:
        """
        Register a detected error

        Args:
            error: RobotError object

        Returns:
            True if new error was added, False if error already exists
        """
        robot_id = error.robot_id

        # Check if error already exists for this robot
        if robot_id in self.active_errors:
            existing = self.active_errors[robot_id]
            # Only replace if it's a different error type
            if existing.error_type == error.error_type:
                logger.debug(f"Error already active for {robot_id}: {error.error_type.value}")
                return False

        # Store in active errors
        self.active_errors[robot_id] = error

        # Store in history
        if robot_id not in self.error_history:
            self.error_history[robot_id] = []
        self.error_history[robot_id].append(error)

        logger.warning(f"Error registered for robot {robot_id}: {error.error_type.value}")
        return True

    def has_error(self, robot_id: str) -> bool:
        """
        Check if robot has active error

        Args:
            robot_id: Robot ID

        Returns:
            True if robot has active error, False otherwise
        """
        return robot_id in self.active_errors

    def get_error(self, robot_id: str) -> Optional[RobotError]:
        """
        Get active error for robot

        Args:
            robot_id: Robot ID

        Returns:
            RobotError if exists, None otherwise
        """
        return self.active_errors.get(robot_id)

    def get_all_errors(self) -> Dict[str, RobotError]:
        """
        Get all active errors

        Returns:
            Dictionary of {robot_id: RobotError}
        """
        return dict(self.active_errors)

    def get_error_count(self) -> int:
        """Get count of robots with active errors"""
        return len(self.active_errors)

    def _clear_error(self, robot_id: str):
        """
        Clear error for robot (internal method)

        Args:
            robot_id: Robot ID
        """
        if robot_id in self.active_errors:
            error = self.active_errors.pop(robot_id)
            logger.info(f"Error cleared for robot {robot_id}: {error.error_type.value}")

    def clear_error(self, robot_id: str) -> bool:
        """
        Manually clear error for robot (operator action)

        Args:
            robot_id: Robot ID

        Returns:
            True if error was cleared, False if no error existed
        """
        if robot_id in self.active_errors:
            self._clear_error(robot_id)
            return True
        return False

    def get_error_statistics(self) -> Dict:
        """
        Get error statistics

        Returns:
            Dictionary with error stats
        """
        error_counts = {}
        for error in self.active_errors.values():
            error_type = error.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        # Count robots in error
        error_robots = set(self.active_errors.keys())

        return {
            'total_errors': len(self.active_errors),
            'error_robots': list(error_robots),
            'error_types': error_counts,
            'error_details': [e.to_dict() for e in self.active_errors.values()]
        }

    def get_error_history(self, robot_id: str, limit: int = 10) -> list:
        """
        Get error history for a robot

        Args:
            robot_id: Robot ID
            limit: Maximum number of errors to return

        Returns:
            List of RobotError objects
        """
        history = self.error_history.get(robot_id, [])
        return history[-limit:]
