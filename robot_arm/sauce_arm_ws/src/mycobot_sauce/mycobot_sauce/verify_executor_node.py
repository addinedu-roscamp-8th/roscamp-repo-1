#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import threading
from concurrent.futures import Future
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.action import ActionClient
from std_msgs.msg import String

from mycobot_sauce_msgs.action import MoveToPose
from mycobot_sauce_msgs.srv import SetGripper, GetCorrectedPose

from .common_tray import (
    load_yaml, parse_cmd, get_pose6,
    publish_status, wait_ready, correct_pose, move_coords, gripper
)


class TrayTransportNode(Node):
    def __init__(self):
        super().__init__("tray_transport_node")

        self.declare_parameter("poses_yaml", "poses_tray.yaml")
        self.declare_parameter("enable_bias", True)

        self.declare_parameter("speed_move", 50)
        self.declare_parameter("speed_z", 30)
        self.declare_parameter("mode", 1)
        self.declare_parameter("settle_sec", 0.3)

        self.declare_parameter("z_approach_mm", 40.0)
        self.declare_parameter("z_offset_mm", 10.0)

        self.declare_parameter("gripper_speed", 50)
        self.declare_parameter("gripper_open_value", 100)
        self.declare_parameter("gripper_close_value", 0)

        self.poses = load_yaml(self.get_parameter("poses_yaml").value)

        self.cmd_sub = self.create_subscription(String, "/arm_b/cmd", self._on_cmd, 10)
        self.status_pub = self.create_publisher(String, "/arm_b/status", 10)

        self.gripper_cli = self.create_client(SetGripper, "set_gripper")
        self.bias_cli = self.create_client(GetCorrectedPose, "get_corrected_pose")
        self.move_ac = ActionClient(self, MoveToPose, "move_to_pose")

        self._active_move_goal_handle = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(target=self._loop_worker, daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=5.0)

        self._run_task: Optional[Future] = None
        self._active_job_id: Optional[str] = None
        self._lock = threading.Lock()

        publish_status(self, "sys", "IDLE")

    def _loop_worker(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()
        loop.run_forever()

    def _on_cmd(self, msg: String):
        job_id, op, _ = parse_cmd(msg.data)
        if not job_id:
            return
        if op not in ("TRANSPORT_VERIFY", "TRANSPORT_TO_VERIFY"):
            return

        with self._lock:
            if self._run_task and not self._run_task.done():
                publish_status(self, job_id, "FAIL", reason="busy")
                return
            self._active_job_id = job_id

        publish_status(self, job_id, "RUNNING", phase="start")
        fut = asyncio.run_coroutine_threadsafe(self._run(job_id), self._loop)

        def _done(f: Future):
            try:
                f.result()
                publish_status(self, job_id, "DONE")
            except Exception as e:
                publish_status(self, job_id, "FAIL", reason=f"{type(e).__name__}:{e}")
            finally:
                with self._lock:
                    self._run_task = None
                    self._active_job_id = None

        fut.add_done_callback(_done)
        with self._lock:
            self._run_task = fut

    async def _run(self, job_id: str):
        await wait_ready(self)

        speed_move = int(self.get_parameter("speed_move").value)
        speed_z = int(self.get_parameter("speed_z").value)
        mode = int(self.get_parameter("mode").value)
        settle = float(self.get_parameter("settle_sec").value)

        gspeed = int(self.get_parameter("gripper_speed").value)
        gopen = int(self.get_parameter("gripper_open_value").value)
        gclose = int(self.get_parameter("gripper_close_value").value)

        z_move = float(self.get_parameter("z_approach_mm").value)
        z_offset = float(self.get_parameter("z_offset_mm").value)

        pick_tray = get_pose6(self.poses, "pick_tray")
        base = get_pose6(self.poses, "base")
        place_verify = get_pose6(self.poses, "place_verify")

        pick_tray_down = list(pick_tray)
        pick_tray_down[2] = float(pick_tray_down[2]) - (z_move + z_offset)

        place_verify_down = list(place_verify)
        place_verify_down[2] = float(place_verify_down[2]) - (z_move - z_offset)

        publish_status(self, job_id, "RUNNING", phase="gripper_open")
        ok, msg = await gripper(self, gopen, gspeed)
        if not ok:
            raise RuntimeError(f"gripper_open:{msg}")
        await asyncio.sleep(settle)

        publish_status(self, job_id, "RUNNING", phase="move_pick_tray")
        p = await correct_pose(self, pick_tray)
        ok, msg = await move_coords(self, p, speed_move, mode)
        if not ok:
            raise RuntimeError(f"move_pick_tray:{msg}")
        await asyncio.sleep(settle)

        publish_status(self, job_id, "RUNNING", phase="move_pick_tray_down")
        p = await correct_pose(self, pick_tray_down)
        ok, msg = await move_coords(self, p, speed_z, mode)
        if not ok:
            raise RuntimeError(f"move_pick_tray_down:{msg}")
        await asyncio.sleep(settle)

        publish_status(self, job_id, "RUNNING", phase="gripper_close")
        ok, msg = await gripper(self, gclose, gspeed)
        if not ok:
            raise RuntimeError(f"gripper_close:{msg}")
        await asyncio.sleep(settle)

        publish_status(self, job_id, "RUNNING", phase="move_base")
        p = await correct_pose(self, base)
        ok, msg = await move_coords(self, p, speed_move, mode)
        if not ok:
            raise RuntimeError(f"move_base:{msg}")
        await asyncio.sleep(settle)

        publish_status(self, job_id, "RUNNING", phase="move_place_verify")
        p = await correct_pose(self, place_verify)
        ok, msg = await move_coords(self, p, speed_move, mode)
        if not ok:
            raise RuntimeError(f"move_place_verify:{msg}")
        await asyncio.sleep(settle)

        publish_status(self, job_id, "RUNNING", phase="move_place_verify_down")
        p = await correct_pose(self, place_verify_down)
        ok, msg = await move_coords(self, p, speed_z, mode)
        if not ok:
            raise RuntimeError(f"move_place_verify_down:{msg}")
        await asyncio.sleep(settle)


def main():
    rclpy.init()
    node = TrayTransportNode()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    try:
        ex.spin()
    finally:
        ex.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()