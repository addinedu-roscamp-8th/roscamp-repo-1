import time

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

        # [UPDATED] Marker2D 확장 필드 저장
        self.center_x_err = None        # 화면 중앙 오차 (-1~+1)
        self.pose_yaw_err = None        # 마커 법선 기준 yaw 오차(rad)

        # ---- 제어 파라미터(초기값, 이후 yaml로 이동 예정) ----
        # 목표: 1cm
        self.default_target_dist = 0.01

        # 타임아웃/워치독
        self.marker_timeout_sec = 0.5

        # -----------------------------
        # FSM 임계값
        # -----------------------------
        # 기존 단일 threshold(yaw_align_th)는 “진입/전이”가 같아서 튐이 생길 수 있음.
        # [UPDATE] yaw 히스테리시스(ENTER/EXIT)로 분리
        self.yaw_align_enter = 0.10   # 약 6도: ALIGN 상태를 "유지"할 수 있는 최대 yaw (이보다 크면 다시 SEARCH/재탐색 유도 가능)
        self.yaw_align_exit = 0.035   # 약 2도: APPROACH로 넘어갈 만큼 충분히 정렬됐다고 보는 기준

        self.yaw_final_th = 0.017     # 1 deg
        self.final_zone_dist = 0.10   # 10cm 진입 시 FINAL
        self.dist_done_th = 0.01      # 1cm 이내면 완료 조건에 사용

        # [UPDATED] CENTERING/FACE_ALIGN에서 마커가 잠깐 끊겨도 즉시 SEARCH로 안 가도록 grace
        self.align_loss_grace = 0.30  # 초: 0.1~0.5 사이에서 튜닝
        self.align_lost_since = None  # 처음 끊긴 시각 기록용

        # -----------------------------
        # [UPDATED] CENTERING / FACE_ALIGN / VERIFY_POSE 임계값
        # -----------------------------
        # center_x_err가 이 범위면 “화면 중앙에 거의 있다”
        self.center_exit_th = 0.08     # (정규화 -1~+1 기준) 약 8% 이내면 중앙으로 판단
        self.center_enter_th = 0.15    # 중앙에서 벗어나면(15% 이상) 다시 CENTERING으로 복귀 가능

        # pose_yaw_err가 이 범위면 “마커 법선이 정면(카메라를 바라봄)에 가깝다”
        self.pose_exit_th = 0.10       # rad (약 5.7도)
        self.pose_enter_th = 0.20      # rad (약 11.5도)

        # VERIFY_POSE: 조건이 잠깐 만족했다고 바로 APPROACH로 가지 않게 "연속 만족" 요구
        self.verify_hold_sec = 0.25    # 0.2~0.5 추천
        self.verify_started = None     # [UPDATED] VERIFY_POSE 시작 시각

        # [IMPROVED] CENTERING 타임아웃: 무한 대기 방지
        self.centering_timeout_sec = 10.0  # CENTERING 상태 최대 지속 시간 (초)
        self.centering_started = None       # CENTERING 진입 시각 기록용
        
        # [IMPROVED] 회전 방향 자동 감지 및 안전장치
        self.centering_last_cx = None       # 이전 center_x_err 값
        self.centering_wrong_direction_count = 0  # 잘못된 방향 카운트
        self.centering_direction_reversed = False  # 방향 반전 플래그

        # -----------------------------
        # 속도 제한
        # -----------------------------
        self.max_v = 0.12
        self.max_w = 0.6
        
        # [중요] ALIGN 전용 각속도 제한: 급회전으로 마커를 FOV 밖으로 날리는 현상을 막음
        self.max_w_align = 0.25  # 🔴 중요: ALIGN 전용 제한

        # [UPDATED] CENTERING 단계에서는 회전을 더 부드럽게(너무 세게 돌면 바로 유실)
        # [IMPROVED] 큰 오차 수정을 위해 기본 속도 제한 증가 및 적응형 제한 사용
        self.max_w_center = 0.30  # 0.20 → 0.30으로 증가 (큰 오차 수정 속도 향상)
        self.max_w_center_high = 0.40  # 큰 오차(>0.5)일 때 사용할 더 높은 속도 제한

        # [UPDATED] FACE_ALIGN 단계에서는 정말 미세하게만 회전
        self.max_w_face = 0.15

        self.max_v_final = 0.02
        self.max_w_final = 0.3

        self.search_w = 0.25  # SEARCH 회전 속도

        # -----------------------------
        # PID (yaw는 PD부터 시작 권장)
        # -----------------------------
        self.pid_yaw = PID(PIDGains(kp=1.6, ki=0.0, kd=0.10, i_limit=0.2))
        self.pid_dist = PID(PIDGains(kp=0.8, ki=0.0, kd=0.0, i_limit=0.2))
        self.pid_dist_final = PID(PIDGains(kp=0.6, ki=0.0, kd=0.0, i_limit=0.2))

         # [UPDATED] CENTERING 전용 "픽셀 중심 PID" (간단히 P만 써도 됨)
        # [IMPROVED] kp 증가로 수렴 속도 향상
        self.pid_center = PID(PIDGains(kp=1.2, ki=0.0, kd=0.0, i_limit=0.0))

        # [UPDATED] FACE_ALIGN 전용 "법선 yaw PID"
        self.pid_pose = PID(PIDGains(kp=1.2, ki=0.0, kd=0.08, i_limit=0.2))

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

        if msg.valid:
            self.last_marker_time = time.time()
            # 디버그: 마커 수신 확인 (확장 필드 포함)
            self.get_logger().info(
                f"[MARKER] id={self.marker_id} dist={self.distance_m:.3f} yaw={self.yaw_rad:.3f} "
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
        # 여기서 간단한 유효성 검사 가능
        return GoalResponse.ACCEPT

    def cancel_cb(self, goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    # ---------------------------
    # Core FSM helpers
    # ---------------------------
    def marker_is_fresh(self) -> bool:
        return (time.time() - self.last_marker_time) <= self.marker_timeout_sec

    def reset_controllers(self):
        self.pid_yaw.reset()
        self.pid_dist.reset()
        self.pid_dist_final.reset()
        # [UPDATED] 추가 PID도 reset
        self.pid_center.reset()
        self.pid_pose.reset()

    def hard_stop(self, repeats: int = 5, dt: float = 0.05):
        # cancel 직후에도 관성/통신 문제로 속도가 남을 수 있어 0을 여러 번 보냄
        for _ in range(repeats):
            self.publish_cmd(0.0, 0.0)
            time.sleep(dt)


    # ---------------------------
    # Action execute
    # ---------------------------
    def execute_cb(self, goal_handle):
        goal = goal_handle.request

        # Goal 파라미터
        target_ids = list(goal.target_ids) if len(goal.target_ids) > 0 else [2, 4]
        target_dist = float(goal.target_dist_m) if goal.target_dist_m > 0.0 else self.default_target_dist
        reverse = bool(goal.reverse)
        timeout_sec = float(goal.timeout_sec) if goal.timeout_sec > 0.0 else 30.0

        self.get_logger().info(
            f"Dock goal accepted: target_ids={target_ids}, target_dist={target_dist}, reverse={reverse}, timeout={timeout_sec}"
        )

        # 주요 상태 지표 모니터링 로그
        self.get_logger().info(
            f"[MONITOR] state={self.state.name}, marker_valid={self.marker_valid}, "
            f"marker_id={self.marker_id}, distance_m={self.distance_m}, yaw_rad={self.yaw_rad}, "
            f"last_marker_time={self.last_marker_time:.3f}, target_ids={target_ids}, "
            f"target_dist={target_dist:.3f}, marker_is_fresh={self.marker_is_fresh()}"
        )

        # FSM init
        self.reset_controllers()
        self.state = DockState.SEARCH
        start_time = time.time()
        last_time = time.time()

        # [UPDATED] grace/verify 타이머 초기화
        self.align_lost_since = None
        self.verify_started = None
        self.centering_started = None
        # [IMPROVED] 회전 방향 감지 초기화
        self.centering_last_cx = None
        self.centering_wrong_direction_count = 0
        self.centering_direction_reversed = False

        feedback = Dock.Feedback()
        result = Dock.Result()
        locked_target_id = -1

        # 안전: 시작 시 정지 1회
        self.publish_cmd(0.0, 0.0)


        while rclpy.ok():
            # cancel 처리 (CLI가 없더라도, action client에서 cancel 요청이 오면 여기서 처리)
            if goal_handle.is_cancel_requested:
                self.get_logger().warn("[ACTION] Cancel requested -> stopping")
                self.publish_cmd(0.0, 0.0)
                time.sleep(0.05)
                self.publish_cmd(0.0, 0.0)

                self.hard_stop()  # ✅ 확실 정지
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

            # timeout 처리
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

            # ------------------------------------------------------------
            # [UPDATED] 전역 마커 유실 처리 수정 (grace 로직을 무력화하지 않도록)
            # - SEARCH: 유실 정상(계속 회전)
            # - CENTERING/FACE_ALIGN/VERIFY_POSE: 각 상태의 grace 로직이 처리
            # - APPROACH/FINAL_ALIGN: 안전상 유실이면 FAILSAFE
            # ------------------------------------------------------------
            if not self.marker_is_fresh():
                if self.state in (DockState.APPROACH, DockState.FINAL_ALIGN):
                    self.get_logger().error("[WATCHDOG] Marker stale during motion -> FAILSAFE")
                    self.state = DockState.FAILSAFE
                # else: SEARCH/CENTERING/FACE_ALIGN/VERIFY_POSE/IDLE 등은 여기서 강제 전이하지 않음


            # 현재 marker가 목표 대상인지 판정
            if self.marker_valid and self.marker_id in target_ids:
                locked_target_id = self.marker_id

            # FSM 실행
            v_cmd, w_cmd = 0.0, 0.0

            if self.state == DockState.SEARCH:
                # 마커를 찾을 때까지 제자리 회전
                v_cmd = 0.0
                w_cmd = self.search_w

                # 조건문 변수 확인 로그
                marker_is_fresh_result = self.marker_is_fresh()
                marker_id_in_targets = self.marker_id in target_ids
                time_since_last_marker = time.time() - self.last_marker_time
                self.get_logger().info(
                    f"[CONDITION_CHECK] marker_valid={self.marker_valid}, "
                    f"marker_id={self.marker_id}, target_ids={target_ids}, "
                    f"marker_id_in_targets={marker_id_in_targets}, "
                    f"marker_is_fresh={marker_is_fresh_result}, "
                    f"time_since_last_marker={time_since_last_marker:.3f}, "
                    f"marker_timeout_sec={self.marker_timeout_sec}, "
                    f"last_marker_time={self.last_marker_time:.3f}"
                )

                if self.marker_valid and self.marker_id in target_ids and self.marker_is_fresh():
                    self.get_logger().warn(f"[FSM] SEARCH -> CENTERING (id={self.marker_id})")
                    self.state = DockState.CENTERING
                    self.reset_controllers()
                    self.align_lost_since = None
                    self.verify_started = None
                    self.centering_started = now  # [IMPROVED] CENTERING 시작 시각 기록
                    # [IMPROVED] 회전 방향 감지 초기화
                    self.centering_last_cx = None
                    self.centering_wrong_direction_count = 0
                    self.centering_direction_reversed = False

            # -------------------------
            # [UPDATED] CENTERING
            # - 화면 중앙(center_x_err)을 먼저 맞춘다
            # - 차동구동이므로 회전(w)으로 "중앙 맞추기"
            # -------------------------
            elif self.state == DockState.CENTERING:
                # [IMPROVED] CENTERING 타임아웃 체크
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
                        # 타임아웃 로그 (10초마다 또는 마지막 2초)
                        if centering_duration > 8.0 or int(centering_duration) % 2 == 0:
                            self.get_logger().info(
                                f"[CENTERING_MONITOR] Centering duration: {centering_duration:.2f}s / {self.centering_timeout_sec}s"
                            )
                else:
                    # 처음 진입 시 타이머 시작
                    self.centering_started = now

                # 타임아웃 발생 시 나머지 로직 건너뛰기
                if not timeout_occurred:
                    # 조건 변수 평가
                    marker_valid_check = self.marker_valid
                    marker_id_check = self.marker_id in target_ids if self.marker_id != -1 else False
                    marker_fresh_check = self.marker_is_fresh()
                    center_x_err_exists = self.center_x_err is not None
                    
                    marker_ok = (marker_valid_check and marker_id_check and marker_fresh_check and center_x_err_exists)

                    # CENTERING 진입점 상세 모니터링 로그
                    self.get_logger().info(
                        f"[CENTERING_MONITOR] === CENTERING State Entry ==="
                    )
                    self.get_logger().info(
                        f"[CENTERING_MONITOR] marker_valid: {marker_valid_check} "
                        f"({'✓' if marker_valid_check else '✗'})"
                    )
                    self.get_logger().info(
                        f"[CENTERING_MONITOR] marker_id: {self.marker_id}, target_ids: {target_ids}, "
                        f"marker_id_in_targets: {marker_id_check} {'✓' if marker_id_check else '✗'}"
                    )
                    self.get_logger().info(
                        f"[CENTERING_MONITOR] marker_is_fresh: {marker_fresh_check} "
                        f"({'✓' if marker_fresh_check else '✗'}) "
                        f"(time_since_last={time.time() - self.last_marker_time:.3f}s, "
                        f"timeout={self.marker_timeout_sec}s)"
                    )
                    self.get_logger().info(
                        f"[CENTERING_MONITOR] center_x_err exists: {center_x_err_exists} "
                        f"({'✓' if center_x_err_exists else '✗'})"
                    )
                    self.get_logger().info(
                        f"[CENTERING_MONITOR] marker_ok (all conditions): {marker_ok} "
                        f"({'✓ ALL PASS' if marker_ok else '✗ FAILED'})"
                    )

                    if not marker_ok:
                        # [UPDATED] loss grace 적용
                        if self.align_lost_since is None:
                            self.align_lost_since = now
                        elif (now - self.align_lost_since) > self.align_loss_grace:
                            self.get_logger().warn("[FSM] CENTERING lost marker (grace exceeded) -> SEARCH")
                            self.state = DockState.SEARCH
                            self.align_lost_since = None
                            self.centering_started = None  # [IMPROVED] 타이머 리셋
                            # [IMPROVED] 회전 방향 감지 상태 리셋
                            self.centering_last_cx = None
                            self.centering_wrong_direction_count = 0
                            self.centering_direction_reversed = False
                        v_cmd, w_cmd = 0.0, 0.0
                    else:
                        self.align_lost_since = None

                        # [SAFETY] 멀티스레드 환경에서 center_x_err가 None으로 변경될 수 있으므로 재확인
                        if self.center_x_err is None:
                            self.get_logger().warn("[CENTERING_MONITOR] center_x_err became None during processing, skipping control")
                            v_cmd, w_cmd = 0.0, 0.0
                        else:
                            # center_x_err: -면 왼쪽에 있음 → 왼쪽으로 돌면 중앙으로 온다(환경마다 부호 반대일 수 있음)
                            cx = float(self.center_x_err)
                            abs_cx = abs(cx)

                            # [UPDATED] 중앙 맞추기: P 제어로 부드럽게 회전
                            raw_w = self.pid_center.step(cx, dt, saturated=False)

                            # [IMPROVED] 회전 방향 자동 감지 및 안전장치
                            direction_correct = True
                            if self.centering_last_cx is not None:
                                # 이전 값과 비교하여 오차가 개선되었는지 확인
                                prev_abs_cx = abs(self.centering_last_cx)
                                if abs_cx > prev_abs_cx * 1.1:  # 10% 이상 악화
                                    self.centering_wrong_direction_count += 1
                                    direction_correct = False
                                    self.get_logger().warn(
                                        f"[CENTERING_MONITOR] Error increased: {prev_abs_cx:.6f} -> {abs_cx:.6f} "
                                        f"(wrong_direction_count={self.centering_wrong_direction_count})"
                                    )
                                elif abs_cx < prev_abs_cx * 0.9:  # 10% 이상 개선
                                    self.centering_wrong_direction_count = 0  # 리셋
                                    direction_correct = True
                            
                            # 잘못된 방향이 3회 연속 발생하면 방향 반전
                            if self.centering_wrong_direction_count >= 3 and not self.centering_direction_reversed:
                                self.get_logger().warn(
                                    "[CENTERING_MONITOR] Wrong direction detected! Reversing rotation direction."
                                )
                                self.centering_direction_reversed = True
                                self.centering_wrong_direction_count = 0
                                self.pid_center.reset()  # PID 리셋
                            
                            # [IMPROVED] 적응형 속도 제한: 큰 오차일 때 더 빠르게 회전
                            if abs_cx > 0.5:
                                # 큰 오차(>50%)일 때 더 높은 속도 제한 사용
                                max_w_current = self.max_w_center_high
                            else:
                                # 작은 오차일 때 기본 속도 제한 사용
                                max_w_current = self.max_w_center

                            # [FIXED] 회전 방향 반전 적용 (로그 분석 결과 회전 방향이 반대였음)
                            # center_x_err가 음수(왼쪽)일 때 양수 회전(시계 방향)이 필요
                            # 로그 분석: 기본 방향이 반대였으므로 기본적으로 반전된 방향 사용
                            if self.centering_direction_reversed:
                                # 자동 감지로 다시 원래 방향으로 돌아간 경우
                                w_cmd = clamp(raw_w, -max_w_current, max_w_current)
                            else:
                                # 기본 방향: 반전된 방향 사용 (로그 분석 결과)
                                w_cmd = clamp(-raw_w, -max_w_current, max_w_current)
                            
                            v_cmd = 0.0  # CENTERING에서는 전진 최소화 (유실 방지)
                            
                            # [IMPROVED] 이전 값 저장 (다음 루프에서 비교용)
                            self.centering_last_cx = cx

                            # FACE_ALIGN 이행 조건 상세 모니터링
                            center_exit_threshold = self.center_exit_th
                            condition_met = abs_cx <= center_exit_threshold
                            
                            self.get_logger().info(
                                f"[CENTERING_MONITOR] center_x_err: {cx:.6f}, abs(center_x_err): {abs_cx:.6f}"
                            )
                            self.get_logger().info(
                                f"[CENTERING_MONITOR] center_exit_threshold: {center_exit_threshold:.6f}"
                            )
                            self.get_logger().info(
                                f"[CENTERING_MONITOR] Adaptive speed limit: max_w={max_w_current:.3f} "
                                f"(high={abs_cx > 0.5})"
                            )
                            self.get_logger().info(
                                f"[CENTERING_MONITOR] Rotation direction: reversed={self.centering_direction_reversed}, "
                                f"direction_correct={direction_correct}, wrong_count={self.centering_wrong_direction_count}"
                            )
                            self.get_logger().info(
                                f"[CENTERING_MONITOR] Transition condition: abs(cx) <= center_exit_th "
                                f"-> {abs_cx:.6f} <= {center_exit_threshold:.6f} = {condition_met} "
                                f"({'✓ TRANSITION READY' if condition_met else '✗ NOT READY'})"
                            )
                            self.get_logger().info(
                                f"[CENTERING_MONITOR] PID output: raw_w={raw_w:.6f}, w_cmd={w_cmd:.6f}, "
                                f"v_cmd={v_cmd:.6f}, direction_reversed={self.centering_direction_reversed}"
                            )

                            # [UPDATED] 중앙 조건 만족하면 FACE_ALIGN로
                            if condition_met:
                                self.get_logger().info("[FSM] CENTERING -> FACE_ALIGN (center ok)")
                                self.state = DockState.FACE_ALIGN
                                self.reset_controllers()
                                self.verify_started = None
                                self.centering_started = None  # [IMPROVED] 타이머 리셋
                                # [IMPROVED] 회전 방향 감지 상태 리셋
                                self.centering_last_cx = None
                                self.centering_wrong_direction_count = 0
                                self.centering_direction_reversed = False

            # -------------------------
            # [UPDATED] FACE_ALIGN
            # - 마커 법선이 카메라/로봇을 정면으로 보게(pose_yaw_err ~ 0) 만든다
            # - 필요 시 “짧은 전진 + 회전”을 줄 수 있지만, 일단은 회전 위주로 안전하게 시작
            # -------------------------
            elif self.state == DockState.FACE_ALIGN:
                marker_ok = (self.marker_valid and (self.marker_id in target_ids) and self.marker_is_fresh()
                             and (self.pose_yaw_err is not None) and (self.center_x_err is not None))

                if not marker_ok:
                    if self.align_lost_since is None:
                        self.align_lost_since = now
                    elif (now - self.align_lost_since) > self.align_loss_grace:
                        self.get_logger().warn("[FSM] FACE_ALIGN lost marker (grace exceeded) -> SEARCH")
                        self.state = DockState.SEARCH
                        self.align_lost_since = None
                    v_cmd, w_cmd = 0.0, 0.0
                else:
                    self.align_lost_since = None

                    pose_err = float(self.pose_yaw_err)
                    cx = float(self.center_x_err)
                    abs_cx = abs(cx)

                    # [UPDATED] 법선 yaw 정렬은 pose_yaw_err로
                    raw_w_pose = self.pid_pose.step(pose_err, dt, saturated=False)

                    # [IMPROVED] center_x_err도 함께 제어하여 드리프트 방지
                    # 항상 작은 가중치로 center_x_err 보정을 적용하여 드리프트를 미리 방지
                    raw_w_center = self.pid_center.step(cx, dt, saturated=False)
                    # [FIXED] 회전 방향 반전 적용 (CENTERING과 동일한 로직 사용)
                    # CENTERING과 동일: centering_direction_reversed=False일 때는 -raw_w 사용
                    if not self.centering_direction_reversed:
                        # 기본 방향: 반전된 방향 사용 (로그 분석 결과)
                        raw_w_center = -raw_w_center
                    # centering_direction_reversed=True일 때는 원래 방향 사용 (그대로)
                    
                    # center_x_err가 임계값에 가까워지면 보정 가중치 증가
                    # 보정 시작 임계값을 낮춰서 더 일찍 보정 시작
                    center_correction_threshold = self.center_exit_th * 1.1  # 0.08 * 1.1 = 0.088
                    if abs_cx > center_correction_threshold:
                        # center_x_err가 크면 더 강하게 보정
                        # 가중치 계산: 0.088 이상이면 보정 시작, 0.15 이상이면 최대 가중치
                        center_weight = min(0.5, (abs_cx - center_correction_threshold) / (self.center_enter_th - center_correction_threshold))
                    else:
                        # 작은 오차일 때도 미세하게 보정 (드리프트 방지)
                        center_weight = 0.1 * (abs_cx / center_correction_threshold)  # 최대 0.1 가중치

                    # [UPDATED] 동시에 center가 다시 틀어지면 CENTERING으로 되돌리기 (히스테리시스)
                    if abs_cx > self.center_enter_th:
                        self.get_logger().warn(f"[FSM] FACE_ALIGN center drift (cx={abs_cx:.6f}) -> CENTERING")
                        self.state = DockState.CENTERING
                        self.reset_controllers()
                        self.verify_started = None
                        # [IMPROVED] 회전 방향 감지 상태 유지
                        self.centering_started = now
                        v_cmd, w_cmd = 0.0, 0.0
                    else:
                        # [IMPROVED] center_x_err가 임계값에 가까우면 우선 보정
                        # center_x_err가 center_exit_th의 1.25배 이상이면 center_x_err 보정을 우선시 (임계값 낮춤)
                        center_priority_threshold = self.center_exit_th * 1.25  # 0.08 * 1.25 = 0.10
                        
                        # [IMPROVED] pose_yaw_err가 매우 클 때도 center_x_err 보정을 더 적극적으로
                        # pose_yaw_err가 2.0 rad 이상이면 center_x_err 보정 가중치 증가
                        pose_err_large = abs(pose_err) > 2.0
                        if pose_err_large and abs_cx > self.center_exit_th:
                            # pose_yaw_err가 클 때 center_x_err도 크면 우선 보정 모드
                            center_weight = min(0.7, center_weight * 1.5)  # 가중치 증가
                        
                        if abs_cx > center_priority_threshold:
                            # [CRITICAL] center_x_err가 center_enter_th의 80% 이상이면 pose_yaw_err 제어를 완전히 중단
                            center_critical_threshold = self.center_enter_th * 0.8  # 0.15 * 0.8 = 0.12
                            
                            if abs_cx > center_critical_threshold:
                                # center_x_err만 제어 (pose_yaw_err 제어 완전 중단)
                                # [CRITICAL] raw_w_center는 이미 방향 반전이 적용된 상태
                                # 하지만 로그 분석 결과 회전 방향이 여전히 잘못되었을 수 있으므로
                                # CENTERING과 동일하게 한 번 더 반전
                                center_weight = 1.0
                                max_w_for_center = self.max_w_face * 2.0  # 0.15 → 0.30
                                # CENTERING과 동일: 한 번 더 반전하여 올바른 방향 보장
                                w_cmd = clamp(-raw_w_center, -max_w_for_center, max_w_for_center)
                                self.get_logger().warn(
                                    f"[FACE_ALIGN_MONITOR] Center CRITICAL mode: center_x_err ONLY control, "
                                    f"abs_cx={abs_cx:.6f}, cx={cx:.6f}, max_w={max_w_for_center:.3f}, "
                                    f"raw_w_center={raw_w_center:.6f}, w_cmd={w_cmd:.6f}, "
                                    f"direction_reversed={self.centering_direction_reversed}"
                                )
                            else:
                                # center_x_err 보정을 우선시: center_weight를 높이고 pose_yaw_err 제어를 줄임
                                center_weight = min(0.9, 0.5 + (abs_cx - center_priority_threshold) / (center_critical_threshold - center_priority_threshold) * 0.4)
                                # center_x_err 보정에 더 많은 속도 제한 할당
                                max_w_for_center = self.max_w_face * 2.0  # 일시적으로 속도 제한 증가 (0.15 → 0.30)
                                w_cmd_combined = (1.0 - center_weight) * raw_w_pose + center_weight * raw_w_center
                                w_cmd = clamp(w_cmd_combined, -max_w_for_center, max_w_for_center)
                                self.get_logger().warn(
                                    f"[FACE_ALIGN_MONITOR] Center priority mode: center_weight={center_weight:.3f}, "
                                    f"abs_cx={abs_cx:.6f}, max_w={max_w_for_center:.3f}, pose_err_large={pose_err_large}"
                                )
                        else:
                            # [IMPROVED] pose_yaw_err와 center_x_err를 가중 평균으로 결합
                            # 항상 center_x_err 보정을 포함 (드리프트 방지)
                            w_cmd_combined = (1.0 - center_weight) * raw_w_pose + center_weight * raw_w_center
                            
                            # [IMPROVED] pose_yaw_err가 매우 클 때는 속도 제한을 일시적으로 증가
                            if pose_err_large and abs_cx > self.center_exit_th:
                                max_w_temp = self.max_w_face * 1.5  # 0.15 → 0.225
                                w_cmd = clamp(w_cmd_combined, -max_w_temp, max_w_temp)
                                self.get_logger().info(
                                    f"[FACE_ALIGN_MONITOR] Large pose_err mode: max_w={max_w_temp:.3f}, "
                                    f"center_weight={center_weight:.3f}, abs_cx={abs_cx:.6f}"
                                )
                            else:
                                w_cmd = clamp(w_cmd_combined, -self.max_w_face, self.max_w_face)
                            
                            # 로그는 center_weight가 의미있을 때만 출력
                            if center_weight > 0.05:
                                self.get_logger().info(
                                    f"[FACE_ALIGN_MONITOR] Hybrid control: center_weight={center_weight:.3f}, "
                                    f"raw_w_pose={raw_w_pose:.6f}, raw_w_center={raw_w_center:.6f}, "
                                    f"w_cmd_combined={w_cmd_combined:.6f}"
                                )

                        # [UPDATED] “회전만으로 부족”한 상황을 고려해 아주 짧은 전진을 허용(옵션)
                        # - pose_err가 어느 정도 줄었을 때만 전진(너무 비스듬할 때 전진하면 더 유실될 수 있음)
                        if abs(pose_err) < self.pose_enter_th:
                            v_cmd = 0.01  # 1cm/s: 짧게 전진하며 시야 유지에 도움
                        else:
                            v_cmd = 0.0

                        # [IMPROVED] FACE_ALIGN 상태 모니터링 로그
                        self.get_logger().info(
                            f"[FACE_ALIGN_MONITOR] pose_yaw_err={pose_err:.6f}, center_x_err={cx:.6f}, "
                            f"abs(center_x_err)={abs_cx:.6f}, center_weight={center_weight:.3f}"
                        )
                        self.get_logger().info(
                            f"[FACE_ALIGN_MONITOR] w_cmd={w_cmd:.6f}, v_cmd={v_cmd:.6f}, "
                            f"center_enter_th={self.center_enter_th:.6f}"
                        )

                        # [UPDATED] 조건 만족하면 VERIFY_POSE로
                        if abs(pose_err) <= self.pose_exit_th:
                            self.get_logger().info("[FSM] FACE_ALIGN -> VERIFY_POSE (pose ok)")
                            self.state = DockState.VERIFY_POSE
                            self.verify_started = None  # 시작 시각은 아래에서 설정

            # -------------------------
            # [UPDATED] VERIFY_POSE
            # - “중앙 + 법선”이 잠깐 만족했다고 바로 APPROACH로 가지 않게
            # - 일정 시간 동안 안정적으로 유지되는지 확인
            # -------------------------
            elif self.state == DockState.VERIFY_POSE:
                marker_ok = (self.marker_valid and (self.marker_id in target_ids) and self.marker_is_fresh()
                             and (self.pose_yaw_err is not None) and (self.center_x_err is not None))

                if not marker_ok:
                    self.get_logger().warn("[FSM] VERIFY_POSE lost marker -> SEARCH")
                    self.state = DockState.SEARCH
                    self.verify_started = None
                    v_cmd, w_cmd = 0.0, 0.0
                else:
                    pose_err = float(self.pose_yaw_err)
                    cx = float(self.center_x_err)

                    # 기준 이탈하면 다시 정렬 상태로
                    if abs(cx) > self.center_enter_th:
                        self.get_logger().warn("[FSM] VERIFY_POSE center drift -> CENTERING")
                        self.state = DockState.CENTERING
                        self.verify_started = None
                        v_cmd, w_cmd = 0.0, 0.0
                    elif abs(pose_err) > self.pose_enter_th:
                        self.get_logger().warn("[FSM] VERIFY_POSE pose drift -> FACE_ALIGN")
                        self.state = DockState.FACE_ALIGN
                        self.verify_started = None
                        v_cmd, w_cmd = 0.0, 0.0
                    else:
                        # 조건 유지 시간 체크
                        if self.verify_started is None:
                            self.verify_started = now

                        # VERIFY 동안은 “움직이지 않는 게” 안정적
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

                    # [UPDATED] yaw가 커지면(ENTER threshold보다 크면) 다시 정렬 상태로 복귀
                    if abs(yaw_err) > self.yaw_align_enter:
                        self.get_logger().warn("[FSM] APPROACH yaw too big -> CENTERING")
                        self.state = DockState.CENTERING
                        self.reset_controllers()
                        self.align_lost_since = None
                        self.verify_started = None
                    else:
                        # 거리/각도 제어
                        raw_v = self.pid_dist.step(dist_err, dt, saturated=False)
                        raw_w = self.pid_yaw.step(yaw_err, dt, saturated=False)

                        # 접근 구간에서는 앞으로만 가도록(안전)
                        v_cmd = clamp(raw_v, 0.0, self.max_v)
                        w_cmd = clamp(raw_w, -self.max_w, self.max_w)

                        # FINAL 구간 진입
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

                    # [IMPORTANT] 후진 도킹(reverse)이면 v 방향을 반대로
                    # - reverse=True: 로봇이 뒤로 들어가야 하므로 v_cmd는 음수 방향
                    # - yaw 제어는 기본적으로 동일하게 두되, 실제 후진 시에는 yaw 부호를 반대로 느낄 수 있음
                    #   (현장 기준으로 필요 시 yaw_err = -yaw_err 로 전환하는 옵션 추가 가능)
                    raw_v = self.pid_dist_final.step(dist_err, dt, saturated=False)
                    raw_w = self.pid_yaw.step(yaw_err, dt, saturated=False)

                    v_cmd = clamp(raw_v, -self.max_v_final, self.max_v_final)
                    w_cmd = clamp(raw_w, -self.max_w_final, self.max_w_final)

                    if reverse:
                        v_cmd = -abs(v_cmd)  # 뒤로만 움직이게

                    # 완료 조건(1cm + 1deg)
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

            # 루프 주기 (20Hz 권장)
            # await rclpy.task.Future()  # executor에 양보(아래 sleep 대체)
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