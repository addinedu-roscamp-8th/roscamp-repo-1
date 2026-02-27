#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import threading
import time
import uuid
from concurrent.futures import Future
from typing import Dict, List, Optional, Set, Tuple

import yaml

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.action import ActionServer, ActionClient, GoalResponse, CancelResponse

from std_msgs.msg import String
from action_msgs.msg import GoalStatus

from mycobot_kitchen_msgs.action import MoveToPose, RefillStock, ExecuteRecipe
from mycobot_kitchen_msgs.srv import (
    GetCorrectedPose,
    SetSuction,
    SetGripper,
    GetInventory,
    ConsumeInventory,
)


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


def _is_empty_sauce(val: str) -> bool:
    s = (val or "").strip().lower()
    return s in ("", "none", "null", "no", "false", "0")


class RecipeExecutorNode(Node):
    """
    Arm A: ExecuteRecipe ActionServer + Coordinator topic control.

    /arm_a/cmd:
      "<job_id>|START|recipe=...|pause_before_last=1|sauce=..."
      "<job_id>|RESUME"
      "<job_id>|PAUSE"
      "<job_id>|CANCEL"
      "<job_id>|RESET"  # Force reset - clears stuck task regardless of job_id

    /arm_a/status:
      "<job_id>|RUNNING|recipe=..."
      "<job_id>|WAIT_FOR_SAUCE"
      "<job_id>|DONE"
      "<job_id>|FAIL|reason=..."
      "<job_id>|PROGRESS|step=..|item=.."
      "<job_id>|RESET_OK"  # Reset completed successfully
    """

    def __init__(self):
        super().__init__("recipe_executor_node")

        # params
        self.declare_parameter("poses_yaml", "poses.yaml")
        self.declare_parameter("recipes_yaml", "recipes.yaml")
        self.declare_parameter("refill_threshold", 0)
        self.declare_parameter("refill_at_end", True)

        self.declare_parameter("item_thickness_mm", 5.0)
        self.declare_parameter("pick_down_offset_mm", 40.0)
        self.declare_parameter("place_down_offset_mm", 80.0)

        self.poses = load_yaml(self.get_parameter("poses_yaml").value)
        self.recipes = load_yaml(self.get_parameter("recipes_yaml").value)

        # coordinator topic interface
        self.cmd_sub = self.create_subscription(String, "/arm_a/cmd", self._on_cmd, 10)
        self.status_pub = self.create_publisher(String, "/arm_a/status", 10)

        # clients
        self.bias_cli = self.create_client(GetCorrectedPose, "get_corrected_pose")
        self.suction_cli = self.create_client(SetSuction, "set_suction")
        self.gripper_cli = self.create_client(SetGripper, "set_gripper")
        self.inv_get_cli = self.create_client(GetInventory, "inventory/get")
        self.inv_consume_cli = self.create_client(ConsumeInventory, "inventory/consume")

        # Arm B status 관측
        self.sub_b = self.create_subscription(String, "/arm_b/status", self._on_b_status, 10)
        self.b_state: Dict[str, Tuple[str, Dict[str, str]]] = {}   # job_id -> (state, kv)

        # action clients
        self.move_ac = ActionClient(self, MoveToPose, "move_to_pose")
        self.refill_ac = ActionClient(self, RefillStock, "refill_stock")

        # asyncio loop thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pause_event: Optional[asyncio.Event] = None
        self._sauce_event: Optional[asyncio.Event] = None
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(target=self._loop_worker, daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=5.0)

        # run-state
        self._run_task: Optional[Future] = None
        self._current_recipe: Optional[str] = None
        self._active_job_id: Optional[str] = None
        self._pause_before_last: int = 0
        self._waiting_for_sauce: bool = False

        self._active_goal_handle = None
        self._active_move_goal_handle = None
        self._active_refill_goal_handle = None

        self._state_lock = threading.Lock()

        # ✅ job meta (START kv 저장용)  <-- 이게 없어서 AttributeError 났음
        self.job_kv: Dict[str, Dict[str, str]] = {}

        # ActionServer
        self._as = ActionServer(
            self,
            ExecuteRecipe,
            "execute_recipe",
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=self.cancel_cb,
        )

        self._publish_status("sys", "IDLE")
        self.get_logger().info("Ready: /execute_recipe + /arm_a/cmd + /arm_a/status")

    def _loop_worker(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._sauce_event = asyncio.Event()
        self._sauce_event.set()
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

    def _on_b_status(self, msg: String) -> None:
        job_id, state, kv = parse_cmd(msg.data)
        if job_id and state:
            with self._state_lock:
                self.b_state[job_id] = (state, kv)
                active = (self._active_job_id == job_id)
                waiting = self._waiting_for_sauce

            # B DONE이면 A의 barrier 해제
            if active and waiting and state == "DONE":
                if self._loop and self._sauce_event:
                    self._loop.call_soon_threadsafe(self._sauce_event.set)

    # coordinator cmd callback
    def _on_cmd(self, msg: String) -> None:
        raw = (msg.data or "").strip()
        job_id, op, kv = parse_cmd(raw)

        if not job_id or not op:
            self.get_logger().warn(f"ignore invalid cmd: {raw}")
            return

        if op == "START":
            recipe = kv.get("recipe")
            if not recipe:
                self._publish_status(job_id, "FAIL", reason="START requires recipe")
                return

            pause_before_last = int(kv.get("pause_before_last", "1"))
            sauce = kv.get("sauce", "")  # ✅ coordinator가 주면 여기로 들어옴

            # ✅ START kv 저장 (sauce 포함)
            with self._state_lock:
                self.job_kv[job_id] = {
                    "recipe": str(recipe),
                    "pause_before_last": str(pause_before_last),
                    "sauce": str(sauce or ""),
                }

            ok = self._start_internal(job_id, recipe, pause_before_last, goal_handle=None)
            if not ok:
                self._publish_status(job_id, "FAIL", reason="busy_or_loop_not_ready")
            return

        if op == "CANCEL":
            self._cancel_internal(job_id)
            return

        if op == "PAUSE":
            self._pause_internal(job_id)
            return

        if op == "RESUME":
            self._resume_internal(job_id)
            return

        if op == "RESET":
            self._reset_internal(job_id)
            return

        self._publish_status(job_id, "FAIL", reason=f"unknown_op:{op}")

    # ActionServer callbacks
    def goal_cb(self, goal_request: ExecuteRecipe.Goal):
        with self._state_lock:
            if self._run_task is not None and not self._run_task.done():
                return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def cancel_cb(self, goal_handle):
        return CancelResponse.ACCEPT

    def execute_cb(self, goal_handle):
        out = ExecuteRecipe.Result()

        recipe_name = str(goal_handle.request.recipe_name)
        job_id = uuid.uuid4().hex[:8]

        # ✅ action로 들어온 경우에도 job_kv 기본값 만들어둠 (sauce는 기본 empty)
        with self._state_lock:
            self.job_kv[job_id] = {"recipe": recipe_name, "pause_before_last": "0", "sauce": ""}

        started = self._start_internal(job_id, recipe_name, pause_before_last=0, goal_handle=goal_handle)
        if not started:
            out.success = False
            out.message = "busy"
            goal_handle.abort()
            return out

        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                self._cancel_internal(job_id)
                out.success = False
                out.message = f"canceled job_id={job_id}"
                goal_handle.canceled()
                return out

            with self._state_lock:
                fut = self._run_task

            if fut is None:
                out.success = False
                out.message = f"internal_error: no task job_id={job_id}"
                goal_handle.abort()
                return out

            if fut.done():
                break

            time.sleep(0.05)

        try:
            fut.result()
            out.success = True
            out.message = f"ok job_id={job_id}"
            goal_handle.succeed()
            return out
        except asyncio.CancelledError:
            out.success = False
            out.message = f"canceled job_id={job_id}"
            goal_handle.canceled()
            return out
        except Exception as e:
            out.success = False
            out.message = f"{type(e).__name__}: {e} job_id={job_id}"
            goal_handle.abort()
            return out
        finally:
            with self._state_lock:
                if self._active_goal_handle == goal_handle:
                    self._active_goal_handle = None

    # internal controls
    def _start_internal(self, job_id: str, recipe_name: str, pause_before_last: int, goal_handle=None) -> bool:
        if self._loop is None or self._pause_event is None or self._sauce_event is None:
            self._publish_status(job_id, "FAIL", reason="asyncio_loop_not_ready")
            return False

        with self._state_lock:
            if self._run_task is not None and not self._run_task.done():
                self._publish_status(job_id, "FAIL", reason="busy")
                return False

            # ✅ START로 안 들어오고 내부에서 시작된 경우 대비
            self.job_kv.setdefault(job_id, {
                "recipe": str(recipe_name),
                "pause_before_last": str(int(pause_before_last)),
                "sauce": "",
            })

            self._active_job_id = job_id
            self._current_recipe = recipe_name
            self._pause_before_last = int(pause_before_last)
            self._waiting_for_sauce = False
            self._active_goal_handle = goal_handle

        # reset gates
        self._loop.call_soon_threadsafe(self._pause_event.set)
        self._loop.call_soon_threadsafe(self._sauce_event.set)

        self._publish_status(job_id, "RUNNING", recipe=recipe_name, pause_before_last=str(self._pause_before_last))

        fut = asyncio.run_coroutine_threadsafe(
            self._run_recipe_by_name(job_id, recipe_name, self._pause_before_last),
            self._loop,
        )

        def _done_cb(f: Future):
            try:
                f.result()
                self._publish_status(job_id, "DONE", recipe=recipe_name)
            except asyncio.CancelledError:
                self._publish_status(job_id, "FAIL", recipe=recipe_name, reason="canceled")
            except Exception as e:
                self._publish_status(job_id, "FAIL", recipe=recipe_name, reason=f"{type(e).__name__}:{e}")
            finally:
                with self._state_lock:
                    self._run_task = None
                    self._current_recipe = None
                    self._active_job_id = None
                    self._pause_before_last = 0
                    self._waiting_for_sauce = False
                    # ✅ job meta 정리
                    self.job_kv.pop(job_id, None)

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
                asyncio.run_coroutine_threadsafe(self._cancel_sub_goals(), self._loop)
        except Exception:
            pass

        if self._loop and self._pause_event and self._sauce_event:
            self._loop.call_soon_threadsafe(self._pause_event.set)
            self._loop.call_soon_threadsafe(self._sauce_event.set)

        fut.cancel()
        self._publish_status(job_id, "FAIL", reason="canceling")

    def _reset_internal(self, job_id: str) -> None:
        """
        Force reset: 현재 작업과 관계없이 강제로 상태를 초기화합니다.
        stuck된 작업을 정리할 때 사용합니다.
        """
        with self._state_lock:
            active = self._active_job_id
            fut = self._run_task

        # Cancel any running task regardless of job_id
        if fut is not None and not fut.done():
            try:
                if self._loop:
                    asyncio.run_coroutine_threadsafe(self._cancel_sub_goals(), self._loop)
            except Exception:
                pass

            if self._loop and self._pause_event and self._sauce_event:
                self._loop.call_soon_threadsafe(self._pause_event.set)
                self._loop.call_soon_threadsafe(self._sauce_event.set)

            fut.cancel()

        # Clear state
        with self._state_lock:
            self._run_task = None
            self._active_job_id = None
            self._current_recipe = None
            self._waiting_for_sauce = False
            self._active_goal_handle = None

        self.get_logger().info(f"RESET: Cleared stuck task (was: {active})")
        self._publish_status(job_id, "RESET_OK")

    def _pause_internal(self, job_id: str) -> None:
        with self._state_lock:
            active = self._active_job_id
            fut = self._run_task
        if active != job_id:
            return
        if fut is None or fut.done():
            self._publish_status(job_id, "FAIL", reason="not_running")
            return
        if self._loop and self._pause_event:
            self._loop.call_soon_threadsafe(self._pause_event.clear)
        self._publish_status(job_id, "PAUSED")

    def _resume_internal(self, job_id: str) -> None:
        with self._state_lock:
            active = self._active_job_id
            fut = self._run_task
            waiting = self._waiting_for_sauce
        if active != job_id:
            return
        if fut is None or fut.done():
            self._publish_status(job_id, "FAIL", reason="not_running")
            return

        if self._loop and self._pause_event:
            self._loop.call_soon_threadsafe(self._pause_event.set)

        if waiting and self._loop and self._sauce_event:
            self._loop.call_soon_threadsafe(self._sauce_event.set)
            with self._state_lock:
                self._waiting_for_sauce = False

        self._publish_status(job_id, "RUNNING", recipe=str(self._current_recipe or ""))

    # asyncio-side helpers
    async def _pause_gate(self) -> None:
        if self._pause_event is None:
            return
        await self._pause_event.wait()

    async def _await_ros_future(self, ros_future, poll_sec: float = 0.01):
        while rclpy.ok() and not ros_future.done():
            await asyncio.sleep(poll_sec)
        if not rclpy.ok():
            raise RuntimeError("ROS shutdown while waiting future")
        return ros_future.result()

    async def _wait_ready(self) -> None:
        for cli in (self.bias_cli, self.suction_cli, self.gripper_cli, self.inv_get_cli, self.inv_consume_cli):
            while not cli.wait_for_service(timeout_sec=0.2):
                await asyncio.sleep(0.05)
        while not self.move_ac.wait_for_server(timeout_sec=0.2):
            await asyncio.sleep(0.05)
        while not self.refill_ac.wait_for_server(timeout_sec=0.2):
            await asyncio.sleep(0.05)

    async def _cancel_sub_goals(self) -> None:
        try:
            gh = self._active_move_goal_handle
            if gh is not None:
                fut = gh.cancel_goal_async()
                _ = await self._await_ros_future(fut, poll_sec=0.02)
        except Exception:
            pass
        finally:
            self._active_move_goal_handle = None

        try:
            gh = self._active_refill_goal_handle
            if gh is not None:
                fut = gh.cancel_goal_async()
                _ = await self._await_ros_future(fut, poll_sec=0.02)
        except Exception:
            pass
        finally:
            self._active_refill_goal_handle = None

    async def _correct_pose(self, pose6: List[float]) -> List[float]:
        req = GetCorrectedPose.Request()
        req.raw_pose = list(pose6)
        fut = self.bias_cli.call_async(req)
        res = await self._await_ros_future(fut)
        return list(res.corrected_pose)

    async def _move_coords(self, pose6: List[float], speed: int = 50, mode: int = 1) -> Tuple[bool, str]:
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

    async def _suction(self, on: bool) -> Tuple[bool, str]:
        req = SetSuction.Request()
        req.on = bool(on)
        fut = self.suction_cli.call_async(req)
        res = await self._await_ros_future(fut)
        return bool(res.ok), str(res.message)

    async def _gripper(self, value: int, speed: int = 50):
        req = SetGripper.Request()
        req.value = int(value)
        req.speed = int(speed)
        fut = self.gripper_cli.call_async(req)
        res = await self._await_ros_future(fut)
        return bool(res.ok), str(res.message)

    async def _inv_get(self, item_key: str):
        req = GetInventory.Request()
        req.item_key = str(item_key)
        fut = self.inv_get_cli.call_async(req)
        return await self._await_ros_future(fut)

    async def _inv_consume(self, item_key: str, amount: int = 1):
        req = ConsumeInventory.Request()
        req.item_key = str(item_key)
        req.amount = int(amount)
        fut = self.inv_consume_cli.call_async(req)
        return await self._await_ros_future(fut)

    async def _refill(self, item_key: str) -> Tuple[bool, str]:
        g = RefillStock.Goal()
        g.items = [str(item_key)]

        fut = self.refill_ac.send_goal_async(g)
        gh = await self._await_ros_future(fut)
        if not gh.accepted:
            return False, "refill_goal_rejected"

        self._active_refill_goal_handle = gh
        fut2 = gh.get_result_async()
        res = await self._await_ros_future(fut2)
        self._active_refill_goal_handle = None

        status = int(getattr(res, "status", -1))
        # result.success는 환경에 따라 False로 들어오는 케이스가 있어 "참고용"으로만 둔다
        ok_field = bool(getattr(res.result, "success", False))
        msg = str(getattr(res.result, "message", "") or "")

        # 디버그: status=4인데 ok_field가 False면 여기서 경고만 찍고 통과
        if status == GoalStatus.STATUS_SUCCEEDED and not ok_field:
            self.get_logger().warn(
                f"refill SUCCEEDED but result.success==False (ignore). item={item_key} msg='{msg}'"
            )

        if status != GoalStatus.STATUS_SUCCEEDED:
            return False, msg or f"refill_action_not_succeeded status={status}"

        return True, (msg or "ok")


    # recipe execution
    async def _run_recipe_by_name(self, job_id: str, recipe_name: str, pause_before_last: int) -> None:
        await self._wait_ready()

        root = self.recipes
        if isinstance(root, dict) and "recipes" in root and isinstance(root["recipes"], dict):
            recipe = root["recipes"].get(recipe_name)
        else:
            recipe = root.get(recipe_name) if isinstance(root, dict) else None

        if recipe is None:
            raise RuntimeError(f"recipe not found: {recipe_name}")

        steps = recipe.get("steps", recipe) if isinstance(recipe, dict) else recipe
        if not isinstance(steps, list):
            raise RuntimeError("recipe steps must be list")

        layer_idx = 0
        z_speed = 30
        used_items: Set[str] = set()

        th = float(self.get_parameter("item_thickness_mm").value)
        pick_down_offset = float(self.get_parameter("pick_down_offset_mm").value)
        place_down_offset = float(self.get_parameter("place_down_offset_mm").value)

        pick_base_pose = list(self.poses["base_pose"]["pick_suction_base"])
        board_base_pose = list(self.poses["base_pose"]["board_base"])
        untwist_pose = list(self.poses["untwist_angle"])

        last_index = len(steps) - 1

        ok, msg = await self._gripper(100, 50)
        if not ok:
            raise RuntimeError(f"gripper open failed: {msg}")

        p = await self._correct_pose(pick_base_pose)
        ok, msg = await self._move_coords(p)
        if not ok:
            raise RuntimeError(f"pick_base return failed: {msg}")

        try:
            for i, step in enumerate(steps):
                await self._pause_gate()
                await asyncio.sleep(0)

                need_barrier = (pause_before_last == 1) and (i == last_index)

                if need_barrier:
                    # ✅ START에서 저장된 sauce를 기준으로 "빈 소스면 barrier 스킵"
                    with self._state_lock:
                        kv0 = dict(self.job_kv.get(job_id, {}))
                        b_state, b_kv = self.b_state.get(job_id, ("", {}))

                    sauce_val = (kv0.get("sauce", "") or "")
                    if _is_empty_sauce(sauce_val):
                        self._publish_status(job_id, "RUNNING", recipe=recipe_name, note="skip_wait_for_sauce:empty_sauce")
                    else:
                        # B가 PASS 계열 DONE이면 스킵
                        is_skip = (b_state == "DONE") and (b_kv.get("reason", "") in ("pass_cmd", "skipped_no_sauce"))
                        if is_skip:
                            self._publish_status(job_id, "RUNNING", recipe=recipe_name,
                                                note=f"skip_wait_for_sauce:{b_kv.get('reason','')}")
                        else:
                            with self._state_lock:
                                self._waiting_for_sauce = True

                            self._publish_status(job_id, "WAIT_FOR_SAUCE")

                            if self._sauce_event is not None:
                                self._sauce_event.clear()
                                await self._sauce_event.wait()

                            with self._state_lock:
                                self._waiting_for_sauce = False

                            self._publish_status(job_id, "RUNNING", recipe=recipe_name)

                item = step["item"] if isinstance(step, dict) else str(step)
                used_items.add(item)
                self._publish_status(job_id, "PROGRESS", step=str(i), item=item)

                item_pose = list(self.poses["pick_suction"][item])

                inv = await self._inv_get(item)
                if not inv.ok:
                    raise RuntimeError(f"inventory get failed: {inv.message}")

                if int(inv.remaining_inven) <= 0:
                    # ✅ 남은 vat(미개봉) 0이면 refill 금지
                    if int(inv.remaining_vat) <= 0:
                        raise RuntimeError(f"no vats remaining for refill: {item}")

                    ok, msg = await self._refill(item)
                    if not ok:
                        raise RuntimeError(f"refill failed: {msg}")

                    inv = await self._inv_get(item)
                    if (not inv.ok) or int(inv.remaining_inven) <= 0:
                        raise RuntimeError("still empty after refill")

                cons = await self._inv_consume(item, 1)
                if not cons.ok:
                    ok, msg = await self._refill(item)
                    if not ok:
                        raise RuntimeError(f"consume failed and refill failed: {cons.message} / {msg}")
                    cons = await self._inv_consume(item, 1)
                    if not cons.ok:
                        raise RuntimeError(f"consume failed after refill: {cons.message}")

                remaining_now = int(cons.remaining)

                dz_pick = (5 - remaining_now) * th
                dz_place = layer_idx * th

                # pick
                p = await self._correct_pose(pick_base_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"pick_base move failed: {msg}")

                p = await self._correct_pose(item_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"item approach move failed: {msg}")

                item_down = list(item_pose)
                item_down[2] -= (dz_pick + pick_down_offset)
                p = await self._correct_pose(item_down)
                ok, msg = await self._move_coords(p, speed=z_speed)
                if not ok:
                    raise RuntimeError(f"item down move failed: {msg}")

                ok, msg = await self._suction(True)
                if not ok:
                    raise RuntimeError(f"suction on failed: {msg}")

                p = await self._correct_pose(item_pose)
                ok, msg = await self._move_coords(p, speed=z_speed)
                if not ok:
                    raise RuntimeError(f"item retreat move failed: {msg}")

                # place
                p = await self._correct_pose(board_base_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"board_base move failed: {msg}")

                ok, msg = await self._move_angles(untwist_pose)
                if not ok:
                    raise RuntimeError(f"untwist move failed: {msg}")

                p = await self._correct_pose(board_base_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"board_base(2) move failed: {msg}")

                place_down = list(board_base_pose)
                place_down[2] += (dz_place - place_down_offset)
                p = await self._correct_pose(place_down)
                ok, msg = await self._move_coords(p, speed=z_speed)
                if not ok:
                    raise RuntimeError(f"place down move failed: {msg}")

                ok, msg = await self._suction(False)
                if not ok:
                    raise RuntimeError(f"suction off failed: {msg}")

                p = await self._correct_pose(board_base_pose)
                ok, msg = await self._move_coords(p, speed=z_speed)
                if not ok:
                    raise RuntimeError(f"board_base retreat failed: {msg}")

                p = await self._correct_pose(pick_base_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"pick_base return failed: {msg}")

                layer_idx += 1

            if bool(self.get_parameter("refill_at_end").value):
                threshold = int(self.get_parameter("refill_threshold").value)
                for k in sorted(used_items):
                    inv2 = await self._inv_get(k)
                    if inv2.ok and int(inv2.remaining_inven) <= threshold:
                        if int(inv2.remaining_vat) <= 0:
                            self.get_logger().warn(f"skip refill_at_end: no vats remaining ({k})")
                            continue

                        ok, msg = await self._refill(k)
                        if not ok:
                            raise RuntimeError(f"refill_end_failed({k}): {msg}")

        except asyncio.CancelledError:
            try:    
                await self._suction(False)
            except Exception:
                pass
            raise
        except Exception:
            try:
                await self._suction(False)
            except Exception:
                pass
            raise


def main():
    rclpy.init()
    node = RecipeExecutorNode()

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