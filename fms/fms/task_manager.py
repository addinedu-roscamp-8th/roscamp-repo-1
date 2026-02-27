"""
Fleet Management System용 Task Manager
주문 대기열과 서빙 로봇에 대한 task 할당을 처리합니다
"""

import logging
from typing import List, Optional, Dict, Any
from collections import deque
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class Task:
    """
    서빙 로봇을 위한 배달 task를 나타냅니다
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
        """이 task를 로봇에 할당합니다"""
        self.assigned_robot = robot_id
        self.assigned_at = datetime.utcnow()
        self.status = 'ASSIGNED'
        logger.info(f"Task {self.task_id} assigned to robot {robot_id}")

    def start(self):
        """task를 진행 중으로 표시합니다"""
        self.status = 'IN_PROGRESS'
        logger.info(f"Task {self.task_id} started")

    def complete(self):
        """task를 완료로 표시합니다"""
        self.status = 'COMPLETED'
        self.completed_at = datetime.utcnow()
        logger.info(f"Task {self.task_id} completed")

    def fail(self):
        """task를 실패로 표시합니다"""
        self.status = 'FAILED'
        logger.error(f"Task {self.task_id} failed")

    def to_dict(self) -> Dict[str, Any]:
        """task를 dictionary로 변환합니다"""
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
    서빙 로봇에 대한 task 대기열과 할당을 관리합니다

    책임:
    - task 대기열 유지
    - 가용 로봇에 task 할당
    - task 상태 추적
    - task 완료 및 실패 처리
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
        주문으로부터 새로운 task를 생성합니다

        Args:
            order_id: Order UUID
            menu_id: Menu ID (M001, M002)
            table_number: 테이블 번호 (T01-T08)
            quantity: 주문 수량
            sauce_type: 소스 타입
            voice_order: 음성으로 주문되었는지 여부

        Returns:
            Task 객체
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
        다음 대기 중인 task를 로봇에 할당합니다

        Args:
            robot_id: task를 할당할 Robot ID

        Returns:
            할당 성공 시 Task 객체, 실패 시 None
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
        task를 진행 중으로 표시합니다

        Args:
            task_id: Task ID

        Returns:
            성공 시 True, 실패 시 False
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
        task를 완료로 표시합니다

        Args:
            task_id: Task ID

        Returns:
            성공 시 True, 실패 시 False
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
        task를 실패로 표시하고 대기열로 되돌립니다

        Args:
            task_id: Task ID

        Returns:
            성공 시 True, 실패 시 False
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
        Order ID로 task를 가져옵니다

        Args:
            order_id: Order UUID

        Returns:
            찾으면 Task 객체, 아니면 None
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
        로봇에 할당된 현재 task를 가져옵니다

        Args:
            robot_id: Robot ID

        Returns:
            찾으면 Task 객체, 아니면 None
        """
        for task in self.assigned_tasks.values():
            if task.assigned_robot == robot_id:
                return task
        return None

    def get_pending_count(self) -> int:
        """대기 중인 task 개수를 가져옵니다"""
        return len(self.pending_tasks)

    def get_active_count(self) -> int:
        """활성(할당된) task 개수를 가져옵니다"""
        return len(self.assigned_tasks)

    def get_all_tasks(self) -> List[Task]:
        """모든 task를 가져옵니다 (대기 중, 할당됨, 완료됨)"""
        all_tasks = list(self.pending_tasks) + list(self.assigned_tasks.values()) + self.completed_tasks
        return all_tasks

    def get_status_summary(self) -> Dict[str, int]:
        """
        task 상태 요약을 가져옵니다

        Returns:
            각 상태별 개수를 담은 dictionary
        """
        return {
            'pending': len(self.pending_tasks),
            'assigned': sum(1 for t in self.assigned_tasks.values() if t.status == 'ASSIGNED'),
            'in_progress': sum(1 for t in self.assigned_tasks.values() if t.status == 'IN_PROGRESS'),
            'completed': len(self.completed_tasks),
            'failed': sum(1 for t in self.pending_tasks if t.status == 'FAILED')
        }
