#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
from typing import List
import RPi.GPIO as GPIO

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse

from pymycobot.mycobot import MyCobot

from mycobot_kitchen_msgs.action import MoveToPose  # target_type+target 기반
from mycobot_kitchen_msgs.srv import SetGripper,SetSuction

class ArmDriverNode(Node):
    def __init__(self):
        super().__init__("arm_driver_node")

        # params
        self.declare_parameter("port", "/dev/ttyJETCOBOT")
        self.declare_parameter("baud", 1000000)

        self.declare_parameter("default_speed", 50)
        self.declare_parameter("default_mode", -1)       # coords에서만 의미 있음

        port = self.get_parameter("port").value
        baud = int(self.get_parameter("baud").value)

        self.get_logger().info(f"Connecting MyCobot: port={port}, baud={baud}")
        self.mc = MyCobot(port, baud)

        # suction params
        self.declare_parameter("suction_gpio", 23)
        self.declare_parameter("suction_active_high", False)
        self.declare_parameter("pump_on_delay", 1.0)
        self.declare_parameter("pump_off_delay", 0.5)

        self.suction_gpio = int(self.get_parameter("suction_gpio").value)
        self.suction_active_high = bool(self.get_parameter("suction_active_high").value)
        self.pump_on_delay = float(self.get_parameter("pump_on_delay").value)
        self.pump_off_delay = float(self.get_parameter("pump_off_delay").value)

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.suction_gpio, GPIO.OUT, initial=self._suction_level(False))

        self.create_service(SetSuction, "set_suction", self.on_set_suction)

        # gripper params
        self.declare_parameter("gripper_wait_sec", 1.0)
        self.gripper_wait_sec = float(self.get_parameter("gripper_wait_sec").value)

        self.create_service(SetGripper, "set_gripper", self.on_set_gripper)

        self._as = ActionServer(
            self,
            MoveToPose,
            "move_to_pose",
            execute_callback=self.execute_cb,
            goal_callback=self.goal_cb,
            cancel_callback=self.cancel_cb,
        )

    def _suction_level(self, on: bool) -> int:
        if self.suction_active_high:
            return GPIO.HIGH if on else GPIO.LOW
        return GPIO.LOW if on else GPIO.HIGH

    def on_set_suction(self, req: SetSuction.Request, res: SetSuction.Response):
        try:
            GPIO.output(self.suction_gpio, self._suction_level(bool(req.on)))
            time.sleep(self.pump_on_delay if req.on else self.pump_off_delay)
            res.ok = True
            res.message = "ok"
        except Exception as e:
            res.ok = False
            res.message = f"exception: {e}"
        return res

    def on_set_gripper(self, req: SetGripper.Request, res: SetGripper.Response):
        try:
            self.mc.set_gripper_value(int(req.value), int(req.speed))
            time.sleep(self.gripper_wait_sec)
            res.ok = True
            res.message = "ok"
        except Exception as e:
            res.ok = False
            res.message = f"exception: {e}"
        return res

    def goal_cb(self, goal_request: MoveToPose.Goal):
        # 필요시 범위/속도 제한 등 safety 체크 추가 가능
        # target_type: 0(coords) or 1(angles)
        if int(goal_request.target_type) not in (0, 1):
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def cancel_cb(self, goal_handle):
        # MyCobot는 즉시 stop이 제한적 → best-effort
        return CancelResponse.ACCEPT

    def _send_coords(self, pose: List[float], speed: int, mode: int):
        if mode is None or mode < 0:
            self.mc.send_coords(pose, speed,_async=True)
        else:
            self.mc.send_coords(pose, speed, mode,_async=True)

    def _send_angles(self, angles: List[float], speed: int):
        self.mc.send_angles(angles, speed, _async=True)

    def destroy_node(self):
        try:
            GPIO.cleanup(self.suction_gpio)
        except Exception:
            pass
        super().destroy_node()

    def _wait_motion_done(self, goal_handle, timeout_sec: float = 15.0) -> None:
        """
        MyCobot 명령(_async=True) 이후, is_moving(ALL=0)이 0이 될 때까지 대기.
        - timeout 시 예외 발생
        - cancel 요청 들어오면 goal cancel 처리
        """
        fb = MoveToPose.Feedback()
        t0 = time.time()

        last_fb_t = 0.0
        while True:
            # cancel 우선 처리
            if goal_handle.is_cancel_requested:
                fb.state = "canceled"
                goal_handle.publish_feedback(fb)
                goal_handle.canceled()
                raise RuntimeError("canceled")

            mv = self.mc.is_moving()  # 0=ALL
            if mv == -1:
                raise RuntimeError("is_moving() error data")
            if mv == 0:
                return  # stopped

            # 주기적으로 feedback
            now = time.time()
            if now - last_fb_t > 0.2:
                fb.state = "moving"
                goal_handle.publish_feedback(fb)
                last_fb_t = now

            # timeout
            if now - t0 > timeout_sec:
                raise RuntimeError(f"motion timeout ({timeout_sec}s)")

            time.sleep(0.1)  # 고정대기 X, 폴링 안정화용 최소 딜레이

    def execute_cb(self, goal_handle):
        goal = goal_handle.request

        target_type = int(goal.target_type)
        target = list(goal.target)

        speed = int(goal.speed) if goal.speed > 0 else int(self.get_parameter("default_speed").value)
        mode = int(goal.mode) if goal.mode >= 0 else int(self.get_parameter("default_mode").value)

        fb = MoveToPose.Feedback()
        result = MoveToPose.Result()

        try:
            fb.state = "command_sent"
            goal_handle.publish_feedback(fb)

            if target_type == 0:
                self._send_coords(target, speed, mode)
            elif target_type == 1:
                self._send_angles(target, speed)
            else:
                raise RuntimeError(f"invalid target_type: {target_type}")

            fb.state = "waiting_done"
            goal_handle.publish_feedback(fb)
            self._wait_motion_done(goal_handle, timeout_sec=15.0)

            result.success = True
            result.message = "ok"
            goal_handle.succeed()
            return result

        except Exception as e:

            if str(e) == "canceled":
                result.success = False
                result.message = "canceled"
                return result

            result.success = False
            result.message = f"exception: {e}"
            goal_handle.abort()
            return result



def main():
    rclpy.init()
    node = ArmDriverNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()