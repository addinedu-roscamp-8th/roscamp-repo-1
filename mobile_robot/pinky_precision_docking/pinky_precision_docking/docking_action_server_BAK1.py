# pinky_precision_control_ws/src/pinky_precision_docking/pinky_precision_docking/docking_action_server.py

import time
import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from geometry_msgs.msg import Twist

from pinky_precision_interfaces.msg import Marker2D
from pinky_precision_interfaces.action import Dock

from .pid import PID, PIDGains, clamp
from .fsm import DockState


def wrap_pi(a: float) -> float:
    """각도를 [-pi, +pi]로 정규화."""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


class PrecisionDockingServer(Node):
    """
    Dock.action 서버:
    - Goal을 받으면 도킹 FSM을 시작
    - /precision/marker2d를 구독해서 yaw/dist 오차를 계산
    - /cmd_vel_raw로 속도를 출력
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

        # [UPDATED] Vision에서 오는 확장 관측값
        self.center_x_err = None         # 화면 중앙 오차 (-1~+1)
        self.pose_yaw_err = None         # 마커 법선 기반 yaw 오차(rad)

        # [NEW] Vision에서 오는 tvec 성분 (camera/base 근사)
        self.tx_m = None                 # 마커 중심 x (m)
        self.tz_m = None                 # 마커 중심 z (m)

        # ---- 제어 파라미터 ----
        self.default_target_dist = 0.01
        self.marker_timeout_sec = 0.5

        # -----------------------------
        # FSM 임계값
        # -----------------------------
        self.yaw_align_enter = 0.10      # APPROACH에서 yaw 커지면 정렬 복귀
        self.yaw_align_exit = 0.035

        self.yaw_final_th = 0.017
        self.final_zone_dist = 0.10
        self.dist_done_th = 0.01

        # [UPDATED] grace
        self.align_loss_grace = 0.30
        self.align_lost_since = None

        # CENTERING threshold (히스테리시스)
        self.center_exit_th = 0.08
        self.center_enter_th = 0.15

        # VERIFY_POSE threshold (pose)
        self.pose_exit_th = 0.10
        self.pose_enter_th = 0.20

        self.verify_hold_sec = 0.25
        self.verify_started = None

        # [IMPROVED] CENTERING timeout
        self.centering_timeout_sec = 10.0
        self.centering_started = None

        # [IMPROVED] 회전 방향 감지(센터링)
        self.centering_last_cx = None
        self.centering_wrong_direction_count = 0
        self.centering_direction_reversed = False

        # -----------------------------
        # [NEW] FACE_ALIGN_TRANSLATE 파라미터
        # -----------------------------
        # [NEW] standoff: 사용자가 지정한 기본값 0.15m
        self.translate_standoff_m = 0.15

        # [NEW] ROTATE로 넘어가는 기준값(느슨→엄격)
        # - 요구사항: "느슨하게 시작해서 엄격하게 적용"
        # - 1차 전이: loose_th로 ROTATE 진입 가능
        # - ROTATE에서 안정되면(또는 튜닝 후) strict_th로 낮추는 방향 추천
        self.pose_rotate_only_th_loose = 1.0   # rad (≈57°)  [NEW]
        self.pose_rotate_only_th_strict = 0.6  # rad (≈35°)  [NEW]
        self.use_strict_rotate_th = False      # [NEW] 기본은 느슨하게 시작

        # [NEW] TRANSLATE에서 목표점 추종용 속도 제한
        self.max_v_translate = 0.06            # [NEW] 천천히 이동
        self.max_w_translate = 0.35            # [NEW] 회전도 과하지 않게

        # [NEW] TRANSLATE 종료 조건(목표점 근접)
        self.translate_goal_tol_m = 0.03       # [NEW] 목표점까지 3cm 이내면 충분

        # [NEW] 재시도 스위치(요구사항: 두 모드 모두 테스트 가능)
        # - "강한 재시도": FACE_ALIGN 계열에서 실패하면 FAILSAFE로 바로 가지 않고 translate/centering로 적극 복귀
        # - "보수적": 빠르게 FAILSAFE
        self.face_retry_mode = "aggressive"    # [NEW] "aggressive" or "conservative"

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

        # center_x_err 제어
        self.pid_center = PID(PIDGains(kp=1.2, ki=0.0, kd=0.0, i_limit=0.0))

        # pose_yaw_err 제어
        self.pid_pose = PID(PIDGains(kp=1.2, ki=0.0, kd=0.08, i_limit=0.2))

        # [NEW] TRANSLATE 목표점(각도) 추종용 간단 P 제어
        self.kp_translate_heading = 1.4   # [NEW] heading error -> w
        self.kp_translate_speed = 0.8     # [NEW] distance-to-goal -> v

        self.get_logger().info("Precision docking action server started.")

    # ---------------------------
    # ROS callbacks
    # ---------------------------
    def marker_cb(self, msg: Marker2D):
        self.marker_valid = bool(msg.valid)
        self.marker_id = int(msg.id)

        self.distance_m = float(msg.distance_m) if msg.valid else None
        self.yaw_rad = float(msg.yaw_rad) if msg.valid else None

        self.center_x_err = float(msg.center_x_err) if msg.valid else None
        self.pose_yaw_err = float(msg.pose_yaw_err) if msg.valid else None

        # [NEW] tx/tz 저장 (TRANSLATE 삼각함수 기반 목표점 계산에 필수)
        self.tx_m = float(msg.tx_m) if msg.valid else None
        self.tz_m = float(msg.tz_m) if msg.valid else None

        if msg.valid:
            self.last_marker_time = time.time()
            self.get_logger().info(
                f"[MARKER] id={self.marker_id} dist={self.distance_m:.3f} yaw={self.yaw_rad:.3f} "
                f"tx={self.tx_m:.3f} tz={self.tz_m:.3f} "
                f"center_x_err={self.center_x_err:.3f} pose_yaw_err={self.pose_yaw_err:.3f}"
            )

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
    # Core helpers
    # ---------------------------
    def marker_is_fresh(self) -> bool:
        return (time.time() - self.last_marker_time) <= self.marker_timeout_sec

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

    def current_rotate_only_th(self) -> float:
        """ROTATE 진입 기준(느슨/엄격 스위치)."""
        return self.pose_rotate_only_th_strict if self.use_strict_rotate_th else self.pose_rotate_only_th_loose

    # ---------------------------
    # Action execute
    # ---------------------------
    def execute_cb(self, goal_handle):
        goal = goal_handle.request

        target_ids = list(goal.target_ids) if len(goal.target_ids) > 0 else [2, 4]
        target_dist = float(goal.target_dist_m) if goal.target_dist_m > 0.0 else self.default_target_dist
        reverse = bool(goal.reverse)
        timeout_sec = float(goal.timeout_sec) if goal.timeout_sec > 0.0 else 30.0

        self.get_logger().info(
            f"Dock goal accepted: target_ids={target_ids}, target_dist={target_dist}, reverse={reverse}, timeout={timeout_sec}"
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

        feedback = Dock.Feedback()
        result = Dock.Result()
        locked_target_id = -1

        self.publish_cmd(0.0, 0.0)

        while rclpy.ok():
            # cancel
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

            # timeout
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

            # watchdog: 이동 중(APPROACH/FINAL)에서 stale이면 즉시 FAILSAFE
            if not self.marker_is_fresh():
                if self.state in (DockState.APPROACH, DockState.FINAL_ALIGN):
                    self.get_logger().error("[WATCHDOG] Marker stale during motion -> FAILSAFE")
                    self.state = DockState.FAILSAFE

            # lock target
            if self.marker_valid and self.marker_id in target_ids:
                locked_target_id = self.marker_id

            v_cmd, w_cmd = 0.0, 0.0

            # =========================
            # SEARCH
            # =========================
            if self.state == DockState.SEARCH:
                v_cmd = 0.0
                w_cmd = self.search_w

                if self.marker_valid and self.marker_id in target_ids and self.marker_is_fresh():
                    self.get_logger().warn(f"[FSM] SEARCH -> CENTERING (id={self.marker_id})")
                    self.state = DockState.CENTERING
                    self.reset_controllers()
                    self.align_lost_since = None
                    self.verify_started = None
                    self.centering_started = now

                    self.centering_last_cx = None
                    self.centering_wrong_direction_count = 0
                    self.centering_direction_reversed = False

            # =========================
            # CENTERING
            # =========================
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
                        self.marker_valid and
                        (self.marker_id in target_ids) and
                        self.marker_is_fresh() and
                        (self.center_x_err is not None)
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

                        # 방향 자동 감지
                        direction_correct = True
                        if self.centering_last_cx is not None:
                            prev_abs_cx = abs(self.centering_last_cx)
                            if abs_cx > prev_abs_cx * 1.1:
                                self.centering_wrong_direction_count += 1
                                direction_correct = False
                            elif abs_cx < prev_abs_cx * 0.9:
                                self.centering_wrong_direction_count = 0
                                direction_correct = True

                        if self.centering_wrong_direction_count >= 3 and not self.centering_direction_reversed:
                            self.get_logger().warn("[CENTERING] Wrong direction detected -> reverse")
                            self.centering_direction_reversed = True
                            self.centering_wrong_direction_count = 0
                            self.pid_center.reset()

                        max_w_current = self.max_w_center_high if abs_cx > 0.5 else self.max_w_center

                        # [IMPORTANT] 기존 로그 분석 기반 방향 반전 기본 적용
                        if self.centering_direction_reversed:
                            w_cmd = clamp(raw_w, -max_w_current, max_w_current)
                        else:
                            w_cmd = clamp(-raw_w, -max_w_current, max_w_current)

                        v_cmd = 0.0
                        self.centering_last_cx = cx

                        # 전이
                        if abs_cx <= self.center_exit_th:
                            self.get_logger().info("[FSM] CENTERING -> FACE_ALIGN_TRANSLATE (center ok)")
                            self.state = DockState.FACE_ALIGN_TRANSLATE   # [UPDATED]
                            self.reset_controllers()
                            self.verify_started = None
                            self.centering_started = None

            # =========================
            # FACE_ALIGN_TRANSLATE (삼각함수 기반 “법선 방향 standoff” 위치로 이동)
            # =========================
            elif self.state == DockState.FACE_ALIGN_TRANSLATE:
                marker_ok = (
                    self.marker_valid and
                    (self.marker_id in target_ids) and
                    self.marker_is_fresh() and
                    (self.pose_yaw_err is not None) and
                    (self.tx_m is not None) and
                    (self.tz_m is not None)
                )

                if not marker_ok:
                    # [UPDATED] 재시도/FAILSAFE 스위치 적용
                    if self.align_lost_since is None:
                        self.align_lost_since = now
                    elif (now - self.align_lost_since) > self.align_loss_grace:
                        if self.face_retry_mode == "aggressive":
                            self.get_logger().warn("[FSM] TRANSLATE lost marker -> SEARCH (aggressive retry)")
                            self.state = DockState.SEARCH
                        else:
                            self.get_logger().error("[FSM] TRANSLATE lost marker -> FAILSAFE (conservative)")
                            self.state = DockState.FAILSAFE
                        self.align_lost_since = None
                    v_cmd, w_cmd = 0.0, 0.0
                else:
                    self.align_lost_since = None

                    # -----------------------------
                    # [CORE] 삼각함수 기반 목표점 생성
                    # - marker 위치 p = (tx, tz)
                    # - marker normal 각도 theta_n = pose_yaw_err
                    # - 원하는 로봇 위치: 마커 normal 방향으로 standoff 만큼 떨어진 곳
                    #   => 원하는 "마커가 보이는 위치" p_des = u * standoff
                    #      u = (sin(theta_n), cos(theta_n))
                    # -----------------------------
                    theta_n = wrap_pi(float(self.pose_yaw_err))
                    tx = float(self.tx_m)
                    tz = float(self.tz_m)

                    u_x = math.sin(theta_n)
                    u_z = math.cos(theta_n)

                    tx_des = u_x * self.translate_standoff_m
                    tz_des = u_z * self.translate_standoff_m

                    # 목표점 오차(현재 마커 위치 - 원하는 마커 위치)
                    e_x = tx - tx_des
                    e_z = tz - tz_des

                    dist_to_goal = math.sqrt(e_x * e_x + e_z * e_z)

                    # 목표점으로 향하는 heading(로봇 전방 기준)
                    heading_err = wrap_pi(math.atan2(e_x, e_z))

                    # [CONTROL] 차동구동: v(전진) + w(회전)
                    raw_w = self.kp_translate_heading * heading_err
                    raw_v = self.kp_translate_speed * dist_to_goal

                    w_cmd = clamp(raw_w, -self.max_w_translate, self.max_w_translate)
                    v_cmd = clamp(raw_v, 0.0, self.max_v_translate)

                    # [UPDATED] center_x_err는 "느슨하게" 유지: 너무 벗어나면 CENTERING으로 복귀
                    if self.center_x_err is not None and abs(float(self.center_x_err)) > (self.center_enter_th * 1.2):
                        self.get_logger().warn("[FSM] TRANSLATE center drift too big -> CENTERING")
                        self.state = DockState.CENTERING
                        self.reset_controllers()
                        self.centering_started = now
                        v_cmd, w_cmd = 0.0, 0.0

                    # -----------------------------
                    # 전이 조건:
                    # 1) pose_yaw_err가 ROTATE-only 가능한 범위로 들어오거나
                    # 2) 목표점에 충분히 근접하면
                    # -----------------------------
                    rotate_th = self.current_rotate_only_th()

                    if abs(theta_n) <= rotate_th or dist_to_goal <= self.translate_goal_tol_m:
                        self.get_logger().info(
                            f"[FSM] TRANSLATE -> FACE_ALIGN_ROTATE (pose={theta_n:.3f}, th={rotate_th:.3f}, dist={dist_to_goal:.3f})"
                        )
                        self.state = DockState.FACE_ALIGN_ROTATE
                        self.reset_controllers()

            # =========================
            # FACE_ALIGN_ROTATE (회전-only로 pose_yaw_err -> 0)
            # =========================
            elif self.state == DockState.FACE_ALIGN_ROTATE:
                marker_ok = (
                    self.marker_valid and
                    (self.marker_id in target_ids) and
                    self.marker_is_fresh() and
                    (self.pose_yaw_err is not None) and
                    (self.center_x_err is not None)
                )

                if not marker_ok:
                    if self.align_lost_since is None:
                        self.align_lost_since = now
                    elif (now - self.align_lost_since) > self.align_loss_grace:
                        if self.face_retry_mode == "aggressive":
                            self.get_logger().warn("[FSM] ROTATE lost marker -> TRANSLATE (aggressive retry)")
                            self.state = DockState.FACE_ALIGN_TRANSLATE
                        else:
                            self.get_logger().error("[FSM] ROTATE lost marker -> FAILSAFE (conservative)")
                            self.state = DockState.FAILSAFE
                        self.align_lost_since = None
                    v_cmd, w_cmd = 0.0, 0.0
                else:
                    self.align_lost_since = None

                    pose_err = wrap_pi(float(self.pose_yaw_err))
                    cx = float(self.center_x_err)

                    # [UPDATED] center가 다시 틀어지면 CENTERING으로 복귀
                    if abs(cx) > self.center_enter_th:
                        self.get_logger().warn("[FSM] ROTATE center drift -> CENTERING")
                        self.state = DockState.CENTERING
                        self.reset_controllers()
                        self.centering_started = now
                        v_cmd, w_cmd = 0.0, 0.0
                    else:
                        # pose_yaw_err 회전-only 제어
                        raw_w_pose = self.pid_pose.step(pose_err, dt, saturated=False)
                        w_cmd = clamp(raw_w_pose, -self.max_w_face, self.max_w_face)
                        v_cmd = 0.0

                        # [UPDATED] pose가 너무 커지면(기하학적으로 다시 불리) TRANSLATE로 복귀
                        if abs(pose_err) > (self.current_rotate_only_th() * 1.4):
                            self.get_logger().warn("[FSM] ROTATE pose grew too much -> TRANSLATE")
                            self.state = DockState.FACE_ALIGN_TRANSLATE
                            self.reset_controllers()
                            v_cmd, w_cmd = 0.0, 0.0

                        # VERIFY로 전이
                        if abs(pose_err) <= self.pose_exit_th:
                            self.get_logger().info("[FSM] ROTATE -> VERIFY_POSE (pose ok)")
                            self.state = DockState.VERIFY_POSE
                            self.verify_started = None

            # =========================
            # VERIFY_POSE
            # =========================
            elif self.state == DockState.VERIFY_POSE:
                marker_ok = (
                    self.marker_valid and
                    (self.marker_id in target_ids) and
                    self.marker_is_fresh() and
                    (self.pose_yaw_err is not None) and
                    (self.center_x_err is not None)
                )

                if not marker_ok:
                    self.get_logger().warn("[FSM] VERIFY_POSE lost marker -> SEARCH")
                    self.state = DockState.SEARCH
                    self.verify_started = None
                    v_cmd, w_cmd = 0.0, 0.0
                else:
                    pose_err = wrap_pi(float(self.pose_yaw_err))
                    cx = float(self.center_x_err)

                    if abs(cx) > self.center_enter_th:
                        self.get_logger().warn("[FSM] VERIFY_POSE center drift -> CENTERING")
                        self.state = DockState.CENTERING
                        self.verify_started = None
                        self.centering_started = now
                        v_cmd, w_cmd = 0.0, 0.0
                    elif abs(pose_err) > self.pose_enter_th:
                        self.get_logger().warn("[FSM] VERIFY_POSE pose drift -> FACE_ALIGN_ROTATE")
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

            # =========================
            # APPROACH
            # =========================
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
                        self.centering_started = now
                    else:
                        raw_v = self.pid_dist.step(dist_err, dt, saturated=False)
                        raw_w = self.pid_yaw.step(yaw_err, dt, saturated=False)

                        v_cmd = clamp(raw_v, 0.0, self.max_v)
                        w_cmd = clamp(raw_w, -self.max_w, self.max_w)

                        if self.distance_m is not None and self.distance_m < self.final_zone_dist:
                            self.get_logger().info("[FSM] APPROACH -> FINAL_ALIGN")
                            self.state = DockState.FINAL_ALIGN
                            self.reset_controllers()

            # =========================
            # FINAL_ALIGN
            # =========================
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

            # =========================
            # DOCKED
            # =========================
            elif self.state == DockState.DOCKED:
                self.publish_cmd(0.0, 0.0)
                goal_handle.succeed()
                result.success = True
                result.message = "Docked"
                result.locked_target_id = locked_target_id
                result.final_dist_err_m = float(self.distance_m - target_dist) if self.distance_m is not None else 0.0
                result.final_yaw_err_rad = float(self.yaw_rad) if self.yaw_rad is not None else 0.0
                return result

            # =========================
            # FAILSAFE
            # =========================
            elif self.state == DockState.FAILSAFE:
                self.publish_cmd(0.0, 0.0)
                goal_handle.abort()
                result.success = False
                result.message = "Failsafe (marker lost or invalid)"
                result.locked_target_id = locked_target_id
                result.final_dist_err_m = 0.0
                result.final_yaw_err_rad = 0.0
                return result

            # ---- publish cmd ----
            self.publish_cmd(v_cmd, w_cmd)

            # ---- feedback ----
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
