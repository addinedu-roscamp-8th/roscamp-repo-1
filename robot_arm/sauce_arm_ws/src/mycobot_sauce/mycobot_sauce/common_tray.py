# -*- coding: utf-8 -*-
import asyncio
import time
from typing import Dict, List, Optional, Tuple

import yaml
import rclpy

from std_msgs.msg import String
from mycobot_sauce_msgs.action import MoveToPose
from mycobot_sauce_msgs.srv import SetGripper, GetCorrectedPose


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_kv(parts: List[str]) -> Dict[str, str]:
    d: Dict[str, str] = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def parse_cmd(raw: str) -> Tuple[Optional[str], str, Dict[str, str]]:
    raw = (raw or "").strip()
    chunks = [c.strip() for c in raw.split("|") if c.strip() != ""]
    if len(chunks) < 2:
        return None, "", {}
    job_id = chunks[0]
    op = chunks[1].upper()
    kv = _parse_kv(chunks[2:])
    return job_id, op, kv


def build_msg(job_id: str, state: str, **kv) -> str:
    s = f"{job_id}|{state}"
    for k, v in kv.items():
        s += f"|{k}={v}"
    return s


def wrap_deg(a: float) -> float:
    return (float(a) + 180.0) % 360.0 - 180.0


def sanitize_pose(p: List[float]) -> List[float]:
    out = list(map(float, p))
    if len(out) != 6:
        raise ValueError("pose must be 6 floats [x,y,z,rx,ry,rz]")
    out[3] = wrap_deg(out[3])
    out[4] = wrap_deg(out[4])
    out[5] = wrap_deg(out[5])
    return out


def get_pose6(poses: dict, key: str) -> List[float]:
    root = poses
    if isinstance(root, dict) and "poses" in root and isinstance(root["poses"], dict):
        root = root["poses"]
    if not isinstance(root, dict) or key not in root:
        raise RuntimeError(f"pose not found: {key}")
    v = root[key]
    if not isinstance(v, list) or len(v) != 6:
        raise RuntimeError(f"pose invalid(need 6): {key} -> {v}")
    return [float(x) for x in v]


async def await_ros_future(ros_future, poll_sec: float = 0.01, timeout_sec: Optional[float] = None):
    t0 = time.time()
    while rclpy.ok() and not ros_future.done():
        if timeout_sec is not None and (time.time() - t0) > float(timeout_sec):
            raise TimeoutError("ROS future wait timeout")
        await asyncio.sleep(poll_sec)
    if not rclpy.ok():
        raise RuntimeError("ROS shutdown while waiting future")
    return ros_future.result()


async def correct_pose(node, pose6: List[float]) -> List[float]:
    pose6 = sanitize_pose(pose6)
    if not bool(node.get_parameter("enable_bias").value):
        return pose6
    req = GetCorrectedPose.Request()
    req.raw_pose = list(pose6)
    fut = node.bias_cli.call_async(req)
    res = await await_ros_future(fut, timeout_sec=5.0)
    return sanitize_pose(list(res.corrected_pose))


async def gripper(node, value: int, speed: int):
    req = SetGripper.Request()
    req.value = int(value)
    req.speed = int(speed)
    fut = node.gripper_cli.call_async(req)
    res = await await_ros_future(fut, timeout_sec=3.0)
    return bool(res.ok), str(res.message)


async def move_coords(node, pose6: List[float], speed: int, mode: int) -> Tuple[bool, str]:
    g = MoveToPose.Goal()
    g.target_type = 0
    g.target = list(pose6)
    g.speed = int(speed)
    g.mode = int(mode)

    fut = node.move_ac.send_goal_async(g)
    gh = await await_ros_future(fut, timeout_sec=5.0)
    if not gh.accepted:
        return False, "move_goal_rejected"

    node._active_move_goal_handle = gh
    fut2 = gh.get_result_async()
    res = await await_ros_future(fut2, timeout_sec=30.0)
    node._active_move_goal_handle = None
    return bool(res.result.success), str(res.result.message)


async def wait_ready(node) -> None:
    while not node.gripper_cli.wait_for_service(timeout_sec=0.2):
        await asyncio.sleep(0.05)

    if bool(node.get_parameter("enable_bias").value):
        while not node.bias_cli.wait_for_service(timeout_sec=0.2):
            await asyncio.sleep(0.05)

    while not node.move_ac.wait_for_server(timeout_sec=0.2):
        await asyncio.sleep(0.05)


def publish_status(node, job_id: str, state: str, **kv) -> None:
    msg = String()
    msg.data = build_msg(job_id, state, **kv)
    node.status_pub.publish(msg)