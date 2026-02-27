"""
FMS용 Error Recovery Handler
운영자 명령을 처리하고 복구 작업을 실행합니다

복구 작업:
- RETRY: 실패한 네비게이션 task를 재시도
- RETURN_HOME: 로봇을 parking spot으로 강제 복귀
- EMERGENCY_STOP: 로봇을 즉시 정지 (안전)
- CLEAR_ERROR: 오류 상태를 수동으로 클리어
"""

import logging
from typing import Dict, Optional, Callable
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class OperatorCommand(Enum):
    """오류 복구를 위한 운영자 명령"""
    RETRY = 'RETRY'                    # Retry current task
    RETURN_HOME = 'RETURN_HOME'        # Return to parking spot
    EMERGENCY_STOP = 'EMERGENCY_STOP'  # Emergency stop
    CLEAR_ERROR = 'CLEAR_ERROR'        # Clear error state


class OperatorAction:
    """오류 복구를 위한 운영자 명령을 나타냅니다"""

    def __init__(self, robot_id: str, command: OperatorCommand, order_id: str = None,
                 reason: str = None):
        """
        운영자 작업을 초기화합니다

        Args:
            robot_id: 대상 Robot ID
            command: 운영자 명령 타입
            order_id: 연관된 Order ID (선택사항)
            reason: 명령 사유 (운영자 메모)
        """
        self.robot_id = robot_id
        self.command = command
        self.order_id = order_id
        self.reason = reason or "Operator intervention"
        self.timestamp = datetime.utcnow()
        self.executed = False
        self.execution_time = None

    def mark_executed(self):
        """작업을 실행됨으로 표시합니다"""
        self.executed = True
        self.execution_time = datetime.utcnow()

    def to_dict(self):
        """dictionary로 변환합니다"""
        return {
            'robot_id': self.robot_id,
            'command': self.command.value,
            'order_id': self.order_id,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat(),
            'executed': self.executed,
            'execution_time': self.execution_time.isoformat() if self.execution_time else None
        }


class ErrorRecoveryHandler:
    """
    오류 복구와 운영자 명령을 처리합니다

    책임:
    - Admin GUI로부터 운영자 명령 수신
    - 복구 작업 실행
    - 네비게이션과 로봇 제어를 위한 FMS 조정
    - 복구 시도 이력 추적
    """

    def __init__(self):
        """오류 복구 handler를 초기화합니다"""
        self.pending_actions: Dict[str, OperatorAction] = {}  # {robot_id: OperatorAction}
        self.completed_actions: list = []  # History of completed actions
        self.action_callbacks: Dict[OperatorCommand, Callable] = {}  # Command callbacks

        logger.info("ErrorRecoveryHandler initialized")

    def register_action_callback(self, command: OperatorCommand, callback: Callable):
        """
        운영자 명령에 대한 callback을 등록합니다

        Args:
            command: OperatorCommand enum 값
            callback: 이 명령을 위해 실행할 함수
                     (robot_id, order_id, reason)를 파라미터로 받아야 합니다
        """
        self.action_callbacks[command] = callback
        logger.debug(f"Registered callback for {command.value}")

    def submit_operator_command(self, robot_id: str, command: OperatorCommand,
                               order_id: str = None, reason: str = None) -> bool:
        """
        Submit operator command for error recovery

        Args:
            robot_id: Target robot ID
            command: Type of operator command
            order_id: Associated order ID (optional)
            reason: Reason for command

        Returns:
            True if command accepted, False otherwise
        """
        # Create action
        action = OperatorAction(robot_id, command, order_id, reason)

        # Store pending action
        self.pending_actions[robot_id] = action

        logger.info(f"Operator command submitted for {robot_id}: {command.value}")
        logger.info(f"  Reason: {reason}")
        if order_id:
            logger.info(f"  Order: {order_id}")

        return True

    def get_pending_action(self, robot_id: str) -> Optional[OperatorAction]:
        """
        Get pending action for robot

        Args:
            robot_id: Robot ID

        Returns:
            OperatorAction if pending, None otherwise
        """
        return self.pending_actions.get(robot_id)

    def has_pending_action(self, robot_id: str) -> bool:
        """
        Check if robot has pending operator action

        Args:
            robot_id: Robot ID

        Returns:
            True if action pending, False otherwise
        """
        return robot_id in self.pending_actions

    def execute_action(self, robot_id: str) -> bool:
        """
        Execute pending operator action

        Args:
            robot_id: Robot ID

        Returns:
            True if action executed successfully, False otherwise
        """
        action = self.pending_actions.get(robot_id)
        if not action:
            logger.warning(f"No pending action for robot {robot_id}")
            return False

        # Get callback for this command
        callback = self.action_callbacks.get(action.command)
        if not callback:
            logger.error(f"No callback registered for {action.command.value}")
            return False

        # Execute callback
        try:
            logger.info(f"Executing {action.command.value} for robot {robot_id}")
            callback(robot_id, action.order_id, action.reason)
            action.mark_executed()

            # Move to completed
            self.completed_actions.append(action)
            del self.pending_actions[robot_id]

            logger.info(f"Successfully executed {action.command.value} for robot {robot_id}")
            return True

        except Exception as e:
            logger.error(f"Error executing action for {robot_id}: {e}")
            return False

    def get_action_history(self, robot_id: str = None, limit: int = 20) -> list:
        """
        Get operator action history

        Args:
            robot_id: If specified, only return actions for this robot
            limit: Maximum number of actions to return

        Returns:
            List of OperatorAction objects
        """
        if robot_id:
            history = [a for a in self.completed_actions if a.robot_id == robot_id]
        else:
            history = list(self.completed_actions)

        return history[-limit:]

    def get_action_statistics(self) -> Dict:
        """
        Get operator action statistics

        Returns:
            Dictionary with action stats
        """
        command_counts = {}
        for action in self.completed_actions:
            cmd = action.command.value
            command_counts[cmd] = command_counts.get(cmd, 0) + 1

        return {
            'total_actions': len(self.completed_actions),
            'pending_actions': len(self.pending_actions),
            'command_counts': command_counts,
            'pending_robots': list(self.pending_actions.keys())
        }
