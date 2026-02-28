#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml
from typing import Dict

import rclpy
from rclpy.node import Node

from std_msgs.msg import Empty
from mycobot_kitchen_msgs.srv import GetInventory, ConsumeInventory, SetInventory


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class InventoryManagerNode(Node):
    def __init__(self):
        super().__init__("inventory_manager_node")

        # params
        # 예: inventory.yaml:
        # capacity: {ham: 20, cheese: 20, lettuce: 20, tomato: 20}
        # remaining: {ham: 20, cheese: 20, lettuce: 20, tomato: 20}  # 없으면 capacity로 초기화
        self.declare_parameter("inventory_yaml", "inventory.yaml")

        inv_path = self.get_parameter("inventory_yaml").value
        data = load_yaml(inv_path)

        cap = data.get("capacity", {}) if isinstance(data, dict) else {}
        rem = data.get("remaining", {}) if isinstance(data, dict) else {}

        self.capacity: Dict[str, int] = {k: int(v) for k, v in cap.items()}
        self.remaining: Dict[str, int] = {}
        for k, c in self.capacity.items():
            self.remaining[k] = int(rem.get(k, c))

        self.create_service(GetInventory, "inventory/get", self.on_get)
        self.create_service(ConsumeInventory, "inventory/consume", self.on_consume)
        self.create_service(SetInventory, "inventory/set", self.on_set)

        # Reset all inventory to capacity (triggered by FMS on startup)
        self.create_subscription(Empty, "inventory/reset_all", self.on_reset_all, 10)

        self.get_logger().info(f"Loaded inventory from {inv_path}: {self.remaining}")

    def on_get(self, req: GetInventory.Request, res: GetInventory.Response):
        k = req.item_key
        if k not in self.capacity:
            res.ok = False
            res.remaining = 0
            res.capacity = 0
            res.message = "unknown_item"
            return res
        res.ok = True
        res.remaining = int(self.remaining.get(k, 0))
        res.capacity = int(self.capacity.get(k, 0))
        res.message = "ok"
        return res

    def on_consume(self, req: ConsumeInventory.Request, res: ConsumeInventory.Response):
        k = req.item_key
        amt = int(req.amount)
        if amt <= 0:
            res.ok = False
            res.remaining = int(self.remaining.get(k, 0))
            res.message = "amount_must_be_positive"
            return res
        if k not in self.capacity:
            res.ok = False
            res.remaining = 0
            res.message = "unknown_item"
            return res

        cur = int(self.remaining.get(k, 0))
        if cur < amt:
            res.ok = False
            res.remaining = cur
            res.message = "not_enough_stock"
            return res

        cur -= amt
        self.remaining[k] = cur
        res.ok = True
        res.remaining = cur
        res.message = "ok"
        return res

    def on_set(self, req: SetInventory.Request, res: SetInventory.Response):
        k = req.item_key
        if k not in self.capacity:
            # 새 item도 허용하고 싶으면 여기서 등록해도 됨
            res.ok = False
            res.message = "unknown_item"
            return res

        if int(req.capacity) > 0:
            self.capacity[k] = int(req.capacity)

        new_rem = int(req.remaining)
        if new_rem < 0:
            new_rem = 0
        if new_rem > self.capacity[k]:
            new_rem = self.capacity[k]
        self.remaining[k] = new_rem

        res.ok = True
        res.message = "ok"
        return res

    def on_reset_all(self, msg: Empty):
        """Reset all inventory to full capacity (triggered by FMS on startup)"""
        for k in self.capacity:
            self.remaining[k] = self.capacity[k]
        self.get_logger().info(f"[RESET] All inventory reset to capacity: {self.remaining}")


def main():
    rclpy.init()
    node = InventoryManagerNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
