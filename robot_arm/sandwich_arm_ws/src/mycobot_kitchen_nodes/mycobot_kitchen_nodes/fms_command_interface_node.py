#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FMS Command Interface Node

이 노드는 FMS로부터 조리 명령을 받아 로봇팔에 전달하고,
로봇팔의 상태를 FMS로 피드백하는 역할을 담당합니다.

Clean Architecture 원칙:
- Domain: CookingCommand, CookingStatus 엔티티
- Application: FMS 명령 처리 유즈케이스
- Infrastructure: ROS2 토픽/서비스 통신
- Presentation: FMS 인터페이스
"""

import json
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from enum import Enum

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


# ============================================================================
# Domain Layer: Entities and Value Objects
# ============================================================================

class OperationType(Enum):
    """조리 명령 타입"""
    START = "START"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CANCEL = "CANCEL"


class CookingStatusType(Enum):
    """조리 상태 타입"""
    IDLE = "idle"
    COOKING = "cooking"
    READY = "ready"
    PAUSED = "paused"
    ERROR = "error"
    WAIT_FOR_SAUCE = "wait_for_sauce"


@dataclass
class MenuItem:
    """메뉴 아이템"""
    menu_id: int
    name: str
    quantity: int = 1


@dataclass
class Order:
    """주문 정보"""
    order_id: str
    items: list[MenuItem]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_id': self.order_id,
            'items': [asdict(item) for item in self.items]
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Order':
        items = [MenuItem(**item) for item in data.get('items', [])]
        return Order(
            order_id=data.get('order_id', ''),
            items=items
        )


@dataclass
class CookingCommand:
    """FMS로부터 받는 조리 명령"""
    job_id: str
    operation: OperationType
    order: Optional[Order] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'job_id': self.job_id,
            'operation': self.operation.value
        }
        if self.order:
            result['order'] = self.order.to_dict()
        return result

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'CookingCommand':
        operation = OperationType(data.get('operation', 'START'))
        order = None
        if 'order' in data and data['order']:
            order = Order.from_dict(data['order'])

        return CookingCommand(
            job_id=data.get('job_id', ''),
            operation=operation,
            order=order
        )


@dataclass
class CookingStatus:
    """로봇팔의 조리 상태"""
    job_id: str
    status: CookingStatusType
    progress: int = 0
    message: str = ""
    recipe: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'status': self.status.value,
            'progress': self.progress,
            'message': self.message,
            'recipe': self.recipe
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'CookingStatus':
        status_value = data.get('status', 'idle')
        status = CookingStatusType(status_value)

        return CookingStatus(
            job_id=data.get('job_id', ''),
            status=status,
            progress=data.get('progress', 0),
            message=data.get('message', ''),
            recipe=data.get('recipe', '')
        )


# ============================================================================
# Application Layer: Use Cases
# ============================================================================

class CookingCommandHandler:
    """조리 명령 처리 유즈케이스"""

    def __init__(self, logger, mock_mode: bool = False):
        self.logger = logger
        self.mock_mode = mock_mode
        self.current_job_id: Optional[str] = None
        self.current_status = CookingStatusType.IDLE
        self.mock_start_time: Optional[float] = None

    def handle_command(self, command: CookingCommand) -> tuple[bool, str]:
        """
        조리 명령 처리

        Returns:
            (success, arm_command_string)
        """
        try:
            if command.operation == OperationType.START:
                return self._handle_start(command)
            elif command.operation == OperationType.PAUSE:
                return self._handle_pause(command)
            elif command.operation == OperationType.RESUME:
                return self._handle_resume(command)
            elif command.operation == OperationType.CANCEL:
                return self._handle_cancel(command)
            else:
                return False, ""
        except Exception as e:
            self.logger.error(f"Command handling error: {e}")
            return False, ""

    def _handle_start(self, command: CookingCommand) -> tuple[bool, str]:
        """START 명령 처리"""
        if self.current_status != CookingStatusType.IDLE:
            self.logger.warn(f"Already cooking: {self.current_job_id}")
            return False, ""

        if not command.order or not command.order.items:
            self.logger.warn("No order items in START command")
            return False, ""

        # 첫 번째 메뉴 아이템을 레시피로 변환
        # TODO: 메뉴 ID -> 레시피 이름 매핑 필요
        menu_item = command.order.items[0]
        recipe_name = self._menu_to_recipe(menu_item)

        self.current_job_id = command.job_id
        self.current_status = CookingStatusType.COOKING

        if self.mock_mode:
            self.mock_start_time = time.time()
            return True, ""  # Mock 모드에서는 arm 명령 불필요

        # 기존 recipe_executor_node 명령 형식으로 변환
        # Format: "<job_id>|START|recipe=<name>|pause_before_last=1"
        arm_cmd = f"{command.job_id}|START|recipe={recipe_name}|pause_before_last=1"
        return True, arm_cmd

    def _handle_pause(self, command: CookingCommand) -> tuple[bool, str]:
        """PAUSE 명령 처리"""
        if command.job_id != self.current_job_id:
            return False, ""

        self.current_status = CookingStatusType.PAUSED

        if self.mock_mode:
            return True, ""

        arm_cmd = f"{command.job_id}|PAUSE"
        return True, arm_cmd

    def _handle_resume(self, command: CookingCommand) -> tuple[bool, str]:
        """RESUME 명령 처리"""
        if command.job_id != self.current_job_id:
            return False, ""

        self.current_status = CookingStatusType.COOKING

        if self.mock_mode:
            return True, ""

        arm_cmd = f"{command.job_id}|RESUME"
        return True, arm_cmd

    def _handle_cancel(self, command: CookingCommand) -> tuple[bool, str]:
        """CANCEL 명령 처리"""
        if command.job_id != self.current_job_id:
            return False, ""

        self.current_status = CookingStatusType.IDLE
        self.current_job_id = None
        self.mock_start_time = None

        if self.mock_mode:
            return True, ""

        arm_cmd = f"{command.job_id}|CANCEL"
        return True, arm_cmd

    def _menu_to_recipe(self, menu_item: MenuItem) -> str:
        """메뉴 아이템을 레시피 이름으로 변환"""
        # TODO: 실제 메뉴 ID -> 레시피 매핑 테이블 필요
        menu_map = {
            1: "sandwich_recipe_1",
            2: "sandwich_recipe_2",
        }
        return menu_map.get(menu_item.menu_id, "default_recipe")

    def get_mock_status(self) -> Optional[CookingStatus]:
        """Mock 모드 상태 생성"""
        if not self.mock_mode or not self.current_job_id:
            return None

        if self.mock_start_time is None:
            return None

        elapsed = time.time() - self.mock_start_time

        # 5초 후 자동으로 ready 상태
        if elapsed >= 5.0:
            status = CookingStatus(
                job_id=self.current_job_id,
                status=CookingStatusType.READY,
                progress=100,
                message="Mock cooking completed"
            )
            self.current_status = CookingStatusType.IDLE
            self.current_job_id = None
            self.mock_start_time = None
            return status
        else:
            progress = int((elapsed / 5.0) * 100)
            return CookingStatus(
                job_id=self.current_job_id,
                status=CookingStatusType.COOKING,
                progress=progress,
                message="Mock cooking in progress"
            )


class ArmStatusParser:
    """로봇팔 상태 메시지 파싱"""

    @staticmethod
    def parse(raw_status: str) -> Optional[CookingStatus]:
        """
        로봇팔 상태 메시지를 CookingStatus로 변환

        Input format: "<job_id>|<state>|k=v|k=v..."
        """
        try:
            parts = [p.strip() for p in raw_status.split('|') if p.strip()]
            if len(parts) < 2:
                return None

            job_id = parts[0]
            state = parts[1]

            # 추가 키-값 파싱
            kv = {}
            for p in parts[2:]:
                if '=' in p:
                    k, v = p.split('=', 1)
                    kv[k.strip()] = v.strip()

            # 상태 매핑
            status_map = {
                'IDLE': CookingStatusType.IDLE,
                'RUNNING': CookingStatusType.COOKING,
                'DONE': CookingStatusType.READY,
                'FAIL': CookingStatusType.ERROR,
                'PAUSED': CookingStatusType.PAUSED,
                'WAIT_FOR_SAUCE': CookingStatusType.WAIT_FOR_SAUCE,
                'PROGRESS': CookingStatusType.COOKING,
            }

            status = status_map.get(state, CookingStatusType.IDLE)

            # 진행률 계산 (PROGRESS 상태인 경우)
            progress = 0
            if state == 'DONE':
                progress = 100
            elif state == 'PROGRESS':
                # TODO: 실제 레시피 스텝 정보로 계산
                progress = 50

            return CookingStatus(
                job_id=job_id,
                status=status,
                progress=progress,
                message=kv.get('reason', ''),
                recipe=kv.get('recipe', '')
            )
        except Exception as e:
            return None


# ============================================================================
# Infrastructure & Presentation Layer: ROS2 Node
# ============================================================================

class FMSCommandInterfaceNode(Node):
    """
    FMS 명령 인터페이스 노드

    Subscribes:
        /arm/command (std_msgs/String): FMS로부터 조리 명령

    Publishes:
        /arm/status (std_msgs/String): FMS로 조리 상태 피드백
        /arm_a/cmd (std_msgs/String): 로봇팔로 명령 전달

    Subscribes (Internal):
        /arm_a/status (std_msgs/String): 로봇팔로부터 상태 수신
    """

    def __init__(self):
        super().__init__('fms_command_interface_node')

        # Parameters
        self.declare_parameter('mock_mode', False)
        self.declare_parameter('status_publish_rate', 1.0)  # Hz

        mock_mode = self.get_parameter('mock_mode').value
        status_rate = self.get_parameter('status_publish_rate').value

        # Use Case
        self.command_handler = CookingCommandHandler(
            logger=self.get_logger(),
            mock_mode=mock_mode
        )
        self.status_parser = ArmStatusParser()

        # FMS Interface
        self.fms_cmd_sub = self.create_subscription(
            String,
            '/arm/command',
            self._on_fms_command,
            10
        )
        self.fms_status_pub = self.create_publisher(
            String,
            '/arm/status',
            10
        )

        # Arm Interface
        self.arm_cmd_pub = self.create_publisher(
            String,
            '/arm_a/cmd',
            10
        )
        self.arm_status_sub = self.create_subscription(
            String,
            '/arm_a/status',
            self._on_arm_status,
            10
        )

        # Status publishing timer
        self.status_timer = self.create_timer(
            1.0 / status_rate,
            self._publish_status_periodic
        )

        self.last_status: Optional[CookingStatus] = None

        self.get_logger().info(
            f"FMS Command Interface ready (mock_mode={mock_mode})"
        )

    def _on_fms_command(self, msg: String) -> None:
        """FMS 명령 수신"""
        try:
            # JSON 파싱
            data = json.loads(msg.data)
            command = CookingCommand.from_dict(data)

            self.get_logger().info(
                f"Received FMS command: {command.operation.value} "
                f"job_id={command.job_id}"
            )

            # 명령 처리
            success, arm_cmd = self.command_handler.handle_command(command)

            if success and arm_cmd:
                # 로봇팔로 명령 전달
                arm_msg = String()
                arm_msg.data = arm_cmd
                self.arm_cmd_pub.publish(arm_msg)
                self.get_logger().info(f"Sent to arm: {arm_cmd}")
            elif not success:
                self.get_logger().warn(
                    f"Command handling failed: {command.operation.value}"
                )

        except json.JSONDecodeError as e:
            self.get_logger().error(f"Invalid JSON format: {e}")
        except Exception as e:
            self.get_logger().error(f"Command processing error: {e}")

    def _on_arm_status(self, msg: String) -> None:
        """로봇팔 상태 수신"""
        status = self.status_parser.parse(msg.data)
        if status:
            self.last_status = status
            self._publish_status(status)

    def _publish_status_periodic(self) -> None:
        """주기적 상태 발행 (Mock 모드)"""
        if not self.command_handler.mock_mode:
            return

        mock_status = self.command_handler.get_mock_status()
        if mock_status:
            self._publish_status(mock_status)

    def _publish_status(self, status: CookingStatus) -> None:
        """FMS로 상태 발행"""
        msg = String()
        msg.data = json.dumps(status.to_dict())
        self.fms_status_pub.publish(msg)

        self.get_logger().info(
            f"Published status: job_id={status.job_id} "
            f"status={status.status.value} progress={status.progress}%"
        )


def main(args=None):
    rclpy.init(args=args)
    node = FMSCommandInterfaceNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
