#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cooking Interface Node

FMS로부터 /cooking/command 토픽으로 조리 명령을 수신하고,
/cooking/status 토픽으로 상태를 피드백합니다.

Topics:
    Subscribe: /cooking/command (std_msgs/String) - JSON 조리 명령
    Publish: /cooking/status (std_msgs/String) - JSON 상태 피드백
"""

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class CookingState(Enum):
    """조리 상태"""
    IDLE = "idle"
    COOKING = "cooking"
    READY = "ready"
    ERROR = "error"


@dataclass
class CookingJob:
    """현재 조리 작업 정보"""
    job_id: str
    order_id: str
    start_time: float
    state: CookingState = CookingState.COOKING


class CookingInterfaceNode(Node):
    """
    FMS 조리 명령 인터페이스 노드

    Mock 모드: 5초 후 자동으로 ready 상태 전송
    """

    MOCK_COOKING_DURATION = 5.0  # seconds

    def __init__(self):
        super().__init__('cooking_interface_node')

        # Parameters
        self.declare_parameter('mock_mode', True)
        self.declare_parameter('status_rate', 1.0)  # Hz

        self.mock_mode = self.get_parameter('mock_mode').value
        status_rate = self.get_parameter('status_rate').value

        # Current job
        self.current_job: Optional[CookingJob] = None

        # Subscribers
        self.cmd_sub = self.create_subscription(
            String,
            '/cooking/command',
            self._on_command,
            10
        )

        # Publishers
        self.status_pub = self.create_publisher(
            String,
            '/cooking/status',
            10
        )

        # Status timer
        self.status_timer = self.create_timer(
            1.0 / status_rate,
            self._publish_status
        )

        self.get_logger().info(
            f"CookingInterfaceNode started (mock_mode={self.mock_mode})"
        )

    def _on_command(self, msg: String) -> None:
        """조리 명령 수신 처리"""
        try:
            data = json.loads(msg.data)
            operation = data.get('operation', 'START')
            job_id = data.get('job_id', '')
            order_id = data.get('order_id', '')

            self.get_logger().info(
                f"Received command: operation={operation}, "
                f"job_id={job_id}, order_id={order_id}"
            )

            if operation == 'START':
                self._handle_start(job_id, order_id)
            elif operation == 'CANCEL':
                self._handle_cancel(job_id)

        except json.JSONDecodeError as e:
            self.get_logger().error(f"Invalid JSON: {e}")
        except Exception as e:
            self.get_logger().error(f"Command error: {e}")

    def _handle_start(self, job_id: str, order_id: str) -> None:
        """START 명령 처리"""
        if self.current_job is not None:
            self.get_logger().warn(
                f"Already cooking job: {self.current_job.job_id}"
            )
            return

        self.current_job = CookingJob(
            job_id=job_id,
            order_id=order_id,
            start_time=time.time(),
            state=CookingState.COOKING
        )

        self.get_logger().info(f"Started cooking job: {job_id}")
        self._send_status(CookingState.COOKING, 0)

    def _handle_cancel(self, job_id: str) -> None:
        """CANCEL 명령 처리"""
        if self.current_job and self.current_job.job_id == job_id:
            self.get_logger().info(f"Cancelled job: {job_id}")
            self.current_job = None
            self._send_status(CookingState.IDLE, 0)

    def _publish_status(self) -> None:
        """주기적 상태 발행 (Mock 모드)"""
        if not self.mock_mode or not self.current_job:
            return

        elapsed = time.time() - self.current_job.start_time
        progress = min(int((elapsed / self.MOCK_COOKING_DURATION) * 100), 100)

        if elapsed >= self.MOCK_COOKING_DURATION:
            # 조리 완료
            self._send_status(CookingState.READY, 100)
            self.get_logger().info(
                f"Cooking completed: {self.current_job.job_id}"
            )
            self.current_job = None
        else:
            # 조리 중
            self._send_status(CookingState.COOKING, progress)

    def _send_status(self, state: CookingState, progress: int) -> None:
        """상태 메시지 발행"""
        job_id = self.current_job.job_id if self.current_job else ""
        order_id = self.current_job.order_id if self.current_job else ""

        status = {
            'job_id': job_id,
            'order_id': order_id,
            'status': state.value,
            'progress': progress
        }

        msg = String()
        msg.data = json.dumps(status)
        self.status_pub.publish(msg)

        self.get_logger().debug(
            f"Status: {state.value}, progress={progress}%"
        )


def main(args=None):
    rclpy.init(args=args)
    node = CookingInterfaceNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
