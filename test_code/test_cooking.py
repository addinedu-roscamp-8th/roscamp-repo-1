#!/usr/bin/env python3
"""
로봇팔 조리 테스트 스크립트
사용법: python3 test_cooking.py `ham_cheese` `mayo`

지정된 메뉴와 소스로 조리를 시작하기 위해 coordinator에게 조리 주문을 전송합니다.
로봇팔은 조리를 완료하고, 샌드위치를 검증한 후, pinky를 위해 pickup_spot에 배치합니다.

요구사항: Domain Bridge, FMS workspace sourced, Coordinator 실행, 로봇팔 실행.
"""

import sys
import os
import time
import datetime
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

# Import fleet_interfaces - need to source the workspace first
try:
    from fleet_interfaces.msg import CookingOrder, LoadingComplete
except ImportError:
    print("Error: fleet_interfaces not found.")
    print("Please source the workspace first:")
    print("  cd ~/kitchmatics/roscamp-repo-1")
    print("  source install/setup.bash")
    sys.exit(1)

# Menu mapping (menu_id -> recipe name)
MENUS = {
    "M001": "ham_cheese",
    "M002": "mushroom",
    "M003": "all_in_one",
    # Also allow recipe names directly
    "ham_cheese": "M001",
    "mushroom": "M002",
    "all_in_one": "M003",
}

# Valid sauces
VALID_SAUCES = ["mayo", "mustard", "ketchup", ""]

# Recipe descriptions
RECIPE_INFO = {
    "M001": {
        "name": "ham_cheese",
        "korean": "햄치즈샌드위치",
        "steps": ["bread", "lettuce", "cheese", "tomato", "ham", "bread"],
    },
    "M002": {
        "name": "mushroom",
        "korean": "머쉬룸샌드위치",
        "steps": ["bread", "mushroom", "tomato", "cheese", "ham", "bread"],
    },
    "M003": {
        "name": "all_in_one",
        "korean": "올인원샌드위치",
        "steps": ["bread", "tomato", "cheese", "ham", "mushroom", "lettuce", "bread"],
    },
}


class CookingOrderClient(Node):
    def __init__(self):
        super().__init__('cooking_order_client')

        # QoS for reliable delivery
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Publisher for cooking orders
        self.order_pub = self.create_publisher(
            CookingOrder,
            '/cooking/order',
            qos
        )

        # Subscriber for loading complete (result)
        self.loading_sub = self.create_subscription(
            LoadingComplete,
            '/cooking/loading_complete',
            self.loading_complete_callback,
            qos
        )

        self.order_id = None
        self.completed = False
        self.success = False

        self.get_logger().info('Cooking order client initialized')

    def send_order(self, menu_id: str, sauce: str, robot_id: str = "pinky1"):
        """coordinator에게 조리 주문을 전송합니다.

        Args:
            menu_id: 메뉴 ID (M001, M002, M003)
            sauce: 소스 종류 (mayo, mustard, ketchup, 또는 빈 문자열)
            robot_id: 배정할 로봇 ID (기본값: "pinky1")
        """

        # Wait for subscribers
        self.get_logger().info('Waiting for coordinator subscriber...')
        time.sleep(1.0)

        count = self.order_pub.get_subscription_count()
        if count == 0:
            self.get_logger().warn('No subscribers on /cooking/order - coordinator may not be running')
            self.get_logger().warn('Proceeding anyway...')

        # Generate order ID
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.order_id = f"ORD-{timestamp}-TEST"

        # Create order message
        msg = CookingOrder()
        msg.order_id = self.order_id
        msg.menu_id = menu_id
        msg.quantity = 1
        msg.sauce_type = sauce
        msg.assigned_robot_id = robot_id

        # Get recipe info
        info = RECIPE_INFO.get(menu_id, {})

        self.get_logger().info("="*50)
        self.get_logger().info(f"Sending Cooking Order")
        self.get_logger().info("="*50)
        self.get_logger().info(f"  Order ID: {msg.order_id}")
        self.get_logger().info(f"  Menu: {menu_id} ({info.get('korean', 'Unknown')})")
        self.get_logger().info(f"  Recipe: {info.get('name', 'Unknown')}")
        self.get_logger().info(f"  Sauce: {sauce if sauce else '(none)'}")
        self.get_logger().info(f"  Robot: {robot_id}")
        self.get_logger().info("="*50)

        self.order_pub.publish(msg)
        self.get_logger().info('Order sent! Waiting for completion...')
        self.get_logger().info('(Coordinator will process the order)')

    def loading_complete_callback(self, msg: LoadingComplete):
        """coordinator로부터 loading complete 메시지를 처리합니다.

        Args:
            msg: LoadingComplete 메시지 (주문 ID, 성공 여부, 로봇 ID, 메시지 포함)
        """
        if msg.order_id == self.order_id:
            self.completed = True
            self.success = msg.success

            self.get_logger().info("="*50)
            if msg.success:
                self.get_logger().info(f"ORDER COMPLETED SUCCESSFULLY!")
                self.get_logger().info(f"  Food is ready on {msg.robot_id} at pickup_spot")
            else:
                self.get_logger().error(f"ORDER FAILED!")
                self.get_logger().error(f"  Message: {msg.message}")
            self.get_logger().info("="*50)


def print_usage():
    print("Usage: python3 test_cooking.py `<menu>` `<sauce>`")
    print("")
    print("Menus:")
    print("  M001 or ham_cheese   - 햄치즈샌드위치 (ham, cheese, lettuce, tomato)")
    print("  M002 or mushroom     - 머쉬룸샌드위치 (mushroom, tomato, cheese, ham)")
    print("  M003 or all_in_one   - 올인원샌드위치 (all ingredients)")
    print("")
    print("Sauces:")
    print("  mayo     - 마요네즈")
    print("  mustard  - 머스터드")
    print("  ketchup  - 케첩")
    print("  (empty)  - 소스 없음 (use empty string or 'none')")
    print("")
    print("Examples:")
    print("  python3 test_cooking.py `ham_cheese` `mayo`")
    print("  python3 test_cooking.py `M002` `mustard`")
    print("  python3 test_cooking.py `all_in_one` ``     # no sauce")
    print("")
    print("Prerequisites:")
    print("  1. Source workspace: source ~/kitchmatics/roscamp-repo-1/install/setup.bash")
    print("  2. Domain Bridge running")
    print("  3. Robot arms running (Arm A: kitchen.launch.py, Arm B: sauce.launch.py)")
    print("  4. Coordinator running: ros2 run sandwich_coordinator sandwich_coordinator")
    print("")
    print("Note: Pinky robot should be at pickup_spot for handoff (or test without pinky)")


def normalize_menu(menu_input: str) -> str:
    """메뉴 입력값을 menu_id로 변환합니다 (M001, M002, M003).

    Args:
        menu_input: 사용자 입력 메뉴 (예: "ham_cheese", "M001")

    Returns:
        str: 표준화된 메뉴 ID (M001, M002, M003) 또는 None (잘못된 입력)
    """
    menu_input = menu_input.lower().strip()

    # Direct menu ID
    if menu_input.upper() in RECIPE_INFO:
        return menu_input.upper()

    # Recipe name
    for menu_id, info in RECIPE_INFO.items():
        if info["name"] == menu_input:
            return menu_id

    return None


def normalize_sauce(sauce_input: str) -> str:
    """소스 입력값을 표준화합니다.

    Args:
        sauce_input: 사용자 입력 소스 (예: "mayo", "none", "")

    Returns:
        str: 표준화된 소스 이름 (mayo, mustard, ketchup, 빈 문자열) 또는 None (잘못된 입력)
    """
    sauce = sauce_input.lower().strip()

    # Handle empty/none cases
    if sauce in ["", "none", "no", "null", "empty"]:
        return ""

    if sauce in VALID_SAUCES:
        return sauce

    return None


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    # Parse arguments (remove backticks if present)
    menu_input = sys.argv[1].strip('`')
    sauce_input = sys.argv[2].strip('`') if len(sys.argv) > 2 else ""

    # Normalize inputs
    menu_id = normalize_menu(menu_input)
    if menu_id is None:
        print(f"Error: Unknown menu '{menu_input}'")
        print(f"Available menus: M001/ham_cheese, M002/mushroom, M003/all_in_one")
        sys.exit(1)

    sauce = normalize_sauce(sauce_input)
    if sauce is None:
        print(f"Error: Unknown sauce '{sauce_input}'")
        print(f"Available sauces: mayo, mustard, ketchup, (empty)")
        sys.exit(1)

    # Initialize ROS2
    rclpy.init()

    client = CookingOrderClient()

    try:
        # Send the order
        client.send_order(menu_id, sauce, robot_id="pinky1")

        # Spin and wait for completion (with timeout)
        timeout = 300  # 5 minutes
        start_time = time.time()

        while rclpy.ok() and not client.completed:
            rclpy.spin_once(client, timeout_sec=1.0)

            elapsed = time.time() - start_time
            if elapsed > timeout:
                client.get_logger().error(f'Timeout waiting for order completion ({timeout}s)')
                break

        if client.completed:
            sys.exit(0 if client.success else 1)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        client.get_logger().info('Interrupted by user')
    finally:
        client.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
