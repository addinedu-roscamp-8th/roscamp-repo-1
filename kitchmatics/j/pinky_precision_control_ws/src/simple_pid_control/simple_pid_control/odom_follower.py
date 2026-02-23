import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import math

# 로직을 단순화한 PID 클래스
class SimplePID:
    def __init__(self, kp, ki, kd, i_limit=0.0):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.i_limit, self.integral, self.prev_error = i_limit, 0.0, 0.0

    def calculate(self, error, dt):
        if dt <= 0: return 0.0
        p_term = self.kp * error
        self.integral += error * dt
        if self.i_limit > 0:
            self.integral = max(-self.i_limit, min(self.i_limit, self.integral))
        i_term = self.ki * self.integral
        d_term = self.kd * (error - self.prev_error) / dt
        self.prev_error = error
        return p_term + i_term + d_term

class OdomFollower(Node):
    def __init__(self):
        super().__init__('odom_follower')
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        # 로봇의 현재 위치(엔코더/IMU 통합 데이터) 구독
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        
        # 가상의 도착 목표 지점 (로봇 시작 위치 기준) - 파라미터에서 읽기
        self.declare_parameter('goal_x', 1.0)
        self.declare_parameter('goal_y', 0.5)
        self.goal_x = self.get_parameter('goal_x').get_parameter_value().double_value
        self.goal_y = self.get_parameter('goal_y').get_parameter_value().double_value
        
        self.get_logger().info(f"Goal position set to: x={self.goal_x}, y={self.goal_y}") 
        
        self.v_pid = SimplePID(0.5, 0.0, 0.0)
        self.w_pid = SimplePID(1.2, 0.0, 0.1)
        self.last_time = self.get_clock().now()

    def odom_cb(self, msg):
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        self.last_time = now
        if dt <= 0: return

        # 1. 현재 로봇 위치 및 각도 추출 (Quaternion -> Yaw 변환)
        curr_x = msg.pose.pose.position.x
        curr_y = msg.pose.pose.position.y
        # 단순화를 위해 각도 변환 생략 (로봇이 보는 방향)
        
        # 2. 목표까지의 오차 계산 (상대 좌표 변환 필요)
        # 여기서는 로봇 중심 기준 가상의 상대 좌표(dx, dy)를 구합니다.
        dx = self.goal_x - curr_x
        dy = self.goal_y - curr_y
        
        dist_err = math.sqrt(dx**2 + dy**2)
        # 로봇이 현재 바라보는 각도를 고려한 heading_err 계산이 핵심
        heading_err = math.atan2(dy, dx) 

        # 3. PID 제어 및 속도 명령 생성
        v_raw = self.v_pid.calculate(dist_err, dt)
        w_raw = self.w_pid.calculate(heading_err, dt)

        # 적응형 속도 제어 적용
        v_cmd = v_raw * math.cos(heading_err)
        w_cmd = w_raw

        # 4. 발행
        cmd = Twist()
        cmd.linear.x = float(max(0.0, min(0.2, v_cmd)))
        cmd.angular.z = float(max(-0.5, min(0.5, w_cmd)))
        self.cmd_pub.publish(cmd)

        if dist_err < 0.01:
            self.get_logger().info("가상 목표 지점 도착!")
            self.cmd_pub.publish(Twist()) # 정지

def main():
    rclpy.init()
    rclpy.spin(OdomFollower())
    rclpy.shutdown()