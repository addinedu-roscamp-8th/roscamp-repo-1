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
from mycobot_sauce_msgs.srv import SetGripper, GetCorrectedPose

# ✅ ADD: 공통 파라미터/포즈 로더
from dataclasses import dataclass
from typing import Dict, List, Any

import json
import urllib.request
import urllib.error

# -----------------------------
# utils (keep same style)
# -----------------------------
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


def _get_pose6(poses: dict, key: str) -> List[float]:
    root = poses
    if isinstance(root, dict) and "poses" in root and isinstance(root["poses"], dict):
        root = root["poses"]
    if not isinstance(root, dict) or key not in root:
        raise RuntimeError(f"pose not found: {key}")
    v = root[key]
    if not isinstance(v, list) or len(v) != 6:
        raise RuntimeError(f"pose invalid(need 6): {key} -> {v}")
    return [float(x) for x in v]


def call_analyze_arm_cmd(api_base: str = "http://192.168.0.27:5001", timeout: float = 15.0) -> dict:
    """
    이미지 분석 서버 GET /analyze/arm_cmd 호출.
    서버가 스냅샷을 받아 분석하고, 결과에 따라 ROS_DOMAIN_ID=21 로
    ros2 topic pub --once /arm_b/cmd std_msgs/msg/String "data: 'j1|HANDOFF_PINKY'" 등 실행.

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
    url = f"{api_base.rstrip('/')}/analyze/arm_cmd/ws"
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
# -----------------------------
# Node
# -----------------------------
class BTrayOrchestratorNode(Node):
    """
    Arm B tray orchestrator (single node).

    /arm_b/cmd:
      "<job_id>|TRANSPORT_TO_VERIFY"
      "<job_id>|HANDOFF_PINKY"
      "<job_id>|DISCARD"
      "<job_id>|CANCEL"
      "<job_id>|RESET"  # Force reset - clears stuck state regardless of job_id

    /arm_b/status:
      "<job_id>|RUNNING|phase=..."
      "<job_id>|DONE|op=..."
      "<job_id>|FAIL|reason=..."
    """

    def __init__(self):
        super().__init__("b_tray_orchestrator_node")

        # params
        self.declare_parameter("poses_yaml", "poses_tray.yaml")
        self.declare_parameter("enable_bias", True)

        self.declare_parameter("speed_move", 50)
        self.declare_parameter("speed_z", 30)
        self.declare_parameter("mode", 1)
        self.declare_parameter("settle_sec", 0.3)

        # down tuning
        self.declare_parameter("z_approach_mm", 40.0)  # base down amount
        self.declare_parameter("z_offset_mm", 15.0)    # fine tweak

        # gripper
        self.declare_parameter("gripper_speed", 50)
        self.declare_parameter("gripper_open_value", 100)
        self.declare_parameter("gripper_close_value", 0)

        # (optional) force release at targets
        self.declare_parameter("release_at_verify", False)
        self.declare_parameter("release_at_pinky", True)
        self.declare_parameter("release_at_trash", True)

        self.poses = load_yaml(self.get_parameter("poses_yaml").value)

        # topic interface - /verify/cmd 사용 (TRANSPORT_TO_VERIFY, HANDOFF_PINKY 등)
        self.cmd_sub = self.create_subscription(String, "/verify/cmd", self._on_cmd, 10)
        self.status_pub = self.create_publisher(String, "/verify/status", 10)

        # clients
        self.gripper_cli = self.create_client(SetGripper, "set_gripper")
        self.bias_cli = self.create_client(GetCorrectedPose, "get_corrected_pose")
        self.move_ac = ActionClient(self, MoveToPose, "move_to_pose")

        # asyncio loop thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(target=self._loop_worker, daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=5.0)

        # run-state
        self._run_task: Optional[Future] = None
        self._active_job_id: Optional[str] = None
        self._active_op: str = ""
        self._active_move_goal_handle = None
        self._lock = threading.Lock()

        self._publish_status("sys", "IDLE")
        self.get_logger().info("Ready: /arm_b/cmd -> tray orchestrator")

    @dataclass
    class MotionCfg:
        speed_move: int
        speed_z: int
        mode: int
        settle: float
        z_move: float
        z_offset: float

    @dataclass
    class GripperCfg:
        gspeed: int
        gopen: int
        gclose: int

    @staticmethod
    def _pose_down(pose6: List[float], dz: float) -> List[float]:
        p = list(pose6)
        p[2] = float(p[2]) - float(dz)
        return p


    def _get_ctx(self) -> tuple["BTrayOrchestratorNode.MotionCfg", "BTrayOrchestratorNode.GripperCfg"]:
        m = self.MotionCfg(
            speed_move=int(self.get_parameter("speed_move").value),
            speed_z=int(self.get_parameter("speed_z").value),
            mode=int(self.get_parameter("mode").value),
            settle=float(self.get_parameter("settle_sec").value),
            z_move=float(self.get_parameter("z_approach_mm").value),
            z_offset=float(self.get_parameter("z_offset_mm").value),
        )
        g = self.GripperCfg(
            gspeed=int(self.get_parameter("gripper_speed").value),
            gopen=int(self.get_parameter("gripper_open_value").value),
            gclose=int(self.get_parameter("gripper_close_value").value),
        )
        return m, g


    def _get_poses(self, *keys: str) -> Dict[str, List[float]]:
        return {k: _get_pose6(self.poses, k) for k in keys}

    # -----------------------------
    # infra
    # -----------------------------
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
            with self._lock:
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

    def _publish_status(self, job_id: str, state: str, **kv) -> None:
        if not job_id or not state:
            return
        msg = String()
        msg.data = build_msg(job_id, state, **kv)
        self.status_pub.publish(msg)

    # -----------------------------
    # cmd handling
    # -----------------------------
    def _on_cmd(self, msg: String) -> None:
        job_id, op, kv = parse_cmd(msg.data)
        if not job_id or not op:
            return

        if op == "CANCEL":
            self._cancel_internal(job_id)
            return

        if op == "RESET":
            self._reset_internal(job_id)
            return

        # supported ops
        if op not in (
            "TRANSPORT_VERIFY", "TRANSPORT_TO_VERIFY",
            "HANDOFF_PINKY", "PLACE_PINKY",
            "DISCARD", "TRASH",
        ):
            self._publish_status(job_id, "FAIL", reason=f"unknown_op:{op}")
            return

        ok = self._start_internal(job_id, op)
        if not ok:
            self._publish_status(job_id, "FAIL", reason="busy_or_loop_not_ready")

    def _start_internal(self, job_id: str, op: str) -> bool:
        if self._loop is None:
            self._publish_status(job_id, "FAIL", reason="asyncio_loop_not_ready")
            return False

        with self._lock:
            if self._run_task is not None and not self._run_task.done():
                self._publish_status(job_id, "FAIL", reason="busy")
                return False
            self._active_job_id = job_id
            self._active_op = op

        self._publish_status(job_id, "RUNNING", phase="start", op=op)

        fut = asyncio.run_coroutine_threadsafe(self._run_by_op(job_id, op), self._loop)

        def _done_cb(f: Future):
            try:
                f.result()
                self._publish_status(job_id, "DONE", op=op)
            except asyncio.CancelledError:
                self._publish_status(job_id, "FAIL", reason="canceled", op=op)
            except Exception as e:
                self._publish_status(job_id, "FAIL", reason=f"{type(e).__name__}:{e}", op=op)
            finally:
                with self._lock:
                    self._run_task = None
                    self._active_job_id = None
                    self._active_op = ""

        fut.add_done_callback(_done_cb)

        with self._lock:
            self._run_task = fut

        return True

    def _cancel_internal(self, job_id: str) -> None:
        with self._lock:
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

    def _reset_internal(self, job_id: str) -> None:
        """Force reset: 현재 작업과 관계없이 강제로 상태를 초기화합니다."""
        with self._lock:
            old_job = self._active_job_id
            fut = self._run_task

        # Cancel any running task regardless of job_id
        if fut is not None and not fut.done():
            try:
                if self._loop:
                    asyncio.run_coroutine_threadsafe(self._cancel_move_goal(), self._loop)
            except Exception:
                pass
            fut.cancel()

        # Clear state
        with self._lock:
            self._run_task = None
            self._active_job_id = None
            self._active_op = None

        self.get_logger().info(f"RESET: Cleared stuck task (was: {old_job})")
        self._publish_status(job_id, "RESET_OK")

    # -----------------------------
    # asyncio helpers
    # -----------------------------
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
                _ = await self._await_ros_future(fut, poll_sec=0.02, timeout_sec=2.0)
        except Exception:
            pass
        finally:
            self._active_move_goal_handle = None

    async def _correct_pose(self, pose6: List[float]) -> List[float]:
        pose6 = sanitize_pose(pose6)
        if not bool(self.get_parameter("enable_bias").value):
            return pose6

        req = GetCorrectedPose.Request()
        req.raw_pose = list(pose6)
        fut = self.bias_cli.call_async(req)
        res = await self._await_ros_future(fut, timeout_sec=5.0)
        return sanitize_pose(list(res.corrected_pose))

    async def _gripper(self, value: int, speed: int):
        req = SetGripper.Request()
        req.value = int(value)
        req.speed = int(speed)
        fut = self.gripper_cli.call_async(req)
        res = await self._await_ros_future(fut, timeout_sec=3.0)
        return bool(res.ok), str(res.message)

    async def _move_coords(self, pose6: List[float], speed: int, mode: int) -> Tuple[bool, str]:
        g = MoveToPose.Goal()
        g.target_type = 0
        g.target = list(pose6)
        g.speed = int(speed)
        g.mode = int(mode)

        fut = self.move_ac.send_goal_async(g)
        gh = await self._await_ros_future(fut, timeout_sec=5.0)
        if not gh.accepted:
            return False, "move_goal_rejected"

        self._active_move_goal_handle = gh
        fut2 = gh.get_result_async()
        res = await self._await_ros_future(fut2, timeout_sec=30.0)
        self._active_move_goal_handle = None
        return bool(res.result.success), str(res.result.message)

    async def _move_angles(self, angles6: List[float], speed: int = 70) -> Tuple[bool, str]:
        g = MoveToPose.Goal()
        g.target_type = 1
        g.target = list(angles6)
        g.speed = int(speed)
        g.mode = -1

        fut = self.move_ac.send_goal_async(g)
        gh = await self._await_ros_future(fut)
        if not gh.accepted:
            return False, "move_goal_rejected"

        self._active_move_goal_handle = gh
        fut2 = gh.get_result_async()
        res = await self._await_ros_future(fut2)
        self._active_move_goal_handle = None
        return bool(res.result.success), str(res.result.message)

    async def _go(self, pose6: List[float], speed: int, mode: int) -> None:
        p = await self._correct_pose(pose6)
        ok, msg = await self._move_coords(p, speed=speed, mode=mode)
        if not ok:
            raise RuntimeError(msg)

    async def _post_analyze(self, url: str, payload: dict, timeout_sec: float = 2.0) -> Tuple[bool, str]:
        def _do_post() -> Tuple[bool, str]:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url=url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    body = resp.read().decode("utf-8", errors="ignore")
                    return True, f"HTTP {resp.status} {body[:200]}"
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    body = ""
                return False, f"HTTPError {e.code} {body[:200]}"
            except Exception as e:
                return False, f"{type(e).__name__}:{e}"

        return await asyncio.to_thread(_do_post)

    # -----------------------------
    # op dispatcher
    # -----------------------------
    async def _run_by_op(self, job_id: str, op: str) -> None:
        await self._wait_ready()

        op = (op or "").upper()
        if op in ("TRANSPORT_VERIFY", "TRANSPORT_TO_VERIFY"):
            await self._run_transport_verify(job_id)
            return
        if op in ("HANDOFF_PINKY", "PLACE_PINKY"):
            await self._run_handoff_pinky(job_id)
            return
        if op in ("DISCARD", "TRASH"):
            await self._run_discard(job_id)
            return
        raise RuntimeError(f"unknown_op:{op}")

    # -----------------------------
    # sequences
    # -----------------------------
    async def _run_transport_verify(self, job_id: str) -> None:
        m, g = self._get_ctx()
        poses = self._get_poses("pick_tray", "base", "place_verify", "place_verify_s2")

        pick_tray = poses["pick_tray"]
        base = poses["base"]
        place_verify = poses["place_verify"]
        place_verify_s2 = poses["place_verify_s2"]

        pick_tray_down = self._pose_down(pick_tray, dz=m.z_move)

        self._publish_status(job_id, "RUNNING", phase="gripper_open")
        ok, msg = await self._gripper(g.gopen, g.gspeed)
        if not ok:
            raise RuntimeError(f"gripper_open:{msg}")
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_pick_tray")
        await self._go(pick_tray, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_pick_tray_down")
        await self._go(pick_tray_down, m.speed_z, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="gripper_close")
        ok, msg = await self._gripper(g.gclose, g.gspeed)
        if not ok:
            raise RuntimeError(f"gripper_close:{msg}")
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_base")
        await self._go(base, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_place_verify")
        await self._go(place_verify, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_place_verify_down")
        await self._go(place_verify_s2, m.speed_z, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="gripper_open")
        ok, msg = await self._gripper(g.gopen, g.gspeed)
        if not ok:
            raise RuntimeError(f"gripper_open:{msg}")
        await asyncio.sleep(m.settle)

        # 이미지 분석 API 호출 (서버가 /arm_b/cmd 로도 발행하므로, 여기서는 응답만 사용해 다음 동작을 결정)
        data = await asyncio.to_thread(call_analyze_arm_cmd)
        if data.get("success"):
            command_key = data.get("command_key")  # "handoff_pinky" | "discard" | None
            ros_published = data.get("ros_published")
            detections = data.get("detections", [])
            self.get_logger().info(
                f"analyze_arm_cmd: command_key={command_key}, ros_published={ros_published}, detections={len(detections)}"
            )
            self.get_logger().info(f"detections raw = {detections}")
            if command_key == "handoff_pinky":
                await self._run_handoff_pinky(job_id)
            elif command_key == "discard":
                await self._run_discard(job_id)
        else:
            self.get_logger().warn(
                f"analyze_arm_cmd failed: error={data.get('error')}, message={data.get('message')}"
            )

    # --------------------------------------------------------------------------------------------------------------
    async def _run_handoff_pinky(self, job_id: str) -> None:
        m, g = self._get_ctx()
        poses = self._get_poses("base", "place_verify", "place_verify_s2", "place_pinky")

        base = poses["base"]
        place_verify = poses["place_verify"]
        place_verify_s2 = poses["place_verify_s2"]
        place_pinky = poses["place_pinky"]

        # 1) verify로 가서 트레이 집기

        verify_down = self._pose_down(place_verify_s2, dz=(m.z_move - m.z_offset))
        verify_down[0]-=12

        self._publish_status(job_id, "RUNNING", phase="move_place_verify_down")
        await self._go(verify_down, m.speed_z, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="gripper_close")
        ok, msg = await self._gripper(g.gclose, g.gspeed)
        if not ok:
            raise RuntimeError(f"gripper_close:{msg}")
        await asyncio.sleep(m.settle)

        verify_down[2]+=30
        verify_up=verify_down
        self._publish_status(job_id, "RUNNING", phase="move_verify_up")
        await self._go(verify_up, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_place_verify")
        await self._go(place_verify, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        # 2) base로 복귀
        self._publish_status(job_id, "RUNNING", phase="move_base")
        await self._go(base, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        # 3) pinky 위치로 이동 후 내려놓기
        self._publish_status(job_id, "RUNNING", phase="move_place_pinky")
        await self._go(place_pinky, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)
        
        place_turn = place_pinky
        place_turn[5]+=90
        
        self._publish_status(job_id, "RUNNING", phase="move_place_turn")
        await self._go(place_turn, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="gripper_open_release")
        ok, msg = await self._gripper(g.gopen, g.gspeed)
        if not ok:
            raise RuntimeError(f"gripper_open_release:{msg}")
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="gripper_open_release")                
        ok, msg = await self._move_angles([0,0,0,0,0,0])
        if not ok:
            raise RuntimeError(f"gripper_open_release:{msg}")

        self._publish_status(job_id, "RUNNING", phase="move_base")
        await self._go(base, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)
    # --------------------------------------------------------------------------------------------------------------
    async def _run_discard(self, job_id: str) -> None:
        m, g = self._get_ctx()
        poses = self._get_poses("base","pick_tray", "place_verify", "place_verify_s2", "trash", "trash_s2")
        
        base = poses["base"]
        pick_tray = poses["pick_tray"]
        place_verify = poses["place_verify"]
        place_verify_s2 = poses["place_verify_s2"]
        trash = poses["trash"]
        trash_s2 = poses["trash_s2"]

        # 1) verify로 가서 트레이 집기

        verify_down = self._pose_down(place_verify_s2, dz=(m.z_move - m.z_offset))
        verify_down[0]-=12
        self._publish_status(job_id, "RUNNING", phase="move_place_verify_down")
        await self._go(verify_down, m.speed_z, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="gripper_close")
        ok, msg = await self._gripper(g.gclose, g.gspeed)
        if not ok:
            raise RuntimeError(f"gripper_close:{msg}")
        await asyncio.sleep(m.settle)

        verify_down[2]+=30
        verify_up=verify_down

        self._publish_status(job_id, "RUNNING", phase="move_verify_up")
        await self._go(verify_up, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_place_verify")
        await self._go(place_verify, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        # 3) trash로 이동 후 버리기
        self._publish_status(job_id, "RUNNING", phase="move_trash")
        await self._go(trash, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_trash_s2")
        await self._go(trash_s2, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        # 4) base 복귀
        self._publish_status(job_id, "RUNNING", phase="move_base")
        await self._go(base, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="move_pick_tray")
        await self._go(pick_tray, m.speed_move, m.mode)
        await asyncio.sleep(m.settle)

        self._publish_status(job_id, "RUNNING", phase="gripper_open_release")
        ok, msg = await self._gripper(g.gopen, g.gspeed)
        if not ok:
            raise RuntimeError(f"gripper_open_release:{msg}")
        await asyncio.sleep(m.settle)


        
def main():
    rclpy.init()
    node = BTrayOrchestratorNode()

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