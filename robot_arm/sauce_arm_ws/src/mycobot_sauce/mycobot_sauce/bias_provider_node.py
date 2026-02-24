# nodes/bias_provider_node.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import rclpy
from rclpy.node import Node

from mycobot_sauce_msgs.srv import GetCorrectedPose  # Request: raw_pose[6], Response: corrected_pose[6], applied, message


@dataclass
class BiasPoint:
    x: float; y: float; z: float; rx: float; ry: float; rz: float
    ex: float; ey: float; ez: float; erx: float; ery: float; erz: float


def wrap_deg(a: float) -> float:
    while a > 180.0:
        a -= 360.0
    while a < -180.0:
        a += 360.0
    return a


class BiasProviderNode(Node):
    def __init__(self):
        super().__init__("bias_provider_node")

        # params
        self.declare_parameter("bias_csv", "sauce_err.csv")  # 항상 읽는 구조
        self.declare_parameter("max_xyz_mm", 80.0)
        self.declare_parameter("max_r_deg", 35.0)
        self.declare_parameter("max_corr_mm", 25.0)
        self.declare_parameter("max_corr_deg", 12.0)
        self.declare_parameter("w_r_deg", 1.0)

        self.bias_pts: List[BiasPoint] = []
        self._load_bias()

        self.srv = self.create_service(GetCorrectedPose, "get_corrected_pose", self.on_srv)
        self.get_logger().info("Ready: /get_corrected_pose")

    def _load_bias(self):
        path = self.get_parameter("bias_csv").value
        pts: List[BiasPoint] = []
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                rd = csv.DictReader(f)
                for row in rd:
                    # 너 CSV 컬럼명에 맞게 수정 가능 (현재는 흔한 형태 가정)
                    pts.append(
                        BiasPoint(
                            x=float(row["send_x"]), y=float(row["send_y"]), z=float(row["send_z"]),
                            rx=float(row["send_rx"]), ry=float(row["send_ry"]), rz=float(row["send_rz"]),
                            ex=float(row["ex"]), ey=float(row["ey"]), ez=float(row["ez"]),
                            erx=float(row.get("erx", 0.0)), ery=float(row.get("ery", 0.0)), erz=float(row.get("erz", 0.0)),
                        )
                    )
            self.bias_pts = pts
            self.get_logger().info(f"Loaded bias points: {len(self.bias_pts)} from {path}")
        except Exception as e:
            self.bias_pts = []
            self.get_logger().warn(f"Bias CSV load failed: {path} ({e})")

    def _score(self, pose: List[float], p: BiasPoint, w_r_deg: float) -> Tuple[float, float, float]:
        dx = pose[0] - p.x
        dy = pose[1] - p.y
        dz = pose[2] - p.z
        dxyz = math.sqrt(dx*dx + dy*dy + dz*dz)

        drx = wrap_deg(pose[3] - p.rx)
        dry = wrap_deg(pose[4] - p.ry)
        drz = wrap_deg(pose[5] - p.rz)
        dr = math.sqrt(drx*drx + dry*dry + drz*drz)

        score = dxyz + w_r_deg * dr
        return score, dxyz, dr

    def apply_bias_nearest(self, pose: List[float]) -> Tuple[List[float], bool, str]:
        if not self.bias_pts:
            return pose, False, "no_bias_points"

        max_xyz = float(self.get_parameter("max_xyz_mm").value)
        max_r = float(self.get_parameter("max_r_deg").value)
        max_corr_mm = float(self.get_parameter("max_corr_mm").value)
        max_corr_deg = float(self.get_parameter("max_corr_deg").value)
        w_r = float(self.get_parameter("w_r_deg").value)

        best = None
        best_score = 1e18
        best_dxyz = 0.0
        best_dr = 0.0

        for p in self.bias_pts:
            score, dxyz, dr = self._score(pose, p, w_r)
            if score < best_score:
                best_score = score
                best = p
                best_dxyz = dxyz
                best_dr = dr

        if best is None or best_dxyz > max_xyz or best_dr > max_r:
            return pose, False, "no_match"

        # clamp correction
        ex = max(-max_corr_mm, min(max_corr_mm, best.ex))
        ey = max(-max_corr_mm, min(max_corr_mm, best.ey))
        ez = max(-max_corr_mm, min(max_corr_mm, best.ez))

        erx = max(-max_corr_deg, min(max_corr_deg, best.erx))
        ery = max(-max_corr_deg, min(max_corr_deg, best.ery))
        erz = max(-max_corr_deg, min(max_corr_deg, best.erz))

        corrected = [
            pose[0] - ex, pose[1] - ey, pose[2] - ez,
            wrap_deg(pose[3] - erx), wrap_deg(pose[4] - ery), wrap_deg(pose[5] - erz),
        ]
        return corrected, True, f"matched(dxyz={best_dxyz:.1f},dr={best_dr:.1f})"

    def on_srv(self, req: GetCorrectedPose.Request, res: GetCorrectedPose.Response):
        raw = list(req.raw_pose)
        corrected, applied, msg = self.apply_bias_nearest(raw)
        res.corrected_pose = corrected
        res.applied = applied
        res.message = msg
        return res


def main():
    rclpy.init()
    node = BiasProviderNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
