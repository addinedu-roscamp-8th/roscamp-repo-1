#!/usr/bin/env python3
"""
/verify/cmd 토픽을 구독하여 API가 발행한 명령이 도달하는지 확인하는 테스트 노드.
ROS_DOMAIN_ID=21 환경에서 실행해야 함.
사용법: ros2 run arm_cmd_api_client arm_cmd_echo_test
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ArmCmdEchoTestNode(Node):
    def __init__(self):
        super().__init__("arm_cmd_echo_test_node")
        self.sub = self.create_subscription(
            String,
            "/verify/cmd",
            self.cb,
            10,
        )
        self.get_logger().info("Subscribed to /verify/cmd (ROS_DOMAIN_ID=21). Waiting for messages...")

    def cb(self, msg):
        self.get_logger().info(f"Received: data='{msg.data}'")


def main(args=None):
    rclpy.init(args=args)
    node = ArmCmdEchoTestNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
