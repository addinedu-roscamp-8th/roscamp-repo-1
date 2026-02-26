#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FMS Command Test Script

FMS 없이 로봇팔에 직접 조리 명령을 보내는 테스트 스크립트입니다.

Usage:
    # START 명령
    python test_fms_command.py start

    # PAUSE 명령
    python test_fms_command.py pause

    # RESUME 명령
    python test_fms_command.py resume

    # CANCEL 명령
    python test_fms_command.py cancel

    # 상태 모니터링
    python test_fms_command.py monitor
"""

import sys
import json
import argparse
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class FMSCommandTester(Node):
    """FMS 명령 테스트 노드"""

    def __init__(self):
        super().__init__('fms_command_tester')

        self.cmd_pub = self.create_publisher(
            String,
            '/arm/command',
            10
        )

        self.status_sub = self.create_subscription(
            String,
            '/arm/status',
            self._on_status,
            10
        )

        self.last_status: Optional[dict] = None
        self.job_id = f"TEST-{int(time.time())}"

    def _on_status(self, msg: String) -> None:
        """상태 수신"""
        try:
            data = json.loads(msg.data)
            self.last_status = data
            print(f"[Status] job_id={data.get('job_id')} "
                  f"status={data.get('status')} "
                  f"progress={data.get('progress')}% "
                  f"message={data.get('message', '')}")
        except json.JSONDecodeError:
            print(f"[Status] Raw: {msg.data}")

    def send_start_command(self, menu_id: int = 1, menu_name: str = "햄버거"):
        """START 명령 전송"""
        command = {
            'job_id': self.job_id,
            'operation': 'START',
            'order': {
                'order_id': f'ORD-{int(time.time())}',
                'items': [
                    {
                        'menu_id': menu_id,
                        'name': menu_name,
                        'quantity': 1
                    }
                ]
            }
        }

        msg = String()
        msg.data = json.dumps(command)
        self.cmd_pub.publish(msg)

        print(f"[Sent] START command - job_id={self.job_id} menu={menu_name}")

    def send_pause_command(self):
        """PAUSE 명령 전송"""
        command = {
            'job_id': self.job_id,
            'operation': 'PAUSE'
        }

        msg = String()
        msg.data = json.dumps(command)
        self.cmd_pub.publish(msg)

        print(f"[Sent] PAUSE command - job_id={self.job_id}")

    def send_resume_command(self):
        """RESUME 명령 전송"""
        command = {
            'job_id': self.job_id,
            'operation': 'RESUME'
        }

        msg = String()
        msg.data = json.dumps(command)
        self.cmd_pub.publish(msg)

        print(f"[Sent] RESUME command - job_id={self.job_id}")

    def send_cancel_command(self):
        """CANCEL 명령 전송"""
        command = {
            'job_id': self.job_id,
            'operation': 'CANCEL'
        }

        msg = String()
        msg.data = json.dumps(command)
        self.cmd_pub.publish(msg)

        print(f"[Sent] CANCEL command - job_id={self.job_id}")

    def monitor(self, duration: float = 60.0):
        """상태 모니터링"""
        print(f"[Monitor] Monitoring status for {duration} seconds...")
        print("Press Ctrl+C to stop")

        start_time = time.time()

        try:
            while rclpy.ok() and (time.time() - start_time) < duration:
                rclpy.spin_once(self, timeout_sec=0.1)
        except KeyboardInterrupt:
            print("\n[Monitor] Stopped by user")


def main():
    parser = argparse.ArgumentParser(
        description='Test FMS command interface'
    )
    parser.add_argument(
        'command',
        choices=['start', 'pause', 'resume', 'cancel', 'monitor'],
        help='Command to send'
    )
    parser.add_argument(
        '--menu-id',
        type=int,
        default=1,
        help='Menu ID for START command (default: 1)'
    )
    parser.add_argument(
        '--menu-name',
        type=str,
        default='햄버거',
        help='Menu name for START command (default: 햄버거)'
    )
    parser.add_argument(
        '--duration',
        type=float,
        default=60.0,
        help='Monitor duration in seconds (default: 60)'
    )
    parser.add_argument(
        '--job-id',
        type=str,
        default=None,
        help='Specific job ID to use (optional)'
    )

    args = parser.parse_args()

    rclpy.init()
    tester = FMSCommandTester()

    # 특정 job_id 사용
    if args.job_id:
        tester.job_id = args.job_id

    # 노드가 준비될 때까지 대기
    time.sleep(0.5)

    try:
        if args.command == 'start':
            tester.send_start_command(args.menu_id, args.menu_name)
            # 상태 확인을 위해 5초간 대기
            print("Waiting for status updates (5 seconds)...")
            tester.monitor(5.0)

        elif args.command == 'pause':
            tester.send_pause_command()
            tester.monitor(3.0)

        elif args.command == 'resume':
            tester.send_resume_command()
            tester.monitor(3.0)

        elif args.command == 'cancel':
            tester.send_cancel_command()
            tester.monitor(3.0)

        elif args.command == 'monitor':
            tester.monitor(args.duration)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        tester.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
