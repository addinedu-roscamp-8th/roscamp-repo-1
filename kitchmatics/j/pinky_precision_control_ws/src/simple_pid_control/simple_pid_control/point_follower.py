import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import math

from pinky_precision_interfaces.msg import Marker2D

# ---------------------------------------------------------
# 1. 직관적인 PID 제어 로직 (분리형)
# ---------------------------------------------------------
class SimplePID:
    def __init__(self, kp, ki, kd, i_limit=0.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.i_limit = i_limit
        self.integral = 0.0
        self.prev_error = 0.0

    def calculate(self, error, dt):
        if dt <= 0: return 0.0

        # [P] 현재의 오차 해결
        p_term = self.kp * error

        # [I] 과거의 누적 오차 해결 (안전장치 포함)
        self.integral += error * dt
        if self.i_limit > 0:
            self.integral = max(-self.i_limit, min(self.i_limit, self.integral))
        i_term = self.ki * self.integral

        # [D] 미래의 오차 변화 예측 (예방)
        d_term = self.kd * (error - self.prev_error) / dt
        self.prev_error = error

        return p_term + i_term + d_term

# ---------------------------------------------------------
# 2. ROS 2 포인트 추종 노드
# ---------------------------------------------------------
class PointFollower(Node):
    def __init__(self):
        super().__init__('point_follower')
        self.get_logger().info("PointFollower node initialized")
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10) #

        # [수정] 실시간 마커 정보를 받기 위한 구독자 추가
        self.marker_sub = self.create_subscription(
            Marker2D, "/precision/marker2d", self.marker_callback, 10
        )

        
        # 실시간으로 업데이트될 마커 좌표
        self.current_x = 0.0
        self.current_z = 0.0
        self.marker_valid = False
        
        # 선속도 제어용 PID (거리 오차 해결용)
        self.v_pid = SimplePID(kp=0.8, ki=0.0, kd=0.0, i_limit=0.2)
        
        # 각속도 제어용 PID (방향 오차 해결용)
        self.w_pid = SimplePID(kp=1.6, ki=0.0, kd=0.1, i_limit=0.2)
        
        self.timer = self.create_timer(0.05, self.control_loop) # 20Hz 주행
        self.last_time = self.get_clock().now()

    def marker_callback(self, msg: Marker2D):
        # [핵심] 센서로부터 들어오는 실시간 좌표를 업데이트
        if msg.valid:
            self.current_x = msg.tx_m # 마커의 실제 x 오프셋
            self.current_z = msg.tz_m # 마커의 실제 z 거리
            self.marker_valid = True
        else:
            self.marker_valid = False

        self.get_logger().info(f"current_x: {self.current_x}, current_z: {self.current_z}")

    def control_loop(self):
        if not self.marker_valid:
            self.stop_robot()
            return

        # 시간 계산
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        self.last_time = now
        if dt <= 0: return

        # 실시간 좌표로 오차 계산
        dist_err = math.sqrt(self.current_x**2 + self.current_z**2)
        # 카메라 x가 오른쪽이므로, 오른쪽으로 가려면 음수 각속도가 필요함
        heading_err = math.atan2(self.current_x, self.current_z)

        self.get_logger().info(f"dist_err: {dist_err}, heading_err: {heading_err}")

        # (2) 도착 판정
        if dist_err < 0.01: # 1cm 이내면 정지
            self.stop_robot()
            self.get_logger().info("목표 지점에 도착했습니다!")
            return

        # (3) 선속도(Linear) 및 각속도(Angular) 독립 제어
        v_raw = self.v_pid.calculate(dist_err, dt)
        w_raw = self.w_pid.calculate(heading_err, dt)

        # (4) 제어 명령 통합 (적응형 속도 제어)
        # 각도가 많이 틀어졌다면(cos 값이 작아짐), 전진 속도를 줄여서 안정한 회전을 유도합니다.
        v_cmd = v_raw * math.cos(heading_err)
        w_cmd = -w_raw

        # (5) 속도 클램핑 (로봇 보호)
        v_cmd = max(0.0, min(0.12, v_cmd))  # 최대 선속도 0.12m/s
        w_cmd = max(-0.6, min(0.6, w_cmd))  # 최대 각속도 0.6rad/s

        self.publish_cmd(v_cmd, w_cmd)

    def publish_cmd(self, v, w):
        msg = Twist()
        msg.linear.x = float(v)
        msg.angular.z = float(w)
        self.cmd_pub.publish(msg)

    def stop_robot(self):
        self.publish_cmd(0.0, 0.0)

def main():
    rclpy.init()
    node = PointFollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.stop_robot()
    finally:
        rclpy.shutdown()

if __name__ == '__main__':
    main()