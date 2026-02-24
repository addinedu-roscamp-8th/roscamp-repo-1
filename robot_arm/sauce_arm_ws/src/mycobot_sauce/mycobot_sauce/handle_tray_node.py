#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import threading
import time
from concurrent.futures import Future
from typing import Dict, List, Optional, Tuple

import yaml

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.action import ActionClient

from std_msgs.msg import String

from mycobot_sauce_msgs.action import MoveToPose
from mycobot_sauce_msgs.srv import SetGripper
from mycobot_sauce_msgs.srv import GetCorrectedPose

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
    """
    cmd = "<job_id>|<OP>|k=v|k=v..."
    returns (job_id, op, kv)
    """
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

def _get_pose6(poses: dict, key: str) -> List[float]:
    """
    poses.yaml 구조가 아래 둘 중 뭐든 대응:
      1) {poses:{pick_tray:[..], base:[..]}}
      2) {pick_tray:[..], base:[..]}
    """
    root = poses
    if isinstance(root, dict) and "poses" in root and isinstance(root["poses"], dict):
        root = root["poses"]
    if not isinstance(root, dict) or key not in root:
        raise RuntimeError(f"pose not found: {key}")
    v = root[key]
    if not isinstance(v, list) or len(v) != 6:
        raise RuntimeError(f"pose invalid(need 6): {key} -> {v}")
    return [float(x) for x in v]


class BTrayTransportNode(Node):
    """
    Arm B: tray transport only (pick tray -> verify table).
    Topic control:
      /arm_b/cmd:
        "<job_id>|TRANSPORT_VERIFY"
        "<job_id>|TRANSPORT_TO_VERIFY"
        "<job_id>|CANCEL"
      /arm_b/status:
        "<job_id>|RUNNING|phase=..."
        "<job_id>|DONE"
        "<job_id>|FAIL|reason=..."
    """

    def __init__(self):
        super().__init__("b_tray_transport_node")

        # params (launch로 PathJoinSubstitution 넣기)
        self.declare_parameter("poses_yaml", "poses_tray.yaml")
        self.declare_parameter("enable_bias", True)

        self.declare_parameter("speed_move", 50)
        self.declare_parameter("speed_z", 30)
        self.declare_parameter("mode", 1)
        self.declare_parameter("settle_sec", 0.3)

        self.declare_parameter("z_approach_mm", 50.0)
        self.declare_parameter("z_offset_mm", 40.0)

        # gripper value는 너 SetGripper 정의에 맞게
        self.declare_parameter("gripper_speed", 50)
        self.declare_parameter("gripper_open_value", 100)
        self.declare_parameter("gripper_close_value", 0)

        self.declare_parameter("release_at_verify", False)  # True면 place_verify에서 open까지 수행

        self.poses = load_yaml(self.get_parameter("poses_yaml").value)

        # coordinator topic interface (B로컬이라면 /arm_b/cmd 유지)
        self.cmd_sub = self.create_subscription(String, "/arm_b/cmd", self._on_cmd, 10)
        self.status_pub = self.create_publisher(String, "/arm_b/status", 10)

        # clients
        self.gripper_cli = self.create_client(SetGripper, "set_gripper")
        self.move_ac = ActionClient(self, MoveToPose, "move_to_pose")
        self.bias_cli = self.create_client(GetCorrectedPose, "get_corrected_pose")  # ✅ 추가

        # asyncio loop thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(target=self._loop_worker, daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=5.0)

        # run-state
        self._run_task: Optional[Future] = None
        self._active_job_id: Optional[str] = None

        self._active_move_goal_handle = None
        self._state_lock = threading.Lock()

        self._publish_status("sys", "IDLE")
        self.get_logger().info("Ready: /arm_b/cmd -> tray transport (poses_yaml via launch)")

    def _loop_worker(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()
        loop.run_forever()

        pending = asyncio.all_tasks(loop=loop)
        for t in pending:
            t.cancel()
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        loop.close()

    def destroy_node(self):
        try:
            with self._state_lock:
                job_id = self._active_job_id
            if job_id:
                self._cancel_internal(job_id)
        except Exception:
            pass

        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
        super().destroy_node()

    # status
    def _publish_status(self, job_id: str, state: str, **kv) -> None:
        if not job_id or not state:
            return
        msg = String()
        msg.data = build_msg(job_id, state, **kv)
        self.status_pub.publish(msg)

    # cmd callback
    def _on_cmd(self, msg: String) -> None:
        raw = (msg.data or "").strip()
        job_id, op, kv = parse_cmd(raw)

        if not job_id or not op:
            self.get_logger().warn(f"ignore invalid cmd: {raw}")
            return

        if op in ("TRANSPORT_VERIFY", "TRANSPORT_TO_VERIFY"):
            ok = self._start_internal(job_id)
            if not ok:
                self._publish_status(job_id, "FAIL", reason="busy_or_loop_not_ready")
            return

        if op == "CANCEL":
            self._cancel_internal(job_id)
            return

        self._publish_status(job_id, "FAIL", reason=f"unknown_op:{op}")

    # internal controls
    def _start_internal(self, job_id: str) -> bool:
        if self._loop is None:
            self._publish_status(job_id, "FAIL", reason="asyncio_loop_not_ready")
            return False

        with self._state_lock:
            if self._run_task is not None and not self._run_task.done():
                self._publish_status(job_id, "FAIL", reason="busy")
                return False
            self._active_job_id = job_id

        self._publish_status(job_id, "RUNNING", phase="start")

        fut = asyncio.run_coroutine_threadsafe(self._run_transport(job_id), self._loop)

        def _done_cb(f: Future):
            try:
                f.result()
                self._publish_status(job_id, "DONE")
            except asyncio.CancelledError:
                self._publish_status(job_id, "FAIL", reason="canceled")
            except Exception as e:
                self._publish_status(job_id, "FAIL", reason=f"{type(e).__name__}:{e}")
            finally:
                with self._state_lock:
                    self._run_task = None
                    self._active_job_id = None

        fut.add_done_callback(_done_cb)

        with self._state_lock:
            self._run_task = fut

        return True

    def _cancel_internal(self, job_id: str) -> None:
        with self._state_lock:
            active = self._active_job_id
            fut = self._run_task

        if active != job_id:
            return

        if fut is None or fut.done():
            self._publish_status(job_id, "FAIL", reason="not_running")
            return

        try:
            if self._loop:
                asyncio.run_coroutine_threadsafe(self._cancel_move_goal(), self._loop)
        except Exception:
            pass

        fut.cancel()
        self._publish_status(job_id, "FAIL", reason="canceling")

    async def _correct_pose(self, pose6: List[float]) -> List[float]:
        pose6 = sanitize_pose(pose6)
        if not bool(self.get_parameter("enable_bias").value):
            return pose6

        req = GetCorrectedPose.Request()
        req.raw_pose = list(pose6)

        fut = self.bias_cli.call_async(req)
        res = await self._await_ros_future(fut, timeout_sec=5.0)

        # 응답 필드명은 네 srv 정의 기준으로 corrected_pose로 가정
        return sanitize_pose(list(res.corrected_pose))

    async def _await_ros_future(self, ros_future, poll_sec: float = 0.01, timeout_sec: Optional[float] = None):
        t0 = time.time()
        while rclpy.ok() and not ros_future.done():
            if timeout_sec is not None and (time.time() - t0) > float(timeout_sec):
                raise TimeoutError("ROS future wait timeout")
            await asyncio.sleep(poll_sec)
        if not rclpy.ok():
            raise RuntimeError("ROS shutdown while waiting future")
        return ros_future.result()

    async def _wait_ready(self) -> None:
        while not self.gripper_cli.wait_for_service(timeout_sec=0.2):
            await asyncio.sleep(0.05)

        if bool(self.get_parameter("enable_bias").value):
            while not self.bias_cli.wait_for_service(timeout_sec=0.2):
                await asyncio.sleep(0.05)

        while not self.move_ac.wait_for_server(timeout_sec=0.2):
            await asyncio.sleep(0.05)

    async def _cancel_move_goal(self) -> None:
        try:
            gh = self._active_move_goal_handle
            if gh is not None:
                fut = gh.cancel_goal_async()
                _ = await self._await_ros_future(fut, poll_sec=0.02)
        except Exception:
            pass
        finally:
            self._active_move_goal_handle = None

    async def _gripper(self, value: int, speed: int):
        req = SetGripper.Request()
        req.value = int(value)
        req.speed = int(speed)
        fut = self.gripper_cli.call_async(req)
        res = await self._await_ros_future(fut)
        return bool(res.ok), str(res.message)

    async def _move_coords(self, pose6: List[float], speed: int, mode: int) -> Tuple[bool, str]:
        g = MoveToPose.Goal()
        g.target_type = 0
        g.target = list(pose6)
        g.speed = int(speed)
        g.mode = int(mode)

        fut = self.move_ac.send_goal_async(g)
        gh = await self._await_ros_future(fut)
        if not gh.accepted:
            return False, "move_goal_rejected"

        self._active_move_goal_handle = gh
        fut2 = gh.get_result_async()
        res = await self._await_ros_future(fut2)
        self._active_move_goal_handle = None
        return bool(res.result.success), str(res.result.message)

    # main sequence
    async def _run_transport(self, job_id: str) -> None:
        await self._wait_ready()

        speed_move = int(self.get_parameter("speed_move").value)
        speed_z = int(self.get_parameter("speed_z").value)
        mode = int(self.get_parameter("mode").value)
        settle = float(self.get_parameter("settle_sec").value)

        gspeed = int(self.get_parameter("gripper_speed").value)
        gopen = int(self.get_parameter("gripper_open_value").value)
        gclose = int(self.get_parameter("gripper_close_value").value)

        z_move = float(self.get_parameter("z_approach_mm").value)
        z_offset = float(self.get_parameter("z_offset_mm").value)
        release_at_verify = bool(self.get_parameter("release_at_verify").value)

        pick_tray = _get_pose6(self.poses, "pick_tray")
        base = _get_pose6(self.poses, "base")
        place_verify = _get_pose6(self.poses, "place_verify")
        place_verify_s2 = _get_pose6(self.poses, "place_verify_s2")

        self._publish_status(job_id, "RUNNING", phase="move_base")
        p = await self._correct_pose(base)
        ok, msg = await self._move_coords(p, speed=speed_move, mode=mode)
        if not ok:
            raise RuntimeError(f"move pick_tray failed: {msg}")
        await asyncio.sleep(settle)

        # 1) gripper_open
        self._publish_status(job_id, "RUNNING", phase="gripper_open")
        ok, msg = await self._gripper(gopen, gspeed)
        if not ok:
            raise RuntimeError(f"gripper open failed: {msg}")
        await asyncio.sleep(settle)

        # down 방식: pick_tray에서 바로 아래로 접근
        pick_tray_down = list(pick_tray)
        pick_tray_down[2] = float(pick_tray_down[2]) - z_move

        # 2) pick_tray (수평 접근)
        self._publish_status(job_id, "RUNNING", phase="move_pick_tray")
        p = await self._correct_pose(pick_tray)
        ok, msg = await self._move_coords(p, speed=speed_move, mode=mode)
        if not ok:
            raise RuntimeError(f"move pick_tray failed: {msg}")
        await asyncio.sleep(settle)

        # 3) down to pick_tray
        self._publish_status(job_id, "RUNNING", phase="move_pick_tray_down")
        p = await self._correct_pose(pick_tray_down)
        ok, msg = await self._move_coords(p, speed=speed_move, mode=mode)
        if not ok:
            raise RuntimeError(f"move pick_tray_down failed: {msg}")
        await asyncio.sleep(settle)

        # 4) gripper_close
        self._publish_status(job_id, "RUNNING", phase="gripper_close")
        ok, msg = await self._gripper(gclose, gspeed)
        if not ok:
            raise RuntimeError(f"gripper close failed: {msg}")
        await asyncio.sleep(settle)

        # 5) goto_base
        self._publish_status(job_id, "RUNNING", phase="move_base")
        p = await self._correct_pose(base)
        ok, msg = await self._move_coords(p, speed=speed_move, mode=mode)
        if not ok:
            raise RuntimeError(f"move base failed: {msg}")
        await asyncio.sleep(settle)

        # move to verify (수평 접근)
        self._publish_status(job_id, "RUNNING", phase="move_place_verify")
        p = await self._correct_pose(place_verify)
        ok, msg = await self._move_coords(p, speed=speed_move, mode=mode)
        if not ok:
            raise RuntimeError(f"move place_verify failed: {msg}")
        await asyncio.sleep(settle)

        # down to verify
        self._publish_status(job_id, "RUNNING", phase="move_place_verify_s2")
        p = await self._correct_pose(place_verify_s2)
        ok, msg = await self._move_coords(p, speed=speed_move, mode=mode)
        if not ok:
            raise RuntimeError(f"move place_verify_s2 failed: {msg}")
        await asyncio.sleep(settle)

        # gripper_open
        self._publish_status(job_id, "RUNNING", phase="gripper_open")
        ok, msg = await self._gripper(gopen, gspeed)
        if not ok:
            raise RuntimeError(f"gripper open failed: {msg}")
        await asyncio.sleep(settle)

"""
        # gripper_open
        self._publish_status(job_id, "RUNNING", phase="gripper_open")
        ok, msg = await self._gripper(gopen, gspeed)
        if not ok:
            raise RuntimeError(f"gripper open failed: {msg}")
        await asyncio.sleep(settle)



        # optional release at verify
        if release_at_verify:
            self._publish_status(job_id, "RUNNING", phase="gripper_open_release")
            ok, msg = await self._gripper(gopen, gspeed)
            if not ok:
                raise RuntimeError(f"gripper open(release) failed: {msg}")
            await asyncio.sleep(settle)

            self._publish_status(job_id, "RUNNING", phase="move_base_return")
            p = await self._correct_pose(pick_tray)
            ok, msg = await self._move_coords(p, speed=speed_move, mode=mode)
            if not ok:
                raise RuntimeError(f"move base_return failed: {msg}")
            await asyncio.sleep(settle)
"""

def main():
    rclpy.init()
    node = BTrayTransportNode()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()