#!/usr/bin/env python3
"""
이미지 분석 서버 /analyze/arm_cmd API를 주기적으로 호출하는 테스트 노드.
로봇 팔 패키지에서 API 호출 방식을 참고할 수 있음.
"""
import json
import rclpy
from rclpy.node import Node

# API 기본 URL (파라미터 또는 상수)
DEFAULT_API_BASE = "http://192.168.0.27:5001"


def call_analyze_arm_cmd(api_base: str = DEFAULT_API_BASE, timeout: float = 15.0) -> dict:
    """
    GET /analyze/arm_cmd 호출. 로봇 팔 패키지에서 이 함수를 복사해 사용 가능.
    """
    import requests
    url = f"{api_base.rstrip('/')}/analyze/arm_cmd"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


class ArmCmdApiClientNode(Node):
    def __init__(self):
        super().__init__("arm_cmd_api_client_node")
        self.declare_parameter("api_base", DEFAULT_API_BASE)
        self.declare_parameter("interval_sec", 5.0)
        self.api_base = self.get_parameter("api_base").value
        self.interval_sec = self.get_parameter("interval_sec").value
        self.timer = self.create_timer(self.interval_sec, self.timer_callback)
        self.get_logger().info(
            f"Arm cmd API client started: {self.api_base}/analyze/arm_cmd, interval={self.interval_sec}s"
        )

    def timer_callback(self):
        try:
            data = call_analyze_arm_cmd(self.api_base)
            if not data.get("success"):
                self.get_logger().warn(f"API error: {data.get('error')} - {data.get('message')}")
                return
            detections = data.get("detections", [])
            command_key = data.get("command_key")
            ros_published = data.get("ros_published")
            self.get_logger().info(
                f"detections={len(detections)}, command_key={command_key}, ros_success={ros_published.get('success') if ros_published else None}"
            )
        except Exception as e:
            self.get_logger().warn(f"API call failed: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = ArmCmdApiClientNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
