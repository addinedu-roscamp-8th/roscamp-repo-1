"""
Task Scheduler for Multi-Robot Fleet Management

Handles:
- Task queue management (FIFO)
- Robot-to-task assignment
- Pickup spot access control (only 1 robot at a time)
- Robot waiting strategy (waiting zone designation)
- Collision avoidance coordination
"""

import logging
from typing import Dict, List, Optional, Tuple, Set
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
import uuid

try:
    from .task_manager import Task
    from .zone_manager import ZoneManager
except ImportError:
    # Allow standalone imports
    from task_manager import Task
    from zone_manager import ZoneManager

logger = logging.getLogger(__name__)


class TaskState(Enum):
    """Task lifecycle states"""
    PENDING = "PENDING"                    # Waiting to be assigned
    ASSIGNED = "ASSIGNED"                  # Assigned to robot
    MOVING_TO_PICKUP = "MOVING_TO_PICKUP" # Robot heading to pickup
    WAITING_FOR_PICKUP = "WAITING_FOR_PICKUP"  # Robot waiting for pickup slot
    AT_PICKUP = "AT_PICKUP"                # Robot at pickup slot (loading)
    LOADED = "LOADED"                      # Food loaded, heading to table
    MOVING_TO_TABLE = "MOVING_TO_TABLE"   # Robot heading to table
    AT_TABLE = "AT_TABLE"                  # Robot at table (delivering)
    COMPLETED = "COMPLETED"                # Delivery complete
    FAILED = "FAILED"                      # Task failed


class PickupSlotManager:
    """
    Manages pickup_spot access control with enhanced multi-robot queue management.

    Pickup spot can only be accessed by one robot at a time.
    Other robots wait in designated waiting zones based on queue priority:
    - 1st priority (next in line): point13 - directly in front of pickup_spot
    - 2nd+ priority: robot's parking spot or point2/point3

    Provides callbacks for position updates when queue order changes.
    """

    def __init__(self, zone_manager: ZoneManager):
        self.zone_manager = zone_manager
        self.pickup_queue: deque = deque()      # Robots waiting for pickup slot
        self.current_holder: Optional[str] = None  # Robot currently at pickup
        self.holder_arrival_time: Optional[datetime] = None
        self.holding_timeout: float = 60.0      # Max time to hold pickup slot (seconds)
        self.assigned_waiting_zones: Dict[str, str] = {}  # robot_id -> waiting_zone

        # Waiting positions tracking: {robot_id: waiting_waypoint}
        self.waiting_positions: Dict[str, str] = {}

        # Callback for position updates when queue changes
        self._position_update_callback = None

        # Define waiting zones based on map layout (from navigation_graph.yaml)
        # Robots wait at point13 or their parking spot
        self.waiting_zone_positions = {
            'point13': {'x': 0.585, 'y': 0.63, 'zone_id': 'zone_point13'},
            'point2': {'x': 0.78, 'y': 0.35, 'zone_id': 'zone_point2'},
            'point3': {'x': 0.78, 'y': 0.65, 'zone_id': 'zone_point3'},
            'pinky1_spot': {'x': 0.585, 'y': 0.085, 'zone_id': 'zone_parking1'},
            'pinky2_spot': {'x': 0.585, 'y': 0.255, 'zone_id': 'zone_parking2'},
            'pinky3_spot': {'x': 0.585, 'y': 0.915, 'zone_id': 'zone_parking3'},
        }

        # Secondary waiting positions for 2nd+ priority robots
        self.secondary_waiting_positions = {
            'pinky1': 'point2',   # pinky1 waits at point2
            'pinky2': 'point2',   # pinky2 waits at point2
            'pinky3': 'point3',   # pinky3 waits at point3
        }

        logger.info("PickupSlotManager initialized with enhanced queue management")

    def set_position_update_callback(self, callback):
        """
        Set callback for position updates when queue order changes.

        The callback will be invoked with (robot_id, new_waypoint) when a robot's
        waiting position needs to be updated due to queue changes.

        Args:
            callback: Function with signature (robot_id: str, waypoint: str) -> None
        """
        self._position_update_callback = callback
        logger.info("Position update callback registered")

    def _notify_position_update(self, robot_id: str, waypoint: str):
        """
        Notify position update via callback.

        Args:
            robot_id: Robot that needs to move
            waypoint: New destination waypoint
        """
        self.waiting_positions[robot_id] = waypoint
        if self._position_update_callback:
            try:
                self._position_update_callback(robot_id, waypoint)
                logger.info(f"Position update callback invoked: {robot_id} -> {waypoint}")
            except Exception as e:
                logger.error(f"Position update callback failed: {e}")

    def _update_queue_positions(self):
        """
        Update waiting positions for all robots in queue after queue changes.

        - 1st in queue: moves to point13 (closest to pickup)
        - 2nd+ in queue: moves to secondary position (point2/point3 or parking)
        """
        queue_list = list(self.pickup_queue)

        for idx, robot_id in enumerate(queue_list):
            queue_position = idx + 1  # 1-indexed position in queue

            if queue_position == 1:
                # First in queue: move to point13 (pickup waiting hub)
                new_waypoint = 'point13'
            else:
                # 2nd+ in queue: use secondary position based on robot
                new_waypoint = self.secondary_waiting_positions.get(robot_id, 'point2')

            # Check if position changed
            current_pos = self.waiting_positions.get(robot_id)
            if current_pos != new_waypoint:
                logger.info(
                    f"Queue position update: {robot_id} position {queue_position}, "
                    f"moving from {current_pos} to {new_waypoint}"
                )
                self._notify_position_update(robot_id, new_waypoint)

    def request_pickup_slot(self, robot_id: str) -> bool:
        """
        Request pickup slot for robot.

        Robot is added to queue if slot is occupied. Waiting position is
        automatically assigned based on queue priority.

        Args:
            robot_id: Robot requesting pickup access

        Returns:
            True if robot is immediately granted access (was first in queue),
            False if robot must wait in queue
        """
        # If no one is using the slot, grant immediate access
        if self.current_holder is None and len(self.pickup_queue) == 0:
            self.current_holder = robot_id
            self.holder_arrival_time = datetime.utcnow()
            # Clear any waiting position since robot now holds the slot
            self.waiting_positions.pop(robot_id, None)
            logger.info(f"Robot {robot_id} granted immediate pickup slot access")
            return True
        else:
            # Add to queue if not already in queue
            if robot_id not in self.pickup_queue:
                self.pickup_queue.append(robot_id)
                queue_position = len(self.pickup_queue)
                logger.info(f"Robot {robot_id} added to pickup queue (position: {queue_position})")

                # Assign waiting position based on queue position
                if queue_position == 1:
                    waiting_waypoint = 'point13'
                else:
                    waiting_waypoint = self.secondary_waiting_positions.get(robot_id, 'point2')

                self._notify_position_update(robot_id, waiting_waypoint)
            else:
                logger.debug(f"Robot {robot_id} already in pickup queue")

            return False

    def release_pickup_slot(self, robot_id: str) -> Optional[str]:
        """
        Release pickup slot from current robot and grant to next in queue.

        When slot is released:
        1. Next robot in queue is granted access
        2. Remaining robots' positions are updated (1st -> point13, others stay)
        3. Position update callbacks are invoked

        Args:
            robot_id: Robot releasing the slot

        Returns:
            Next robot to receive slot, or None if queue is empty
        """
        if self.current_holder != robot_id:
            logger.warning(f"Robot {robot_id} tried to release slot it doesn't hold")
            return None

        self.current_holder = None
        self.holder_arrival_time = None

        # Grant slot to next robot in queue
        if self.pickup_queue:
            next_robot = self.pickup_queue.popleft()
            self.current_holder = next_robot
            self.holder_arrival_time = datetime.utcnow()

            # Clear waiting position for robot that now holds the slot
            self.waiting_positions.pop(next_robot, None)

            logger.info(f"Pickup slot released by {robot_id}, granted to {next_robot}")

            # Update positions for remaining robots in queue
            # The new first-in-queue robot should move to point13
            self._update_queue_positions()

            return next_robot
        else:
            logger.info(f"Pickup slot released by {robot_id}, no robots waiting")
            return None

    def get_queue_position(self, robot_id: str) -> int:
        """
        Get queue position for robot (0-indexed).

        Args:
            robot_id: Robot ID

        Returns:
            Queue position if robot is in queue or holding slot, -1 otherwise
            0 = currently holding slot
            1+ = waiting in queue
        """
        if self.current_holder == robot_id:
            return 0  # Currently holding

        try:
            return list(self.pickup_queue).index(robot_id) + 1
        except ValueError:
            return -1

    def get_robot_queue_position(self, robot_id: str) -> int:
        """
        Get robot's queue position with detailed semantics.

        Args:
            robot_id: Robot ID to check

        Returns:
            0: Robot is currently holding the pickup slot
            1+: Robot's position in the waiting queue (1 = next in line)
            -1: Robot is not in queue and not holding slot
        """
        if self.current_holder == robot_id:
            return 0  # Currently occupying pickup slot

        try:
            idx = list(self.pickup_queue).index(robot_id)
            return idx + 1  # 1-indexed queue position
        except ValueError:
            return -1  # Not in queue

    def is_holding_slot(self, robot_id: str) -> bool:
        """Check if robot is currently holding pickup slot"""
        return self.current_holder == robot_id

    def is_in_queue(self, robot_id: str) -> bool:
        """Check if robot is in pickup queue (not holding slot)"""
        return robot_id in self.pickup_queue

    def get_next_in_queue(self) -> Optional[str]:
        """Peek at next robot in queue without removing"""
        return self.pickup_queue[0] if self.pickup_queue else None

    def check_slot_timeout(self) -> bool:
        """
        Check if current slot holder has exceeded timeout

        Returns:
            True if timeout exceeded, False otherwise
        """
        if self.current_holder and self.holder_arrival_time:
            elapsed = (datetime.utcnow() - self.holder_arrival_time).total_seconds()
            if elapsed > self.holding_timeout:
                logger.warning(
                    f"Pickup slot timeout for {self.current_holder} "
                    f"(held for {elapsed:.1f}s, timeout: {self.holding_timeout}s)"
                )
                return True
        return False

    def force_release_slot(self) -> Optional[str]:
        """
        Force release slot due to timeout or error.

        This is called when a robot exceeds the holding timeout or encounters
        an error. The slot is released and granted to the next robot in queue.

        Returns:
            Next robot to receive slot, or None if queue is empty
        """
        if self.current_holder:
            old_holder = self.current_holder
            logger.warning(f"Forcing release of pickup slot from {old_holder}")
            return self.release_pickup_slot(old_holder)
        return None

    def remove_from_queue(self, robot_id: str) -> bool:
        """
        Remove a robot from the waiting queue (e.g., due to error or cancellation).

        Args:
            robot_id: Robot to remove from queue

        Returns:
            True if robot was removed, False if not found in queue
        """
        if robot_id not in self.pickup_queue:
            logger.debug(f"Robot {robot_id} not found in pickup queue")
            return False

        # Remove from queue
        self.pickup_queue = deque(r for r in self.pickup_queue if r != robot_id)

        # Clear waiting position
        self.waiting_positions.pop(robot_id, None)

        logger.info(f"Robot {robot_id} removed from pickup queue")

        # Update positions for remaining robots
        self._update_queue_positions()

        return True

    def get_waiting_position(self, robot_id: str) -> Optional[str]:
        """
        Get the current waiting position waypoint for a robot.

        Args:
            robot_id: Robot ID to check

        Returns:
            Waypoint name where robot should wait, or None if not waiting
        """
        return self.waiting_positions.get(robot_id)

    def get_waiting_zone(self, robot_id: str, current_position: Tuple[float, float]) -> str:
        """
        Assign waiting zone for robot waiting in pickup queue

        Strategy:
        - First in queue (next to get pickup): point13 (closest to pickup)
        - Others: assigned parking spots or other waypoints

        Args:
            robot_id: Robot ID
            current_position: Current position (x, y)

        Returns:
            Waiting zone location name
        """
        queue_position = self.get_queue_position(robot_id)

        if queue_position == -1:
            return None  # Not in queue or holding

        # First in queue should move to point13 (closest to pickup)
        if queue_position == 1:  # Next to get slot
            return 'point13'

        # Others wait at parking spot
        # Map robot_id to parking spot
        parking_spots = {
            'pinky1': 'pinky1_spot',
            'pinky2': 'pinky2_spot',
            'pinky3': 'pinky3_spot'
        }

        return parking_spots.get(robot_id, 'pinky1_spot')

    def get_all_waiting_robots(self) -> List[str]:
        """Get list of robots waiting for pickup slot"""
        return list(self.pickup_queue)

    def get_queue_status(self) -> Dict:
        """
        Get comprehensive queue status including waiting positions.

        Returns:
            Dict containing:
            - current_holder: Robot currently at pickup slot
            - queue: Ordered list of waiting robots
            - waiting_positions: Dict mapping robot_id to assigned waypoint
            - holder_arrival_time: When current holder arrived
            - queue_length: Number of robots waiting
            - queue_positions: Dict mapping robot_id to queue position
        """
        return {
            'current_holder': self.current_holder,
            'queue': list(self.pickup_queue),
            'waiting_positions': dict(self.waiting_positions),
            'holder_arrival_time': self.holder_arrival_time.isoformat() if self.holder_arrival_time else None,
            'queue_length': len(self.pickup_queue),
            'waiting_robots': list(self.pickup_queue),
            'queue_positions': {
                robot_id: self.get_robot_queue_position(robot_id)
                for robot_id in list(self.pickup_queue) + ([self.current_holder] if self.current_holder else [])
            }
        }


class TaskScheduler:
    """
    Main task scheduler for multi-robot coordination

    Responsibilities:
    - Maintain task queue (FIFO)
    - Assign tasks to available robots
    - Manage pickup slot access (1 robot at a time)
    - Coordinate robot waiting zones
    - Track task state transitions
    """

    def __init__(self, zone_manager: ZoneManager):
        self.zone_manager = zone_manager
        self.pickup_manager = PickupSlotManager(zone_manager)

        # Task queues
        self.pending_tasks: deque = deque()      # Unassigned tasks
        self.assigned_tasks: Dict[str, Task] = {} # task_id -> Task
        self.active_tasks: Dict[str, str] = {}    # robot_id -> task_id (current task)
        self.completed_tasks: List[Task] = []     # Completed task history

        # Task state tracking
        self.task_states: Dict[str, TaskState] = {}  # task_id -> TaskState

        # Robot-to-task mapping
        self.robot_tasks: Dict[str, List[str]] = {}  # robot_id -> [task_ids]

        logger.info("TaskScheduler initialized with PickupSlotManager")

    def add_task(self, task: Task) -> str:
        """
        Add new task to pending queue

        Args:
            task: Task object

        Returns:
            Task ID
        """
        self.pending_tasks.append(task)
        self.task_states[task.task_id] = TaskState.PENDING
        self.robot_tasks.setdefault(task.assigned_robot, []).append(task.task_id)

        logger.info(f"Task {task.task_id} added to queue (queue size: {len(self.pending_tasks)})")
        return task.task_id

    def assign_task_to_robot(self, robot_id: str) -> Optional[Task]:
        """
        Assign next pending task to robot

        Robot must be:
        - Available (no current task)
        - Not low on battery
        - Can enter pickup slot queue

        Args:
            robot_id: Target robot ID

        Returns:
            Task object if assignment successful, None otherwise
        """
        if not self.pending_tasks:
            logger.debug(f"No pending tasks available for robot {robot_id}")
            return None

        # Get next task
        task = self.pending_tasks.popleft()
        task.assign_robot(robot_id)

        # Move to assigned tasks
        self.assigned_tasks[task.task_id] = task
        self.active_tasks[robot_id] = task.task_id

        # Update task state
        self.task_states[task.task_id] = TaskState.ASSIGNED

        logger.info(f"Task {task.task_id} assigned to robot {robot_id}")
        return task

    def request_pickup_access(self, robot_id: str, task_id: str) -> bool:
        """
        Request pickup spot access for robot with task

        Robot is queued if spot is occupied.

        Args:
            robot_id: Robot requesting access
            task_id: Task ID being executed

        Returns:
            True if immediate access granted, False if robot must wait
        """
        task = self.assigned_tasks.get(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False

        # Request pickup slot
        is_granted = self.pickup_manager.request_pickup_slot(robot_id)

        if is_granted:
            self.task_states[task_id] = TaskState.AT_PICKUP
            logger.info(f"Task {task_id} (robot {robot_id}): pickup access GRANTED")
        else:
            self.task_states[task_id] = TaskState.WAITING_FOR_PICKUP
            logger.info(f"Task {task_id} (robot {robot_id}): added to pickup QUEUE")

        return is_granted

    def robot_loaded(self, robot_id: str, task_id: str) -> bool:
        """
        Mark task as loaded and release pickup slot

        Args:
            robot_id: Robot ID
            task_id: Task ID

        Returns:
            True if successful
        """
        task = self.assigned_tasks.get(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False

        # Update task state
        self.task_states[task_id] = TaskState.LOADED

        # Release pickup slot
        next_robot = self.pickup_manager.release_pickup_slot(robot_id)

        logger.info(f"Task {task_id} (robot {robot_id}): food LOADED, moving to table")

        # Notify next robot in queue
        if next_robot:
            logger.info(f"Next robot {next_robot} now has pickup access")

        return True

    def robot_delivered(self, robot_id: str, task_id: str) -> bool:
        """
        Mark task as completed

        Args:
            robot_id: Robot ID
            task_id: Task ID

        Returns:
            True if successful
        """
        task = self.assigned_tasks.get(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False

        # Update task state
        self.task_states[task_id] = TaskState.COMPLETED
        task.complete()

        # Move to completed
        self.completed_tasks.append(task)
        del self.assigned_tasks[task_id]
        if robot_id in self.active_tasks and self.active_tasks[robot_id] == task_id:
            del self.active_tasks[robot_id]

        logger.info(f"Task {task_id} (robot {robot_id}): COMPLETED")
        return True

    def get_next_waiting_zone(self, robot_id: str) -> Optional[str]:
        """
        Get waiting zone for robot waiting in pickup queue

        Args:
            robot_id: Robot ID

        Returns:
            Waiting zone location name, or None if not waiting
        """
        return self.pickup_manager.get_waiting_zone(robot_id, (0, 0))

    def get_pickup_queue_status(self) -> Dict:
        """Get detailed pickup queue status"""
        return self.pickup_manager.get_queue_status()

    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """Get current state of task"""
        return self.task_states.get(task_id)

    def get_robot_task(self, robot_id: str) -> Optional[Task]:
        """Get current task assigned to robot"""
        task_id = self.active_tasks.get(robot_id)
        if task_id:
            return self.assigned_tasks.get(task_id)
        return None

    def get_pending_count(self) -> int:
        """Get number of pending (unassigned) tasks"""
        return len(self.pending_tasks)

    def get_active_count(self) -> int:
        """Get number of active (assigned) tasks"""
        return len(self.assigned_tasks)

    def get_waiting_count(self) -> int:
        """Get number of robots waiting for pickup"""
        return len(self.pickup_manager.get_all_waiting_robots())

    def get_scheduler_status(self) -> Dict:
        """Get comprehensive scheduler status"""
        return {
            'pending_tasks': len(self.pending_tasks),
            'active_tasks': len(self.assigned_tasks),
            'completed_tasks': len(self.completed_tasks),
            'robots_waiting_for_pickup': len(self.pickup_manager.get_all_waiting_robots()),
            'pickup_queue': self.pickup_manager.get_queue_status(),
            'robot_task_mapping': {
                robot_id: {
                    'current_task': task_id,
                    'state': self.task_states.get(task_id, 'UNKNOWN').value
                }
                for robot_id, task_id in self.active_tasks.items()
            }
        }

    def get_task_summary(self) -> Dict:
        """Get summary of all tasks by state"""
        state_counts = {}
        for state in TaskState:
            state_counts[state.value] = 0

        for task_state in self.task_states.values():
            state_counts[task_state.value] += 1

        return state_counts

    def handle_robot_error(self, robot_id: str, error_msg: str) -> bool:
        """
        Handle robot error and cleanup.

        Releases any held pickup slot, removes from queue, and fails the
        current task (returning it to pending queue for retry).

        Args:
            robot_id: Robot ID
            error_msg: Error message

        Returns:
            True if cleanup successful
        """
        logger.error(f"Robot {robot_id} error: {error_msg}")

        # Release pickup slot if robot is holding it
        if self.pickup_manager.is_holding_slot(robot_id):
            self.pickup_manager.release_pickup_slot(robot_id)

        # Remove from queue if waiting (uses new method with position updates)
        if self.pickup_manager.is_in_queue(robot_id):
            self.pickup_manager.remove_from_queue(robot_id)

        # Fail current task and return to queue
        task_id = self.active_tasks.get(robot_id)
        if task_id:
            task = self.assigned_tasks.get(task_id)
            if task:
                task.fail()
                self.task_states[task_id] = TaskState.FAILED
                # Return to pending queue for retry
                self.pending_tasks.appendleft(task)
                del self.assigned_tasks[task_id]
                del self.active_tasks[robot_id]
                logger.warning(f"Task {task_id} failed and returned to queue")

        return True
