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
        self.center_enter_th = 0.15

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

        # [NEW] IMU 보정(있는 경우에만 사용)
        self.use_imu_yaw = False  # IMU가 신뢰할 수 있으면 True로 설정
        self.imu_alpha = 0.15  # (0~1) yaw = (1-a)*odom + a*imu  (작게 시작)

        # ---------------------------------------------------------------------
        # [NEW] Snapshot 저장소
        # ---------------------------------------------------------------------
        self.snapshot_valid = False
        self.snap_x_goal = 0.0
        self.snap_y_goal = 0.0
        self.snap_yaw_goal = 0.0
        self.snap_created_time = 0.0

        self.get_logger().info("Precision docking action server started.")

    # ---------------------------
    # ROS callbacks
    # ---------------------------
    def marker_cb(self, msg: Marker2D):
        self.marker_valid = bool(msg.valid)
        self.marker_id = int(msg.id)

        self.distance_m = float(msg.distance_m) if msg.valid else None
        self.yaw_rad = float(msg.yaw_rad) if msg.valid else None

        # [UPDATED] 확장 관측값 저장
        self.center_x_err = float(msg.center_x_err) if msg.valid else None
        self.pose_yaw_err = float(msg.pose_yaw_err) if msg.valid else None

        # [NEW] tx/tz 저장 (Marker2D.msg에 존재한다고 가정)
        self.tx_m = float(msg.tx_m) if msg.valid else None
        self.tz_m = float(msg.tz_m) if msg.valid else None

        if msg.valid:
            self.last_marker_time = time.time()
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

    # [NEW] Snapshot 생성
    def create_snapshot_goal(self):
        """
        CENTERING 완료 시점에 1회 호출.
        - 현재 odom pose + (tx,tz,pose_yaw_err)로 목표 standoff 점을 odom에 저장
        - 목표 yaw는 '법선 방향을 정면으로 보게' 하는 yaw_goal로 저장
        """
        if not self.odom_is_fresh() or self.odom_x is None or self.odom_y is None:
            self.get_logger().error("[SNAPSHOT] Odom not available/fresh -> cannot create snapshot")
            self.snapshot_valid = False
            return

        if not self.marker_valid or self.tx_m is None or self.tz_m is None or self.pose_yaw_err is None:
            self.get_logger().error("[SNAPSHOT] Marker data not available -> cannot create snapshot")
            self.snapshot_valid = False
            return

        x_now = self.odom_x
        y_now = self.odom_y
        yaw_now = self.get_fused_yaw()

        tx = float(self.tx_m)
        tz = float(self.tz_m)

        # ------------------------------------------------------------------
        # [UPDATED START] standoff 목표점이 "마커 법선 방향 기준 standoff_m"가 되도록 보정
        #  - pose_yaw_err가 ±pi 근처로 튀는 경우를 [-pi/2, +pi/2]로 접어 안정화
        #  - camera(x=right, z=forward) -> base(x=forward, y=left) 변환 시 부호를 명확히 적용
        # ------------------------------------------------------------------
        theta_raw = float(self.pose_yaw_err)

        # 1) [-pi, +pi] 정규화
        theta = normalize_angle(theta_raw)

        # 2) 법선 해석 안정화: 너무 뒤집힌(>90deg) 경우 π를 빼서 같은 방향(정면)으로 접기
        #    예) +170deg -> -10deg,  -170deg -> +10deg
        if abs(theta) > (math.pi / 2.0):
            theta = normalize_angle(theta - math.copysign(math.pi, theta))

        # 3) 마커 법선 단위벡터(카메라 x-z 평면 기준)
        #    theta=0 이면 정면: (nx,nz)=(0,1)
        nx = math.sin(theta)
        nz = math.cos(theta)

        # 4) standoff 목표점(카메라 x,z 평면)
        #    - 현재 관측된 마커 중심(tx,tz)에서
        #    - 마커 법선 방향으로 standoff_m 만큼 "카메라 쪽(앞/뒤 정의 포함)"으로 이동한 점
        #
        #    여기서는 pose_yaw_err가 "카메라가 마커 법선을 바라보도록" 만드는 기준이라고 가정하고,
        #    standoff 점은 마커 중심에서 법선 방향으로 standoff_m 만큼 '빼는' 형태로 유지합니다.
        dx_base = tx - self.standoff_m * nx   # camera x 성분
        dz_base = tz - self.standoff_m * nz   # camera z 성분

        # 5) camera -> base 변환
        #    camera: x=right(+), z=forward(+)
        #    base  : x=forward(+), y=left(+)
        #    => base_x = camera_z
        #    => base_y = -camera_x   (right(+)는 left(+)의 반대)
        base_x = dz_base
        base_y = -dx_base  # [UPDATED] 핵심 부호

        # ------------------------------------------------------------------
        # [UPDATED END]
        # ------------------------------------------------------------------

        # odom으로 회전시켜 목표점 생성
        x_goal = x_now + math.cos(yaw_now) * base_x - math.sin(yaw_now) * base_y
        y_goal = y_now + math.sin(yaw_now) * base_x + math.cos(yaw_now) * base_y

        # 목표 yaw (기존 구조 유지)
        yaw_rad_snap = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
        yaw_goal = normalize_angle(yaw_now + yaw_rad_snap)

        self.snap_x_goal = float(x_goal)
        self.snap_y_goal = float(y_goal)
        self.snap_yaw_goal = float(yaw_goal)
        self.snap_created_time = time.time()
        self.snapshot_valid = True

        # NOTE: 아래 로그는 반복 출력은 아니고 "스냅샷 생성 시 1회"라서 성능 영향이 제한적임.
        #       만약 스냅샷을 매우 자주 만들도록 변경한다면,
        #       '성능을 저하시킬 수 있는 로그 코드이므로 주석을 권합니다.'  # [UPDATED-LOG]
        self.get_logger().info(
            f"[SNAPSHOT] created: x_goal={self.snap_x_goal:.3f}, y_goal={self.snap_y_goal:.3f}, "
            f"yaw_goal={self.snap_yaw_goal:.3f}, standoff={self.standoff_m:.3f} "
            f"(tx={tx:.3f}, tz={tz:.3f}, pose_yaw_err_raw={theta_raw:.3f}, pose_yaw_err_used={theta:.3f}, "
            f"yaw_rad_snap={yaw_rad_snap:.3f}, p_standoff_cam=({dx_base:.3f},{dz_base:.3f}))"
        )

        self.get_logger().warn(
            f"[SNAPSHOT-DEBUG] "
            f"yaw_now={yaw_now:.3f} "
            f"theta_raw={theta_raw:.3f} "
            f"theta_used={theta:.3f} "
            f"nx={nx:.3f} nz={nz:.3f} "
            f"tx={tx:.3f} tz={tz:.3f} "
            f"dx_base={dx_base:.3f} dz_base={dz_base:.3f} "
            f"base_x={base_x:.3f} base_y={base_y:.3f} "
            f"x_goal={x_goal:.3f} y_goal={y_goal:.3f}"
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

            # 전역 watchdog (APPROACH/FINAL만 엄격)
            if not self.marker_is_fresh():
                if self.state in (DockState.APPROACH, DockState.FINAL_ALIGN):
                    self.get_logger().error("[WATCHDOG] Marker stale during motion -> FAILSAFE")
                    self.state = DockState.FAILSAFE

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
                            # [UPDATED 핵심] CENTERING 종료 시점에 snapshot 생성
                            self.create_snapshot_goal()

                            if not self.snapshot_valid:
                                # snapshot 생성 실패면 안전하게 SEARCH로
                                self.get_logger().error("[FSM] CENTERING -> SEARCH (snapshot create failed)")
                                self.state = DockState.SEARCH
                            else:
                                self.get_logger().warn("[FSM] CENTERING -> FACE_ALIGN_TRANSLATE (center ok, snapshot ready)")
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

                    dx = self.snap_x_goal - x_now
                    dy = self.snap_y_goal - y_now
                    dist_goal = math.sqrt(dx * dx + dy * dy)

                    # 목표점 방향
                    ang_to_goal = math.atan2(dy, dx)
                    head_err = normalize_angle(ang_to_goal - yaw_now)

                    # [UPDATED] "회전->이동" 반복 방지:
                    # - v를 항상 주되, head_err가 크면 cos로 감속
                    # - w는 head_err 비례
                    v = self.translate_v_nom * max(0.15, math.cos(head_err))
                    w = self.translate_w_kp * head_err

                    v_cmd = clamp(v, 0.0, self.max_v)
                    w_cmd = clamp(w, -self.translate_max_w, self.translate_max_w)

                    # NOTE: 아래 로그는 20Hz 주기(0.05s)로 계속 출력됨.
                    #       '성능을 저하시킬 수 있는 로그 코드이므로 주석을 권합니다.'  # [UPDATED-LOG]
                    self.get_logger().warn(
                        f"[TRANSLATE] dist_goal={dist_goal:.3f} head_err={head_err:.3f} "
                        f"v={v_cmd:.3f} w={w_cmd:.3f} (goal=({self.snap_x_goal:.3f},{self.snap_y_goal:.3f}) "
                        f"now=({x_now:.3f},{y_now:.3f}) yaw={yaw_now:.3f})"
                    )

                    self.get_logger().warn(
                        f"[TRANSLATE-DEBUG] "
                        f"dist_goal={dist_goal:.3f} "
                        f"current_marker_dist={self.tz_m:.3f} "
                        f"standoff={self.standoff_m:.3f}"
                    )

                    # [UPDATED 핵심] 종료 조건은 dist_goal만
                    if dist_goal <= self.translate_done_th:
                        if self.end_state == "FACE_ALIGN_TRANSLATE":
                            self.get_logger().info("[FSM] TRANSLATE -> IDLE (dist_goal reached, end_state=FACE_ALIGN_TRANSLATE)")
                            self.publish_cmd(0.0, 0.0)
                            goal_handle.succeed()
                            result.success = True
                            result.message = "Translate done"
                            result.locked_target_id = locked_target_id
                            result.final_dist_err_m = float(self.distance_m - target_dist) if self.distance_m is not None else 0.0
                            result.final_yaw_err_rad = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
                            return result
                        self.get_logger().warn("[FSM] TRANSLATE -> FACE_ALIGN_ROTATE (dist_goal reached)")
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

                    self.get_logger().warn(f"[ROTATE] vsion_ok={vision_ok} marker_valid={self.marker_valid} marker_id={self.marker_id} marker_is_fresh={self.marker_is_fresh()} center_x_err={self.center_x_err}")

                    # 기본 회전 (odom 기반)
                    w_odom = self.rotate_w_kp * yaw_err

                    # ✅ [NEW] vision 기반 보정
                    if vision_ok:
                        cx = float(self.center_x_err)

                        # 화면 중앙으로 유도
                        w_vision = -1.2 * cx   # gain은 필요 시 조정

                        # hybrid 결합
                        w = w_odom + w_vision
                    else:
                        w = w_odom

                    v_cmd = 0.0
                    w_cmd = clamp(w, -self.rotate_max_w, self.rotate_max_w)

                    # NOTE: 아래 로그도 반복 출력.
                    #       '성능을 저하시킬 수 있는 로그 코드이므로 주석을 권합니다.'  # [UPDATED-LOG]
                    self.get_logger().warn(
                        f"[ROTATE] yaw_now={yaw_now:.3f} yaw_goal={self.snap_yaw_goal:.3f} yaw_err={yaw_err:.3f} "
                        f"w={w_cmd:.3f}"
                    )

                    # [UPDATED 핵심] ROTATE에서 center drift로 CENTERING 복귀 금지
                    # (Blind rotate는 odom/imu yaw만 본다)

                    if abs(yaw_err) <= self.rotate_done_th:
                        # [UPDATED] ROTATE 종료 후 SEARCH로 되돌아가면
                        # SEARCH->CENTERING->TRANSLATE->ROTATE 루프가 쉽게 발생할 수 있다.
                        # 그래서 바로 VERIFY_POSE로 진입하고, 필요 시 VERIFY 안에서 "짧은 REACQUIRE"를 수행한다.
                        if vision_ok and abs(self.center_x_err) <= self.center_exit_th:
                            self.get_logger().info("[FSM] ROTATE -> VERIFY_POSE")
                        elif not vision_ok:
                            # vision 없으면 odom 기준으로도 진행
                            self.get_logger().info("[FSM] ROTATE (no vision) -> VERIFY_POSE")
                        self.state = DockState.VERIFY_POSE
                        self.verify_started = None
                        self.reacquire_started = now  # [UPDATED] VERIFY에서 재획득 grace 시작
                        self.reset_controllers()

            # ------------------------------------------------------------
            # VERIFY_POSE / APPROACH / FINAL_ALIGN / DOCKED / FAILSAFE
            # ------------------------------------------------------------
            elif self.state == DockState.VERIFY_POSE:
                marker_ok = (
                    self.marker_valid and (self.marker_id in target_ids) and self.marker_is_fresh()
                    and (self.pose_yaw_err is not None) and (self.center_x_err is not None)
                )
                if not marker_ok:
                    # ---------------------------------------------------------
                    # [UPDATED] VERIFY_POSE "짧은 REACQUIRE"
                    # - ROTATE/근접 구간에서 마커가 잠깐 끊겨도 즉시 SEARCH로 빠지지 않음
                    # - 제한 시간 동안만 천천히 회전하며 재획득을 시도
                    # ---------------------------------------------------------
                    if self.reacquire_started is None:
                        self.reacquire_started = now

                    if (now - self.reacquire_started) <= self.reacquire_timeout_sec:
                        # 재획득 시도(느린 회전). v=0 유지.
                        v_cmd = 0.0
                        w_cmd = self.reacquire_w
                        self.get_logger().warn(
                            f"[VERIFY_POSE] marker lost -> REACQUIRE spinning ({now - self.reacquire_started:.2f}/{self.reacquire_timeout_sec:.2f}s)"
                        )
                    else:
                        self.get_logger().warn("[FSM] VERIFY_POSE lost marker (reacquire timeout) -> SEARCH")
                        self.state = DockState.SEARCH
                        self.verify_started = None
                        self.reacquire_started = None
                        v_cmd, w_cmd = 0.0, 0.0
                else:
                    self.reacquire_started = None  # [UPDATED] marker 재획득 성공 -> timer reset
                    pose_err = float(self.pose_yaw_err)
                    cx = float(self.center_x_err)

                    if abs(cx) > self.center_enter_th:
                        self.get_logger().warn("[FSM] VERIFY_POSE center drift -> CENTERING")
                        self.state = DockState.CENTERING
                        self.verify_started = None
                        v_cmd, w_cmd = 0.0, 0.0
                    elif abs(pose_err) > self.pose_enter_th:
                        self.get_logger().warn("[FSM] VERIFY_POSE pose drift -> FACE_ALIGN_ROTATE")
                        # VERIFY에서 drift나면 ROTATE로 재정렬(이미 스냅샷 기반으로 처리했으니 여기서는 단순하게)
                        self.state = DockState.FACE_ALIGN_ROTATE
                        self.verify_started = None
                        v_cmd, w_cmd = 0.0, 0.0
                    else:
                        if self.verify_started is None:
                            self.verify_started = now
                        v_cmd, w_cmd = 0.0, 0.0
                        if (now - self.verify_started) >= self.verify_hold_sec:
                            self.get_logger().info("[FSM] VERIFY_POSE -> APPROACH (stable)")
                            self.state = DockState.APPROACH
                            self.reset_controllers()
                            self.verify_started = None

            elif self.state == DockState.APPROACH:
                marker_ok = (self.marker_valid and (self.marker_id in target_ids) and self.marker_is_fresh())
                if not marker_ok:
                    self.get_logger().error("[FSM] APPROACH lost marker -> FAILSAFE")
                    self.state = DockState.FAILSAFE
                else:
                    yaw_err = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
                    dist_err = float(self.distance_m) - target_dist

                    if abs(yaw_err) > self.yaw_align_enter:
                        self.get_logger().warn("[FSM] APPROACH yaw too big -> CENTERING")
                        self.state = DockState.CENTERING
                        self.reset_controllers()
                        self.align_lost_since = None
                        self.verify_started = None
                    else:
                        raw_v = self.pid_dist.step(dist_err, dt, saturated=False)
                        raw_w = self.pid_yaw.step(yaw_err, dt, saturated=False)
                        v_cmd = clamp(raw_v, 0.0, self.max_v)
                        w_cmd = clamp(raw_w, -self.max_w, self.max_w)

                        if self.distance_m is not None and self.distance_m < self.final_zone_dist:
                            self.get_logger().info("[FSM] APPROACH -> FINAL_ALIGN")
                            self.state = DockState.FINAL_ALIGN
                            self.reset_controllers()

            elif self.state == DockState.FINAL_ALIGN:
                if not (self.marker_valid and self.marker_id in target_ids and self.marker_is_fresh()):
                    self.get_logger().error("[FSM] FINAL_ALIGN lost marker -> FAILSAFE")
                    self.state = DockState.FAILSAFE
                else:
                    yaw_err = float(self.yaw_rad)
                    dist_err = float(self.distance_m) - target_dist

                    raw_v = self.pid_dist_final.step(dist_err, dt, saturated=False)
                    raw_w = self.pid_yaw.step(yaw_err, dt, saturated=False)

                    v_cmd = clamp(raw_v, -self.max_v_final, self.max_v_final)
                    w_cmd = clamp(raw_w, -self.max_w_final, self.max_w_final)

                    if reverse:
                        v_cmd = -abs(v_cmd)

                    if (abs(dist_err) <= self.dist_done_th) and (abs(yaw_err) <= self.yaw_final_th):
                        self.get_logger().info("[FSM] FINAL_ALIGN -> DOCKED")
                        self.state = DockState.DOCKED
                        self.publish_cmd(0.0, 0.0)

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
