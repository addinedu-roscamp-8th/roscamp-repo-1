# FMS Node Code Fixes for Domain Bridge Integration

이 문서는 domain bridge 개선사항을 적용하기 위한 FMS Node 코드 수정 방법을 설명합니다.

**파일 경로**: `/fms/fms/fms_node.py`

---

## 1. 토픽 구독 함수 업데이트 (_setup_robot_monitoring)

### 현재 코드 (fms_node.py 249-296)

```python
def _setup_robot_monitoring(self, robot_configs: List[Dict]):
    """
    Setup subscribers for monitoring robot status
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
    Setup subscribers for monitoring robot status

    Namespace-based topic isolation to prevent collisions
    Expected topics (from domain bridge):
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

        # Cross-domain robots will be monitored via domain bridge
        # (topics will be bridged to current domain with namespace)
        if domain_id != current_domain:
            logger.info(f"Robot {robot_id} on DOMAIN_ID={domain_id}, "
                       f"will monitor via domain bridge with namespace /{robot_id}/")
            # Continue to subscribe - domain bridge will bridge with namespace

        # Create robot-specific namespace
        robot_ns = f"/{robot_id}"

        # Subscribe to AMCL pose (localization)
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

        # Subscribe to odometry
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

        # Subscribe to battery voltage
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

        # Subscribe to battery present flag
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
    Handle robot AMCL pose update (localization)

    Args:
        robot_id: Robot ID
        msg: PoseWithCovarianceStamped message from AMCL
    """
    # Register heartbeat for error detection
    self.error_detector.register_heartbeat(robot_id)

    # Extract pose from message
    pose = msg.pose.pose

    # Update fleet controller
    self.fleet_controller.update_robot_pose(robot_id, pose)

    # Update zone manager
    self.zone_manager.update_robot_position(robot_id, pose)

    # Check if robot reached destination
    self._check_navigation_status(robot_id)

    logger.debug(f"Updated {robot_id} pose: x={pose.position.x:.2f}, "
                f"y={pose.position.y:.2f}")
```

### robot_odom_callback (새로운 함수)

```python
def robot_odom_callback(self, robot_id: str, msg: Odometry):
    """
    Handle robot odometry update

    Args:
        robot_id: Robot ID
        msg: Odometry message
    """
    # Register heartbeat
    self.error_detector.register_heartbeat(robot_id)

    # Extract pose
    pose = msg.pose.pose

    # Update fleet controller with odometry
    self.fleet_controller.update_robot_pose(robot_id, pose)

    logger.debug(f"Received odometry for {robot_id}: "
                f"x={pose.position.x:.2f}, y={pose.position.y:.2f}")
```

### 기존 robot_pose_callback 제거 또는 유지

현재 코드에 `robot_pose_callback`이 있다면:

```python
# 기존 코드 (제거 또는 주석 처리)
def robot_pose_callback(self, robot_id: str, msg: Pose):
    """Handle robot pose update - DEPRECATED

    Use robot_amcl_pose_callback instead for localization data.
    This function is kept for backward compatibility.
    """
    # Register heartbeat for error detection
    self.error_detector.register_heartbeat(robot_id)

    # Update fleet controller
    self.fleet_controller.update_robot_pose(robot_id, msg)

    # Update zone manager
    self.zone_manager.update_robot_position(robot_id, msg)

    # Check if robot reached destination
    self._check_navigation_status(robot_id)
```

---

## 3. 초기 포즈 발행자 업데이트 (__init__)

### 현재 코드 (fms_node.py 129-139)

```python
# Initial pose publishers (for same domain only)
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
# Initial pose publishers with namespaces
self.initialpose_pubs = {}
for robot_id, domain_info in self.robot_domains.items():
    # All robots will be available via domain bridge
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

## 4. 네비게이션 클라이언트 업데이트 (__init__)

### 현재 코드 (fms_node.py 113-127)

```python
# Create action client for robots on same domain
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
# Create action clients for all robots (via domain bridge if needed)
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

## 5. 네비게이션 함수 개선 (_navigate_robot)

### 현재 코드 (fms_node.py 760-782)

```python
def _navigate_robot(self, robot_id: str, goal_pose: Pose):
    """
    Send navigation goal to robot

    Args:
        robot_id: Robot ID
        goal_pose: Goal pose
    """
    nav_client = self.nav_clients.get(robot_id)
    if not nav_client:
        logger.error(f"Navigation client not found for robot {robot_id}")
        return

    # Create goal
    goal_msg = NavigateToPose.Goal()
    goal_msg.pose = PoseStamped()
    goal_msg.pose.header.frame_id = 'map'
    goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
    goal_msg.pose.pose = goal_pose

    # Send goal
    nav_client.send_goal_async(goal_msg)
    logger.debug(f"Sent navigation goal to robot {robot_id}")
```

### 수정된 코드

```python
def _navigate_robot(self, robot_id: str, goal_pose: Pose):
    """
    Send navigation goal to robot with error handling

    Args:
        robot_id: Robot ID
        goal_pose: Goal pose (in 'map' frame)
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

    # Create goal message
    goal_msg = NavigateToPose.Goal()
    goal_msg.pose = PoseStamped()
    goal_msg.pose.header.frame_id = 'map'
    goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
    goal_msg.pose.pose = goal_pose

    # Send goal asynchronously with callback
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
    Handle navigation goal response

    Args:
        robot_id: Robot ID
        future: Future object with goal handle
    """
    try:
        goal_handle = future.result()
        if not goal_handle.accepted:
            logger.warning(f"Navigation goal rejected for {robot_id}")
            return

        logger.info(f"Navigation goal accepted for {robot_id}")

        # Subscribe to result
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
    Handle navigation result

    Args:
        robot_id: Robot ID
        future: Future object with result
    """
    try:
        result = future.result()
        # NavigateToPose action returns empty result on success
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
    Set initial pose for a robot's AMCL localization
    """
    publisher = self.initialpose_pubs.get(robot_id)
    if not publisher:
        logger.error(f"Initial pose publisher not found for robot {robot_id}")
        return

    # Create PoseWithCovarianceStamped message
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.header.stamp = self.get_clock().now().to_msg()
    msg.pose.pose = pose

    # Set covariance matrix
    msg.pose.covariance = [
        0.25, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.25, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.06853892326654787
    ]

    # Publish initial pose
    publisher.publish(msg)
    logger.info(f"Set initial pose for {robot_id}: x={pose.position.x:.3f}, y={pose.position.y:.3f}")
```

### 개선 사항 (추가 로깅)

```python
def set_initial_pose(self, robot_id: str, pose: Pose):
    """
    Set initial pose for a robot's AMCL localization

    This publishes a PoseWithCovarianceStamped message to initialize
    the robot's localization filter.

    Args:
        robot_id: Robot ID (e.g., 'pinky1', 'pinky3')
        pose: Pose with position and orientation
    """
    publisher = self.initialpose_pubs.get(robot_id)
    if not publisher:
        logger.error(f"Initial pose publisher not found for robot {robot_id}")
        logger.debug(f"Available publishers: {list(self.initialpose_pubs.keys())}")
        return

    # Create PoseWithCovarianceStamped message
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.header.stamp = self.get_clock().now().to_msg()
    msg.pose.pose = pose

    # Set covariance matrix (standard AMCL initialization)
    msg.pose.covariance = [
        0.25, 0.0, 0.0, 0.0, 0.0, 0.0,      # x uncertainty
        0.0, 0.25, 0.0, 0.0, 0.0, 0.0,      # y uncertainty
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,       # z (unused)
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,       # roll (unused)
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,       # pitch (unused)
        0.0, 0.0, 0.0, 0.0, 0.0, 0.06853892326654787  # theta uncertainty
    ]

    # Publish initial pose
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
Monitor Domain Bridge Communication Status

Usage:
    python3 monitor_domain_bridge.py
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import math
from datetime import datetime


class DomainBridgeMonitor(Node):
    """Monitor domain bridge status and statistics"""

    def __init__(self):
        super().__init__('domain_bridge_monitor')

        self.logger.info("Starting Domain Bridge Monitor...")

        # Statistics
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

        # Create subscribers for monitoring
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

        # Monitoring timer
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
        """Print monitoring statistics"""
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
- [ ] 네비게이션 액션 확인
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
# Terminal 1: Domain Bridge 시작
ros2 run domain_bridge domain_bridge fms/config/domain_bridge.yaml

# Terminal 2: 로봇 토픽 모니터링
python3 fms/scripts/monitor_domain_bridge.py

# Terminal 3: FMS Node 시작
ros2 launch fms_system fms_bringup.launch.xml

# Terminal 4: 토픽 확인
ros2 topic list | grep pinky
ros2 topic hz /pinky1/amcl_pose
ros2 topic hz /pinky3/amcl_pose
```

