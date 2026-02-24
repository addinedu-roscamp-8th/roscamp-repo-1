#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


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
    def __init__(self):
        super().__init__("sandwich_coordinator")

        # publishers (각각 따로!)
        self.pub_a = self.create_publisher(String, "/arm_a/cmd", 10)
        self.pub_b = self.create_publisher(String, "/arm_b/cmd", 10)
        self.pub_verify = self.create_publisher(String, "/verify/cmd", 10)

        # subscribers (각각 따로!)
        self.sub_a = self.create_subscription(String, "/arm_a/status", self._on_a_status, 10)
        self.sub_b = self.create_subscription(String, "/arm_b/status", self._on_b_status, 10)
        self.sub_verify = self.create_subscription(String, "/verify/status", self._on_verify_status, 10)

        # job_id -> (state, kv)
        self.a_status: Dict[str, Tuple[str, Dict[str, str]]] = {}
        self.b_status: Dict[str, Tuple[str, Dict[str, str]]] = {}
        self.v_status: Dict[str, Tuple[str, Dict[str, str]]] = {}

        self.get_logger().info("CoordinatorNode ready.")

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

    def _publish(self, pub, text: str, settle_sec: float = 0.15):
        m = String()
        m.data = text
        pub.publish(m)
        rclpy.spin_once(self, timeout_sec=0.01)
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

            rclpy.spin_once(self, timeout_sec=0.1)

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
            rclpy.spin_once(self, timeout_sec=0.05)

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

    def run_order(self, order: Order) -> bool:
        job_id = uuid.uuid4().hex[:8]
        sauce = (order.sauce or "").strip()

        self.get_logger().info(f"start job={job_id} recipe={order.recipe} sauce='{sauce}' pause_before_last={order.pause_before_last}")

        # sauce가 비어있으면 B 필요 없음(소스 동기화만)
        need_b = 1 if sauce != "" else 0
        # verify는 이번 요구사항에서 사용하므로 구독자 1 기대(verify 노드가 없다면 0으로 내려)
        self.wait_subscribers(timeout_sec=order.discovery_wait_sec, need_a=1, need_b=max(need_b, 1), need_v=1)

        # 1) A START
        self._publish(
            self.pub_a,
            build_msg(job_id, "START", recipe=order.recipe, pause_before_last=str(order.pause_before_last), sauce=sauce),
        )

        # 2) sauce 있으면 B pour flow
        if sauce != "":
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

            self._publish(self.pub_a, build_msg(job_id, "RESUME"))

        # 3) finish A (샌드위치 쌓기 완료)
        ok, msg = self.wait_for(job_id, "A", "DONE", order.timeout_finish_a_sec)
        if not ok:
            self.get_logger().error(f"A finish failed: {msg}")
            self._publish(self.pub_a, build_msg(job_id, "CANCEL"))
            if sauce != "":
                self._publish(self.pub_b, build_msg(job_id, "CANCEL"))
            return False

        # -----------------------------
        # 4) NEW: B가 verify로 운반 + verify 분석 + 결과 따라 분기
        # -----------------------------
        self.get_logger().info(f"A stacked DONE -> B TRANSPORT_TO_VERIFY job={job_id}")
        self._publish(self.pub_b, build_msg(job_id, "TRANSPORT_TO_VERIFY"))

        ok, msg = self.wait_for(job_id, "B", "DONE", order.timeout_transport_verify_sec)
        if not ok:
            self.get_logger().error(f"B transport_to_verify failed: {msg}")
            self._publish(self.pub_b, build_msg(job_id, "CANCEL"))
            return False

        # verify 분석 트리거 (verify 노드가 이 op를 받는 형태로 맞춰라)
        # 예: verify 노드가 "ANALYZE"를 받도록 구현되어 있어야 함.
        self.get_logger().info(f"request VERIFY analyze job={job_id}")
        self._publish(self.pub_verify, build_msg(job_id, "ANALYZE"))

        # verify 결과 대기: OK 또는 DEFECT (너 verify 노드 출력에 맞춰 변경)
        ok_ok, _ = self.wait_for(job_id, "V", "OK", order.timeout_verify_sec)
        if ok_ok:
            self.get_logger().info(f"VERIFY OK -> HANDOFF_PINKY job={job_id}")
            self._publish(self.pub_b, build_msg(job_id, "HANDOFF_PINKY"))
            ok2, msg2 = self.wait_for(job_id, "B", "DONE", order.timeout_handoff_sec)
            if not ok2:
                self.get_logger().error(f"B handoff failed: {msg2}")
                self._publish(self.pub_b, build_msg(job_id, "CANCEL"))
                return False
        else:
            ok_ng, _ = self.wait_for(job_id, "V", "DEFECT", 0.1)  # 이미 timeout 후면 store에 있을 수도 있어서 짧게 한번 더
            if ok_ng:
                self.get_logger().info(f"VERIFY DEFECT -> DISCARD job={job_id}")
            else:
                self.get_logger().warn(f"VERIFY not OK within timeout -> treat as DEFECT job={job_id}")

            self._publish(self.pub_b, build_msg(job_id, "DISCARD"))
            ok2, msg2 = self.wait_for(job_id, "B", "DONE", order.timeout_handoff_sec)
            if not ok2:
                self.get_logger().error(f"B discard failed: {msg2}")
                self._publish(self.pub_b, build_msg(job_id, "CANCEL"))
                return False

        self.get_logger().info(f"job {job_id} DONE (stack + verify + branch)")
        return True


def main():
    rclpy.init()
    node = CoordinatorNode()

    ok = node.run_order(Order(recipe="ham_cheese", sauce="mustard", pause_before_last=1))
    node.get_logger().info(f"exit ok={ok}")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()