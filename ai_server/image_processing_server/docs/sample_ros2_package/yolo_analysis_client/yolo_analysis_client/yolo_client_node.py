#!/usr/bin/env python3
"""
YOLO 분석 서버를 호출하고 결과를 ROS2 토픽으로 발행하는 노드.
- 서버 주소와 호출 주기만 수정하면 바로 사용 가능합니다.
"""

import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


# ========== 여기만 수정하세요 ==========
# YOLO 분석 서버 주소 (AI 분석 Flask 서버 IP와 포트)
SERVER_BASE_URL = "http://192.168.0.27:5001"
# 이미지 분석 요청 주기 (초). 1.0 이면 1초마다 한 번 요청
ANALYSIS_INTERVAL_SEC = 1.0
# 사용할 API: "image" = 스냅샷 1장 분석, "video" = 영상 여러 프레임 분석
API_MODE = "image"  # "image" 또는 "video"
# ======================================


class YoloClientNode(Node):
    def __init__(self):
        super().__init__("yolo_client_node")
        self.declare_parameter("server_url", SERVER_BASE_URL)
        self.declare_parameter("interval_sec", ANALYSIS_INTERVAL_SEC)
        self.declare_parameter("api_mode", API_MODE)

        self.server_url = self.get_parameter("server_url").value.rstrip("/")
        self.interval_sec = self.get_parameter("interval_sec").value
        self.api_mode = self.get_parameter("api_mode").value

        # 분석 결과를 JSON 문자열로 발행하는 토픽
        self.pub_detections = self.create_publisher(String, "yolo/detections", 10)
        # 주기적으로 서버 호출
        self.timer = self.create_timer(self.interval_sec, self.timer_callback)
        self.get_logger().info(
            f"YOLO client started: {self.server_url}, mode={self.api_mode}, interval={self.interval_sec}s"
        )

    def timer_callback(self):
        import requests
        url = f"{self.server_url}/analyze/image" if self.api_mode == "image" else f"{self.server_url}/analyze/video"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            self.get_logger().warn(f"Server request failed: {e}")
            return
        except json.JSONDecodeError as e:
            self.get_logger().warn(f"Invalid JSON: {e}")
            return

        if not data.get("success", False):
            self.get_logger().warn(f"Server error: {data.get('error', '')} - {data.get('message', '')}")
            return

        # 전체 응답을 JSON 문자열로 발행 (다른 노드에서 파싱해 사용)
        msg = String()
        msg.data = json.dumps(data)
        self.pub_detections.publish(msg)

        count = data.get("count", 0) if self.api_mode == "image" else data.get("total_detections", 0)
        self.get_logger().info(f"Published detections: count={count}")


def main(args=None):
    rclpy.init(args=args)
    node = YoloClientNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
