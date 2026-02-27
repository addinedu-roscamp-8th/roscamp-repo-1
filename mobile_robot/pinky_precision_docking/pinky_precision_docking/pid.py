import math
from dataclasses import dataclass


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass
class PIDGains:
    kp: float
    ki: float
    kd: float
    i_limit: float = 0.0  # 적분항 제한(anti-windup)


class PID:
    """
    [설명]
    - err(오차)를 받아 출력 u를 만드는 제어기
    - I항은 포화(saturation) 시 누적을 막아 anti-windup 적용 가능
    """
    def __init__(self, gains: PIDGains):
        self.g = gains
        self.integral = 0.0
        self.prev_err = None

    def reset(self):
        self.integral = 0.0
        self.prev_err = None

    def step(self, err: float, dt: float, saturated: bool = False) -> float:
        # P
        p = self.g.kp * err

        # I (anti-windup: 출력이 포화라면 integral 누적 억제)
        if (not saturated) and self.g.ki != 0.0 and dt > 0.0:
            self.integral += err * dt
            if self.g.i_limit > 0.0:
                self.integral = clamp(self.integral, -self.g.i_limit, self.g.i_limit)
        i = self.g.ki * self.integral

        # D
        d = 0.0
        if self.prev_err is not None and dt > 1e-6:
            d = self.g.kd * ((err - self.prev_err) / dt)
        self.prev_err = err

        return p + i + d
