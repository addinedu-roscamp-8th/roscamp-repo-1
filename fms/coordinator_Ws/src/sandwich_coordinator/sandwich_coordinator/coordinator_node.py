#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import uuid
import threading
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from queue import Queue

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_msgs.msg import String
from fleet_interfaces.msg import CookingOrder, LoadingComplete, PickupArrival
from builtin_interfaces.msg import Time


def parse_kv(parts):
    d = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def parse_msg(text: str) -> Tuple[Optional[str], Optional[str], Dict[str, str]]:
    parts = [p.strip() for p in str(text).split("|") if p.strip() != ""]
    if len(parts) < 2:
        return None, None, {}
    job_id = parts[0]
    state = parts[1]
    kv = parse_kv(parts[2:])
    return job_id, state, kv


def build_msg(job_id: str, op: str, **kv) -> str:
    s = f"{job_id}|{op}"
    for k, v in kv.items():
        s += f"|{k}={v}"
    return s


@dataclass
class Order:
    recipe: str
    sauce: str
    pause_before_last: int = 1
    timeout_prepare_sec: float = 40.0
    timeout_wait_a_sec: float = 120.0
    timeout_pour_sec: float = 120.0
    timeout_finish_a_sec: float = 180.0

    # verify flow
    timeout_transport_verify_sec: float = 120.0
    timeout_verify_sec: float = 30.0
    timeout_handoff_sec: float = 120.0

    discovery_wait_sec: float = 8.0  # 구독자 매칭 대기


class CoordinatorNode(Node):
    """
    Sandwich Coordinator Node

    Receives cooking orders from FMS and orchestrates robot arms to prepare sandwiches.
    Publishes LoadingComplete when food is ready and loaded onto the serving robot.
    """

    # Menu ID to recipe mapping
    MENU_RECIPES = {
        'M001': 'ham_cheese',      # 햄치즈샌드위치
        'M002': 'mushroom',        # 머쉬룸샌드위치
        'M003': 'all_in_one',      # 올인원샌드위치
    }

    def __init__(self):
        super().__init__("sandwich_coordinator")

        # publishers (각각 따로!)
        self.pub_a = self.create_publisher(String, "/arm_a/cmd", 10)
        self.pub_b = self.create_publisher(String, "/arm_b/cmd", 10)
        self.pub_verify = self.create_publisher(String, "/verify/cmd", 10)

        # LoadingComplete publisher - notify FMS when food is loaded
        self.loading_complete_pub = self.create_publisher(
            LoadingComplete,
            '/cooking/loading_complete',
            10
        )

        # subscribers (각각 따로!)
        self.sub_a = self.create_subscription(String, "/arm_a/status", self._on_a_status, 10)
        self.sub_b = self.create_subscription(String, "/arm_b/status", self._on_b_status, 10)
        self.sub_verify = self.create_subscription(String, "/verify/status", self._on_verify_status, 10)

        # CookingOrder subscriber - receive orders from FMS
        # Use explicit QoS to ensure compatibility with FMS publisher
        cooking_order_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.cooking_order_sub = self.create_subscription(
            CookingOrder,
            '/cooking/order',
            self._on_cooking_order,
            cooking_order_qos
        )
        self.get_logger().info("Subscribed to /cooking/order with RELIABLE QoS")

        # PickupArrival subscriber - receive pinky arrival notifications from FMS
        self.pickup_arrival_sub = self.create_subscription(
            PickupArrival,
            '/fms/pickup_arrival',
            self._on_pickup_arrival,
            10
        )

        # job_id -> (state, kv)
        self.a_status: Dict[str, Tuple[str, Dict[str, str]]] = {}
        self.b_status: Dict[str, Tuple[str, Dict[str, str]]] = {}
        self.v_status: Dict[str, Tuple[str, Dict[str, str]]] = {}

        # Pinky arrival tracking: order_id -> bool (arrived or not)
        self.pinky_at_pickup: Dict[str, bool] = {}
        self.pinky_arrival_lock = threading.Lock()
        self.pinky_arrival_cv = threading.Condition(self.pinky_arrival_lock)

        # Order processing queue and thread
        self.order_queue: Queue = Queue()
        self.processing_thread = threading.Thread(target=self._order_processing_loop, daemon=True)
        self.processing_thread.start()

        self.get_logger().info("CoordinatorNode ready. Listening for orders on /cooking/order")

        # Send RESET to all arms on startup (one-shot timer after brief delay for publisher setup)
        self._startup_reset_timer = self.create_timer(2.0, self._send_startup_reset)

    def _send_startup_reset(self):
        """Send RESET commands to all robot arms on coordinator startup"""
        # Cancel timer so it only fires once
        self._startup_reset_timer.cancel()

        reset_job_id = "startup_reset"
        reset_msg = build_msg(reset_job_id, "RESET")

        self.get_logger().info("========== STARTUP RESET ==========")
        self.get_logger().info(f"Sending RESET to all arms: {reset_msg}")

        # Send RESET to all arms
        self._publish(self.pub_a, reset_msg)
        self._publish(self.pub_b, reset_msg)
        self._publish(self.pub_verify, reset_msg)

        self.get_logger().info("RESET commands sent to arm_a, arm_b, verify")
        self.get_logger().info("=====================================")

    def _on_cooking_order(self, msg: CookingOrder):
        """
        Handle incoming cooking order from FMS

        Args:
            msg: CookingOrder message with order_id, menu_id, sauce_type, assigned_robot_id
        """
        self.get_logger().info(
            f"Received cooking order: order_id={msg.order_id}, "
            f"menu_id={msg.menu_id}, sauce={msg.sauce_type}, robot={msg.assigned_robot_id}"
        )

        # Map menu_id to recipe
        recipe = self.MENU_RECIPES.get(msg.menu_id, 'ham_cheese')

        # Create Order object
        order = Order(
            recipe=recipe,
            sauce=msg.sauce_type if msg.sauce_type else '',
            pause_before_last=1
        )

        # Queue for processing (with metadata)
        self.order_queue.put({
            'order': order,
            'order_id': msg.order_id,
            'robot_id': msg.assigned_robot_id,
            'menu_id': msg.menu_id,
            'quantity': msg.quantity
        })

    def _order_processing_loop(self):
        """
        Background thread to process orders sequentially
        """
        while rclpy.ok():
            try:
                order_data = self.order_queue.get(timeout=1.0)
                self._process_order(order_data)
            except Exception:
                # Queue empty timeout, continue
                pass

    def _process_order(self, order_data: dict):
        """
        Process a single order

        Args:
            order_data: Dictionary with order, order_id, robot_id, etc.
        """
        order = order_data['order']
        order_id = order_data['order_id']
        robot_id = order_data['robot_id']
        quantity = order_data.get('quantity', 1)

        self.get_logger().info(f"Processing order {order_id} for robot {robot_id}")

        # Process each quantity
        success = True
        for i in range(quantity):
            if quantity > 1:
                self.get_logger().info(f"Making sandwich {i+1}/{quantity} for order {order_id}")

            ok = self.run_order(order, order_id)
            if not ok:
                self.get_logger().error(f"Failed to make sandwich for order {order_id}")
                success = False
                break

        # Publish LoadingComplete
        self._publish_loading_complete(order_id, robot_id, success)

        # Cleanup pinky arrival tracking to prevent memory leak
        with self.pinky_arrival_cv:
            self.pinky_at_pickup.pop(order_id, None)

    def _publish_loading_complete(self, order_id: str, robot_id: str, success: bool):
        """
        Publish LoadingComplete message to notify FMS

        Args:
            order_id: Order ID
            robot_id: Serving robot ID that will deliver the food
            success: Whether food was successfully loaded
        """
        msg = LoadingComplete()
        msg.order_id = order_id
        msg.robot_id = robot_id
        msg.success = success
        msg.message = "Food loaded successfully" if success else "Failed to prepare food"

        # Set timestamp
        now = self.get_clock().now()
        msg.completed_at = now.to_msg()

        self.loading_complete_pub.publish(msg)
        self.get_logger().info(
            f"Published LoadingComplete: order={order_id}, robot={robot_id}, success={success}"
        )

    def _on_a_status(self, msg: String):
        job_id, state, kv = parse_msg(msg.data)
        if job_id and state:
            self.a_status[job_id] = (state, kv)

    def _on_b_status(self, msg: String):
        job_id, state, kv = parse_msg(msg.data)
        if job_id and state:
            self.b_status[job_id] = (state, kv)

    def _on_verify_status(self, msg: String):
        job_id, state, kv = parse_msg(msg.data)
        if job_id and state:
            self.v_status[job_id] = (state, kv)

    def _on_pickup_arrival(self, msg: PickupArrival):
        """
        Handle pinky arrival notification at pickup spot

        Args:
            msg: PickupArrival message with robot_id, order_id, current_pose, arrived_at
        """
        self.get_logger().info(
            f"Pinky arrived at pickup: robot={msg.robot_id}, order={msg.order_id}"
        )

        with self.pinky_arrival_cv:
            self.pinky_at_pickup[msg.order_id] = True
            self.pinky_arrival_cv.notify_all()  # Wake up waiting threads

    def _publish(self, pub, text: str, settle_sec: float = 0.15):
        m = String()
        m.data = text
        pub.publish(m)
        # Note: spin_once removed - executor handles callbacks in production mode
        time.sleep(float(settle_sec))

    def wait_subscribers(self, timeout_sec: float = 8.0, need_a: int = 1, need_b: int = 1, need_v: int = 0) -> bool:
        t0 = time.time()
        last_log = 0.0
        while rclpy.ok() and (time.time() - t0) < float(timeout_sec):
            a = self.pub_a.get_subscription_count()
            b = self.pub_b.get_subscription_count()
            v = self.pub_verify.get_subscription_count()

            now = time.time()
            if now - last_log > 1.0:
                self.get_logger().info(f"waiting subscribers... A={a} B={b} V={v} (need A>={need_a} B>={need_b} V>={need_v})")
                last_log = now

            if a >= int(need_a) and b >= int(need_b) and v >= int(need_v):
                self.get_logger().info(f"subscribers ready: A={a} B={b} V={v}")
                return True

            time.sleep(0.1)  # Wait without spin_once - executor handles callbacks

        self.get_logger().warn(
            f"subscribers NOT ready (timeout): "
            f"A={self.pub_a.get_subscription_count()} B={self.pub_b.get_subscription_count()} V={self.pub_verify.get_subscription_count()}"
        )
        return False

    def wait_for(self, job_id: str, who: str, target_state: str, timeout_sec: float) -> Tuple[bool, str]:
        """
        who: "A" | "B" | "V"
        """
        t0 = time.time()
        while (time.time() - t0) < float(timeout_sec) and rclpy.ok():
            time.sleep(0.05)  # Wait without spin_once - executor handles callbacks

            if who == "A":
                store = self.a_status
            elif who == "B":
                store = self.b_status
            else:
                store = self.v_status

            if job_id in store:
                state, kv = store[job_id]
                if state == "FAIL":
                    return False, f"{who}_FAIL:{kv.get('reason','')}"
                if state == target_state:
                    return True, "ok"

        return False, "timeout"

    def wait_for_pinky_arrival(self, order_id: str, timeout_sec: float = 120.0) -> bool:
        """
        Wait for pinky to arrive at pickup spot before handoff

        Args:
            order_id: Order ID to wait for
            timeout_sec: Maximum time to wait

        Returns:
            True if pinky arrived, False if timeout
        """
        self.get_logger().info(f"Waiting for pinky arrival for order {order_id} (timeout={timeout_sec}s)")

        with self.pinky_arrival_cv:
            # Check if already arrived
            if self.pinky_at_pickup.get(order_id, False):
                self.get_logger().info(f"Pinky already at pickup for order {order_id}")
                return True

            # Wait for arrival with timeout
            start_time = time.time()
            while rclpy.ok():
                remaining = timeout_sec - (time.time() - start_time)
                if remaining <= 0:
                    self.get_logger().warn(f"Timeout waiting for pinky arrival: order={order_id}")
                    return False

                if self.pinky_at_pickup.get(order_id, False):
                    self.get_logger().info(f"Pinky arrived for order {order_id}")
                    return True

                # Wait for notification or timeout
                self.pinky_arrival_cv.wait(timeout=min(remaining, 1.0))

        return False

    def clear_previous_jobs(self, job_id: str, max_retries: int = 3) -> bool:
        """
        이전 작업 상태를 클리어하기 위해 RESET 명령을 전송합니다.
        로봇팔이 busy 상태일 때 강제로 리셋합니다.

        Args:
            job_id: 새 작업 ID (RESET 응답 확인용)
            max_retries: 최대 재시도 횟수

        Returns:
            True if reset successful, False otherwise
        """
        for attempt in range(max_retries):
            self.get_logger().info(f"Attempt {attempt + 1}/{max_retries}: Clearing previous jobs for job {job_id}")

            # Clear status stores for this job_id
            self.a_status.pop(job_id, None)
            self.b_status.pop(job_id, None)
            self.v_status.pop(job_id, None)

            # Send RESET to both arms
            self._publish(self.pub_a, build_msg(job_id, "RESET"))
            self._publish(self.pub_b, build_msg(job_id, "RESET"))

            # Wait for RESET_OK from both (short timeout)
            ok_a, msg_a = self.wait_for(job_id, "A", "RESET_OK", timeout_sec=3.0)
            ok_b, msg_b = self.wait_for(job_id, "B", "RESET_OK", timeout_sec=3.0)

            if ok_a and ok_b:
                self.get_logger().info(f"Successfully cleared previous jobs: A={ok_a}, B={ok_b}")
                # Clear status again after RESET_OK
                self.a_status.pop(job_id, None)
                self.b_status.pop(job_id, None)
                return True

            # Check if busy error occurred
            if "busy" in msg_a.lower() or "busy" in msg_b.lower():
                self.get_logger().warn(f"Sync failed due to busy (A={msg_a}, B={msg_b}), retrying...")
                time.sleep(0.3)
                continue
            else:
                # Timeout but no busy error - arms might be ready
                self.get_logger().info(f"RESET response timeout but no busy error - proceeding (A={msg_a}, B={msg_b})")
                return True

        self.get_logger().error(f"Failed after {max_retries} retries due to busy errors")
        return False

    def run_order(self, order: Order, order_id: Optional[str] = None) -> bool:
        job_id = uuid.uuid4().hex[:8]
        sauce = (order.sauce or "").strip()

        self.get_logger().info(f"start job={job_id} recipe={order.recipe} sauce='{sauce}' pause_before_last={order.pause_before_last} order_id={order_id}")

        # Clear any previous stuck jobs before starting
        if not self.clear_previous_jobs(job_id):
            self.get_logger().error(f"Failed to clear previous jobs - cannot start new order")
            return False

        # sauce가 비어있으면 B 필요 없음(소스 동기화만)
        need_b = 1 if sauce != "" else 0
        # verify는 이번 요구사항에서 사용하므로 구독자 1 기대(verify 노드가 없다면 0으로 내려)
        self.wait_subscribers(timeout_sec=order.discovery_wait_sec, need_a=1, need_b=max(need_b, 1), need_v=1)

        # 1) A START
        self.get_logger().info(f"[STEP 1] Sending START to A: recipe={order.recipe}, sauce={sauce}")
        self._publish(
            self.pub_a,
            build_msg(job_id, "START", recipe=order.recipe, pause_before_last=str(order.pause_before_last), sauce=sauce),
        )

        # 2) sauce 있으면 B pour flow
        if sauce != "":
            self.get_logger().info(f"[STEP 2] Sauce flow starting: sauce={sauce}")
            self._publish(self.pub_b, build_msg(job_id, "PREPARE", sauce=sauce))

            ok_a, msg_a2 = self.wait_for(job_id, "A", "WAIT_FOR_SAUCE", order.timeout_wait_a_sec)
            ok_b, msg_b2 = self.wait_for(job_id, "B", "READY_TO_POUR", order.timeout_prepare_sec)
            if not ok_a or not ok_b:
                self.get_logger().error(f"sync failed A={ok_a}({msg_a2}) B={ok_b}({msg_b2})")
                self._publish(self.pub_a, build_msg(job_id, "CANCEL"))
                self._publish(self.pub_b, build_msg(job_id, "CANCEL"))
                return False

            self._publish(self.pub_b, build_msg(job_id, "POUR", sauce=sauce))
            ok, msg = self.wait_for(job_id, "B", "DONE", order.timeout_pour_sec)
            if not ok:
                self.get_logger().error(f"B pour failed: {msg}")
                self._publish(self.pub_a, build_msg(job_id, "CANCEL"))
                self._publish(self.pub_b, build_msg(job_id, "CANCEL"))
                return False

            self.get_logger().info(f"[STEP 2.5] B DONE, sending RESUME to A")
            self._publish(self.pub_a, build_msg(job_id, "RESUME"))

        # 3) wait A FOOD_READY (샌드위치 쌓기 완료, refill은 별도로 진행)
        self.get_logger().info(f"[STEP 3] Waiting for A FOOD_READY (timeout={order.timeout_finish_a_sec}s)")
        # ✅ Changed: Wait for FOOD_READY instead of DONE so B can start immediately
        ok, msg = self.wait_for(job_id, "A", "FOOD_READY", order.timeout_finish_a_sec)
        if not ok:
            self.get_logger().error(f"A FOOD_READY failed: {msg}")
            self._publish(self.pub_a, build_msg(job_id, "CANCEL"))
            if sauce != "":
                self._publish(self.pub_b, build_msg(job_id, "CANCEL"))
            return False

        # -----------------------------
        # 4) NEW: B가 verify로 운반 + verify 분석 + 결과 따라 분기
        # ✅ B starts immediately after A's FOOD_READY (A can refill in parallel)
        # -----------------------------
        self.get_logger().info(f"[STEP 4] A FOOD_READY received! Now sending TRANSPORT_TO_VERIFY to verify node")
        self.get_logger().info(f"A FOOD_READY -> B TRANSPORT_TO_VERIFY job={job_id}")
        self._publish(self.pub_verify, build_msg(job_id, "TRANSPORT_TO_VERIFY", sauce=sauce if sauce else "none"))

        # ✅ Fixed: Use "V" (verify/status) instead of "B" (arm_b/status)
        ok, msg = self.wait_for(job_id, "V", "DONE", order.timeout_transport_verify_sec)
        if not ok:
            self.get_logger().error(f"V transport_to_verify failed: {msg}")
            self._publish(self.pub_verify, build_msg(job_id, "CANCEL"))
            return False

        # verify 분석 트리거 (verify 노드가 이 op를 받는 형태로 맞춰라)
        # 예: verify 노드가 "ANALYZE"를 받도록 구현되어 있어야 함.
        self.get_logger().info(f"request VERIFY analyze job={job_id}")
        self._publish(self.pub_verify, build_msg(job_id, "ANALYZE"))

        # verify 결과 대기: OK 또는 DEFECT (너 verify 노드 출력에 맞춰 변경)
        ok_ok, _ = self.wait_for(job_id, "V", "OK", order.timeout_verify_sec)
        if ok_ok:
            self.get_logger().info(f"VERIFY OK -> waiting for pinky arrival job={job_id}")

            # Wait for pinky arrival before handoff (only in production mode with order_id)
            if order_id:
                pinky_arrived = self.wait_for_pinky_arrival(order_id, timeout_sec=order.timeout_handoff_sec)
                if not pinky_arrived:
                    self.get_logger().error(f"Pinky did not arrive in time for order {order_id}")
                    self._publish(self.pub_b, build_msg(job_id, "CANCEL"))
                    return False
            else:
                self.get_logger().info(f"Test mode: skipping pinky arrival check for job={job_id}")

            self.get_logger().info(f"Pinky ready -> HANDOFF_PINKY job={job_id}")
            self._publish(self.pub_verify, build_msg(job_id, "HANDOFF_PINKY"))
            # ✅ Fixed: Use "V" (verify/status) instead of "B" (arm_b/status)
            ok2, msg2 = self.wait_for(job_id, "V", "DONE", order.timeout_handoff_sec)
            if not ok2:
                self.get_logger().error(f"V handoff failed: {msg2}")
                self._publish(self.pub_verify, build_msg(job_id, "CANCEL"))
                return False
        else:
            ok_ng, _ = self.wait_for(job_id, "V", "DEFECT", 0.1)  # 이미 timeout 후면 store에 있을 수도 있어서 짧게 한번 더
            if ok_ng:
                self.get_logger().info(f"VERIFY DEFECT -> DISCARD job={job_id}")
            else:
                self.get_logger().warn(f"VERIFY not OK within timeout -> treat as DEFECT job={job_id}")

            self._publish(self.pub_verify, build_msg(job_id, "DISCARD"))
            # ✅ Fixed: Use "V" (verify/status) instead of "B" (arm_b/status)
            ok2, msg2 = self.wait_for(job_id, "V", "DONE", order.timeout_handoff_sec)
            if not ok2:
                self.get_logger().error(f"V discard failed: {msg2}")
                self._publish(self.pub_verify, build_msg(job_id, "CANCEL"))
                return False

        self.get_logger().info(f"job {job_id} DONE (stack + verify + branch)")
        return True


def main():
    """
    Entry point for Sandwich Coordinator Node

    Supports two modes:
    - test_mode=True (default): Run hardcoded test order for robot arm team debugging
    - test_mode=False: Listen for CookingOrder messages from FMS (production mode)

    Usage:
        # Test mode (robot arm team debugging) - default behavior
        ros2 launch sandwich_coordinator coordinator_all.launch.py

        # Production mode (FMS integration)
        ros2 launch sandwich_coordinator coordinator_all.launch.py test_mode:=false
    """
    rclpy.init()
    node = CoordinatorNode()

    # Declare and get test_mode parameter (default: True for backward compatibility)
    node.declare_parameter('test_mode', True)
    node.declare_parameter('test_recipe', 'bread')
    node.declare_parameter('test_sauce', 'mustard')
    node.declare_parameter('test_pause_before_last', 1)

    # Get parameter values
    test_mode_raw = node.get_parameter('test_mode').value
    test_recipe = node.get_parameter('test_recipe').value
    test_sauce = node.get_parameter('test_sauce').value
    test_pause = node.get_parameter('test_pause_before_last').value

    # Convert test_mode to boolean (ROS2 launch passes strings like 'true'/'false')
    if isinstance(test_mode_raw, bool):
        test_mode = test_mode_raw
    elif isinstance(test_mode_raw, str):
        test_mode = test_mode_raw.lower() in ('true', '1', 'yes')
    else:
        test_mode = bool(test_mode_raw)

    node.get_logger().info(f"test_mode_raw={test_mode_raw} (type={type(test_mode_raw).__name__}) → test_mode={test_mode}")

    if test_mode:
        # ===== TEST MODE (기존 로봇팔 팀 테스트 방식) =====
        node.get_logger().info("=" * 50)
        node.get_logger().info("TEST MODE: Running hardcoded order")
        node.get_logger().info(f"  recipe: {test_recipe}")
        node.get_logger().info(f"  sauce: {test_sauce}")
        node.get_logger().info(f"  pause_before_last: {test_pause}")
        node.get_logger().info("  NOTE: Pinky arrival check will be skipped in test mode")
        node.get_logger().info("=" * 50)

        ok = node.run_order(
            Order(
                recipe=str(test_recipe),
                sauce=str(test_sauce),
                pause_before_last=int(test_pause)
            ),
            order_id=None  # No order_id in test mode - skips pinky arrival check
        )
        node.get_logger().info(f"Test order result: ok={ok}")

        node.destroy_node()
        rclpy.shutdown()
    else:
        # ===== PRODUCTION MODE (FMS 연동) =====
        node.get_logger().info("=" * 50)
        node.get_logger().info("PRODUCTION MODE: Waiting for FMS orders...")
        node.get_logger().info("Listening on /cooking/order topic")
        node.get_logger().info("Using MultiThreadedExecutor for concurrent callback processing")
        node.get_logger().info("=" * 50)

        # Use MultiThreadedExecutor to allow concurrent callback processing
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(node)

        try:
            executor.spin()
        except KeyboardInterrupt:
            node.get_logger().info("Shutting down Sandwich Coordinator...")
        finally:
            executor.shutdown()
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()