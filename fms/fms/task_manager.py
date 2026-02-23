"""
Task Manager for Fleet Management System
Handles order queue and task assignment to serving robots
"""

import logging
from typing import List, Optional, Dict, Any
from collections import deque
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class Task:
    """
    Represents a delivery task for a serving robot
    """

    def __init__(self, order_id: str, menu_id: str, table_number: str,
                 quantity: int, sauce_type: str, voice_order: bool):
        self.task_id = str(uuid.uuid4())
        self.order_id = order_id
        self.menu_id = menu_id
        self.table_number = table_number
        self.quantity = quantity
        self.sauce_type = sauce_type
        self.voice_order = voice_order
        self.status = 'PENDING'  # PENDING, ASSIGNED, IN_PROGRESS, COMPLETED, FAILED
        self.assigned_robot = None
        self.created_at = datetime.utcnow()
        self.assigned_at = None
        self.completed_at = None

    def assign_robot(self, robot_id: str):
        """Assign this task to a robot"""
        self.assigned_robot = robot_id
        self.assigned_at = datetime.utcnow()
        self.status = 'ASSIGNED'
        logger.info(f"Task {self.task_id} assigned to robot {robot_id}")

    def start(self):
        """Mark task as in progress"""
        self.status = 'IN_PROGRESS'
        logger.info(f"Task {self.task_id} started")

    def complete(self):
        """Mark task as completed"""
        self.status = 'COMPLETED'
        self.completed_at = datetime.utcnow()
        logger.info(f"Task {self.task_id} completed")

    def fail(self):
        """Mark task as failed"""
        self.status = 'FAILED'
        logger.error(f"Task {self.task_id} failed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            'task_id': self.task_id,
            'order_id': self.order_id,
            'menu_id': self.menu_id,
            'table_number': self.table_number,
            'quantity': self.quantity,
            'sauce_type': self.sauce_type,
            'voice_order': self.voice_order,
            'status': self.status,
            'assigned_robot': self.assigned_robot,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class TaskManager:
    """
    Manages task queue and assignment to serving robots

    Responsibilities:
    - Maintain task queue
    - Assign tasks to available robots
    - Track task status
    - Handle task completion and failure
    """

    def __init__(self):
        self.pending_tasks = deque()  # Queue of tasks waiting for robot assignment
        self.assigned_tasks = {}      # {task_id: Task} - Tasks assigned to robots
        self.completed_tasks = []     # List of completed tasks (for history)
        self.task_lookup = {}         # {order_id: task_id} - Quick lookup by order ID

        logger.info("TaskManager initialized")

    def create_task(self, order_id: str, menu_id: str, table_number: str,
                   quantity: int, sauce_type: str, voice_order: bool) -> Task:
        """
        Create a new task from order

        Args:
            order_id: Order UUID
            menu_id: Menu ID (M001, M002)
            table_number: Table number (T01-T08)
            quantity: Order quantity
            sauce_type: Sauce type
            voice_order: Whether order was placed via voice

        Returns:
            Task object
        """
        task = Task(
            order_id=order_id,
            menu_id=menu_id,
            table_number=table_number,
            quantity=quantity,
            sauce_type=sauce_type,
            voice_order=voice_order
        )

        self.pending_tasks.append(task)
        self.task_lookup[order_id] = task.task_id

        logger.info(f"Created task {task.task_id} for order {order_id}, table {table_number}")
        return task

    def assign_task(self, robot_id: str) -> Optional[Task]:
        """
        Assign next pending task to a robot

        Args:
            robot_id: Robot ID to assign task to

        Returns:
            Task object if assignment successful, None otherwise
        """
        if not self.pending_tasks:
            logger.debug(f"No pending tasks available for robot {robot_id}")
            return None

        # Get next task from queue
        task = self.pending_tasks.popleft()
        task.assign_robot(robot_id)

        # Move to assigned tasks
        self.assigned_tasks[task.task_id] = task

        logger.info(f"Assigned task {task.task_id} to robot {robot_id}")
        return task

    def start_task(self, task_id: str) -> bool:
        """
        Mark task as in progress

        Args:
            task_id: Task ID

        Returns:
            True if successful, False otherwise
        """
        task = self.assigned_tasks.get(task_id)
        if task:
            task.start()
            return True
        else:
            logger.warning(f"Task {task_id} not found in assigned tasks")
            return False

    def complete_task(self, task_id: str) -> bool:
        """
        Mark task as completed

        Args:
            task_id: Task ID

        Returns:
            True if successful, False otherwise
        """
        task = self.assigned_tasks.get(task_id)
        if task:
            task.complete()
            # Move to completed tasks
            self.completed_tasks.append(task)
            del self.assigned_tasks[task_id]
            logger.info(f"Task {task_id} completed")
            return True
        else:
            logger.warning(f"Task {task_id} not found in assigned tasks")
            return False

    def fail_task(self, task_id: str) -> bool:
        """
        Mark task as failed and return to queue

        Args:
            task_id: Task ID

        Returns:
            True if successful, False otherwise
        """
        task = self.assigned_tasks.get(task_id)
        if task:
            task.fail()
            # Return to front of pending queue for retry
            self.pending_tasks.appendleft(task)
            del self.assigned_tasks[task_id]
            logger.warning(f"Task {task_id} failed, returned to queue")
            return True
        else:
            logger.warning(f"Task {task_id} not found in assigned tasks")
            return False

    def get_task_by_order_id(self, order_id: str) -> Optional[Task]:
        """
        Get task by order ID

        Args:
            order_id: Order UUID

        Returns:
            Task object if found, None otherwise
        """
        task_id = self.task_lookup.get(order_id)
        if task_id:
            # Check assigned tasks
            task = self.assigned_tasks.get(task_id)
            if task:
                return task

            # Check pending tasks
            for task in self.pending_tasks:
                if task.order_id == order_id:
                    return task

            # Check completed tasks
            for task in self.completed_tasks:
                if task.order_id == order_id:
                    return task

        return None

    def get_task_by_robot(self, robot_id: str) -> Optional[Task]:
        """
        Get current task assigned to robot

        Args:
            robot_id: Robot ID

        Returns:
            Task object if found, None otherwise
        """
        for task in self.assigned_tasks.values():
            if task.assigned_robot == robot_id:
                return task
        return None

    def get_pending_count(self) -> int:
        """Get number of pending tasks"""
        return len(self.pending_tasks)

    def get_active_count(self) -> int:
        """Get number of active (assigned) tasks"""
        return len(self.assigned_tasks)

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks (pending, assigned, and completed)"""
        all_tasks = list(self.pending_tasks) + list(self.assigned_tasks.values()) + self.completed_tasks
        return all_tasks

    def get_status_summary(self) -> Dict[str, int]:
        """
        Get task status summary

        Returns:
            Dictionary with counts for each status
        """
        return {
            'pending': len(self.pending_tasks),
            'assigned': sum(1 for t in self.assigned_tasks.values() if t.status == 'ASSIGNED'),
            'in_progress': sum(1 for t in self.assigned_tasks.values() if t.status == 'IN_PROGRESS'),
            'completed': len(self.completed_tasks),
            'failed': sum(1 for t in self.pending_tasks if t.status == 'FAILED')
        }
