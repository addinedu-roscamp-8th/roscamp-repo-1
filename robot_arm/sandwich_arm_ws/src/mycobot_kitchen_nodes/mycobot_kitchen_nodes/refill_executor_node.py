#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import yaml

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.action import ActionClient

from mycobot_kitchen_msgs.action import RefillStock, MoveToPose
from mycobot_kitchen_msgs.srv import GetCorrectedPose, GetInventory, SetGripper, ConsumeVat


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class RefillExecutorNode(Node):
    def __init__(self):
        super().__init__("refill_executor_node")

        self.declare_parameter("poses_yaml", "poses.yaml")
        self.poses = load_yaml(self.get_parameter("poses_yaml").value)

        # clients
        self.bias_cli = self.create_client(GetCorrectedPose, "get_corrected_pose")
        self.gripper_cli = self.create_client(SetGripper, "set_gripper")
        self.move_ac = ActionClient(self, MoveToPose, "move_to_pose")

        self.inv_get = self.create_client(GetInventory, "inventory/get")
        self.vat_consume = self.create_client(ConsumeVat, "inventory/consume_vat") 

        self._as = ActionServer(
            self, RefillStock, "refill_stock",
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=self.cancel_cb,
        )
        self.get_logger().info("Ready: /refill_stock")

    def goal_cb(self, goal_request: RefillStock.Goal):
        return GoalResponse.ACCEPT

    def cancel_cb(self, goal_handle):
        return CancelResponse.ACCEPT

    # ActionServer execute_callback은 동기 함수로 두고, 내부에서 asyncio.run으로 코루틴 실행
    def execute_cb(self, goal_handle):
        return asyncio.run(self._execute_async(goal_handle))

    async def _wait_ready(self):
        for cli in (self.bias_cli, self.gripper_cli, self.inv_get, self.vat_consume):
            while not cli.wait_for_service(timeout_sec=0.2):
                await asyncio.sleep(0.05)
        while not self.move_ac.wait_for_server(timeout_sec=0.2):
            await asyncio.sleep(0.05)

    async def _await_ros_future(self, fut, timeout_sec: float = 10.0):
        t0 = self.get_clock().now()
        while rclpy.ok() and not fut.done():
            dt = (self.get_clock().now() - t0).nanoseconds / 1e9
            if timeout_sec is not None and dt > float(timeout_sec):
                raise TimeoutError(f"ros_future_timeout:{timeout_sec}s")
            await asyncio.sleep(0.01)
        if not rclpy.ok():
            raise RuntimeError("ros_shutdown")
        return fut.result()

    async def _correct_pose(self, pose6):
        req = GetCorrectedPose.Request()
        req.raw_pose = list(pose6)
        res = await self._await_ros_future(self.bias_cli.call_async(req), timeout_sec=5.0)
        return list(res.corrected_pose)

    async def _move_coords(self, pose6, speed=50, mode=1):
        g = MoveToPose.Goal()
        g.target_type = 0
        g.target = list(pose6)
        g.speed = int(speed)
        g.mode = int(mode)

        gh = await self._await_ros_future(self.move_ac.send_goal_async(g), timeout_sec=10.0)
        if not gh.accepted:
            return False, "move_goal_rejected"
        res = await self._await_ros_future(gh.get_result_async(), timeout_sec=60.0)
        return bool(res.result.success), str(res.result.message)

    async def _gripper(self, value: int, speed: int = 50):
        req = SetGripper.Request()
        req.value = int(value)
        req.speed = int(speed)
        res = await self._await_ros_future(self.gripper_cli.call_async(req), timeout_sec=5.0)
        return bool(res.ok), str(res.message)
    
    async def _consume_vat(self, item_key: str, vats: int = 1):
        req = ConsumeVat.Request()
        req.item_key = str(item_key)
        req.vats = int(vats)
        res = await self._await_ros_future(self.vat_consume.call_async(req), timeout_sec=5.0)
        return bool(res.ok), str(res.message), int(res.vats_remaining), int(res.open_units)
    
    def _calc_dz_pick(self, vats_remaining: int, base_when_1: float = 130.0, vat_h: float = 30.0) -> float:
        """
        vats_remaining=1 -> 130
        vats_remaining=n -> 130 + (n-1)*30  (더 아래로 내려가게)
        """
        n = max(1, int(vats_remaining))
        return float(base_when_1 + (n - 1) * vat_h)
    
    async def _execute_async(self, goal_handle):
        await self._wait_ready()

        goal = goal_handle.request
        fb = RefillStock.Feedback()
        out = RefillStock.Result()

        try:
            items = list(goal.items or [])
            if not items:
                # 빈 요청도 성공으로 처리 (정책은 자유)
                out.success = True
                out.message = "ok(no_items)"
                goal_handle.succeed()
                return out

            for i, item in enumerate(items):
                if goal_handle.is_cancel_requested:
                    out.success = False
                    out.message = "canceled"
                    goal_handle.canceled()
                    return out

                fb.idx = i
                fb.item_key = str(item)
                fb.phase = "start"
                goal_handle.publish_feedback(fb)

                # poses.yaml 키 구조
                place_base = list(self.poses["base_pose"]["place_gripper_base"])
                pick_base  = list(self.poses["base_pose"]["pick_gripper_base"])
                dump_pose  = list(self.poses["base_pose"]["dump_empty_tray"])

                stock_pick_top  = list(self.poses["stock_pick"][item])
                stock_place_top = list(self.poses["stock_place"][item])

                DZ_PLACE = 80.0

                # 1) pre_place
                fb.phase = "pre_place"
                goal_handle.publish_feedback(fb)

                p = await self._correct_pose(place_base)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"place_base move failed: {msg}")

                p = await self._correct_pose(stock_place_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_place_top move failed: {msg}")

                stock_place_down = list(stock_place_top)
                stock_place_down[2] -= DZ_PLACE
                p = await self._correct_pose(stock_place_down)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_place_down move failed: {msg}")

                # 여기 동작이 “빈 트레이 내려놓기/잡기” 컨셉이면 close/open 방향은 네 장비에 맞게 유지
                ok, _ = await self._gripper(20, 50)  # close
                if not ok:
                    raise RuntimeError("gripper close failed (pre_place)")

                p = await self._correct_pose(stock_place_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_place_top retreat failed: {msg}")

                p = await self._correct_pose(place_base)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"place_base return failed: {msg}")

                # 2) dump
                fb.phase = "dump"
                goal_handle.publish_feedback(fb)

                p = await self._correct_pose(dump_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"dump move failed: {msg}")

                ok, _ = await self._gripper(95, 50)  # open
                if not ok:
                    raise RuntimeError("gripper open failed (dump)")

                # 3) pick
                fb.phase = "pick"
                goal_handle.publish_feedback(fb)
                
                inv = await self._await_ros_future(
                    self.inv_get.call_async(GetInventory.Request(item_key=str(item))),
                    timeout_sec=5.0
                )
                vats_rem = int(getattr(inv, "vats_remaining", 1))
                dz_pick = self._calc_dz_pick(vats_rem, base_when_1=130.0, vat_h=30.0)
                self.get_logger().info(f"[{item}] vats_remaining={vats_rem} -> DZ_PICK={dz_pick:.1f}mm")

                p = await self._correct_pose(pick_base)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"pick_base move failed: {msg}")

                p = await self._correct_pose(stock_pick_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_pick_top move failed: {msg}")

                stock_pick_down = list(stock_pick_top)
                stock_pick_down[2] -= dz_pick
                p = await self._correct_pose(stock_pick_down)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_pick_down move failed: {msg}")

                ok, _ = await self._gripper(20, 50)  # close
                if not ok:
                    raise RuntimeError("gripper close failed (pick)")

                p = await self._correct_pose(stock_pick_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_pick_top retreat failed: {msg}")

                # 4) final place
                fb.phase = "place"
                goal_handle.publish_feedback(fb)

                p = await self._correct_pose(place_base)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"place_base(2) move failed: {msg}")

                p = await self._correct_pose(stock_place_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_place_top(2) move failed: {msg}")

                stock_place_down2 = list(stock_place_top)
                stock_place_down2[2] -= DZ_PLACE
                p = await self._correct_pose(stock_place_down2)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_place_down2 move failed: {msg}")

                ok, _ = await self._gripper(95, 50)  # open
                if not ok:
                    raise RuntimeError("gripper open failed (final place)")
                
                fb.phase = "consume_vat"
                goal_handle.publish_feedback(fb)

                ok, msg, vats_rem, open_units = await self._consume_vat(item, 1)
                if not ok:
                    raise RuntimeError(f"consume_vat failed: {msg} vats_remaining={vats_rem} open_units={open_units}")

                # 확인 로그: open_units가 5가 되는지 확인
                self.get_logger().info(f"[{item}] consume_vat ok: vats_remaining={vats_rem} open_units={open_units}")

                p = await self._correct_pose(stock_place_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_place_top final retreat failed: {msg}")

                p = await self._correct_pose(place_base)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"place_base final return failed: {msg}")

            out.success = True
            out.message = "ok"
            goal_handle.succeed()
            return out

        except Exception as e:
            out.success = False
            out.message = f"exception:{type(e).__name__}:{e}"
            goal_handle.abort()
            return out


def main():
    rclpy.init()
    node = RefillExecutorNode()
    ex = rclpy.executors.MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    try:
        ex.spin()
    finally:
        ex.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()