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


def canonicalize_normal_yaw(theta_n: float) -> float:
    """
    [UPDATED-TRANSLATE-FIX]
    pose_yaw_err(법선 yaw)가 ±pi 근처로 들어오는 경우(법선이 뒤집힘)를 정면 기준으로 정규화한다.

    아이디어:
      - 우리가 원하는 건 "카메라/로봇 기준 앞쪽(+Z)으로 향하는 법선"을 기준으로 standoff를 잡는 것
      - cos(theta) < 0 이면 법선이 뒤를 보고 있다는 뜻(±90° 밖)
      - 이때 theta += pi 로 뒤집어 앞을 보게 만든다.

    효과:
      - pose_yaw_err ≈ 2.5 rad 같은 값이 ≈ -0.64 rad로 바뀌어
        ROTATE/TRANSLATE에서 현실적으로 줄일 수 있는 값이 된다.
    """
    theta_n = wrap_pi(theta_n)
    if math.cos(theta_n) < 0.0:
        theta_n = wrap_pi(theta_n + math.pi)
    return theta_n


class PrecisionDockingServer(Node):
    def __init__(self):
        super().__init__("pinky_precision_docking_server")

        self.cb_group = ReentrantCallbackGroup()

        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel_raw", 10)
        self.marker_sub = self.create_subscription(
            Marker2D, "/precision/marker2d", self.marker_cb, 10,
            callback_group=self.cb_group
        )

        self._action_server = ActionServer(
            self,
            Dock,
            "/precision/dock",
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=self.cancel_cb,
            callback_group=self.cb_group
        )

        self.state = DockState.IDLE

        # time split
        self.last_msg_time = 0.0
        self.last_valid_time = 0.0

        self.marker_valid = False
        self.marker_id = -1

        self.distance_m = None
        self.yaw_rad = None
        self.center_x_err = None
        self.pose_yaw_err = None

        self.tx_m = None
        self.tz_m = None

        self.default_target_dist = 0.01

        self.marker_timeout_sec = 0.6
        self.valid_marker_timeout_sec = 0.8

        # FSM thresholds
        self.yaw_align_enter = 0.10
        self.yaw_align_exit = 0.035

        self.yaw_final_th = 0.017
        self.final_zone_dist = 0.10
        self.dist_done_th = 0.01

        self.align_loss_grace = 0.50
        self.align_lost_since = None

        self.center_exit_th = 0.08
        self.center_enter_th = 0.15

        self.pose_exit_th = 0.10
        self.pose_enter_th = 0.20

        self.verify_hold_sec = 0.25
        self.verify_started = None

        self.centering_timeout_sec = 10.0
        self.centering_started = None

        self.centering_last_cx = None
        self.centering_wrong_direction_count = 0
        self.centering_direction_reversed = False

        # TRANSLATE params
        self.translate_standoff_m = 0.15

        self.pose_rotate_only_th_loose = 1.0
        self.pose_rotate_only_th_strict = 0.6
        self.use_strict_rotate_th = False

        self.max_v_translate = 0.06
        self.max_w_translate = 0.35
        self.translate_goal_tol_m = 0.03

        # [UPDATED-TRANSLATE-FIX] TRANSLATE에서 center를 상태 전이가 아니라 "내부 제어"로 처리하기 위한 파라미터
        self.translate_center_soft_th = self.center_enter_th          # 0.15: 여기부터 감속/보정 강화
        self.translate_center_hard_th = self.center_enter_th * 2.0    # 0.30: 여기 넘으면 CENTERING으로 강제 전이(안전)

        # [UPDATED-TRANSLATE-FIX] 원호 유지용 center 보정 gain
        self.kp_translate_center = 0.8   # w_cmd에 center 기반 보정 추가(원호 유지)

        self.face_retry_mode = "conservative"  # "aggressive" or "conservative"

        # speed limits
        self.max_v = 0.12
        self.max_w = 0.6

        self.max_w_align = 0.25
        self.max_w_center = 0.30
        self.max_w_center_high = 0.40
        self.max_w_face = 0.15

        self.max_v_final = 0.02
        self.max_w_final = 0.3

        self.search_w = 0.25

        # PID
        self.pid_yaw = PID(PIDGains(kp=1.6, ki=0.0, kd=0.10, i_limit=0.2))
        self.pid_dist = PID(PIDGains(kp=0.8, ki=0.0, kd=0.0, i_limit=0.2))
        self.pid_dist_final = PID(PIDGains(kp=0.6, ki=0.0, kd=0.0, i_limit=0.2))

        self.pid_center = PID(PIDGains(kp=1.2, ki=0.0, kd=0.0, i_limit=0.0))
        self.pid_pose = PID(PIDGains(kp=1.2, ki=0.0, kd=0.08, i_limit=0.2))

        self.kp_translate_heading = 1.4
        self.kp_translate_speed = 0.8

        self.get_logger().info("Precision docking action server started.")

    def marker_cb(self, msg: Marker2D):
        self.last_msg_time = time.time()

        self.marker_valid = bool(msg.valid)
        self.marker_id = int(msg.id) if msg.valid else -1

        self.distance_m = float(msg.distance_m) if msg.valid else None
        self.yaw_rad = float(msg.yaw_rad) if msg.valid else None
        self.center_x_err = float(msg.center_x_err) if msg.valid else None
        self.pose_yaw_err = float(msg.pose_yaw_err) if msg.valid else None

        self.tx_m = float(msg.tx_m) if msg.valid else None
        self.tz_m = float(msg.tz_m) if msg.valid else None

        if msg.valid:
            self.last_valid_time = self.last_msg_time
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

    def goal_cb(self, goal_request: Dock.Goal) -> GoalResponse:
        return GoalResponse.ACCEPT

    def cancel_cb(self, goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    def marker_stream_is_fresh(self) -> bool:
        return (time.time() - self.last_msg_time) <= self.marker_timeout_sec

    def valid_marker_is_recent(self) -> bool:
        return (time.time() - self.last_valid_time) <= self.valid_marker_timeout_sec

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
        return self.pose_rotate_only_th_strict if self.use_strict_rotate_th else self.pose_rotate_only_th_loose

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

            if not self.marker_stream_is_fresh():
                if self.state in (DockState.APPROACH, DockState.FINAL_ALIGN):
                    self.get_logger().error("[WATCHDOG] Marker stream stale during motion -> FAILSAFE")
                    self.state = DockState.FAILSAFE

            if self.marker_valid and self.marker_id in target_ids:
                locked_target_id = self.marker_id

            v_cmd, w_cmd = 0.0, 0.0

            # =========================
            # SEARCH
            # =========================
            if self.state == DockState.SEARCH:
                v_cmd = 0.0
                w_cmd = self.search_w

                if self.marker_valid and (self.marker_id in target_ids) and self.valid_marker_is_recent():
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
                        self.valid_marker_is_recent() and
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

                        if self.centering_last_cx is not None:
                            prev_abs_cx = abs(self.centering_last_cx)
                            if abs_cx > prev_abs_cx * 1.1:
                                self.centering_wrong_direction_count += 1
                            elif abs_cx < prev_abs_cx * 0.9:
                                self.centering_wrong_direction_count = 0

                        if self.centering_wrong_direction_count >= 3 and not self.centering_direction_reversed:
                            self.get_logger().warn("[CENTERING] Wrong direction detected -> reverse")
                            self.centering_direction_reversed = True
                            self.centering_wrong_direction_count = 0
                            self.pid_center.reset()

                        max_w_current = self.max_w_center_high if abs_cx > 0.5 else self.max_w_center

                        if self.centering_direction_reversed:
                            w_cmd = clamp(raw_w, -max_w_current, max_w_current)
                        else:
                            w_cmd = clamp(-raw_w, -max_w_current, max_w_current)

                        v_cmd = 0.0
                        self.centering_last_cx = cx

                        if abs_cx <= self.center_exit_th:
                            self.get_logger().info("[FSM] CENTERING -> FACE_ALIGN_TRANSLATE (center ok)")
                            self.state = DockState.FACE_ALIGN_TRANSLATE
                            self.reset_controllers()
                            self.verify_started = None
                            self.centering_started = None

            # =========================
            # FACE_ALIGN_TRANSLATE
            # =========================
            elif self.state == DockState.FACE_ALIGN_TRANSLATE:
                marker_ok = (
                    self.marker_valid and
                    (self.marker_id in target_ids) and
                    self.valid_marker_is_recent() and
                    (self.pose_yaw_err is not None) and
                    (self.tx_m is not None) and
                    (self.tz_m is not None) and
                    (self.center_x_err is not None)
                )

                if not marker_ok:
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

                    # ---------- 핵심: 법선 yaw 정규화 ----------
                    raw_theta = float(self.pose_yaw_err)
                    theta_n = canonicalize_normal_yaw(raw_theta)   # [UPDATED-TRANSLATE-FIX]

                    tx = float(self.tx_m)
                    tz = float(self.tz_m)
                    cx = float(self.center_x_err)
                    abs_cx = abs(cx)

                    # ---------- 목표 standoff 점(마커 앞) ----------
                    u_x = math.sin(theta_n)
                    u_z = math.cos(theta_n)

                    tx_des = u_x * self.translate_standoff_m
                    tz_des = u_z * self.translate_standoff_m

                    e_x = tx - tx_des
                    e_z = tz - tz_des

                    dist_to_goal = math.sqrt(e_x * e_x + e_z * e_z)
                    heading_err = wrap_pi(math.atan2(e_x, e_z))

                    # ---------- 원호 제어 기본 ----------
                    raw_w_heading = self.kp_translate_heading * heading_err
                    raw_v = self.kp_translate_speed * dist_to_goal

                    # ---------- [UPDATED-TRANSLATE-FIX] TRANSLATE 내부에서 center drift를 "상태 전이"가 아니라 "제어"로 해결 ----------
                    # center가 커지면:
                    #   - 전진 속도를 줄이고(혹은 0)
                    #   - center를 다시 회복하도록 회전을 더 줌
                    # 이게 실제로 "원호로 가다 시야가 틀어지면 감속하며 시야를 회복"하는 동작이다.

                    raw_w_center = self.kp_translate_center * cx
                    raw_w = raw_w_heading + raw_w_center

                    # 감속 스케줄: center가 커질수록 v를 줄임
                    if abs_cx <= self.translate_center_soft_th:
                        v_cmd = clamp(raw_v, 0.0, self.max_v_translate)
                    else:
                        # soft_th(0.15)~hard_th(0.30) 구간: 선형으로 속도 축소
                        t = min(1.0, (abs_cx - self.translate_center_soft_th) /
                                     (self.translate_center_hard_th - self.translate_center_soft_th))
                        v_scale = max(0.0, 1.0 - t)  # 1 -> 0
                        v_cmd = clamp(raw_v * v_scale, 0.0, self.max_v_translate)

                    # center가 너무 크면(하드) 안전하게 CENTERING으로 넘김
                    if abs_cx > self.translate_center_hard_th:
                        self.get_logger().warn(
                            f"[FSM] TRANSLATE center HARD drift (cx={abs_cx:.3f} > {self.translate_center_hard_th:.3f}) -> CENTERING"
                        )
                        self.state = DockState.CENTERING
                        self.reset_controllers()
                        self.centering_started = now
                        v_cmd, w_cmd = 0.0, 0.0
                    else:
                        w_cmd = clamp(raw_w, -self.max_w_translate, self.max_w_translate)

                        # 디버그 핵심 로그(스팸 줄이기 목적이면 추후 throttle 가능)
                        self.get_logger().warn(
                            f"[TRANSLATE] theta_raw={raw_theta:.3f} theta_used={theta_n:.3f} "
                            f"cx={cx:.3f} dist_goal={dist_to_goal:.3f} head_err={heading_err:.3f} "
                            f"v={v_cmd:.3f} w={w_cmd:.3f}"
                        )

                        rotate_th = self.current_rotate_only_th()
                        if abs(theta_n) <= rotate_th or dist_to_goal <= self.translate_goal_tol_m:
                            self.get_logger().warn(
                                f"[FSM] TRANSLATE -> FACE_ALIGN_ROTATE (pose={theta_n:.3f}, th={rotate_th:.3f}, dist={dist_to_goal:.3f})"
                            )
                            self.state = DockState.FACE_ALIGN_ROTATE
                            self.reset_controllers()

            # =========================
            # FACE_ALIGN_ROTATE
            # =========================
            elif self.state == DockState.FACE_ALIGN_ROTATE:
                marker_ok = (
                    self.marker_valid and
                    (self.marker_id in target_ids) and
                    self.valid_marker_is_recent() and
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

                    # [UPDATED-TRANSLATE-FIX] ROTATE에서도 동일한 법선 정규화 적용
                    pose_err = canonicalize_normal_yaw(float(self.pose_yaw_err))

                    cx = float(self.center_x_err)
                    if abs(cx) > self.center_enter_th:
                        self.get_logger().warn("[FSM] ROTATE center drift -> CENTERING")
                        self.state = DockState.CENTERING
                        self.reset_controllers()
                        self.centering_started = now
                        v_cmd, w_cmd = 0.0, 0.0
                    else:
                        raw_w_pose = self.pid_pose.step(pose_err, dt, saturated=False)
                        w_cmd = clamp(raw_w_pose, -self.max_w_face, self.max_w_face)
                        v_cmd = 0.0

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
                    self.valid_marker_is_recent() and
                    (self.pose_yaw_err is not None) and
                    (self.center_x_err is not None)
                )

                if not marker_ok:
                    self.get_logger().warn("[FSM] VERIFY_POSE lost marker -> SEARCH")
                    self.state = DockState.SEARCH
                    self.verify_started = None
                    v_cmd, w_cmd = 0.0, 0.0
                else:
                    pose_err = canonicalize_normal_yaw(float(self.pose_yaw_err))
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
                marker_ok = (self.marker_valid and (self.marker_id in target_ids) and self.valid_marker_is_recent())
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
                if not (self.marker_valid and self.marker_id in target_ids and self.valid_marker_is_recent()):
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

            self.publish_cmd(v_cmd, w_cmd)

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
