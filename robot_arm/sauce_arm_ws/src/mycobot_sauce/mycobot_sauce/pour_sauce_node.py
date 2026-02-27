#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import threading
from typing import Any, Dict, List, Optional, Tuple

import yaml

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import String

from mycobot_sauce_msgs.action import MoveToPose
from mycobot_sauce_msgs.srv import SetGripper, GetCorrectedPose


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_cmd(text: str) -> Tuple[Optional[str], Optional[str], Dict[str, str]]:
    parts = [p.strip() for p in str(text).split("|") if p.strip() != ""]
    if len(parts) < 2:
        return None, None, {}
    job_id = parts[0]
    op = parts[1].upper()
    kv = {}
    for p in parts[2:]:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k.strip()] = v.strip()
    return job_id, op, kv


def _build_msg(job_id: str, state: str, **kv) -> str:
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


def make_pour_zigzag(
    pour_pose: List[float],
    t_list: List[float],
    zig_mm: float,
) -> List[List[float]]:
    px, py, pz, prx, pry, prz = sanitize_pose(pour_pose)

    seq: List[List[float]] = []
    sign = +1.0
    for t in t_list:
        # baselink쪽으로 진행(예: x 감소 방향). 필요하면 계수/방향은 여기서만 바꿔라.
        x = px - 10.0 * float(t)

        y1 = py + sign * float(zig_mm)
        seq.append(sanitize_pose([x, y1, pz, prx, pry, prz]))
        sign *= -1.0

        y2 = py + sign * float(zig_mm)
        seq.append(sanitize_pose([x, y2, pz, prx, pry, prz]))
        sign *= -1.0

    return seq


class PourSauceNode(Node):
    """
    Arm B (topic-based)
      /arm_b/cmd:
        "<job_id>|PREPARE|sauce=<key>"
        "<job_id>|POUR|sauce=<key>"
        "<job_id>|PASS"
        "<job_id>|CANCEL"
        "<job_id>|RESET"  # Force reset - clears stuck state regardless of job_id
      /arm_b/status:
        "<job_id>|STATE|k=v..."

    중요 수정:
    - rclpy Future는 asyncio awaitable이 아님 -> 폴링 기반 _await_ros_future()로 대기
    - DONE 이후 FAIL을 절대 내지 않음 (coordinator/A 동기화 깨짐 방지)
    """

    def __init__(self):
        super().__init__("pour_sauce_node")

        self.declare_parameter("poses_yaml", "poses_sauce.yaml")
        self.cfg = load_yaml(self.get_parameter("poses_yaml").value)

        # action / services
        self.move_ac = ActionClient(self, MoveToPose, "move_to_pose")
        self.gripper_cli = self.create_client(SetGripper, "set_gripper")
        self.bias_cli = self.create_client(GetCorrectedPose, "get_corrected_pose")

        # params
        self.declare_parameter("default_speed", 50)

        # pour zigzag
        self.declare_parameter("pour_zig_mm", 15.0)
        self.declare_parameter("pour_t_list", [0.10, 0.40, 0.80])

        # gripper
        self.declare_parameter("gripper_speed", 50)
        self.declare_parameter("gr_open", 95)
        self.declare_parameter("gr_close", 0)

        # bias
        self.declare_parameter("enable_bias", True)

        # Coordinator interface
        self.arm_b_cmd_sub = self.create_subscription(String, "/arm_b/cmd", self._on_arm_b_cmd, 10)
        self.arm_b_status_pub = self.create_publisher(String, "/arm_b/status", 10)

        # job control
        self._job_id: Optional[str] = None
        self._cancel_flag: bool = False

        # prepare caching
        self._prepared: bool = False
        self._prepared_sauce: Optional[str] = None

        # PASS timers
        self._pass_done_timers: Dict[str, Any] = {}

        # asyncio loop thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._busy_lock: Optional[asyncio.Lock] = None
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(target=self._loop_worker, daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=5.0)

        self.get_logger().info("Ready: /arm_b/cmd -> /arm_b/status")

    def _loop_worker(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._busy_lock = asyncio.Lock()
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

    # -----------------------------
    # status helpers
    # -----------------------------
    def _pub_b_status(self, job_id: str, state: str, **kv):
        if not job_id:
            return
        msg = String()
        msg.data = _build_msg(job_id, state, **kv)
        self.arm_b_status_pub.publish(msg)

    def _cancel_pass_timer(self, job_id: str):
        t = self._pass_done_timers.pop(job_id, None)
        if t is not None:
            try:
                t.cancel()
            except Exception:
                pass

    def _start_pass_job(self, job_id: str, reason: str = "pass_job", done_delay_sec: float = 0.15):
        # PASS는 READY_TO_POUR -> DONE을 빠르게 내서 A barrier를 풀기 위한 용도
        self._cancel_pass_timer(job_id)

        self._pub_b_status(job_id, "READY_TO_POUR", sauce="", reason=reason)

        def _done_cb():
            self._cancel_pass_timer(job_id)
            self._pub_b_status(job_id, "DONE", sauce="", reason=reason)

        self._pass_done_timers[job_id] = self.create_timer(float(done_delay_sec), _done_cb)

    # -----------------------------
    # cmd handler
    # -----------------------------
    def _on_arm_b_cmd(self, msg: String):
        job_id, op, kv = _parse_cmd(msg.data)
        if not job_id or not op:
            return

        # CANCEL
        if op == "CANCEL":
            if job_id == self._job_id:
                self._cancel_flag = True
            self._cancel_pass_timer(job_id)
            return

        # RESET - Force clear stuck state (regardless of job_id)
        if op == "RESET":
            old_job = self._job_id
            self._job_id = None
            self._cancel_flag = True
            self.get_logger().info(f"RESET: Cleared stuck state (was: {old_job})")
            self._pub_b_status(job_id, "RESET_OK")
            return

        sauce = kv.get("sauce", "").strip()

        # PASS
        if op == "PASS":
            if self._loop is None:
                self._pub_b_status(job_id, "FAIL", reason="loop_not_ready")
                return
            self._start_pass_job(job_id, reason="pass_cmd")
            return

        # sauce 비어있으면 PREPARE/POUR도 PASS로 처리
        if op in ("PREPARE", "POUR") and sauce == "":
            self._start_pass_job(job_id, reason="skipped_no_sauce")
            return

        # busy check (다른 job이 돌고 있으면 거절)
        if self._job_id is not None and job_id != self._job_id and op in ("PREPARE", "POUR"):
            self._pub_b_status(job_id, "FAIL", reason="busy_other_job")
            return

        sauce_key = self._normalize_sauce_key(sauce)
        if sauce_key is None:
            self._pub_b_status(job_id, "FAIL", reason="invalid_sauce")
            return

        if self._loop is None:
            self._pub_b_status(job_id, "FAIL", reason="loop_not_ready")
            return

        # dispatch
        self._job_id = job_id
        self._cancel_flag = False

        if op == "PREPARE":
            self._loop.call_soon_threadsafe(asyncio.create_task, self._run_prepare(job_id, sauce_key))
            return

        if op == "POUR":
            self._loop.call_soon_threadsafe(asyncio.create_task, self._run_pour(job_id, sauce_key))
            return

        self._pub_b_status(job_id, "FAIL", reason=f"unknown_op:{op}")

    # -----------------------------
    # cfg helpers
    # -----------------------------
    def _normalize_sauce_key(self, s: str) -> Optional[str]:
        if not s:
            return None

        sauce_map = None
        if isinstance(self.cfg.get("sauce"), dict):
            sauce_map = self.cfg["sauce"]
        elif isinstance(self.cfg.get("sauces"), dict):
            sauce_map = self.cfg["sauces"]

        if not isinstance(sauce_map, dict) or not sauce_map:
            return None

        if s in sauce_map:
            return s

        # Alias mapping: short names -> actual keys in poses_sauce.yaml
        alias = {
            "mayo": "mayonnaise",
            "마요": "mayonnaise",
            "마요네즈": "mayonnaise",
            "must": "mustard",
            "머스타드": "mustard",
            "ketch": "ketchup",
            "케첩": "ketchup",
        }
        if s in alias and alias[s] in sauce_map:
            return alias[s]

        return None

    def _pose6(self, key: str) -> List[float]:
        v = self.cfg.get(key)
        if not (isinstance(v, list) and len(v) == 6):
            raise KeyError(f"poses_sauce.yaml missing/invalid '{key}' (need 6-float coords)")
        return sanitize_pose(v)

    def _sauce_pose(self, sauce_key: str) -> List[float]:
        sauce_map = None
        if isinstance(self.cfg.get("sauce"), dict):
            sauce_map = self.cfg["sauce"]
        elif isinstance(self.cfg.get("sauces"), dict):
            sauce_map = self.cfg["sauces"]
        if not isinstance(sauce_map, dict):
            raise KeyError("poses_sauce.yaml missing dict 'sauce' or 'sauces'")

        v = sauce_map.get(sauce_key)
        if not (isinstance(v, list) and len(v) == 6):
            raise KeyError(f"poses_sauce.yaml sauce missing/invalid key '{sauce_key}'")
        return sanitize_pose(v)

    # -----------------------------
    # async helpers (ROS future polling)
    # -----------------------------
    async def _await_ros_future(self, ros_future, timeout_sec: float = 10.0, poll_sec: float = 0.01):
        t0 = self.get_clock().now()
        while rclpy.ok() and not ros_future.done():
            if timeout_sec is not None:
                dt = (self.get_clock().now() - t0).nanoseconds / 1e9
                if dt > float(timeout_sec):
                    raise TimeoutError(f"ros_future_timeout:{timeout_sec}s")
            await asyncio.sleep(float(poll_sec))
        if not rclpy.ok():
            raise RuntimeError("ros_shutdown")
        return ros_future.result()

    async def _wait_ready(self):
        while not self.gripper_cli.wait_for_service(timeout_sec=0.2):
            await asyncio.sleep(0.05)

        if bool(self.get_parameter("enable_bias").value):
            while not self.bias_cli.wait_for_service(timeout_sec=0.2):
                await asyncio.sleep(0.05)

        while not self.move_ac.wait_for_server(timeout_sec=0.2):
            await asyncio.sleep(0.05)

    async def _correct_pose(self, pose6: List[float]) -> List[float]:
        pose6 = sanitize_pose(pose6)
        if not bool(self.get_parameter("enable_bias").value):
            return pose6
        req = GetCorrectedPose.Request()
        req.raw_pose = list(pose6)
        fut = self.bias_cli.call_async(req)
        res = await self._await_ros_future(fut, timeout_sec=5.0)
        return sanitize_pose(list(res.corrected_pose))

    async def _move_coords(self, pose6: List[float], speed: int, mode: int = 1):
        g = MoveToPose.Goal()
        g.target_type = 0  # coords
        g.target = list(pose6)
        g.speed = int(speed)
        g.mode = int(mode)

        fut = self.move_ac.send_goal_async(g)
        gh = await self._await_ros_future(fut, timeout_sec=10.0)
        if not gh.accepted:
            return False, "move_goal_rejected"

        fut2 = gh.get_result_async()
        res = await self._await_ros_future(fut2, timeout_sec=30.0)
        return bool(res.result.success), str(res.result.message)

    async def _gripper(self, value: int, speed: int):
        req = SetGripper.Request()
        req.value = int(value)
        req.speed = int(speed)
        fut = self.gripper_cli.call_async(req)
        res = await self._await_ros_future(fut, timeout_sec=5.0)
        return bool(res.ok), str(res.message)

    # -----------------------------
    # shared motion logic
    # -----------------------------
    def _canceled(self) -> bool:
        return bool(self._cancel_flag)

    async def _go(self, pose6: List[float], speed: int, mode: int = 1):
        if self._canceled():
            return False, "canceled"
        p = await self._correct_pose(pose6)
        return await self._move_coords(p, speed=speed, mode=mode)

    async def _do_prepare(self, sauce_key: str):
        speed = int(self.get_parameter("default_speed").value)
        gr_speed = int(self.get_parameter("gripper_speed").value)
        gr_open = int(self.get_parameter("gr_open").value)
        gr_close = int(self.get_parameter("gr_close").value)

        sauce_base = self._pose6("sauce_base")
        sauce_top = self._sauce_pose(sauce_key)

        ok, msg = await self._go(sauce_base, speed)
        if not ok:
            return False, msg

        if self._canceled():
            return False, "canceled"
        ok, msg = await self._gripper(gr_open, gr_speed)
        if not ok:
            return False, msg

        ok, msg = await self._go(sauce_top, speed)
        if not ok:
            return False, msg

        if self._canceled():
            return False, "canceled"
        ok, msg = await self._gripper(gr_close, gr_speed)
        if not ok:
            return False, msg

        ok, msg = await self._go(sauce_base, speed)
        if not ok:
            return False, msg

        return True, "ok"

    async def _do_pour(self):
        speed = int(self.get_parameter("default_speed").value)

        if "pour" in self.cfg:
            pour_pose = self._pose6("pour")
        else:
            return False, "no_pour_pose_in_yaml"

        ok, msg = await self._go(pour_pose, speed)
        if not ok:
            return False, msg

        t_list = list(self.get_parameter("pour_t_list").value)
        zig = float(self.get_parameter("pour_zig_mm").value)
        zigzag = make_pour_zigzag(pour_pose, t_list=t_list, zig_mm=zig)

        for p in zigzag:
            if self._canceled():
                return False, "canceled"
            ok, msg = await self._go(p, 10, mode=1)
            if not ok:
                return False, msg

        return True, "ok"

    async def _do_return(self, sauce_key: str):
        speed = int(self.get_parameter("default_speed").value)
        gr_speed = int(self.get_parameter("gripper_speed").value)
        gr_open = int(self.get_parameter("gr_open").value)

        sauce_base = self._pose6("sauce_base")
        sauce_top = self._sauce_pose(sauce_key)

        if self._canceled():
            return False, "canceled"

        ok, msg = await self._go(sauce_base, speed)
        if not ok:
            return False, msg

        ok, msg = await self._go(sauce_top, speed=max(10, speed // 2))
        if not ok:
            return False, msg

        ok, msg = await self._gripper(gr_open, gr_speed)
        if not ok:
            return False, msg

        ok, msg = await self._go(sauce_base, speed)
        if not ok:
            return False, msg

        return True, "ok"

    # -----------------------------
    # coordinator runnables
    # -----------------------------
    async def _run_prepare(self, job_id: str, sauce_key: str):
        if self._busy_lock is None:
            self._pub_b_status(job_id, "FAIL", reason="busy_lock_not_ready")
            return

        async with self._busy_lock:
            try:
                await self._wait_ready()
                self._pub_b_status(job_id, "PREPARING", sauce=sauce_key)

                ok, msg = await self._do_prepare(sauce_key=sauce_key)
                if not ok:
                    self._pub_b_status(job_id, "FAIL", reason=("canceled" if msg == "canceled" else msg))
                    self._prepared = False
                    self._prepared_sauce = None
                    return

                self._prepared = True
                self._prepared_sauce = sauce_key
                self._pub_b_status(job_id, "READY_TO_POUR", sauce=sauce_key)

            except Exception as e:
                self._pub_b_status(job_id, "FAIL", reason=f"exception:{e}")
            finally:
                # PREPARE는 job 유지(POUR로 이어질 수 있으니). 다만 외부에서 다른 job이 들어오면 busy로 막힘.
                self._cancel_flag = False

    async def _run_pour(self, job_id: str, sauce_key: str):
        if self._busy_lock is None:
            self._pub_b_status(job_id, "FAIL", reason="busy_lock_not_ready")
            return

        async with self._busy_lock:
            done_published = False
            try:
                await self._wait_ready()

                # 필요시 준비 자동 수행
                if (not self._prepared) or (self._prepared_sauce != sauce_key):
                    self._pub_b_status(job_id, "PREPARING", sauce=sauce_key)
                    ok, msg = await self._do_prepare(sauce_key=sauce_key)
                    if not ok:
                        self._pub_b_status(job_id, "FAIL", reason=("canceled" if msg == "canceled" else msg))
                        self._prepared = False
                        self._prepared_sauce = None
                        return
                    self._prepared = True
                    self._prepared_sauce = sauce_key
                    self._pub_b_status(job_id, "READY_TO_POUR", sauce=sauce_key)

                self._pub_b_status(job_id, "POURING", sauce=sauce_key)

                ok, msg = await self._do_pour()
                if not ok:
                    self._pub_b_status(job_id, "FAIL", reason=("canceled" if msg == "canceled" else msg))
                    self._prepared = False
                    self._prepared_sauce = None
                    return

                # ✅ DONE은 "소스 뿌리기 완료" 의미로 한 번만 발행
                self._pub_b_status(job_id, "DONE", sauce=sauce_key)
                done_published = True

                # 반환 동작은 실패해도 DONE을 FAIL로 덮어쓰지 않는다(동기화 붕괴 방지)
                ok, msg = await self._do_return(sauce_key=sauce_key)
                if not ok:
                    self.get_logger().error(f"return failed after DONE (job={job_id}): {msg}")
                    # 필요하면 상태를 하나 더 내고 싶으면 아래처럼 DONE에 note를 달아 '추가로' 발행 가능
                    # self._pub_b_status(job_id, "DONE", sauce=sauce_key, note=f"return_failed:{msg}")
                    return

                self._prepared = False
                self._prepared_sauce = None

            except Exception as e:
                if not done_published:
                    self._pub_b_status(job_id, "FAIL", reason=f"exception:{e}")
                else:
                    # DONE 이후 예외도 FAIL로 덮지 않음. 로그만.
                    self.get_logger().error(f"exception after DONE (job={job_id}): {e}")
            finally:
                self._job_id = None
                self._cancel_flag = False


def main():
    rclpy.init()
    node = PourSauceNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if node._loop:
            try:
                node._loop.call_soon_threadsafe(node._loop.stop)
            except Exception:
                pass
        rclpy.shutdown()


if __name__ == "__main__":
    main()