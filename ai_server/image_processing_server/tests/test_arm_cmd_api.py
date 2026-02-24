#!/usr/bin/env python3
"""
/analyze/arm_cmd API 연동 테스트 (로봇 팔 패키지 삽입용 참고 코드).
이미지 분석 서버가 떠 있고, JetBot 스냅샷이 가능한 환경에서 실행.

사용법:
  python tests/test_arm_cmd_api.py
  또는 로봇 팔 패키지에서 call_analyze_arm_cmd() 만 복사해 사용.
"""
import os
import sys

# 프로젝트 루트를 path에 추가 (패키지 외부에서 실행 시)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def call_analyze_arm_cmd(api_base: str = "http://192.168.0.27:5001", timeout: float = 15.0) -> dict:
    """
    이미지 분석 서버 GET /analyze/arm_cmd 호출.
    서버가 스냅샷을 받아 분석하고, 결과에 따라 ROS_DOMAIN_ID=21 로
    ros2 topic pub --once /verify/cmd std_msgs/msg/String "data: 'j1|HANDOFF_PINKY'" 등 실행.

    Returns:
        {
            "success": bool,
            "detections": [...],
            "command_key": "handoff_pinky" | "discard" | None,
            "ros_published": {"success": bool, "command": str, ...} | None,
        }
    """
    try:
        import requests
    except ImportError:
        return {
            "success": False,
            "error": "requests not installed",
            "detections": [],
            "command_key": None,
            "ros_published": None,
        }
    url = f"{api_base.rstrip('/')}/analyze/arm_cmd"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": "request_failed",
            "message": str(e),
            "detections": [],
            "command_key": None,
            "ros_published": None,
        }


def main():
    print("Calling GET http://192.168.0.27:5001/analyze/arm_cmd ...")
    data = call_analyze_arm_cmd()
    print("Response:", data)
    if data.get("success"):
        print("  command_key:", data.get("command_key"))
        print("  ros_published:", data.get("ros_published"))
        print("  detections count:", data.get("count", 0))
    else:
        print("  error:", data.get("error"), data.get("message"))
    return 0 if data.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
