# geometry.py
# ------------------------------------------------------------
# 좌표 / 기하 계산 전담 유틸리티
#
# 책임:
#  - 마커 기준 standoff 목표점 계산
#  - 법선 벡터 기반 위치 산출
#
# 주의:
#  - 이 파일은 "수학적 진실"만 담는다.
#  - FSM / 상태 / 제어 로직은 절대 넣지 않는다.
# ------------------------------------------------------------

import math
import numpy as np


def normalize(v: np.ndarray) -> np.ndarray:
    """벡터 정규화"""
    norm = np.linalg.norm(v)
    if norm < 1e-6:
        return v
    return v / norm


def compute_marker_normal_from_yaw(pose_yaw_err: float) -> np.ndarray:
    """
    마커 법선 벡터 (camera frame, x-z 평면)

    pose_yaw_err:
        vision_node에서 계산된
        normal_cam yaw = atan2(nx, nz)

    반환:
        np.array([nx, nz])  (정규화됨)
    """
    nx = math.sin(pose_yaw_err)
    nz = math.cos(pose_yaw_err)
    return normalize(np.array([nx, nz], dtype=np.float32))


def compute_standoff_point_camera(
    tx: float,
    tz: float,
    pose_yaw_err: float,
    standoff_dist: float = 0.15,
) -> np.ndarray:
    """
    camera frame 기준 standoff 위치 계산

    입력:
        tx, tz          : 마커 위치 (camera frame)
        pose_yaw_err    : 마커 법선 yaw
        standoff_dist   : 마커로부터 떨어질 거리 (m)

    출력:
        np.array([x, z]) : camera frame 상 standoff 위치
    """

    # 마커 위치 벡터
    p_marker = np.array([tx, tz], dtype=np.float32)

    # 마커 법선 벡터
    n = compute_marker_normal_from_yaw(pose_yaw_err)

    # standoff = 마커 위치 - 법선 방향 * 거리
    p_standoff = p_marker - standoff_dist * n

    return p_standoff


def transform_camera_to_base_2d(
    p_cam: np.ndarray,
    camera_yaw_in_base: float = 0.0,
    camera_offset_xy: np.ndarray = np.zeros(2),
) -> np.ndarray:
    """
    camera frame (x,z) → base frame (x,y)

    단순화 가정:
        - 카메라는 base_link에 고정
        - yaw 오프셋만 고려
        - 높이(y)는 무시 (2D)

    camera_yaw_in_base:
        base 기준 카메라 yaw 오프셋 (rad)

    camera_offset_xy:
        base 기준 카메라 위치 [x, y]
    """

    # camera (x,z) → base (x,y) 회전
    x_cam, z_cam = p_cam
    cos_y = math.cos(camera_yaw_in_base)
    sin_y = math.sin(camera_yaw_in_base)

    x_base = cos_y * z_cam - sin_y * x_cam
    y_base = sin_y * z_cam + cos_y * x_cam

    return np.array([x_base, y_base], dtype=np.float32) + camera_offset_xy
