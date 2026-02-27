# 파일 경로(프로젝트 루트 기준):
# pinky_precision_control_ws/src/pinky_precision_docking/pinky_precision_docking/docking_action_server.py

import time
import math  # [NEW]

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from geometry_msgs.msg import Twist

from nav_msgs.msg import Odometry  # [NEW]
from sensor_msgs.msg import Imu    # [NEW]

from pinky_precision_interfaces.msg import Marker2D
from pinky_precision_interfaces.action import Dock

from .pid import PID, PIDGains, clamp
from .fsm import DockState


def normalize_angle(rad: float) -> float:
    """[-pi, +pi]로 정규화"""
    while rad > math.pi:
        rad -= 2.0 * math.pi
    while rad < -math.pi:
        rad += 2.0 * math.pi
    return rad


def yaw_from_quat(x: float, y: float, z: float, w: float) -> float:
    """
    Quaternion -> yaw (Z축 회전)
    ROS 표준(ENU)에서 base_link yaw 추출
    """
    # yaw = atan2(2(wz + xy), 1 - 2(y^2 + z^2))
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class PrecisionDockingServer(Node):
    """
    Dock.action 서버:
    - Goal을 받으면 도킹 FSM을 시작
    - /precision/marker2d를 구독해서 yaw/dist 오차를 계산
    - /cmd_vel_raw로 속도를 출력

    [UPDATED]
    - /odom 구독 추가: Blind Translate/Rotate를 위해 "이동량/현재 pose"를 사용
    - (선택) /imu 구독 추가: yaw 안정화 보정(있는 경우에만 사용)
    """

    def __init__(self):
        super().__init__("pinky_precision_docking_server")

        self.cb_group = ReentrantCallbackGroup()

        # ---- Pub/Sub ----
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel_raw", 10)
        self.marker_sub = self.create_subscription(
            Marker2D, "/precision/marker2d", self.marker_cb, 10,
            callback_group=self.cb_group
        )

        # [NEW] Odometry
        self.odom_sub = self.create_subscription(
            Odometry, "/odom", self.odom_cb, 20,
            callback_group=self.cb_group
        )

        # [NEW] IMU (있으면 사용)
        self.imu_sub = self.create_subscription(
            Imu, "/imu", self.imu_cb, 50,
            callback_group=self.cb_group
        )

        # ---- Action Server ----
        self._action_server = ActionServer(
            self,
            Dock,
            "/precision/dock",
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=self.cancel_cb,
            callback_group=self.cb_group
        )

        # ---- 상태/센서 최신값 ----
        self.state = DockState.IDLE
        self.last_marker_time = 0.0

        self.marker_valid = False
        self.marker_id = -1
        self.distance_m = None
        self.yaw_rad = None
        self.end_state = "IDLE"

        # [UPDATED] Marker2D 확장 필드 저장
        self.center_x_err = None        # 화면 중앙 오차 (-1~+1)
        self.pose_yaw_err = None        # 마커 법선 기준 yaw 오차(rad)

        # [NEW] Marker2D의 tvec 저장(로그에 이미 나오고 있으니 실제 msg에 존재한다고 가정)
        self.tx_m = None
        self.tz_m = None

        # ---------------------------------------------------------------------
        # [NEW] last valid marker cache (vision loss 대비)
        # - msg.valid=False가 되면 center_x_err/tx/tz가 None으로 떨어지므로,
        #   "마지막으로 유효했던 관측"을 저장해 근접(blind) 구간 판단에 사용
        # ---------------------------------------------------------------------
        self.last_valid_marker_time = 0.0
        self.last_valid_marker_id = -1
        self.last_valid_distance_m = None
        self.last_valid_yaw_rad = None
        self.last_valid_center_x_err = None
        self.last_valid_pose_yaw_err = None
        self.last_valid_tx_m = None
        self.last_valid_tz_m = None

        # ---------------------------------------------------------------------
        # [NEW] blind-zone absolute threshold (절대값 기준)
        # - standoff 값과 무관하게, 카메라-마커 거리(tz)가 13cm 이내면
        #   환경상 마커가 사라질 수 있으므로 blind-zone으로 간주
        # ---------------------------------------------------------------------
        self.blind_zone_dist_m = 0.13   # ✅ 절대 기준: 13cm

        # last valid 마커를 "최근"으로 보는 최대 시간(s)
        self.last_valid_marker_timeout_sec = 1.0

        # APPROACH에서 dist_goal이 너무 작으면 atan2 기반 head_err가 튀므로
        # heading drift 판정을 비활성화할 거리(m)
        self.approach_head_drift_min_dist = 0.08   # 8cm 이내면 heading drift 체크 완화/비활성

        # [NEW] Odom 최신값
        self.last_odom_time = 0.0
        self.odom_x = None
        self.odom_y = None
        self.odom_yaw = None

        # [NEW] IMU 최신값(선택)
        self.last_imu_time = 0.0
        self.imu_yaw = None

        # ---- 제어 파라미터(초기값, 이후 yaml로 이동 예정) ----
        # 목표: 1cm
        self.default_target_dist = 0.01

        # 타임아웃/워치독
        self.marker_timeout_sec = 0.5
        self.odom_timeout_sec = 0.5  # [NEW] odom 신선도

        # -----------------------------
        # FSM 임계값
        # -----------------------------
        self.yaw_align_enter = 0.10
        self.yaw_align_exit = 0.035

        self.yaw_final_th = 0.017
        self.final_zone_dist = 0.10
        self.dist_done_th = 0.01

        # [UPDATED] CENTERING/FACE_ALIGN에서 마커가 잠깐 끊겨도 즉시 SEARCH로 안 가도록 grace
        self.align_loss_grace = 0.30
        self.align_lost_since = None

        # -----------------------------
        # [UPDATED] CENTERING / VERIFY_POSE 임계값
        # -----------------------------
        self.center_exit_th = 0.08
        self.center_enter_th = 0.20

        self.pose_exit_th = 0.10
        self.pose_enter_th = 0.20

        self.verify_hold_sec = 0.25
        self.verify_started = None

        # -----------------------------------------------------------------
        # [UPDATED] VERIFY_POSE 내 "짧은 REACQUIRE" 지원
        # - ROTATE 직후 마커가 잠깐 끊기는 경우(특히 근접/모션블러) SEARCH로 루프되는 것을 방지
        # - VERIFY_POSE에서 제한 시간 동안만 느리게 회전하며 재획득 시도
        # -----------------------------------------------------------------
        self.reacquire_timeout_sec = 1.0   # [UPDATED] 재획득 최대 허용 시간(s)
        self.reacquire_w = 0.15            # [UPDATED] 재획득 회전 속도(rad/s)
        self.reacquire_started = None      # [UPDATED] 재획득 시작 시각

        # [IMPROVED] CENTERING 타임아웃
        self.centering_timeout_sec = 10.0
        self.centering_started = None

        # [IMPROVED] 회전 방향 자동 감지 및 안전장치
        self.centering_last_cx = None
        self.centering_wrong_direction_count = 0
        self.centering_direction_reversed = False

        # -----------------------------
        # 속도 제한
        # -----------------------------
        self.max_v = 0.12
        self.max_w = 0.6

        self.max_w_align = 0.25
        self.max_w_center = 0.30
        self.max_w_center_high = 0.40
        self.max_w_face = 0.15

        self.max_v_final = 0.02
        self.max_w_final = 0.3

        self.search_w = 0.25

        # -----------------------------
        # PID
        # -----------------------------
        self.pid_yaw = PID(PIDGains(kp=1.6, ki=0.0, kd=0.10, i_limit=0.2))
        self.pid_dist = PID(PIDGains(kp=0.8, ki=0.0, kd=0.0, i_limit=0.2))
        self.pid_dist_final = PID(PIDGains(kp=0.6, ki=0.0, kd=0.0, i_limit=0.2))

        # [UPDATED] CENTERING 전용
        self.pid_center = PID(PIDGains(kp=1.2, ki=0.0, kd=0.0, i_limit=0.0))

        # [UPDATED] FACE_ALIGN 전용(법선 yaw)
        self.pid_pose = PID(PIDGains(kp=1.2, ki=0.0, kd=0.08, i_limit=0.2))

        # ---------------------------------------------------------------------
        # [NEW] Blind Translate/Rotate 관련 파라미터
        # ---------------------------------------------------------------------
        self.standoff_m = 0.15  # ✅ 요청: 기본 standoff 0.15m

        # TRANSLATE: 목표점까지 남은 거리로 종료(오직 dist_goal)
        self.translate_done_th = 0.02  # 2cm 이내면 목표점 도달로 판단
        self.translate_v_nom = 0.06    # 기본 전진 속도 (원호 유지)
        self.translate_w_kp = 1.5      # 목표점 방향으로 조향 강도
        self.translate_max_w = 0.35    # 로그에 있던 값 유지

        # ROTATE: 목표 yaw로 회전 종료(오직 yaw_err)
        self.rotate_done_th = 0.15     # ~3deg
        self.rotate_w_kp = 1.8
        self.rotate_max_w = 0.35

        # ---------------------------------------------------------------------
        # [NEW] FINAL_ALIGN marker loss grace / reacquire
        # ---------------------------------------------------------------------
        self.final_reacquire_timeout_sec = 1.0   # FINAL에서 마커 재획득 최대 시간
        self.final_reacquire_w = 0.15            # 재획득 회전 속도(rad/s)
        self.final_reacquire_started = None      # FINAL 재획득 시작 시각

        # [NEW] IMU 보정(있는 경우에만 사용)
        self.use_imu_yaw = False  # IMU가 신뢰할 수 있으면 True로 설정
        self.imu_alpha = 0.15  # (0~1) yaw = (1-a)*odom + a*imu  (작게 시작)

        # ---------------------------------------------------------------------
        # [NEW/UPDATED] Snapshot 저장소 (standoff / target 2종)
        #
        # 요구사항:
        # - CENTERING 종료 시점에 standoff_snapshot과 target_snapshot을 "동시에" 생성
        #   * standoff_snapshot: FACE_ALIGN_TRANSLATE / ROTATE / VERIFY 단계에서 사용
        #   * target_snapshot  : APPROACH ~ FINAL_ALIGN 단계에서 사용 (vision 불가 고려)
        #
        # 추가 요구:
        # - ROTATE(법선 정렬) 완료 후 vision이 잠깐이라도 살아있으면
        #   target_snapshot의 yaw_goal만 업데이트하거나(최소),
        #   가능하면 target_snapshot 전체를 1회 재생성(옵션)하여 신뢰도 향상
        # ---------------------------------------------------------------------
        self.snapshot_valid = False

        # standoff snapshot (TRANSLATE/ROTATE/VERIFY 목표)
        self.snap_s_valid = False
        self.snap_s_x_goal = 0.0
        self.snap_s_y_goal = 0.0
        self.snap_s_yaw_goal = 0.0
        self.snap_s_created_time = 0.0

        # target snapshot (APPROACH/FINAL 목표)
        self.snap_t_valid = False
        self.snap_t_x_goal = 0.0
        self.snap_t_y_goal = 0.0
        self.snap_t_yaw_goal = 0.0
        self.snap_t_created_time = 0.0

        # ROTATE 완료 후 vision으로 target snapshot을 "1회" 보강했는지
        self.target_snapshot_refined_once = False

        # (옵션) ROTATE 이후 target snapshot "전체 재생성"을 허용할지
        # - True: tx/tz/pose_yaw_err가 들어오면 target 위치(x,y)도 재계산 (권장)
        # - False: yaw_goal만 업데이트 (더 보수적)
        self.enable_target_snapshot_full_refine = True

        self.get_logger().info("Precision docking action server started.")

    # ---------------------------
    # ROS callbacks
    # ---------------------------
    def marker_cb(self, msg: Marker2D):
        self.marker_valid = bool(msg.valid)
        self.marker_id = int(msg.id)

        self.distance_m = float(msg.distance_m) if msg.valid else None
        self.yaw_rad = float(msg.yaw_rad) if msg.valid else None

        # 확장 관측값
        self.center_x_err = float(msg.center_x_err) if msg.valid else None
        self.pose_yaw_err = float(msg.pose_yaw_err) if msg.valid else None

        # tx/tz
        self.tx_m = float(msg.tx_m) if msg.valid else None
        self.tz_m = float(msg.tz_m) if msg.valid else None

        if msg.valid:
            now = time.time()
            self.last_marker_time = now

            # [NEW] last valid cache 업데이트
            self.last_valid_marker_time = now
            self.last_valid_marker_id = self.marker_id
            self.last_valid_distance_m = self.distance_m
            self.last_valid_yaw_rad = self.yaw_rad
            self.last_valid_center_x_err = self.center_x_err
            self.last_valid_pose_yaw_err = self.pose_yaw_err
            self.last_valid_tx_m = self.tx_m
            self.last_valid_tz_m = self.tz_m

            self.get_logger().info(
                f"[MARKER] id={self.marker_id} dist={self.distance_m:.3f} yaw={self.yaw_rad:.3f} "
                f"tx={self.tx_m:.3f} tz={self.tz_m:.3f} "
                f"center_x_err={self.center_x_err:.3f} pose_yaw_err={self.pose_yaw_err:.3f}"
            )

    # [NEW]
    def odom_cb(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        self.odom_x = float(p.x)
        self.odom_y = float(p.y)
        self.odom_yaw = float(yaw_from_quat(q.x, q.y, q.z, q.w))
        self.last_odom_time = time.time()

    # [NEW]
    def imu_cb(self, msg: Imu):
        q = msg.orientation
        # IMU가 orientation을 제대로 주는 경우에만 의미가 있음.
        # (0,0,0,0) 같은 값이면 무시하도록 간단한 체크.
        if abs(q.w) < 1e-6 and abs(q.x) < 1e-6 and abs(q.y) < 1e-6 and abs(q.z) < 1e-6:
            return
        self.imu_yaw = float(yaw_from_quat(q.x, q.y, q.z, q.w))
        self.last_imu_time = time.time()

    def publish_cmd(self, v: float, w: float):
        t = Twist()
        t.linear.x = float(v)
        t.angular.z = float(w)
        self.cmd_pub.publish(t)

    # ---------------------------
    # Action callbacks
    # ---------------------------
    def goal_cb(self, goal_request: Dock.Goal) -> GoalResponse:
        return GoalResponse.ACCEPT

    def cancel_cb(self, goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    # ---------------------------
    # Core FSM helpers
    # ---------------------------
    def marker_is_fresh(self) -> bool:
        return (time.time() - self.last_marker_time) <= self.marker_timeout_sec

    def last_valid_marker_is_fresh(self) -> bool:
        return (time.time() - self.last_valid_marker_time) <= self.last_valid_marker_timeout_sec

    def in_blind_zone(self) -> bool:
        """
        근접해서 마커가 안 잡히는 환경을 고려한 blind-zone 판정.
        - last valid tz가 standoff에 아주 가까우면(또는 더 작으면) blind-zone으로 간주
        - last valid가 너무 오래전이면 False
        """
        if not self.last_valid_marker_is_fresh():
            return False
        if self.last_valid_tz_m is None:
            return False
        return float(self.last_valid_tz_m) <= float(self.blind_zone_dist_m)

    # [NEW]
    def odom_is_fresh(self) -> bool:
        return (time.time() - self.last_odom_time) <= self.odom_timeout_sec

    # [NEW]
    def get_fused_yaw(self) -> float:
        """
        odom yaw 기반 + imu yaw 보정(있는 경우).
        IMU가 없거나 stale이면 odom yaw만 사용.
        """
        if self.odom_yaw is None:
            return 0.0
        yaw = self.odom_yaw

        if not self.use_imu_yaw:
            return yaw

        imu_fresh = (time.time() - self.last_imu_time) <= 0.5
        if self.imu_yaw is None or not imu_fresh:
            return yaw

        # 간단한 보정: yaw = (1-a)*odom + a*imu  (각도 wrap 고려)
        err = normalize_angle(self.imu_yaw - yaw)
        yaw_fused = normalize_angle(yaw + self.imu_alpha * err)
        return yaw_fused

    def reset_controllers(self):
        self.pid_yaw.reset()
        self.pid_dist.reset()
        self.pid_dist_final.reset()
        self.pid_center.reset()
        self.pid_pose.reset()

    def hard_stop(self, repeats: int = 5, dt: float = 0.05):
        for _ in range(repeats):
            self.publish_cmd(0.0, 0.0)
            time.sleep(dt)

    # ---------------------------
    # [UPDATED] Snapshot 생성/갱신
    # ---------------------------

    def _compute_goal_from_marker(self, standoff_m: float) -> tuple[bool, float, float, float]:
        """
        공통 유틸: "현재 odom pose + marker(tx,tz,pose_yaw_err,yaw_rad)" 로
        standoff_m 에 해당하는 목표점(x_goal,y_goal)과 목표 yaw_goal을 계산한다.

        - 반환: (ok, x_goal, y_goal, yaw_goal)
        - ok=False 이면 필요한 센서/비전/odom 정보가 부족한 상황

        NOTE
        - 여기서 standoff_m은 "마커 법선 방향 기준으로 마커 중심에서 떨어질 거리"를 의미.
        - camera frame: x=right(+), z=forward(+)
          base frame  : x=forward(+), y=left(+)
        """
        if not self.odom_is_fresh() or self.odom_x is None or self.odom_y is None:
            self.get_logger().error("[SNAPSHOT] Odom not available/fresh")
            return (False, 0.0, 0.0, 0.0)

        if (not self.marker_valid) or (self.tx_m is None) or (self.tz_m is None) or (self.pose_yaw_err is None):
            self.get_logger().error("[SNAPSHOT] Marker data not available")
            return (False, 0.0, 0.0, 0.0)

        x_now = float(self.odom_x)
        y_now = float(self.odom_y)
        yaw_now = float(self.get_fused_yaw())

        tx = float(self.tx_m)
        tz = float(self.tz_m)

        # -----------------------------
        # pose_yaw_err 안정화(기존 로직 유지 + 주석 보강)
        # -----------------------------
        theta_raw = float(self.pose_yaw_err)

        # 1) [-pi, +pi]
        theta = normalize_angle(theta_raw)

        # 2) ±90deg 넘어가는 뒤집힘은 π를 접어서 같은 "정면 해석"으로 안정화
        if abs(theta) > (math.pi / 2.0):
            theta = normalize_angle(theta - math.copysign(math.pi, theta))

        # 3) 마커 법선 (camera x-z 평면)
        #    theta=0 이면 정면: (nx,nz)=(0,1)
        nx = math.sin(theta)
        nz = math.cos(theta)

        # 4) standoff_m 목표점(카메라 좌표)
        #    - 관측된 마커 중심(tx,tz)에서
        #    - 마커 법선 방향으로 standoff_m 만큼 떨어진 지점
        #    - 여기서는 기존 방식대로 "tx - standoff*nx", "tz - standoff*nz"를 유지
        dx_cam = tx - float(standoff_m) * nx
        dz_cam = tz - float(standoff_m) * nz

        # 5) camera -> base 변환
        #    base_x = camera_z
        #    base_y = -camera_x
        base_x = dz_cam
        base_y = -dx_cam

        # 6) base -> odom 회전하여 목표점 생성
        x_goal = x_now + math.cos(yaw_now) * base_x - math.sin(yaw_now) * base_y
        y_goal = y_now + math.sin(yaw_now) * base_x + math.cos(yaw_now) * base_y

        # 7) 목표 yaw_goal
        #    yaw_rad는 "현재 로봇 yaw 기준 마커 정면 정렬 오차"라고 가정.
        #    yaw_goal = yaw_now + yaw_err 로 두면 "정렬된 yaw"가 된다.
        yaw_rad_snap = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
        yaw_goal = normalize_angle(yaw_now + yaw_rad_snap)

        # 디버그(생성 시 1회만 찍히도록 상위에서 호출 제어)
        return (True, float(x_goal), float(y_goal), float(yaw_goal))

    def create_snapshots(self, target_dist: float):
        """
        [요구사항 핵심]
        CENTERING 종료 시점에 standoff_snapshot + target_snapshot을 동시에 생성한다.

        - standoff_snapshot: FACE_ALIGN_TRANSLATE / ROTATE / VERIFY 단계에서 사용
        - target_snapshot  : APPROACH ~ FINAL_ALIGN 단계에서 사용 (vision 불가 상황 대비)

        target_snapshot 생성 방식:
        1) 우선 marker 기반으로 target_dist 목표점 직접 계산(정확)
        2) marker 기반이 불안정/실패하면,
           standoff_snapshot + (standoff - target_dist)을 yaw_goal 방향으로 전진한 점으로 fallback 생성
           (vision 불가 환경에서도 "일관된 전진 목표" 확보)
        """
        # ---- 1) standoff snapshot (marker 기반) ----
        ok_s, x_s, y_s, yaw_s = self._compute_goal_from_marker(self.standoff_m)

        if not ok_s:
            self.get_logger().error("[SNAPSHOT] standoff snapshot create failed")
            self.snapshot_valid = False
            self.snap_s_valid = False
            self.snap_t_valid = False
            return

        self.snap_s_x_goal = x_s
        self.snap_s_y_goal = y_s
        self.snap_s_yaw_goal = yaw_s
        self.snap_s_created_time = time.time()
        self.snap_s_valid = True

        # ---- 2) target snapshot ----
        ok_t, x_t, y_t, yaw_t = self._compute_goal_from_marker(target_dist)

        if ok_t:
            # marker 기반 target snapshot 성공
            self.snap_t_x_goal = x_t
            self.snap_t_y_goal = y_t
            self.snap_t_yaw_goal = yaw_t
            self.snap_t_created_time = time.time()
            self.snap_t_valid = True
        else:
            # fallback: standoff 목표점에서 yaw_goal 방향으로 (standoff-target_dist)만큼 전진
            # - yaw_goal은 "정면 정렬된 방향"이므로, 이 방향으로 전진하면 마커 쪽으로 접근하는 효과
            delta = float(self.standoff_m) - float(target_dist)
            x_fb = self.snap_s_x_goal + math.cos(self.snap_s_yaw_goal) * delta
            y_fb = self.snap_s_y_goal + math.sin(self.snap_s_yaw_goal) * delta

            self.snap_t_x_goal = float(x_fb)
            self.snap_t_y_goal = float(y_fb)
            self.snap_t_yaw_goal = float(self.snap_s_yaw_goal)  # yaw는 standoff yaw_goal을 공유
            self.snap_t_created_time = time.time()
            self.snap_t_valid = True

            self.get_logger().warn(
                f"[SNAPSHOT] target snapshot marker-based failed -> fallback from standoff "
                f"(delta={delta:.3f}, standoff={self.standoff_m:.3f}, target_dist={target_dist:.3f})"
            )

        self.snapshot_valid = bool(self.snap_s_valid and self.snap_t_valid)

        self.get_logger().info(
            f"[SNAPSHOT] created "
            f"standoff_goal=({self.snap_s_x_goal:.3f},{self.snap_s_y_goal:.3f}) yaw={self.snap_s_yaw_goal:.3f} "
            f"target_goal=({self.snap_t_x_goal:.3f},{self.snap_t_y_goal:.3f}) yaw={self.snap_t_yaw_goal:.3f} "
            f"(standoff={self.standoff_m:.3f}, target_dist={target_dist:.3f})"
        )

    def refine_target_snapshot_with_vision(self, target_dist: float, update_xy: bool = True, update_yaw: bool = True):
        """
        [요구사항 추가 아이디어 적용]
        ROTATE(법선 정렬) 완료 직후, vision이 "잠깐" 살아있으면 target snapshot을 1회 보강한다.

        - update_yaw=True  : yaw_goal을 최신 vision/odom 기반으로 갱신
        - update_xy=True   : 가능하면 target 목표점(x,y)도 marker 기반으로 1회 재생성

        주의:
        - APPROACH 단계에서는 vision이 보장되지 않으므로, 이 보강은 "ROTATE 직후"에만 수행.
        - 실패해도 기존 target snapshot은 유지(안전하게 계속 진행).
        """
        if self.target_snapshot_refined_once:
            return  # 1회만

        # vision/odom 조건
        vision_ok = (
            self.marker_valid and
            self.marker_is_fresh() and
            (self.tx_m is not None) and (self.tz_m is not None) and
            (self.pose_yaw_err is not None)
        )

        if not vision_ok:
            return

        if not self.snap_t_valid:
            # target snapshot이 없다면(정상이라면 없어야 함), 여기서라도 만들 수 있게 시도
            update_xy = True
            update_yaw = True

        # ---- yaw_goal 업데이트(최소 보강) ----
        if update_yaw:
            # yaw_goal은 marker yaw_rad 기준으로 갱신 가능
            if self.odom_is_fresh() and (self.odom_yaw is not None):
                yaw_now = float(self.get_fused_yaw())
                yaw_rad_snap = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
                self.snap_t_yaw_goal = float(normalize_angle(yaw_now + yaw_rad_snap))

        # ---- x,y 전체 재생성(옵션) ----
        if update_xy and self.enable_target_snapshot_full_refine:
            ok_t, x_t, y_t, yaw_t = self._compute_goal_from_marker(target_dist)
            if ok_t:
                self.snap_t_x_goal = float(x_t)
                self.snap_t_y_goal = float(y_t)
                # yaw도 같이 주는 값이 더 일관됨
                self.snap_t_yaw_goal = float(yaw_t)

        self.snap_t_created_time = time.time()
        self.snap_t_valid = True
        self.snapshot_valid = bool(self.snap_s_valid and self.snap_t_valid)

        self.target_snapshot_refined_once = True

        self.get_logger().warn(
            f"[SNAPSHOT] target refined with vision "
            f"(xy={'Y' if update_xy and self.enable_target_snapshot_full_refine else 'N'}, "
            f"yaw={'Y' if update_yaw else 'N'}) -> "
            f"target_goal=({self.snap_t_x_goal:.3f},{self.snap_t_y_goal:.3f}) yaw={self.snap_t_yaw_goal:.3f}"
        )


    # ---------------------------
    # Action execute
    # ---------------------------
    def execute_cb(self, goal_handle):
        goal = goal_handle.request

        target_ids = list(goal.target_ids) if len(goal.target_ids) > 0 else [2, 4]
        target_dist = float(goal.target_dist_m) if goal.target_dist_m > 0.0 else self.default_target_dist
        self.standoff_m = float(goal.standoff) if goal.standoff > 0.0 else self.standoff_m
        self.search_w = float(goal.search_angular_speed) if abs(goal.search_angular_speed) > 0.0 else self.search_w
        reverse = bool(goal.reverse)
        timeout_sec = float(goal.timeout_sec) if goal.timeout_sec > 0.0 else 30.0
        self.end_state = str(goal.end_state) if goal.end_state in ["IDLE", "SEARCH", "CENTERING", "FACE_ALIGN_TRANSLATE", "FACE_ALIGN_ROTATE", "VERIFY_POSE", "APPROACH", "FINAL_ALIGN", "DOCKED", "FAILSAFE"] else "IDLE"

        self.get_logger().info(
            f"Dock goal accepted: target_ids={target_ids}, target_dist={target_dist}, standoff={self.standoff_m}, search_w={self.search_w}, reverse={reverse}, timeout={timeout_sec}, end_state={self.end_state}"
        )

        self.reset_controllers()
        self.state = DockState.SEARCH
        start_time = time.time()
        last_time = time.time()

        self.align_lost_since = None
        self.verify_started = None
        self.centering_started = None

        self.centering_last_cx = None
        self.centering_wrong_direction_count = 0
        self.centering_direction_reversed = False

        # [NEW] snapshot reset
        self.snapshot_valid = False
        self.reacquire_started = None  # [UPDATED] verify reacquire timer reset
        self.final_reacquire_started = None

        feedback = Dock.Feedback()
        result = Dock.Result()
        locked_target_id = -1

        self.publish_cmd(0.0, 0.0)

        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                self.get_logger().warn("[ACTION] Cancel requested -> stopping")
                self.publish_cmd(0.0, 0.0)
                time.sleep(0.05)
                self.publish_cmd(0.0, 0.0)

                self.hard_stop()
                self.state = DockState.IDLE
                goal_handle.canceled()
                result.success = False
                result.message = "Canceled"
                result.locked_target_id = locked_target_id
                result.final_dist_err_m = 0.0
                result.final_yaw_err_rad = 0.0
                return result

            now = time.time()
            dt = max(1e-3, now - last_time)
            last_time = now

            if (now - start_time) > timeout_sec:
                self.get_logger().error("[ACTION] Timeout -> stopping")
                self.publish_cmd(0.0, 0.0)
                self.state = DockState.FAILSAFE
                goal_handle.abort()
                result.success = False
                result.message = "Timeout"
                result.locked_target_id = locked_target_id
                result.final_dist_err_m = 0.0
                result.final_yaw_err_rad = 0.0
                return result

            # -----------------------------------------------------------------
            # [UPDATED] Vision watchdog 정책
            #
            # 요구사항:
            # - APPROACH 단계에서는 vision이 보장되지 않는다.
            # - 따라서 "marker stale"만으로 APPROACH에서 FAILSAFE로 떨어지면 안 된다.
            #
            # 정책:
            # - CENTERING 계열은 기존 로직(align grace 등)으로 처리
            # - FINAL_ALIGN는 vision이 없더라도 odom fallback로 마무리 가능하므로
            #   marker stale만으로 FAILSAFE 하지 않는다.
            # - 최종 FAILSAFE는 "vision도 없고 odom도 없을 때" FINAL_ALIGN 내부에서 처리.
            # -----------------------------------------------------------------
            # 전역 watchdog (APPROACH/FINAL만 엄격)
            # if not self.marker_is_fresh():
            #     if self.state in (DockState.APPROACH, DockState.FINAL_ALIGN):
            #         self.get_logger().error("[WATCHDOG] Marker stale during motion -> FAILSAFE")
            #         self.state = DockState.FAILSAFE

            if self.marker_valid and self.marker_id in target_ids:
                locked_target_id = self.marker_id

            v_cmd, w_cmd = 0.0, 0.0

            # ------------------------------------------------------------
            # SEARCH
            # ------------------------------------------------------------
            if self.state == DockState.SEARCH:
                v_cmd = 0.0
                w_cmd = self.search_w

                if self.marker_valid and self.marker_id in target_ids and self.marker_is_fresh():
                    self.get_logger().warn(f"[FSM] SEARCH -> CENTERING (id={self.marker_id})")
                    self.state = DockState.CENTERING
                    self.reset_controllers()
                    self.align_lost_since = None
                    self.verify_started = None
                    self.reacquire_started = None  # [UPDATED] search 진입/탈출 시 timer 리셋
                    self.centering_started = now

                    self.centering_last_cx = None
                    self.centering_wrong_direction_count = 0
                    self.centering_direction_reversed = False

            # ------------------------------------------------------------
            # CENTERING
            # ------------------------------------------------------------
            elif self.state == DockState.CENTERING:
                timeout_occurred = False
                if self.centering_started is not None:
                    centering_duration = now - self.centering_started
                    if centering_duration > self.centering_timeout_sec:
                        self.get_logger().warn(
                            f"[FSM] CENTERING timeout ({centering_duration:.2f}s > {self.centering_timeout_sec}s) -> SEARCH"
                        )
                        self.state = DockState.SEARCH
                        self.centering_started = None
                        self.align_lost_since = None
                        v_cmd, w_cmd = 0.0, 0.0
                        timeout_occurred = True
                else:
                    self.centering_started = now

                if not timeout_occurred:
                    marker_ok = (
                        self.marker_valid and (self.marker_id in target_ids) and self.marker_is_fresh()
                        and (self.center_x_err is not None)
                    )

                    if not marker_ok:
                        if self.align_lost_since is None:
                            self.align_lost_since = now
                        elif (now - self.align_lost_since) > self.align_loss_grace:
                            self.get_logger().warn("[FSM] CENTERING lost marker (grace exceeded) -> SEARCH")
                            self.state = DockState.SEARCH
                            self.align_lost_since = None
                            self.centering_started = None
                            self.centering_last_cx = None
                            self.centering_wrong_direction_count = 0
                            self.centering_direction_reversed = False
                        v_cmd, w_cmd = 0.0, 0.0
                    else:
                        self.align_lost_since = None

                        cx = float(self.center_x_err)
                        abs_cx = abs(cx)

                        raw_w = self.pid_center.step(cx, dt, saturated=False)

                        if abs_cx > 0.5:
                            max_w_current = self.max_w_center_high
                        else:
                            max_w_current = self.max_w_center

                        if self.centering_direction_reversed:
                            w_cmd = clamp(raw_w, -max_w_current, max_w_current)
                        else:
                            w_cmd = clamp(-raw_w, -max_w_current, max_w_current)

                        v_cmd = 0.0

                        condition_met = abs_cx <= self.center_exit_th

                        if condition_met:
                            # [UPDATED 핵심]
                            # CENTERING 종료 시점에 standoff + target snapshot을 "동시에" 생성
                            self.create_snapshots(target_dist=target_dist)

                            if not self.snapshot_valid:
                                # snapshot 생성 실패면 안전하게 SEARCH로
                                self.get_logger().error("[FSM] CENTERING -> SEARCH (snapshot create failed)")
                                self.state = DockState.SEARCH
                            else:
                                self.get_logger().warn(
                                    "[FSM] CENTERING -> FACE_ALIGN_TRANSLATE (center ok, snapshots ready)"
                                )
                                self.state = DockState.FACE_ALIGN_TRANSLATE
                                self.reset_controllers()

                            self.verify_started = None
                            self.reacquire_started = None  # [UPDATED] timer reset
                            self.centering_started = None
                            self.centering_last_cx = None
                            self.centering_wrong_direction_count = 0
                            self.centering_direction_reversed = False

            # ------------------------------------------------------------
            # FACE_ALIGN_TRANSLATE  (Blind Translate)
            # ------------------------------------------------------------
            elif self.state == DockState.FACE_ALIGN_TRANSLATE:
                # [UPDATED 핵심] TRANSLATE는 마커 유실을 허용하며,
                # 전이 조건에 center_x_err / pose_yaw_err를 절대 쓰지 않는다.
                if not self.snapshot_valid:
                    self.get_logger().error("[FSM] TRANSLATE no snapshot -> SEARCH")
                    self.state = DockState.SEARCH
                    v_cmd, w_cmd = 0.0, 0.0

                elif not self.odom_is_fresh() or self.odom_x is None or self.odom_y is None:
                    self.get_logger().error("[FSM] TRANSLATE odom stale -> FAILSAFE")
                    self.state = DockState.FAILSAFE
                    v_cmd, w_cmd = 0.0, 0.0

                else:
                    x_now = float(self.odom_x)
                    y_now = float(self.odom_y)
                    yaw_now = float(self.get_fused_yaw())

                    dx = self.snap_s_x_goal - x_now
                    dy = self.snap_s_y_goal - y_now
                    dist_goal = math.sqrt(dx * dx + dy * dy)

                    # 목표점 방향
                    ang_to_goal = math.atan2(dy, dx)
                    head_err = normalize_angle(ang_to_goal - yaw_now)

                    # ==========================================================
                    # ✅ [수정 1] rotate-in-place 게이트 추가 (작은 원 회전 방지)
                    # ==========================================================

                    head_gate = 0.4   # 약 23도

                    # 각속도는 항상 비례제어
                    w = self.translate_w_kp * head_err
                    w_cmd = clamp(w, -self.translate_max_w, self.translate_max_w)

                    # [기존 코드 제거]
                    # v = self.translate_v_nom * max(0.15, math.cos(head_err))

                    # [수정된 코드 시작]
                    if abs(head_err) > head_gate:
                        # 각도가 많이 틀어지면 제자리 회전
                        v = 0.0
                    else:
                        # 정렬되면 전진
                        v = self.translate_v_nom * math.cos(head_err)

                    # 거리 기반 감속 (goal 근처 안정화)
                    slow_down_ratio = min(1.0, dist_goal / 0.10)
                    v *= slow_down_ratio

                    v_cmd = clamp(v, 0.0, self.max_v)
                    # ==========================================================

                    # NOTE: 아래 로그는 20Hz 주기(0.05s)로 계속 출력됨.
                    self.get_logger().warn(
                        f"[TRANSLATE] dist_goal={dist_goal:.3f} head_err={head_err:.3f} "
                        f"v={v_cmd:.3f} w={w_cmd:.3f} "
                        f"(goal=({self.snap_s_x_goal:.3f},{self.snap_s_y_goal:.3f}) "
                        f"now=({x_now:.3f},{y_now:.3f}) yaw={yaw_now:.3f})"
                    )

                    marker_dist_str = (
                        f"{self.tz_m:.3f}" if self.tz_m is not None else "None"
                    )

                    self.get_logger().warn(
                        f"[TRANSLATE-DEBUG] "
                        f"dist_goal={dist_goal:.3f} "
                        f"current_marker_dist={marker_dist_str} "
                        f"standoff={self.standoff_m:.3f}"
                    )

                    # ==========================================================
                    # ✅ 종료 조건은 dist_goal만 사용
                    # ==========================================================
                    if dist_goal <= self.translate_done_th:

                        if self.end_state == "FACE_ALIGN_TRANSLATE":
                            self.get_logger().info(
                                "[FSM] TRANSLATE -> IDLE "
                                "(dist_goal reached, end_state=FACE_ALIGN_TRANSLATE)"
                            )
                            self.publish_cmd(0.0, 0.0)

                            goal_handle.succeed()
                            result.success = True
                            result.message = "Translate done"
                            result.locked_target_id = locked_target_id
                            result.final_dist_err_m = (
                                float(self.distance_m - target_dist)
                                if self.distance_m is not None else 0.0
                            )
                            result.final_yaw_err_rad = (
                                float(self.yaw_rad)
                                if self.yaw_rad is not None else 0.0
                            )
                            return result

                        self.get_logger().warn(
                            "[FSM] TRANSLATE -> FACE_ALIGN_ROTATE (dist_goal reached)"
                        )
                        self.state = DockState.FACE_ALIGN_ROTATE
                        self.reset_controllers()


            # ------------------------------------------------------------
            # FACE_ALIGN_ROTATE  (Blind Rotate)
            # ------------------------------------------------------------
            elif self.state == DockState.FACE_ALIGN_ROTATE:
                if not self.snapshot_valid:
                    self.get_logger().error("[FSM] ROTATE no snapshot -> SEARCH")
                    self.state = DockState.SEARCH
                    v_cmd, w_cmd = 0.0, 0.0
                elif not self.odom_is_fresh() or self.odom_yaw is None:
                    self.get_logger().error("[FSM] ROTATE odom stale -> FAILSAFE")
                    self.state = DockState.FAILSAFE
                    v_cmd, w_cmd = 0.0, 0.0
                else:
                    yaw_now = float(self.get_fused_yaw())
                    yaw_err = normalize_angle(self.snap_yaw_goal - yaw_now)

                    # ✅ [NEW] vision 정보 체크
                    vision_ok = (
                        self.marker_valid and
                        (self.marker_id in target_ids) and
                        self.marker_is_fresh() and
                        (self.center_x_err is not None)
                    )

                    # ✅ [FIX] 멀티스레드 race 방지: center_x_err 로컬 스냅샷
                    cx_local = float(self.center_x_err) if (vision_ok and self.center_x_err is not None) else None

                    self.get_logger().warn(
                        f"[ROTATE] vsion_ok={vision_ok} marker_valid={self.marker_valid} marker_id={self.marker_id} "
                        f"marker_is_fresh={self.marker_is_fresh()} center_x_err={self.center_x_err}"
                    )

                    # 기본 회전 (odom 기반)
                    w_odom = self.rotate_w_kp * yaw_err

                    # ✅ vision 기반 보정(로컬 스냅샷 사용)
                    if vision_ok and (cx_local is not None):
                        w_vision = -1.2 * cx_local   # gain은 필요 시 조정
                        w = w_odom + w_vision
                    else:
                        w = w_odom

                    v_cmd = 0.0
                    w_cmd = clamp(w, -self.rotate_max_w, self.rotate_max_w)

                    self.get_logger().warn(
                        f"[ROTATE] yaw_now={yaw_now:.3f} yaw_goal={self.snap_yaw_goal:.3f} yaw_err={yaw_err:.3f} "
                        f"w={w_cmd:.3f}"
                    )

                    if abs(yaw_err) <= self.rotate_done_th:
                        if self.end_state == "FACE_ALIGN_ROTATE":
                            self.get_logger().info("[FSM] ROTATE -> IDLE (dist_goal reached, end_state=FACE_ALIGN_ROTATE)")
                            self.publish_cmd(0.0, 0.0)
                            goal_handle.succeed()
                            result.success = True
                            result.message = "Rotate done"
                            result.locked_target_id = locked_target_id
                            result.final_dist_err_m = float(self.distance_m - target_dist) if self.distance_m is not None else 0.0
                            result.final_yaw_err_rad = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
                            return result

                        # ✅ [FIX] 여기서 self.center_x_err 직접 abs() 금지 (race로 None 될 수 있음)
                        if vision_ok and (cx_local is not None) and (abs(cx_local) <= self.center_exit_th):
                            # [NEW] ROTATE 직후 vision이 살아있으면 target snapshot을 1회 보강
                            # - APPROACH에서는 vision이 보장되지 않으므로 여기서만 수행
                            self.refine_target_snapshot_with_vision(
                                target_dist=target_dist,
                                update_xy=True,   # 가능하면 x,y도 1회 재생성(옵션)
                                update_yaw=True   # yaw_goal은 최소 보강
                            )
                            self.get_logger().info("[FSM] ROTATE -> VERIFY_POSE")
                        elif not vision_ok:
                            self.get_logger().info("[FSM] ROTATE (no vision) -> VERIFY_POSE")

                        self.state = DockState.VERIFY_POSE
                        self.verify_started = None
                        self.reacquire_started = now
                        self.reset_controllers()


            # ------------------------------------------------------------
            # VERIFY_POSE
            # - yaw 검증: odom/snapshot 기반 yaw_err
            # - center 검증: (가능하면) vision center_x_err로만 확인
            # - vision이 없어도, 근접 blind-zone이면 "블라인드 verify"로 진행 가능
            # ------------------------------------------------------------
            elif self.state == DockState.VERIFY_POSE:

                if (not self.snapshot_valid) or (not self.odom_is_fresh()) or (self.odom_yaw is None):
                    self.get_logger().warn("[FSM] VERIFY_POSE missing snapshot/odom -> SEARCH")
                    self.state = DockState.SEARCH
                    self.verify_started = None
                    self.reacquire_started = None
                    v_cmd, w_cmd = 0.0, 0.0

                else:
                    # odom 기반 yaw_err
                    yaw_now = float(self.get_fused_yaw())
                    yaw_err = normalize_angle(self.snap_yaw_goal - yaw_now)

                    # odom 기반 goal distance도 같이 확인(translate 보정용)
                    x_now = float(self.odom_x) if self.odom_x is not None else 0.0
                    y_now = float(self.odom_y) if self.odom_y is not None else 0.0
                    dx = self.snap_s_x_goal - x_now
                    dy = self.snap_s_y_goal - y_now
                    dist_goal = math.sqrt(dx * dx + dy * dy)

                    # vision center 확인 가능 여부
                    marker_ok_for_center = (
                        self.marker_valid and (self.marker_id in target_ids) and self.marker_is_fresh()
                        and (self.center_x_err is not None)
                    )

                    # ---------------------------------------------------------
                    # [1] vision이 있으면: 기존처럼 center drift 검사 + yaw 검사
                    # ---------------------------------------------------------
                    if marker_ok_for_center:
                        self.reacquire_started = None
                        cx = float(self.center_x_err)

                        if abs(cx) > self.center_enter_th:
                            self.get_logger().warn("[FSM] VERIFY_POSE center drift -> CENTERING")
                            self.state = DockState.CENTERING
                            self.verify_started = None
                            v_cmd, w_cmd = 0.0, 0.0

                        elif abs(yaw_err) > self.rotate_done_th:
                            self.get_logger().warn(
                                f"[FSM] VERIFY_POSE yaw drift(odom) -> FACE_ALIGN_ROTATE "
                                f"(yaw_err={yaw_err:.3f} > {self.rotate_done_th:.3f})"
                            )
                            self.state = DockState.FACE_ALIGN_ROTATE
                            self.verify_started = None
                            v_cmd, w_cmd = 0.0, 0.0

                        elif dist_goal > (self.translate_done_th * 1.5):
                            self.get_logger().warn(
                                f"[FSM] VERIFY_POSE dist drift(odom) -> FACE_ALIGN_TRANSLATE "
                                f"(dist_goal={dist_goal:.3f} > {self.translate_done_th * 1.5:.3f})"
                            )
                            self.state = DockState.FACE_ALIGN_TRANSLATE
                            self.verify_started = None
                            v_cmd, w_cmd = 0.0, 0.0

                        else:
                            if self.verify_started is None:
                                self.verify_started = now

                            v_cmd, w_cmd = 0.0, 0.0
                            if (now - self.verify_started) >= self.verify_hold_sec:
                                self.get_logger().warn(
                                    f"[FSM] VERIFY_POSE -> APPROACH (stable, vision) "
                                    f"(yaw_err={yaw_err:.3f}, cx={cx:.3f}, dist_goal={dist_goal:.3f})"
                                )
                                self.state = DockState.APPROACH
                                self.reset_controllers()
                                self.verify_started = None

                    # ---------------------------------------------------------
                    # [2] vision이 없으면:
                    #    - 근접 blind-zone이면: 블라인드 verify(정지 홀드)로 APPROACH 가능
                    #    - 근접이 아니면: 제한 시간 동안만 REACQUIRE 시도
                    # ---------------------------------------------------------
                    else:
                        blind_ok = self.in_blind_zone()

                        # (a) 근접 블라인드: 의미있는 verify 수행 (odom yaw/dist 안정 홀드)
                        if blind_ok:
                            # dist/yaw가 크게 어긋났으면 먼저 보정 상태로 복귀
                            if abs(yaw_err) > self.rotate_done_th:
                                self.get_logger().warn(
                                    f"[FSM] VERIFY_POSE(blind) yaw drift -> FACE_ALIGN_ROTATE "
                                    f"(yaw_err={yaw_err:.3f} > {self.rotate_done_th:.3f})"
                                )
                                self.state = DockState.FACE_ALIGN_ROTATE
                                self.verify_started = None
                                v_cmd, w_cmd = 0.0, 0.0

                            elif dist_goal > (self.translate_done_th * 1.5):
                                self.get_logger().warn(
                                    f"[FSM] VERIFY_POSE(blind) dist drift -> FACE_ALIGN_TRANSLATE "
                                    f"(dist_goal={dist_goal:.3f} > {self.translate_done_th * 1.5:.3f})"
                                )
                                self.state = DockState.FACE_ALIGN_TRANSLATE
                                self.verify_started = None
                                v_cmd, w_cmd = 0.0, 0.0

                            else:
                                # 블라인드 verify: 정지 + hold
                                if self.verify_started is None:
                                    self.verify_started = now

                                v_cmd, w_cmd = 0.0, 0.0
                                if (now - self.verify_started) >= self.verify_hold_sec:
                                    self.get_logger().warn(
                                        f"[FSM] VERIFY_POSE -> APPROACH (stable, blind) "
                                        f"(yaw_err={yaw_err:.3f}, dist_goal={dist_goal:.3f}, "
                                        f"last_tz={self.last_valid_tz_m})"
                                    )
                                    self.state = DockState.APPROACH
                                    self.reset_controllers()
                                    self.verify_started = None

                        # (b) 근접 블라인드가 아니라면: 제한 시간 REACQUIRE 후 SEARCH
                        else:
                            if self.reacquire_started is None:
                                self.reacquire_started = now

                            if (now - self.reacquire_started) <= self.reacquire_timeout_sec:
                                v_cmd = 0.0
                                w_cmd = self.reacquire_w
                                self.get_logger().warn(
                                    f"[VERIFY_POSE] marker lost -> REACQUIRE spinning "
                                    f"({now - self.reacquire_started:.2f}/{self.reacquire_timeout_sec:.2f}s) "
                                    f"(yaw_err={yaw_err:.3f}, dist_goal={dist_goal:.3f})"
                                )
                            else:
                                self.get_logger().warn("[FSM] VERIFY_POSE lost marker (reacquire timeout) -> SEARCH")
                                self.state = DockState.SEARCH
                                self.verify_started = None
                                self.reacquire_started = None
                                v_cmd, w_cmd = 0.0, 0.0


            elif self.state == DockState.APPROACH:

                # -------------------------------------------------
                # APPROACH: odom 기반 제어 + vision 있으면 보정
                # - dist_goal이 매우 작으면 atan2(head_err)가 튀기 쉬워 heading drift 루프 발생
                # - vision이 없으면 drift 시 CENTERING이 아니라 ROTATE로 복귀(블라인드 환경 고려)
                # -------------------------------------------------

                if (not self.snapshot_valid) or (not self.odom_is_fresh()) \
                or (self.odom_x is None) or (self.odom_y is None) \
                or (self.odom_yaw is None):

                    self.get_logger().error("[FSM] APPROACH odom/snapshot invalid -> FAILSAFE")
                    self.state = DockState.FAILSAFE
                    v_cmd, w_cmd = 0.0, 0.0

                else:
                    x_now = float(self.odom_x)
                    y_now = float(self.odom_y)
                    yaw_now = float(self.get_fused_yaw())

                    dx = self.snap_t_x_goal - x_now
                    dy = self.snap_t_y_goal - y_now

                    dist_goal = math.sqrt(dx * dx + dy * dy)
                    ang_to_goal = math.atan2(dy, dx)
                    head_err = normalize_angle(ang_to_goal - yaw_now)

                    # 기본 제어
                    raw_v = self.pid_dist.step(dist_goal, dt, saturated=False)
                    raw_w = self.pid_yaw.step(head_err, dt, saturated=False)

                    v_cmd = clamp(raw_v, 0.0, self.max_v)
                    w_cmd = clamp(raw_w, -self.max_w, self.max_w)

                    # vision 보정 (있으면만 사용)
                    vision_ok = (
                        self.marker_valid and
                        (self.marker_id in target_ids) and
                        self.marker_is_fresh()
                    )

                    if vision_ok:
                        if self.yaw_rad is not None:
                            yaw_vis = float(self.yaw_rad)
                            w_cmd += -0.8 * yaw_vis

                        if self.center_x_err is not None:
                            cx = float(self.center_x_err)
                            w_cmd += -0.5 * cx

                        w_cmd = clamp(w_cmd, -self.max_w, self.max_w)

                    # -------------------------------------------------
                    # heading drift guard (중요)
                    # - dist_goal이 작으면 head_err가 불연속으로 튀므로 drift 판정을 약화/비활성
                    # -------------------------------------------------
                    if (dist_goal > self.approach_head_drift_min_dist) and (abs(head_err) > 0.6):
                        if vision_ok and (self.center_x_err is not None):
                            self.get_logger().warn("[FSM] APPROACH heading drift -> CENTERING (vision available)")
                            self.state = DockState.CENTERING
                        else:
                            self.get_logger().warn("[FSM] APPROACH heading drift -> FACE_ALIGN_ROTATE (blind)")
                            self.state = DockState.FACE_ALIGN_ROTATE

                        self.reset_controllers()
                        v_cmd, w_cmd = 0.0, 0.0

                    # FINAL 진입
                    elif dist_goal <= self.final_zone_dist:
                        self.get_logger().warn("[FSM] APPROACH -> FINAL_ALIGN (odom-based)")
                        self.state = DockState.FINAL_ALIGN
                        self.reset_controllers()

            elif self.state == DockState.FINAL_ALIGN:

                marker_ok = (
                    self.marker_valid and
                    (self.marker_id in target_ids) and
                    self.marker_is_fresh() and
                    (self.distance_m is not None) and
                    (self.yaw_rad is not None)
                )

                odom_ok = (
                    self.snapshot_valid and
                    self.odom_is_fresh() and
                    self.odom_x is not None and
                    self.odom_y is not None and
                    self.odom_yaw is not None
                )

                self.get_logger().warn(
                    f"[FINAL_ALIGN] marker_ok={marker_ok} odom_ok={odom_ok} "
                    f"marker_valid={self.marker_valid} marker_id={self.marker_id} marker_is_fresh={self.marker_is_fresh()} "
                    f"distance_m={self.distance_m} yaw_rad={self.yaw_rad} "
                    f"snapshot_valid={self.snapshot_valid} odom_x={self.odom_x} odom_y={self.odom_y} odom_yaw={self.odom_yaw}"
                )

                # ==========================================================
                # 1️⃣ VISION MODE (가장 정확)
                # ==========================================================
                if marker_ok:

                    self.final_reacquire_started = None

                    yaw_err = float(self.yaw_rad)
                    dist_err = float(self.distance_m) - target_dist

                    raw_v = self.pid_dist_final.step(dist_err, dt, saturated=False)
                    raw_w = self.pid_yaw.step(yaw_err, dt, saturated=False)

                    v_cmd = clamp(raw_v, -self.max_v_final, self.max_v_final)
                    w_cmd = clamp(raw_w, -self.max_w_final, self.max_w_final)

                    if reverse:
                        v_cmd = -abs(v_cmd)

                    if (abs(dist_err) <= self.dist_done_th) and (abs(yaw_err) <= self.yaw_final_th):
                        self.get_logger().info("[FSM] FINAL_ALIGN -> DOCKED (vision)")
                        self.state = DockState.DOCKED
                        self.publish_cmd(0.0, 0.0)

                # ==========================================================
                # 2️⃣ ODOM FALLBACK MODE (marker 없어도 마무리 가능)
                # ==========================================================
                elif odom_ok:

                    x_now = float(self.odom_x)
                    y_now = float(self.odom_y)
                    yaw_now = float(self.get_fused_yaw())

                    dx = self.snap_t_x_goal - x_now
                    dy = self.snap_t_y_goal - y_now
                    dist_goal = math.sqrt(dx * dx + dy * dy)

                    yaw_err = normalize_angle(self.snap_t_yaw_goal - yaw_now)

                    raw_v = self.pid_dist_final.step(dist_goal, dt, saturated=False)
                    raw_w = self.pid_yaw.step(yaw_err, dt, saturated=False)

                    v_cmd = clamp(raw_v, -self.max_v_final, self.max_v_final)
                    w_cmd = clamp(raw_w, -self.max_w_final, self.max_w_final)

                    if reverse:
                        v_cmd = -abs(v_cmd)

                    self.get_logger().warn(
                        f"[FINAL_ALIGN][ODOM] dist_goal={dist_goal:.3f} yaw_err={yaw_err:.3f}"
                    )

                    # 🔥 핵심: target_dist_m 이 13cm 이내여도 허용
                    # DOCKED 판정은 snapshot 목표점 기준으로 수행
                    if (dist_goal <= self.translate_done_th) and (abs(yaw_err) <= self.rotate_done_th):
                        self.get_logger().info("[FSM] FINAL_ALIGN -> DOCKED (odom fallback)")
                        self.state = DockState.DOCKED
                        self.publish_cmd(0.0, 0.0)

                # ==========================================================
                # 3️⃣ 둘 다 안되면 FAILSAFE
                # ==========================================================
                else:
                    self.get_logger().error("[FSM] FINAL_ALIGN no vision & no odom -> FAILSAFE")
                    self.state = DockState.FAILSAFE
                    v_cmd, w_cmd = 0.0, 0.0

            elif self.state == DockState.DOCKED:
                self.publish_cmd(0.0, 0.0)
                goal_handle.succeed()
                result.success = True
                result.message = "Docked"
                result.locked_target_id = locked_target_id
                result.final_dist_err_m = float(self.distance_m - target_dist) if self.distance_m is not None else 0.0
                result.final_yaw_err_rad = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
                return result

            elif self.state == DockState.FAILSAFE:
                self.publish_cmd(0.0, 0.0)
                goal_handle.abort()
                result.success = False
                result.message = "Failsafe (marker lost or invalid)"
                result.locked_target_id = locked_target_id
                result.final_dist_err_m = 0.0
                result.final_yaw_err_rad = 0.0
                return result

            # 명령 출력
            self.publish_cmd(v_cmd, w_cmd)

            # feedback
            feedback.state = self.state.name
            feedback.target_id = int(locked_target_id)
            feedback.distance_m = float(self.distance_m) if self.distance_m is not None else -1.0
            feedback.yaw_rad = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
            feedback.cmd_v = float(v_cmd)
            feedback.cmd_w = float(w_cmd)
            goal_handle.publish_feedback(feedback)

            time.sleep(0.05)


def main():
    rclpy.init()
    node = PrecisionDockingServer()
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    executor.spin()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
