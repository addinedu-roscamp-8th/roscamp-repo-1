# nodes/recipe_executor_node.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.action import ActionClient

# TODO: 너 패키지명으로 변경
from mycobot_kitchen_msgs.action import ExecuteRecipe, MoveToPose
from mycobot_kitchen_msgs.srv import GetCorrectedPose, SetSuction
# 추가 import
from mycobot_kitchen_msgs.srv import GetInventory, ConsumeInventory
from mycobot_kitchen_msgs.action import RefillStock  # refill 액션 클라

def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class RecipeExecutorNode(Node):
    def __init__(self):
        super().__init__("recipe_executor_node")

        self.declare_parameter("poses_yaml", "poses.yaml")
        self.declare_parameter("recipes_yaml", "recipes.yaml")

        self.poses = load_yaml(self.get_parameter("poses_yaml").value)
        self.recipes = load_yaml(self.get_parameter("recipes_yaml").value)

        # clients
        self.bias_cli = self.create_client(GetCorrectedPose, "get_corrected_pose")
        self.suction_cli = self.create_client(SetSuction, "set_suction")
        self.move_ac = ActionClient(self, MoveToPose, "move_to_pose")

        self.inv_get = self.create_client(GetInventory, "inventory/get")
        self.inv_consume = self.create_client(ConsumeInventory, "inventory/consume")
        self.refill_ac = ActionClient(self, RefillStock, "refill_stock")

        self.declare_parameter("refill_threshold", 0)  # 0이면 empty일 때만, 1~면 부족 기준
        self.declare_parameter("refill_at_end", True)  # 레시피 끝나고 자동 리필

        self.declare_parameter("item_thickness_mm", 5.0)  # 재료 z 두께
        self.declare_parameter("pick_down_offset_mm", 40.0)   # 기본 픽 하강(항상)
        self.declare_parameter("place_down_offset_mm", 80.0)

        self._as = ActionServer(
            self, ExecuteRecipe, "execute_recipe",
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=self.cancel_cb,
        )

        self.get_logger().info("Ready: /execute_recipe")

    def goal_cb(self, goal_request: ExecuteRecipe.Goal):
        return GoalResponse.ACCEPT

    def cancel_cb(self, goal_handle):
        return CancelResponse.ACCEPT

    async def _wait_ready(self):
        for cli in (self.bias_cli, self.suction_cli, self.inv_get, self.inv_consume):
            while not cli.wait_for_service(timeout_sec=0.2):
                pass

        while not self.move_ac.wait_for_server(timeout_sec=0.2):
            pass

        while not self.refill_ac.wait_for_server(timeout_sec=0.2):
            pass

    async def _correct_pose(self, pose6):
        req = GetCorrectedPose.Request()
        req.raw_pose = list(pose6)
        res = await self.bias_cli.call_async(req)
        return list(res.corrected_pose)

    async def _move_coords(self, pose6, speed=50, mode=1):
        g = MoveToPose.Goal()
        g.target_type = 0              # 0: coords
        g.target = list(pose6)
        g.speed = int(speed)
        g.mode = int(mode)

        gh = await self.move_ac.send_goal_async(g)
        if not gh.accepted:
            return False, "move_goal_rejected"
        res = await gh.get_result_async()
        return bool(res.result.success), res.result.message


    async def _move_angles(self, angles6, speed=70):
        g = MoveToPose.Goal()
        g.target_type = 1              # 1: angles
        g.target = list(angles6)
        g.speed = int(speed)
        g.mode = -1                    # angles에서는 의미없음

        gh = await self.move_ac.send_goal_async(g)
        if not gh.accepted:
            return False, "move_goal_rejected"
        res = await gh.get_result_async()
        return bool(res.result.success), res.result.message


    async def _suction(self, on: bool):
        req = SetSuction.Request()
        req.on = bool(on)
        res = await self.suction_cli.call_async(req)
        return bool(res.ok), res.message

    async def _inv_get(self, item_key: str):
        req = GetInventory.Request()
        req.item_key = item_key
        res = await self.inv_get.call_async(req)
        return res

    async def _inv_consume(self, item_key: str, amount: int = 1):
        req = ConsumeInventory.Request()
        req.item_key = item_key
        req.amount = int(amount)
        res = await self.inv_consume.call_async(req)
        return res

    async def _refill(self, item_key: str):
        g = RefillStock.Goal()
        g.items = [item_key]
        gh = await self.refill_ac.send_goal_async(g)
        if not gh.accepted:
            return False, "refill_goal_rejected"
        res = await gh.get_result_async()
        return bool(res.result.success), res.result.message

    async def execute_cb(self, goal_handle):
        await self._wait_ready()

        goal = goal_handle.request
        fb = ExecuteRecipe.Feedback()
        out = ExecuteRecipe.Result()

        layer_idx = 0
        z_speed = 30

        used_items = set()

        root = self.recipes
        # recipes: 아래에 레시피들이 들어있는 구조 지원
        if isinstance(root, dict) and "recipes" in root and isinstance(root["recipes"], dict):
            recipe = root["recipes"].get(goal.recipe_name)
        else:
            recipe = root.get(goal.recipe_name) if isinstance(root, dict) else None

        if recipe is None:
            out.success = False
            out.message = f"recipe not found: {goal.recipe_name}"
            goal_handle.abort()
            return out
    
        try:
            steps = recipe.get("steps", recipe) if isinstance(recipe, dict) else recipe

            for i, step in enumerate(steps):
                if goal_handle.is_cancel_requested:
                    out.success = False
                    out.message = "canceled"
                    goal_handle.canceled()
                    return out

                item = step["item"] if isinstance(step, dict) else str(step)
                used_items.add(item)

                fb.step_i = i
                fb.item_key = item
                fb.phase = "pick"
                goal_handle.publish_feedback(fb)

               # ---- poses (고정) ----
                pick_base_pose = list(self.poses["base_pose"]["pick_suction_base"])
                board_base_pose = list(self.poses["base_pose"]["board_base"])
                untwist_pose = list(self.poses["untwist_angle"])

                # ---- item pose (접근용) ----
                item_pose = list(self.poses["pick_suction"][item])

                # ---- inventory: 0이면 refill, 1개 소비 ----
                inv = await self._inv_get(item)
                if not inv.ok:
                    raise RuntimeError(f"inventory get failed: {inv.message}")

                if inv.remaining <= 0:
                    ok, msg = await self._refill(item)
                    if not ok:
                        raise RuntimeError(f"refill failed: {msg}")
                    inv = await self._inv_get(item)
                    if not inv.ok or inv.remaining <= 0:
                        raise RuntimeError("still empty after refill")

                cons = await self._inv_consume(item, 1)
                if not cons.ok:
                    ok, msg = await self._refill(item)
                    if not ok:
                        raise RuntimeError(f"consume failed and refill failed: {cons.message} / {msg}")
                    cons = await self._inv_consume(item, 1)
                    if not cons.ok:
                        raise RuntimeError(f"consume failed after refill: {cons.message}")

                # ---- dz 계산 ----
                th = float(self.get_parameter("item_thickness_mm").value)  # 5mm
                pick_down_offset = float(self.get_parameter("pick_down_offset_mm").value)
                place_down_offset = float(self.get_parameter("place_down_offset_mm").value)

                capacity = int(inv.capacity)
                remaining_now = int(cons.remaining)  # 소비 후 남은 개수

                # pick: 재고가 줄수록 더 내려감
                dz_pick = (capacity - remaining_now) * th 

                # place: 레이어가 늘수록 더 "위"에 내려가야 함(일반적으로 z+)
                dz_place = layer_idx * th

                # ---- (1) pick_base_pose ----
                p = await self._correct_pose(pick_base_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"pick_base move failed: {msg}")

                # ---- (2) item_pose(접근) ----
                p = await self._correct_pose(item_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"item approach move failed: {msg}")

                # ---- (3) item_pose에서 z 하강(pick) ----
                item_down = list(item_pose)
                item_down[2] -= dz_pick+pick_down_offset
                p = await self._correct_pose(item_down)
                ok, msg = await self._move_coords(p,z_speed)
                if not ok:
                    raise RuntimeError(f"item down move failed: {msg}")

                # suction on (보통 down 후 on)
                ok, _ = await self._suction(True)
                if not ok:
                    raise RuntimeError("suction on failed")

                # ---- (4) item_pose(복귀/상부) ----
                p = await self._correct_pose(item_pose)
                ok, msg = await self._move_coords(p,z_speed)
                if not ok:
                    raise RuntimeError(f"item retreat move failed: {msg}")

                # ---- (5) board_base ----
                p = await self._correct_pose(board_base_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"board_base move failed: {msg}")

                # ---- (6) untwist_angle ----
                ok, msg = await self._move_angles(untwist_pose)
                if not ok:
                    raise RuntimeError(f"untwist move failed: {msg}")

                # ---- (7) board_base ----
                p = await self._correct_pose(board_base_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"board_base(2) move failed: {msg}")

                # ---- (8) board_base에서 z 보정(place 내려가기) ----
                place_down = list(board_base_pose)
                place_down[2] += dz_place - place_down_offset   # ⚠️ 보드 위가 올라가므로 보통 +가 맞음
                p = await self._correct_pose(place_down)
                ok, msg = await self._move_coords(p,z_speed)
                if not ok:
                    raise RuntimeError(f"place down move failed: {msg}")

                # suction off (place down 후 off)
                ok, _ = await self._suction(False)
                if not ok:
                    raise RuntimeError("suction off failed")

                # ---- (9) board_base 복귀 ----
                p = await self._correct_pose(board_base_pose)
                ok, msg = await self._move_coords(p,z_speed)
                if not ok:
                    raise RuntimeError(f"board_base retreat move failed: {msg}")

                # ---- (10) pick_base_pose 복귀 ----
                p = await self._correct_pose(pick_base_pose)
                ok, msg = await self._move_coords(p)
                if not ok:
                    raise RuntimeError(f"pick_base return move failed: {msg}")
                
                layer_idx += 1
                
            # ---- (END) recipe 종료 시 부족 재료 개별 리필 ----
            if bool(self.get_parameter("refill_at_end").value):
                threshold = int(self.get_parameter("refill_threshold").value)

                for k in sorted(used_items):
                    inv2 = await self._inv_get(k)
                    if inv2.ok and int(inv2.remaining) <= threshold:
                        ok, msg = await self._refill(k)   # ✅ item 하나씩
                        if not ok:
                            raise RuntimeError(f"refill_end_failed({k}): {msg}")

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
    node = RecipeExecutorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
