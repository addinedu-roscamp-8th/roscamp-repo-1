# nodes/refill_executor_node.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.action import ActionClient

# TODO: 너 패키지명으로 변경
from mycobot_kitchen_msgs.action import RefillStock, MoveToPose
from mycobot_kitchen_msgs.srv import GetCorrectedPose, SetGripper
from mycobot_kitchen_msgs.srv import SetInventory, GetInventory


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
        self.inv_set = self.create_client(SetInventory, "inventory/set")

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

    async def _wait_ready(self):
        for cli in (self.bias_cli, self.gripper_cli,self.inv_get, self.inv_set):
            while not cli.wait_for_service(timeout_sec=0.2):
                pass
        while not self.move_ac.wait_for_server(timeout_sec=0.2):
            pass

    async def _correct_pose(self, pose6):
        req = GetCorrectedPose.Request()
        req.raw_pose = list(pose6)
        res = await self.bias_cli.call_async(req)
        return list(res.corrected_pose)

    async def _move_coords(self, pose6, speed=50, mode=1):
        g = MoveToPose.Goal()
        g.target_type = 0          # coords
        g.target = list(pose6)
        g.speed = int(speed)
        g.mode = int(mode)

        gh = await self.move_ac.send_goal_async(g)
        if not gh.accepted:
            return False, "move_goal_rejected"
        res = await gh.get_result_async()
        return bool(res.result.success), res.result.message

    async def _gripper(self, value: int, speed: int = 50):
        req = SetGripper.Request()
        req.value = int(value)
        req.speed = int(speed)
        res = await self.gripper_cli.call_async(req)
        return bool(res.ok), res.message

    async def execute_cb(self, goal_handle):
        await self._wait_ready()

        goal = goal_handle.request
        fb = RefillStock.Feedback()
        out = RefillStock.Result()

        try:
            items = list(goal.items)
            for i, item in enumerate(items):
                if goal_handle.is_cancel_requested:
                    out.success = False
                    out.message = "canceled"
                    goal_handle.canceled()
                    return out

                fb.idx = i
                fb.item_key = item

                # TODO: poses.yaml 키 구조에 맞게 수정
                # ---- poses (고정) ----
                place_base = list(self.poses["base_pose"]["place_gripper_base"])
                pick_base  = list(self.poses["base_pose"]["pick_gripper_base"])
                dump_pose  = list(self.poses["base_pose"]["dump_empty_tray"])

                # ---- item 접근 poses ----
                stock_pick_top  = list(self.poses["stock_pick"][item])   # 상부 접근
                stock_place_top = list(self.poses["stock_place"][item])  # 상부 접근

                # ---- 하강값 ----
                DZ_PLACE = 80.0
                DZ_PICK  = 130.0

                # -----------------------------
                # 1) place_gripper_base -> stock_place_item -> z하강(80) -> gripper_on -> stock_place_item -> place_gripper_base
                # -----------------------------
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

                ok, _ = await self._gripper(20, 50)  # gripper_on = close(가정)
                if not ok:
                    raise RuntimeError("gripper_on(close) failed")

                p = await self._correct_pose(stock_place_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_place_top retreat failed: {msg}")

                p = await self._correct_pose(place_base)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"place_base return failed: {msg}")

                # -----------------------------
                # 2) dump_empty_tray
                # -----------------------------
                fb.phase = "dump"
                goal_handle.publish_feedback(fb)

                p = await self._correct_pose(dump_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"dump move failed: {msg}")

                # dump에서 트레이 놓는 동작이 "gripper_off"라면 여기
                ok, _ = await self._gripper(95, 50)  # gripper_off = open(가정)
                if not ok:
                    raise RuntimeError("gripper_off(open) at dump failed")

                # -----------------------------
                # 3) pick_gripper_base -> stock_pick_item -> z하강(130) -> gripper_on -> stock_pick_item -> pick_gripper_base
                # -----------------------------
                fb.phase = "pick"
                goal_handle.publish_feedback(fb)

                p = await self._correct_pose(pick_base)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"pick_base move failed: {msg}")

                p = await self._correct_pose(stock_pick_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_pick_top move failed: {msg}")

                stock_pick_down = list(stock_pick_top)
                stock_pick_down[2] -= DZ_PICK
                p = await self._correct_pose(stock_pick_down)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_pick_down move failed: {msg}")

                ok, _ = await self._gripper(20, 50)  # gripper_on = close(가정)
                if not ok:
                    raise RuntimeError("gripper_on(close) at pick failed")

                p = await self._correct_pose(stock_pick_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_pick_top retreat failed: {msg}")

                # -----------------------------
                # 4) place_gripper_base -> stock_place_item -> z하강(80) -> gripper_off -> stock_place_item -> place_gripper_base
                # -----------------------------
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

                ok, _ = await self._gripper(95, 50)  # gripper_off = open(가정)
                if not ok:
                    raise RuntimeError("gripper_off(open) at final place failed")

                p = await self._correct_pose(stock_place_top)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"stock_place_top final retreat failed: {msg}")

                p = await self._correct_pose(place_base)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"place_base final return failed: {msg}")

                # -----------------------------
                # 5) inventory full 갱신 (원하면 유지)
                # -----------------------------
                inv = await self.inv_get.call_async(GetInventory.Request(item_key=item))
                if inv.ok:
                    req = SetInventory.Request()
                    req.item_key = item
                    req.capacity = 0
                    req.remaining = int(inv.capacity)
                    _ = await self.inv_set.call_async(req)
                    
            out.success = True
            out.message = "ok"
            goal_handle.succeed()
            return out

        except Exception as e:
            out.success = False
            out.message = f"exception: {e}"
            goal_handle.abort()
            return out


def main():
    rclpy.init()
    node = RefillExecutorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
