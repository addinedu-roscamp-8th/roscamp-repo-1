# odom_helper.py
# ------------------------------------------------------------
# odom + IMU 기반 위치 추정 헬퍼
#
# 책임:
#  - 현재 odom 위치 추적
#  - yaw 보정 (odom + IMU fusion)
#
# FSM / 제어 로직과 분리 유지
# ------------------------------------------------------------

import math
import numpy as np


class OdomState:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.yaw_odom = 0.0
        self.yaw_imu = None

    def update_from_odom(self, x: float, y: float, yaw: float):
        self.x = x
        self.y = y
        self.yaw_odom = yaw

    def update_from_imu(self, yaw: float):
        self.yaw_imu = yaw

    def get_fused_yaw(self, alpha: float = 0.7) -> float:
        """
        yaw_fused = alpha * yaw_odom + (1-alpha) * yaw_imu

        IMU 없으면 odom yaw만 사용
        """
        if self.yaw_imu is None:
            return self.yaw_odom
        return alpha * self.yaw_odom + (1.0 - alpha) * self.yaw_imu

    def position(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=np.float32)

    def distance_to(self, goal_xy: np.ndarray) -> float:
        dx = goal_xy[0] - self.x
        dy = goal_xy[1] - self.y
        return math.hypot(dx, dy)

    def heading_error_to(self, goal_xy: np.ndarray, alpha: float = 0.7) -> float:
        """
        현재 위치 → 목표점 heading error
        """
        dx = goal_xy[0] - self.x
        dy = goal_xy[1] - self.y
        desired_yaw = math.atan2(dy, dx)
        yaw = self.get_fused_yaw(alpha)
        return self._normalize_angle(desired_yaw - yaw)

    @staticmethod
    def _normalize_angle(a: float) -> float:
        while a > math.pi:
            a -= 2 * math.pi
        while a < -math.pi:
            a += 2 * math.pi
        return a
