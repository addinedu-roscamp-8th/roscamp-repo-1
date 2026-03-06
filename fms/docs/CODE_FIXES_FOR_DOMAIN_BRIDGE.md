# Domain Bridge 통합을 위한 FMS Node 코드 수정 사항

이 문서는 Domain Bridge 개선사항을 적용하기 위한 FMS Node 코드 수정 방법을 설명합니다.

**파일 경로**: `/fms/fms/fms_node.py`

---

## 1. 토픽 구독 함수 업데이트 (_setup_robot_monitoring)

### 현재 코드 (fms_node.py 249-296)

```python
def _setup_robot_monitoring(self, robot_configs: List[Dict]):
    """
    로봇 상태 모니터링을 위한 구독자 설정
    """
    current_domain = int(os.environ.get('ROS_DOMAIN_ID', 0))

    for config in robot_configs:
        if config.get('enabled', True) is False:
            continue
        robot_id = config['robot_id']
        domain_id = config.get('domain_id', 0)

        if domain_id != current_domain:
            logger.warning(f"Robot {robot_id} on DOMAIN_ID={domain_id}, skipping ROS monitoring")
            continue

        # 문제: /pose 토픽 명이 모든 로봇에서 동일
        self.create_subscription(
            Pose,
            '/pose',  # 충돌: 여러 로봇 데이터 섞임
            lambda msg, rid=robot_id: self.robot_pose_callback(rid, msg),
            10
        )

        # 문제: 토픽 이름이 동일
        self.create_subscription(
            Float32,
            '/battery/voltage',  # 충돌
            lambda msg, rid=robot_id: self.robot_battery_voltage_callback(rid, msg),
            10
        )

        self.create_subscription(
            Bool,
            '/battery/present',  # 충돌
            lambda msg, rid=robot_id: self.robot_battery_present_callback(rid, msg),
            10
        )

        logger.info(f"Setup monitoring for robot {robot_id} (DOMAIN_ID={domain_id})")
```

### 수정된 코드

```python
def _setup_robot_monitoring(self, robot_configs: List[Dict]):
    """
    로봇 상태 모니터링을 위한 구독자 설정

    충돌 방지를 위한 네임스페이스 기반 토픽 격리
    예상 토픽 (Domain Bridge 경유):
    - /pinky1/amcl_pose
    - /pinky1/odom
    - /pinky1/battery/voltage
    - /pinky1/battery/present
    """
    current_domain = int(os.environ.get('ROS_DOMAIN_ID', 0))
    logger.info(f"Setting up robot monitoring (current DOMAIN_ID={current_domain})")

    for config in robot_configs:
        if config.get('enabled', True) is False:
            logger.debug(f"Skipping disabled robot {config['robot_id']}")
            continue

        robot_id = config['robot_id']
        domain_id = config.get('domain_id', 0)

        # 크로스 도메인 로봇은 Domain Bridge를 통해 모니터링
        # (토픽이 네임스페이스와 함께 현재 도메인으로 브릿징됨)
        if domain_id != current_domain:
            logger.info(f"Robot {robot_id} on DOMAIN_ID={domain_id}, "
                       f"will monitor via domain bridge with namespace /{robot_id}/")
            # 구독 계속 진행 - Domain Bridge가 네임스페이스를 포함하여 브릿징

        # 로봇별 네임스페이스 생성
        robot_ns = f"/{robot_id}"

        # AMCL 포즈 구독 (로컬라이제이션)
        self.create_subscription(
            PoseWithCovarianceStamped,
            f"{robot_ns}/amcl_pose",
            lambda msg, rid=robot_id: self.robot_amcl_pose_callback(rid, msg),
            qos_profile=QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=10
            )
        )
        logger.debug(f"Subscribed to {robot_ns}/amcl_pose")

        # 오도메트리 구독
        self.create_subscription(
            Odometry,
            f"{robot_ns}/odom",
            lambda msg, rid=robot_id: self.robot_odom_callback(rid, msg),
            qos_profile=QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
                depth: 5
            )
        )
        logger.debug(f"Subscribed to {robot_ns}/odom")

        # 배터리 전압 구독
        self.create_subscription(
            Float32,
            f"{robot_ns}/battery/voltage",
            lambda msg, rid=robot_id: self.robot_battery_voltage_callback(rid, msg),
            qos_profile=QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=10
            )
        )
        logger.debug(f"Subscribed to {robot_ns}/battery/voltage")

        # 배터리 존재 여부 플래그 구독
        self.create_subscription(
            Bool,
            f"{robot_ns}/battery/present",
            lambda msg, rid=robot_id: self.robot_battery_present_callback(rid, msg),
            qos_profile=QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=5
            )
        )
        logger.debug(f"Subscribed to {robot_ns}/battery/present")

        logger.info(f"Setup monitoring for robot {robot_id} "
                   f"(namespace: {robot_ns}, DOMAIN_ID={domain_id})")
```

### 필요한 Import 추가 (fms_node.py 맨 위)

```python
# 기존 import 유지
from geometry_msgs.msg import PoseWithCovarianceStamped, Pose, PoseStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32, Bool

# 새로 추가
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
```

---

## 2. 새로운 콜백 함수 추가

### robot_amcl_pose_callback (새로운 함수)

```python
def robot_amcl_pose_callback(self, robot_id: str, msg: PoseWithCovarianceStamped):
    """
    로봇 AMCL 포즈 업데이트 처리 (로컬라이제이션)

    Args:
        robot_id: 로봇 ID
        msg: AMCL에서 전송된 PoseWithCovarianceStamped 메시지
    """
    # 오류 감지를 위한 하트비트 등록
    self.error_detector.register_heartbeat(robot_id)

    # 메시지에서 포즈 추출
    pose = msg.pose.pose

    # 플릿 컨트롤러 업데이트
    self.fleet_controller.update_robot_pose(robot_id, pose)

    # Zone Manager 업데이트
    self.zone_manager.update_robot_position(robot_id, pose)

    # 로봇이 목적지에 도달했는지 확인
    self._check_navigation_status(robot_id)

    logger.debug(f"Updated {robot_id} pose: x={pose.position.x:.2f}, "
                f"y={pose.position.y:.2f}")
```

### robot_odom_callback (새로운 함수)

```python
def robot_odom_callback(self, robot_id: str, msg: Odometry):
    """
    로봇 오도메트리 업데이트 처리

    Args:
        robot_id: 로봇 ID
        msg: Odometry 메시지
    """
    # 하트비트 등록
    self.error_detector.register_heartbeat(robot_id)

    # 포즈 추출
    pose = msg.pose.pose

    # 오도메트리로 플릿 컨트롤러 업데이트
    self.fleet_controller.update_robot_pose(robot_id, pose)

    logger.debug(f"Received odometry for {robot_id}: "
                f"x={pose.position.x:.2f}, y={pose.position.y:.2f}")
```

### 기존 robot_pose_callback 제거 또는 유지

현재 코드에 `robot_pose_callback`이 있다면:

```python
# 기존 코드 (제거 또는 주석 처리)
def robot_pose_callback(self, robot_id: str, msg: Pose):
    """로봇 포즈 업데이트 처리 - 더 이상 사용되지 않음

    로컬라이제이션 데이터는 robot_amcl_pose_callback을 대신 사용하세요.
    하위 호환성을 위해 이 함수를 유지합니다.
    """
    # 오류 감지를 위한 하트비트 등록
    self.error_detector.register_heartbeat(robot_id)

    # 플릿 컨트롤러 업데이트
    self.fleet_controller.update_robot_pose(robot_id, msg)

    # Zone Manager 업데이트
    self.zone_manager.update_robot_position(robot_id, msg)

    # 로봇이 목적지에 도달했는지 확인
    self._check_navigation_status(robot_id)
```

---

## 3. 초기 포즈 발행자 업데이트 (__init__)

### 현재 코드 (fms_node.py 129-139)

```python
# 초기 포즈 발행자 (같은 도메인만)
self.initialpose_pubs = {}
for robot_id, domain_info in self.robot_domains.items():
    if domain_info['domain_id'] == current_domain:
        topic_name = '/initialpose'  # 토픽 이름 동일 - 문제!
        self.initialpose_pubs[robot_id] = self.create_publisher(
            PoseWithCovarianceStamped,
            topic_name,
            10
        )
        logger.info(f"Created initial pose publisher for {robot_id}: {topic_name}")
```

### 수정된 코드

```python
# 네임스페이스를 포함한 초기 포즈 발행자
self.initialpose_pubs = {}
for robot_id, domain_info in self.robot_domains.items():
    # 모든 로봇이 Domain Bridge를 통해 접근 가능
    robot_ns = f"/{robot_id}"
    topic_name = f"{robot_ns}/initialpose"  # 로봇별 격리된 토픽

    self.initialpose_pubs[robot_id] = self.create_publisher(
        PoseWithCovarianceStamped,
        topic_name,
        qos_profile=QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )
    )
    logger.info(f"Created initial pose publisher for {robot_id}: {topic_name} "
               f"(DOMAIN_ID={domain_info['domain_id']})")
```

---

## 4. 내비게이션 클라이언트 업데이트 (__init__)

### 현재 코드 (fms_node.py 113-127)

```python
# 같은 도메인의 로봇에 대한 액션 클라이언트 생성
for robot_id, domain_info in self.robot_domains.items():
    if domain_info['domain_id'] == current_domain:
        action_name = '/navigate_to_pose'  # 토픽 이름 동일 - 문제!
        self.nav_clients[robot_id] = ActionClient(self, NavigateToPose, action_name)
        logger.info(f"Created navigation client for {robot_id}: {action_name} (DOMAIN_ID={current_domain})")
    else:
        logger.warning(f"Robot {robot_id} on different DOMAIN_ID={domain_info['domain_id']}, needs TCP/bridge")
```

### 수정된 코드

```python
# 모든 로봇에 대한 액션 클라이언트 생성 (필요시 Domain Bridge 경유)
for robot_id, domain_info in self.robot_domains.items():
    robot_ns = f"/{robot_id}"
    action_name = f"{robot_ns}/navigate_to_pose"  # 로봇별 격리된 액션

    self.nav_clients[robot_id] = ActionClient(self, NavigateToPose, action_name)

    if domain_info['domain_id'] == current_domain:
        logger.info(f"Created navigation client for {robot_id}: {action_name} "
                   f"(same DOMAIN_ID={current_domain})")
    else:
        logger.info(f"Created navigation client for {robot_id}: {action_name} "
                   f"(cross-domain via bridge, robot DOMAIN_ID={domain_info['domain_id']})")
```

---

## 5. 내비게이션 함수 개선 (_navigate_robot)

### 현재 코드 (fms_node.py 760-782)

```python
def _navigate_robot(self, robot_id: str, goal_pose: Pose):
    """
    로봇에 내비게이션 목표 전송

    Args:
        robot_id: 로봇 ID
        goal_pose: 목표 포즈
    """
    nav_client = self.nav_clients.get(robot_id)
    if not nav_client:
        logger.error(f"Navigation client not found for robot {robot_id}")
        return

    # 목표 생성
    goal_msg = NavigateToPose.Goal()
    goal_msg.pose = PoseStamped()
    goal_msg.pose.header.frame_id = 'map'
    goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
    goal_msg.pose.pose = goal_pose

    # 목표 전송
    nav_client.send_goal_async(goal_msg)
    logger.debug(f"Sent navigation goal to robot {robot_id}")
```

### 수정된 코드

```python
def _navigate_robot(self, robot_id: str, goal_pose: Pose):
    """
    오류 처리가 포함된 로봇 내비게이션 목표 전송

    Args:
        robot_id: 로봇 ID
        goal_pose: 목표 포즈 ('map' 프레임 기준)
    """
    nav_client = self.nav_clients.get(robot_id)
    if not nav_client:
        logger.error(f"Navigation client not found for robot {robot_id}")
        self.error_detector.register_error(
            RobotError(
                robot_id=robot_id,
                error_type=ErrorType.NAVIGATION_ERROR,
                error_message="Navigation client not available",
                current_pose=None,
                battery_voltage=0.0
            )
        )
        return

    # 목표 메시지 생성
    goal_msg = NavigateToPose.Goal()
    goal_msg.pose = PoseStamped()
    goal_msg.pose.header.frame_id = 'map'
    goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
    goal_msg.pose.pose = goal_pose

    # 콜백과 함께 비동기 목표 전송
    try:
        future = nav_client.send_goal_async(goal_msg)
        future.add_done_callback(
            lambda f: self._nav_goal_response_callback(robot_id, f)
        )
        logger.info(f"Sent navigation goal to {robot_id}: "
                   f"x={goal_pose.position.x:.2f}, y={goal_pose.position.y:.2f}")
    except Exception as e:
        logger.error(f"Failed to send navigation goal to {robot_id}: {e}")
        self.error_detector.register_error(
            RobotError(
                robot_id=robot_id,
                error_type=ErrorType.NAVIGATION_ERROR,
                error_message=f"Failed to send goal: {str(e)}",
                current_pose=None,
                battery_voltage=0.0
            )
        )

def _nav_goal_response_callback(self, robot_id: str, future):
    """
    내비게이션 목표 응답 처리

    Args:
        robot_id: 로봇 ID
        future: 목표 핸들이 포함된 Future 객체
    """
    try:
        goal_handle = future.result()
        if not goal_handle.accepted:
            logger.warning(f"Navigation goal rejected for {robot_id}")
            return

        logger.info(f"Navigation goal accepted for {robot_id}")

        # 결과 구독
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda f: self._nav_result_callback(robot_id, f)
        )
    except Exception as e:
        logger.error(f"Navigation goal response error for {robot_id}: {e}")
        self.error_detector.register_error(
            RobotError(
                robot_id=robot_id,
                error_type=ErrorType.NAVIGATION_ERROR,
                error_message=f"Goal response error: {str(e)}",
                current_pose=None,
                battery_voltage=0.0
            )
        )

def _nav_result_callback(self, robot_id: str, future):
    """
    내비게이션 결과 처리

    Args:
        robot_id: 로봇 ID
        future: 결과가 포함된 Future 객체
    """
    try:
        result = future.result()
        # NavigateToPose 액션은 성공 시 빈 결과를 반환
        logger.info(f"Navigation completed for {robot_id}")
    except Exception as e:
        logger.warning(f"Navigation failed for {robot_id}: {e}")
        self.error_detector.register_error(
            RobotError(
                robot_id=robot_id,
                error_type=ErrorType.NAVIGATION_ERROR,
                error_message=f"Navigation failed: {str(e)}",
                current_pose=None,
                battery_voltage=0.0
            )
        )
```

---

## 6. 초기 포즈 발행 함수 업데이트 (set_initial_pose)

### 현재 코드 (fms_node.py 420-454)

```python
def set_initial_pose(self, robot_id: str, pose: Pose):
    """
    로봇의 AMCL 로컬라이제이션을 위한 초기 포즈 설정
    """
    publisher = self.initialpose_pubs.get(robot_id)
    if not publisher:
        logger.error(f"Initial pose publisher not found for robot {robot_id}")
        return

    # PoseWithCovarianceStamped 메시지 생성
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.header.stamp = self.get_clock().now().to_msg()
    msg.pose.pose = pose

    # 공분산 행렬 설정
    msg.pose.covariance = [
        0.25, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.25, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.06853892326654787
    ]

    # 초기 포즈 발행
    publisher.publish(msg)
    logger.info(f"Set initial pose for {robot_id}: x={pose.position.x:.3f}, y={pose.position.y:.3f}")
```

### 개선 사항 (추가 로깅)

```python
def set_initial_pose(self, robot_id: str, pose: Pose):
    """
    로봇의 AMCL 로컬라이제이션을 위한 초기 포즈 설정

    로봇의 로컬라이제이션 필터를 초기화하기 위해
    PoseWithCovarianceStamped 메시지를 발행합니다.

    Args:
        robot_id: 로봇 ID (예: 'pinky1', 'pinky3')
        pose: 위치와 방향이 포함된 포즈
    """
    publisher = self.initialpose_pubs.get(robot_id)
    if not publisher:
        logger.error(f"Initial pose publisher not found for robot {robot_id}")
        logger.debug(f"Available publishers: {list(self.initialpose_pubs.keys())}")
        return

    # PoseWithCovarianceStamped 메시지 생성
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.header.stamp = self.get_clock().now().to_msg()
    msg.pose.pose = pose

    # 공분산 행렬 설정 (표준 AMCL 초기화)
    msg.pose.covariance = [
        0.25, 0.0, 0.0, 0.0, 0.0, 0.0,      # x 불확실성
        0.0, 0.25, 0.0, 0.0, 0.0, 0.0,      # y 불확실성
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,       # z (미사용)
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,       # roll (미사용)
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,       # pitch (미사용)
        0.0, 0.0, 0.0, 0.0, 0.0, 0.06853892326654787  # theta 불확실성
    ]

    # 초기 포즈 발행
    publisher.publish(msg)

    theta = 2.0 * math.atan2(pose.orientation.z, pose.orientation.w)
    logger.info(f"Published initial pose for {robot_id}: "
               f"pos=({pose.position.x:.3f}, {pose.position.y:.3f}), "
               f"theta={math.degrees(theta):.1f} deg")
```

---

## 7. Domain Bridge 상태 모니터링 도구 (선택사항)

### 새 파일: `/fms/scripts/monitor_domain_bridge.py`

```python
#!/usr/bin/env python3
"""
Domain Bridge 통신 상태 모니터링

사용법:
    python3 monitor_domain_bridge.py
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import math
from datetime import datetime


class DomainBridgeMonitor(Node):
    """Domain Bridge 상태 및 통계 모니터링"""

    def __init__(self):
        super().__init__('domain_bridge_monitor')

        self.logger.info("Starting Domain Bridge Monitor...")

        # 통계
        self.stats = {
            'pinky1_amcl_pose': {'count': 0, 'last_ts': None},
            'pinky1_odom': {'count': 0, 'last_ts': None},
            'pinky1_battery_voltage': {'count': 0, 'last_ts': None},
            'pinky1_battery_present': {'count': 0, 'last_ts': None},
            'pinky3_amcl_pose': {'count': 0, 'last_ts': None},
            'pinky3_odom': {'count': 0, 'last_ts': None},
            'pinky3_battery_voltage': {'count': 0, 'last_ts': None},
            'pinky3_battery_present': {'count': 0, 'last_ts': None},
        }

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=2
        )

        # 모니터링용 구독자 생성
        for robot_id in ['pinky1', 'pinky3']:
            from geometry_msgs.msg import PoseWithCovarianceStamped
            from nav_msgs.msg import Odometry
            from std_msgs.msg import Float32, Bool

            self.create_subscription(
                PoseWithCovarianceStamped,
                f"/{robot_id}/amcl_pose",
                lambda msg, rid=robot_id: self._amcl_callback(rid, msg),
                qos
            )

            self.create_subscription(
                Odometry,
                f"/{robot_id}/odom",
                lambda msg, rid=robot_id: self._odom_callback(rid, msg),
                qos
            )

            self.create_subscription(
                Float32,
                f"/{robot_id}/battery/voltage",
                lambda msg, rid=robot_id: self._batt_vol_callback(rid, msg),
                qos
            )

            self.create_subscription(
                Bool,
                f"/{robot_id}/battery/present",
                lambda msg, rid=robot_id: self._batt_present_callback(rid, msg),
                qos
            )

        # 모니터링 타이머
        self.create_timer(5.0, self._print_statistics)

    def _amcl_callback(self, robot_id, msg):
        self.stats[f'{robot_id}_amcl_pose']['count'] += 1
        self.stats[f'{robot_id}_amcl_pose']['last_ts'] = datetime.now()

    def _odom_callback(self, robot_id, msg):
        self.stats[f'{robot_id}_odom']['count'] += 1
        self.stats[f'{robot_id}_odom']['last_ts'] = datetime.now()

    def _batt_vol_callback(self, robot_id, msg):
        self.stats[f'{robot_id}_battery_voltage']['count'] += 1
        self.stats[f'{robot_id}_battery_voltage']['last_ts'] = datetime.now()

    def _batt_present_callback(self, robot_id, msg):
        self.stats[f'{robot_id}_battery_present']['count'] += 1
        self.stats[f'{robot_id}_battery_present']['last_ts'] = datetime.now()

    def _print_statistics(self):
        """모니터링 통계 출력"""
        now = datetime.now()
        print("\n" + "="*60)
        print(f"Domain Bridge Monitor - {now.strftime('%H:%M:%S')}")
        print("="*60)

        for topic, stat in sorted(self.stats.items()):
            count = stat['count']
            last_ts = stat['last_ts']

            if last_ts:
                age_sec = (now - last_ts).total_seconds()
                status = "OK" if age_sec < 5.0 else "STALE" if age_sec < 60.0 else "DEAD"
                print(f"{topic:30} | Count: {count:5} | Age: {age_sec:6.2f}s | {status}")
            else:
                print(f"{topic:30} | Count: {count:5} | NO DATA")

        print("="*60)


def main():
    rclpy.init()
    monitor = DomainBridgeMonitor()

    try:
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
```

---

## 8. 적용 체크리스트

### 코드 수정 전

- [ ] 현재 fms_node.py 백업
- [ ] domain_bridge_improved.yaml 검토

### 코드 수정 (순서대로)

- [ ] 1. Import 추가 (QoS 관련)
- [ ] 2. _setup_robot_monitoring() 함수 업데이트
- [ ] 3. robot_amcl_pose_callback(), robot_odom_callback() 추가
- [ ] 4. __init__()에서 initialpose_pubs 업데이트
- [ ] 5. __init__()에서 nav_clients 업데이트
- [ ] 6. _navigate_robot() 및 콜백 함수 업데이트
- [ ] 7. set_initial_pose() 개선

### 테스트

- [ ] Python 문법 검사 (pylint, flake8)
- [ ] 로컬에서 FMS Node 시작 확인
- [ ] 로봇 토픽 구독 확인
  ```bash
  ros2 topic echo /pinky1/amcl_pose
  ros2 topic echo /pinky3/amcl_pose
  ```
- [ ] 내비게이션 액션 확인
  ```bash
  ros2 action list
  ```
- [ ] 실제 로봇에서 FMS 제어 테스트

---

## 9. 마이그레이션 명령어

### Step 1: domain_bridge.yaml 백업 및 교체

```bash
cd /home/gw/kitchmatics/roscamp-repo-1

# 백업
cp fms/config/domain_bridge.yaml fms/config/domain_bridge.yaml.old

# 개선된 버전 적용
cp fms/config/domain_bridge_improved.yaml fms/config/domain_bridge.yaml
```

### Step 2: 코드 수정 (위 내용 참고하여 적용)

### Step 3: 테스트 실행

```bash
# 터미널 1: Domain Bridge 시작
ros2 run domain_bridge domain_bridge fms/config/domain_bridge.yaml

# 터미널 2: 로봇 토픽 모니터링
python3 fms/scripts/monitor_domain_bridge.py

# 터미널 3: FMS Node 시작
ros2 launch fms_system fms_bringup.launch.xml

# 터미널 4: 토픽 확인
ros2 topic list | grep pinky
ros2 topic hz /pinky1/amcl_pose
ros2 topic hz /pinky3/amcl_pose
```
