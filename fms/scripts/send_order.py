#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kitchmatics FMS - 주문 테스트 스크립트

터미널에서 직접 주문을 보내 Pinky 로봇을 테스트합니다.

사용법:
  # 테이블 1번으로 주문
  python3 send_order.py --table 1

  # 테이블 3번으로 햄치즈샌드위치 2개 주문
  python3 send_order.py --table 3 --menu M001 --quantity 2

  # 인터랙티브 모드
  python3 send_order.py --interactive
"""

import sys
import os
import argparse
import time
import uuid

# ROS 2 import
try:
    import rclpy
    from rclpy.node import Node
    from fleet_interfaces.msg import OrderRequest
    from builtin_interfaces.msg import Time
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    print("[WARN] ROS 2 not available, using TCP mode")

# TCP fallback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fms'))
from tcp_communication import FMSTCPClient, TCPMessage, MessageType


class OrderSender:
    """주문 전송 클래스"""

    def __init__(self, use_ros2: bool = True):
        self.use_ros2 = use_ros2 and HAS_ROS2
        self.node = None
        self.publisher = None
        self.tcp_client = None

    def setup(self):
        """설정 초기화"""
        if self.use_ros2:
            rclpy.init()
            self.node = rclpy.create_node('order_sender')
            self.publisher = self.node.create_publisher(
                OrderRequest, '/fms/order_request', 10)
            print("[ROS2] Order sender initialized")
        else:
            self.tcp_client = FMSTCPClient(
                robot_id="order_sender",
                server_host="192.168.1.3",
                server_port=9000,
                robot_type="TEST"
            )
            if self.tcp_client.connect():
                print("[TCP] Connected to FMS server")
            else:
                print("[TCP] Failed to connect to FMS server")

    def send_order(self, table_number: int, menu_id: str = "M001",
                   quantity: int = 1, sauce_type: str = "mayo"):
        """주문 전송"""
        order_id = f"ORD-{int(time.time())}-{uuid.uuid4().hex[:6]}"

        print(f"\n{'='*50}")
        print(f"  주문 전송")
        print(f"{'='*50}")
        print(f"  Order ID:    {order_id}")
        print(f"  Table:       T{table_number:02d}")
        print(f"  Menu:        {menu_id}")
        print(f"  Quantity:    {quantity}")
        print(f"  Sauce:       {sauce_type}")
        print(f"{'='*50}\n")

        if self.use_ros2:
            return self._send_ros2_order(order_id, table_number, menu_id,
                                         quantity, sauce_type)
        else:
            return self._send_tcp_order(order_id, table_number, menu_id,
                                        quantity, sauce_type)

    def _send_ros2_order(self, order_id, table_number, menu_id,
                         quantity, sauce_type):
        """ROS 2로 주문 전송"""
        msg = OrderRequest()
        msg.order_id = order_id
        msg.menu_id = menu_id
        msg.table_number = f"T{table_number:02d}"
        msg.quantity = quantity
        msg.sauce_type = sauce_type
        msg.voice_order = False

        # Timestamp
        now = time.time()
        msg.created_at.sec = int(now)
        msg.created_at.nanosec = int((now - int(now)) * 1e9)

        self.publisher.publish(msg)
        print(f"[ROS2] Order published to /fms/order_request")

        # Spin briefly to ensure message is sent
        rclpy.spin_once(self.node, timeout_sec=0.5)

        return order_id

    def _send_tcp_order(self, order_id, table_number, menu_id,
                        quantity, sauce_type):
        """TCP로 주문 전송"""
        if not self.tcp_client or not self.tcp_client.connected:
            print("[TCP] Not connected!")
            return None

        msg = TCPMessage(
            msg_type=MessageType.TASK_ASSIGN.value,
            data={
                "order_id": order_id,
                "table_number": f"T{table_number:02d}",
                "menu_id": menu_id,
                "quantity": quantity,
                "sauce_type": sauce_type,
                "skip_robot_arm": True  # 로봇팔 스킵
            },
            sender_id="order_sender"
        )

        if self.tcp_client.send_message(msg):
            print(f"[TCP] Order sent to FMS server")
            return order_id
        return None

    def cleanup(self):
        """정리"""
        if self.use_ros2 and self.node:
            self.node.destroy_node()
            rclpy.shutdown()
        if self.tcp_client:
            self.tcp_client.disconnect()


def interactive_mode(sender):
    """인터랙티브 모드"""
    print("\n" + "="*50)
    print("  Kitchmatics FMS - 주문 테스트 (인터랙티브)")
    print("="*50)
    print("\n명령어:")
    print("  order <table> [menu] [qty] - 주문 전송")
    print("  예: order 1              - 테이블 1번에 기본 주문")
    print("  예: order 3 M002 2       - 테이블 3번에 M002 2개")
    print("  quit                     - 종료")
    print()

    while True:
        try:
            cmd = input("FMS> ").strip()
            if not cmd:
                continue

            parts = cmd.split()

            if parts[0] == 'quit' or parts[0] == 'exit':
                break

            elif parts[0] == 'order':
                if len(parts) < 2:
                    print("사용법: order <table> [menu] [qty]")
                    continue

                table = int(parts[1])
                menu = parts[2] if len(parts) > 2 else "M001"
                qty = int(parts[3]) if len(parts) > 3 else 1

                sender.send_order(table, menu, qty)

            else:
                print(f"알 수 없는 명령: {parts[0]}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"오류: {e}")


def main():
    parser = argparse.ArgumentParser(description="FMS 주문 테스트")
    parser.add_argument('--table', '-t', type=int, default=1,
                        help='테이블 번호 (1-8)')
    parser.add_argument('--menu', '-m', default='M001',
                        help='메뉴 ID (M001: 햄치즈, M002: 버섯, M003: 올인원)')
    parser.add_argument('--quantity', '-q', type=int, default=1,
                        help='수량')
    parser.add_argument('--sauce', '-s', default='mayo',
                        help='소스 종류 (mayo, mustard, ketchup)')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='인터랙티브 모드')
    parser.add_argument('--tcp', action='store_true',
                        help='TCP 모드 사용 (ROS 2 대신)')

    args = parser.parse_args()

    # 센더 초기화
    sender = OrderSender(use_ros2=not args.tcp)
    sender.setup()

    try:
        if args.interactive:
            interactive_mode(sender)
        else:
            sender.send_order(
                table_number=args.table,
                menu_id=args.menu,
                quantity=args.quantity,
                sauce_type=args.sauce
            )

            # ROS 2 모드에서 잠시 대기
            if sender.use_ros2:
                print("\n[INFO] 주문이 FMS로 전송되었습니다.")
                print("[INFO] Pinky 로봇이 pickup_spot으로 이동을 시작합니다.")
                time.sleep(1)

    finally:
        sender.cleanup()


if __name__ == "__main__":
    main()
