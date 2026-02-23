import math
import time
import os

import cv2
import numpy as np

import rclpy
from rclpy.node import Node

from pinkylib import Camera
from pinky_precision_interfaces.msg import Marker2D

from ament_index_python.packages import get_package_share_directory


def estimate_pose_from_corners(corners_4x2, marker_length_m, camera_matrix, dist_coeffs):
    """
    [UPDATED] OpenCV 환경에 따라 cv2.aruco.estimatePoseSingleMarkers()가 없는 경우가 있음.
    따라서 각 마커의 4개 코너(2D 픽셀 좌표)와 마커 실제 크기(3D 좌표)를 사용해
    cv2.solvePnP()로 직접 rvec/tvec를 추정한다.

    corners_4x2: np.ndarray shape (4,2)  (픽셀 좌표)
    marker_length_m: 실제 마커 한 변 길이 (m)
    """
    half = marker_length_m / 2.0

    # [UPDATED] 마커의 3D 모델 포인트 (Z=0 평면, 마커 중심이 원점)
    # 코너 순서는 detectMarkers가 주는 순서(일반적으로 좌상-우상-우하-좌하)에 맞춘다.
    objp = np.array([
        [-half,  half, 0.0],  # 좌상
        [ half,  half, 0.0],  # 우상
        [ half, -half, 0.0],  # 우하
        [-half, -half, 0.0],  # 좌하
    ], dtype=np.float32)

    imgp = corners_4x2.astype(np.float32)

    # [UPDATED] solvePnP로 pose 추정
    ok, rvec, tvec = cv2.solvePnP(
        objp, imgp, camera_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not ok:
        return None, None

    return rvec, tvec


# -----------------------------
# EMA Filter
# -----------------------------
class EMA:
    def __init__(self, alpha: float):
        self.alpha = alpha
        self.value = None

    def reset(self):
        self.value = None

    def update(self, new_value: float):
        if self.value is None:
            self.value = new_value
        else:
            # EMA: 과거(필터값)에 alpha 비중, 새 측정값에 (1-alpha) 비중
            self.value = self.alpha * self.value + (1.0 - self.alpha) * new_value
        return self.value


# -----------------------------
# Vision Node
# -----------------------------
class PrecisionVisionNode(Node):
    def __init__(self):
        super().__init__("pinky_precision_vision")

        # Publisher
        self.pub = self.create_publisher(
            Marker2D, "/precision/marker2d", 10
        )

        # Parameters (하드코딩 → 이후 yaml로 이동 예정)
        self.target_ids = [2, 4]
        self.marker_length = 0.02  # meters
        self.publish_hz = 15.0

        # EMA filters
        self.ema_dist = EMA(alpha=0.8)
        self.ema_yaw = EMA(alpha=0.8)

        # Load camera calibration (package share/config)
        share_dir = get_package_share_directory("pinky_precision_vision")
        calib_path = os.path.join(
            share_dir, "config", "camera_calib_1.0247824544157953.npz"
        )

        # [UPDATED] 상대경로가 아닌 share/config의 절대경로로 로드 → ros2 run 환경에서도 항상 찾음
        calib = np.load(calib_path)
        self.camera_matrix = calib["camera_matrix"]
        self.dist_coeffs = calib["dist_coeffs"]
        self.get_logger().info(f"Loaded calib: {calib_path}")

        # OpenCV ArUco AprilTag
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_APRILTAG_36H11
        )
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(
            self.aruco_dict, self.aruco_params
        )

        # Camera
        self.cam = Camera()
        self.cam.start()

        # Timer
        self.timer = self.create_timer(
            1.0 / self.publish_hz, self.loop
        )

        self.get_logger().info("Precision vision node started.")

    def loop(self):
        frame = self.cam.get_frame()
        if frame is None:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)

        msg = Marker2D()
        msg.stamp = self.get_clock().now().to_msg()
        msg.valid = False

        if ids is None or len(ids) == 0:
            self.get_logger().info("No markers detected (publishing valid=false).")
            self.pub.publish(msg)
            return
        else:
            self.get_logger().info(f"Detected ids: {ids.flatten().tolist()}")


        ids = ids.flatten()

        # ------------------------------------------------------------
        # [UPDATED] estimatePoseSingleMarkers() 대신 solvePnP로 rvec/tvec 추정
        # corners는 보통 리스트 형태이며, 원소 하나가 (1,4,2) 형태인 경우가 많음.
        # -> c[0]로 (4,2)로 변환해서 estimate_pose_from_corners에 전달.
        # ------------------------------------------------------------
        rvecs = []
        tvecs = []
        for c in corners:
            c4 = c[0]  # (4,2)
            rvec, tvec = estimate_pose_from_corners(
                c4, self.marker_length, self.camera_matrix, self.dist_coeffs
            )
            rvecs.append(rvec)
            tvecs.append(tvec)

        # 타겟 ID(2,4) 중 "가장 가까운 마커" 선택
        best_idx = None
        best_dist = None

        for i, tag_id in enumerate(ids):
            if int(tag_id) not in self.target_ids:
                continue

            tvec = tvecs[i]
            if tvec is None:
                # [UPDATED] solvePnP 실패한 마커는 스킵
                continue

            tvec = tvec.flatten()  # (3,)
            dist = math.sqrt(tvec[0] ** 2 + tvec[2] ** 2)

            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_idx = i

        if best_idx is None:
            # 타겟 ID(2,4)가 없거나 pose 추정 실패면 valid=False 발행
            self.pub.publish(msg)
            return

        tag_id = int(ids[best_idx])
        tvec = tvecs[best_idx]
        rvec = rvecs[best_idx]  # [UPDATED] best 마커의 rvec도 사용해야 pose_yaw_err 계산 가능

        if tvec is None:
            self.pub.publish(msg)
            return
        
        tvec = tvec.flatten()

        # base_link 기준 근사 (카메라 기준 tvec를 직접 사용)
        # 실제로는 TF(camera->base)를 적용하면 더 정확해짐(이미 TF 해결되었다고 했으니 후속 단계에서 반영 가능)
        distance = math.sqrt(tvec[0] ** 2 + tvec[2] ** 2)
        yaw = math.atan2(tvec[0], tvec[2])  # 좌우 각도

        # EMA 적용 (측정 흔들림 감소)
        distance_f = self.ema_dist.update(distance)
        yaw_f = self.ema_yaw.update(yaw)

        # ============================================================
        # [UPDATED] 화면 중앙 오차(center_x_err) 계산
        #  - corners[best_idx][0] : (4,2)
        #  - 마커 중심 cx는 4개 코너 x의 평균
        #  - 화면 중앙은 w/2
        #  - 정규화: (-1 ~ +1) 범위로 만들기 위해 (w/2)로 나눔
        # ============================================================
        h, w = gray.shape[:2]
        c4 = corners[best_idx][0]
        cx = float(np.mean(c4[:, 0]))
        center_x_err = (cx - (w / 2.0)) / (w / 2.0)  # -1(left) ~ 0(center) ~ +1(right)

        # ============================================================
        # [UPDATED] 마커 법선 기반 yaw 오차(pose_yaw_err) 계산
        #  - rvec -> 회전행렬 R
        #  - 마커 좌표계에서 +Z(0,0,1)이 마커 평면의 법선(normal)
        #  - 이를 카메라 좌표계로 변환하면 normal_cam = R*[0,0,1]
        #  - yaw는 x-z 평면에서 atan2(nx, nz)
        # ============================================================
        R, _ = cv2.Rodrigues(rvec)
        normal_cam = R @ np.array([0.0, 0.0, 1.0], dtype=np.float32)
        pose_yaw_err = math.atan2(float(normal_cam[0]), float(normal_cam[2]))

        msg.valid = True
        msg.id = tag_id
        msg.distance_m = float(distance_f)
        msg.yaw_rad = float(yaw_f)
        msg.tx_m = float(tvec[0])
        msg.tz_m = float(tvec[2])

        # [UPDATED] Marker2D.msg에 필드가 추가되어 있어야 함
        msg.center_x_err = float(center_x_err)   # [UPDATED]
        msg.pose_yaw_err = float(pose_yaw_err)   # [UPDATED]
        
        msg.quality = float(1.0)  # TODO: 마커 픽셀 크기/재투영오차 등으로 개선 가능

        # 좌우(x)와 거리(z) 값 로그 출력
        self.get_logger().info(f"Marker position - x (좌우): {tvec[0]:.4f}m, z (거리): {tvec[2]:.4f}m")

        self.pub.publish(msg)

    def destroy_node(self):
        self.cam.close()
        super().destroy_node()


def main():
    rclpy.init()
    node = PrecisionVisionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
