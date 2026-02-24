"""
이미지 분석 결과에 따라 ROS2 토픽을 발행하는 모듈.
subprocess 로 ros2 topic pub 를 실행하며, ROS_DOMAIN_ID 를 적용합니다.
"""
import subprocess
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "arm_ros_config.yaml"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {
            "ros_domain_id": 21,
            "topic_name": "/arm_b/cmd",
            "message_type": "std_msgs/msg/String",
            "commands": {
                "handoff_pinky": "j1|HANDOFF_PINKY",
                "discard": "j1|DISCARD",
                "cancel": "j1|CANCEL",
            },
            "class_to_command": {
                "Hamcheese": "handoff_pinky",
                "Mushroom": "handoff_pinky",
                "All-in-one": "handoff_pinky",
                "NG": "discard",
            },
        }
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def publish_arm_cmd(command_key: str) -> dict:
    """
    ros2 topic pub --once 로 명령 발행.
    command_key: handoff_pinky | discard | cancel

    Returns:
        {"success": bool, "command": str, "message": str, "returncode": int}
    """
    cfg = _load_config()
    env = dict(__import__("os").environ)
    env["ROS_DOMAIN_ID"] = str(cfg.get("ros_domain_id", 21))
    topic = cfg.get("topic_name", "/arm_b/cmd")
    msg_type = cfg.get("message_type", "std_msgs/msg/String")
    commands = cfg.get("commands", {})
    data = commands.get(command_key)
    if not data:
        return {
            "success": False,
            "command": command_key,
            "message": f"Unknown command_key: {command_key}",
            "returncode": -1,
        }
    # ros2 topic pub --once /arm_b/cmd std_msgs/msg/String "data: 'j1|HANDOFF_PINKY'"
    cmd = [
        "ros2", "topic", "pub", "--once",
        topic,
        msg_type,
        f"data: '{data}'",
    ]
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "success": result.returncode == 0,
            "command": command_key,
            "data": data,
            "message": result.stderr.strip() if result.stderr else ("ok" if result.returncode == 0 else "failed"),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "command": command_key, "message": "timeout", "returncode": -1}
    except FileNotFoundError:
        return {"success": False, "command": command_key, "message": "ros2 not found", "returncode": -1}
    except Exception as e:
        return {"success": False, "command": command_key, "message": str(e), "returncode": -1}


def detection_to_command(detections: list[dict]) -> str | None:
    """
    분석 결과(detections)에서 우선순위에 따라 발행할 명령 키 반환.
    NG 가 있으면 discard, 그 외 샌드위치 클래스면 handoff_pinky, 없으면 None(또는 cancel).
    """
    cfg = _load_config()
    class_to_cmd = cfg.get("class_to_command") or {}
    has_ng = False
    has_sandwich = False
    for d in detections:
        name = (d.get("class_name") or "").strip()
        if not name:
            continue
        cmd = class_to_cmd.get(name)
        if cmd == "discard":
            has_ng = True
        elif cmd == "handoff_pinky":
            has_sandwich = True
    if has_ng:
        return "discard"
    if has_sandwich:
        return "handoff_pinky"
    return cfg.get("no_detection_command")  # None 이면 발행 안 함
