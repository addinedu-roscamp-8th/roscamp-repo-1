# pinky_precision_control_ws/src/pinky_precision_docking/pinky_precision_docking/geometry.py

"""
geometry.py
- 도킹에서 쓰는 '2D 평면(x,y,yaw)' 수학 유틸 모음
- 핵심 목표:
  1) 각도 wrap(-pi~pi), quaternion->yaw
  2) odom 기반 거리/방향(heading) 계산
  3) "마커 -> standoff(법선 0.15m)" 목표점 계산을 위한 보조 함수 제공

중요한 전제(ROS에서 흔한 규약)
- base_link(로봇 기준): x=전방, y=좌측, z=위 (REP-103)
- camera optical(OpenCV 관례): x=우측, y=아래, z=전방
  -> camera_link / camera_optical_frame는 TF로 관계가 정의돼야 함

이 파일은 "순수 수학"에 집중하고,
TF 변환(tf2)은 docking_action_server.py에서 수행하는 것을 권장한다.
"""

from dataclasses import dataclass
import math
from typing import Tuple, Optional


# ----------------------------
# 기본 유틸
# ----------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def wrap_to_pi(angle: float) -> float:
    """
    각도를 -pi ~ +pi 범위로 정규화
    예) 3.5 rad -> -2.783... rad 같은 식으로 변환
    """
    a = (angle + math.pi) % (2.0 * math.pi) - math.pi
    return a


def shortest_angular_distance(from_yaw: float, to_yaw: float) -> float:
    """
    from -> to 로 갈 때 가장 짧은 각도 차이(부호 포함)
    """
    return wrap_to_pi(to_yaw - from_yaw)


def yaw_from_quaternion(qx: float, qy: float, qz: float, qw: float) -> float:
    """
    quaternion -> yaw(2D 회전) 추출
    (롤/피치가 있어도 yaw만 뽑아내는 표준 공식)
    """
    # yaw (z-axis rotation)
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


# ----------------------------
# 2D 포즈/변환
# ----------------------------

@dataclass
class Pose2D:
    """
    odom 평면에서 로봇 자세를 단순화한 형태
    x, y : 위치(m)
    yaw  : 방향(rad)
    """
    x: float
    y: float
    yaw: float


def rot2d(theta: float) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    2D 회전행렬 R(theta)
    """
    c = math.cos(theta)
    s = math.sin(theta)
    return ((c, -s), (s, c))


def transform_point_2d(px: float, py: float, pose: Pose2D) -> Tuple[float, float]:
    """
    pose(=원점 이동 + yaw 회전)를 이용해
    로컬 점(px,py)을 월드(odom)로 변환한다.

    직관:
    - 먼저 점을 yaw만큼 회전시키고
    - 그 다음 pose.x, pose.y 만큼 평행이동
    """
    R = rot2d(pose.yaw)
    xw = R[0][0] * px + R[0][1] * py + pose.x
    yw = R[1][0] * px + R[1][1] * py + pose.y
    return xw, yw


def inverse_transform_point_2d(px: float, py: float, pose: Pose2D) -> Tuple[float, float]:
    """
    월드(odom) 점(px,py)을 pose 좌표계로 "되돌리는" 변환

    직관:
    - 먼저 pose 위치를 빼서 원점으로 옮기고
    - yaw의 역회전(-yaw)을 적용
    """
    dx = px - pose.x
    dy = py - pose.y
    R = rot2d(-pose.yaw)
    xl = R[0][0] * dx + R[0][1] * dy
    yl = R[1][0] * dx + R[1][1] * dy
    return xl, yl


def distance_2d(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def heading_to_target(from_pose: Pose2D, tx: float, ty: float) -> float:
    """
    로봇이 목표점(tx,ty)을 바라보려면 필요한 '헤딩(각도)'
    """
    return math.atan2(ty - from_pose.y, tx - from_pose.x)


# ----------------------------
# IMU yaw 보강 (Complementary Filter)
# ----------------------------

@dataclass
class YawFusionState:
    """
    yaw 융합을 위한 상태(연속성 유지용)
    - fused_yaw: 최종 사용 yaw
    - last_imu_yaw, last_odom_yaw: unwrap에 도움
    """
    fused_yaw: float = 0.0
    last_imu_yaw: Optional[float] = None
    last_odom_yaw: Optional[float] = None


def unwrap_angle(prev: float, new: float) -> float:
    """
    각도 연속성 유지(unwrap)
    - 예: prev가 179도 근처인데 new가 -179도로 튀면 실제론 +181도 근처로 해석해야 함
    """
    delta = wrap_to_pi(new - prev)
    return prev + delta


def fuse_yaw_complementary(
    state: YawFusionState,
    yaw_odom: float,
    yaw_imu: Optional[float],
    alpha: float = 0.90
) -> float:
    """
    odom yaw + imu yaw를 섞어 fused_yaw를 만든다.

    alpha=0.90이면:
      - 90%는 odom yaw(장기 안정, 프레임 일관)
      - 10%는 imu yaw(단기 회전 응답/진동 억제)

    주의:
    - IMU가 없으면 yaw_odom만 사용
    - unwrap을 해서 "연속적인 yaw"를 유지
    """
    yaw_odom_u = yaw_odom
    if state.last_odom_yaw is not None:
        yaw_odom_u = unwrap_angle(state.last_odom_yaw, yaw_odom)
    state.last_odom_yaw = yaw_odom_u

    if yaw_imu is None:
        state.fused_yaw = wrap_to_pi(yaw_odom_u)
        return state.fused_yaw

    yaw_imu_u = yaw_imu
    if state.last_imu_yaw is not None:
        yaw_imu_u = unwrap_angle(state.last_imu_yaw, yaw_imu)
    state.last_imu_yaw = yaw_imu_u

    fused = alpha * yaw_odom_u + (1.0 - alpha) * yaw_imu_u
    state.fused_yaw = wrap_to_pi(fused)
    return state.fused_yaw


# ----------------------------
# "마커 -> standoff" 벡터 (2D 개념)
# ----------------------------

def standoff_vector_from_normal(theta_normal: float, standoff: float) -> Tuple[float, float]:
    """
    '마커 법선 방향'이 theta_normal(rad)라고 할 때,
    마커 원점에서 standoff 만큼 이동하는 벡터를 (dx,dy)로 반환.

    여기서 (dx,dy)는 "어떤 좌표계에서의 2D 평면 벡터"일 뿐이야.
    실제로는 marker frame 또는 base/odom frame 등 '어느 프레임인지'는
    docking_action_server에서 TF로 결정한다.

    직관:
    - theta_normal 방향으로 길이 standoff만큼 이동한 화살표
    """
    dx = standoff * math.cos(theta_normal)
    dy = standoff * math.sin(theta_normal)
    return dx, dy
