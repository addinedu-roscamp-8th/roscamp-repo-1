# Domain Bridge 설정 검토 (ROS2 다중 로봇 통신)

**작성일**: 2026-02-25
**검토 대상**: `/fms/config/domain_bridge.yaml`
**환경**: Main PC (DOMAIN_ID=0) ↔ pinky1 (DOMAIN_ID=11), pinky3 (DOMAIN_ID=13)

---

## 1. 토픽 네이밍 충돌 문제 (CRITICAL)

### 문제 분석

현재 설정에서는 **모든 로봇이 동일한 토픽명** 사용:

```yaml
# pinky1 (DOMAIN_ID=11)
/amcl_pose, /odom, /scan, /battery/voltage, /battery/present

# pinky3 (DOMAIN_ID=13) - 동일한 토픽명
/amcl_pose, /odom, /scan, /battery/voltage, /battery/present
```

### 발생 가능한 문제

Main PC의 FMS Node가 구독할 때 두 로봇의 토픽이 섞임:

```python
# fms_node.py line 273-293 (현재 코드)
self.create_subscription(
    Pose,
    '/pose',  # 토픽명이 동일함
    lambda msg, rid=robot_id: self.robot_pose_callback(rid, msg),
    10
)
```

**결과**:
- pinky1 데이터가 pinky3 상태 변수에 덮어써짐
- 위치 추정 혼동 → 잘못된 로봇 제어
- 배터리 상태 오류

### 권장 해결방안

#### 방식 1: Namespace 기반 (권장)
각 로봇을 namespace로 격리:

```yaml
# Namespace를 통해 토픽 격리
- from_domain: 11
  to_domain: 0
  topics:
    /pinky1/amcl_pose:              # 로봇별 namespace
      type: geometry_msgs/msg/PoseWithCovarianceStamped
    /pinky1/odom:
      type: nav_msgs/msg/Odometry
    /pinky1/battery/voltage:
      type: std_msgs/msg/Float32
    /pinky1/battery/present:
      type: std_msgs/msg/Bool

- from_domain: 13
  to_domain: 0
  topics:
    /pinky3/amcl_pose:              # 다른 namespace
      type: geometry_msgs/msg/PoseWithCovarianceStamped
    /pinky3/odom:
      type: nav_msgs/msg/Odometry
    /pinky3/battery/voltage:
      type: std_msgs/msg/Float32
    /pinky3/battery/present:
      type: std_msgs/msg/Bool
```

#### 방식 2: Robot ID 포함
토픽명에 로봇 ID 직접 포함:

```yaml
- from_domain: 11
  to_domain: 0
  topics:
    /robots/pinky1/amcl_pose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
    /robots/pinky1/odom:
      type: nav_msgs/msg/Odometry

- from_domain: 13
  to_domain: 0
  topics:
    /robots/pinky3/amcl_pose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
    /robots/pinky3/odom:
      type: nav_msgs/msg/Odometry
```

#### FMS Node 구독 업데이트 (방식 1 적용)

```python
# fms_node.py _setup_robot_monitoring() 수정
for config in robot_configs:
    if config.get('enabled', True) is False:
        continue
    robot_id = config['robot_id']
    domain_id = config.get('domain_id', 0)

    if domain_id != current_domain:
        logger.warning(f"Robot {robot_id} on DOMAIN_ID={domain_id}, needs bridge")
        continue

    # Namespace 기반 토픽명
    robot_ns = f"/{robot_id}"  # /pinky1, /pinky3

    self.create_subscription(
        PoseWithCovarianceStamped,
        f"{robot_ns}/amcl_pose",
        lambda msg, rid=robot_id: self.robot_amcl_pose_callback(rid, msg),
        10
    )

    self.create_subscription(
        Odometry,
        f"{robot_ns}/odom",
        lambda msg, rid=robot_id: self.robot_odom_callback(rid, msg),
        10
    )

    self.create_subscription(
        Float32,
        f"{robot_ns}/battery/voltage",
        lambda msg, rid=robot_id: self.robot_battery_voltage_callback(rid, msg),
        10
    )

    self.create_subscription(
        Bool,
        f"{robot_ns}/battery/present",
        lambda msg, rid=robot_id: self.robot_battery_present_callback(rid, msg),
        10
    )
```

---

## 2. 필수 토픽 누락 여부

### 누락된 Nav2 피드백 토픽

현재 설정에서 **브릿징되지 않는 중요 토픽들**:

| 토픽 | 타입 | 필요성 | 현상 |
|------|------|--------|------|
| `/amcl_pose` | `PoseWithCovarianceStamped` | 필수 | ✓ 브릿징됨 |
| `/odom` | `Odometry` | 필수 | ✓ 브릿징됨 (암묵적) |
| `/scan` | `LaserScan` | 선택 | ✓ 브릿징됨 |
| `/tf` | `tf2_msgs/msg/TFMessage` | **누락** | ✗ |
| `/plan` | `nav_msgs/msg/Path` | 선택 | ✗ |
| `/navigate_to_pose/_action/feedback` | 액션 피드백 | **누락** | ✗ |
| `/navigate_to_pose/_action/status` | 액션 상태 | **누락** | ✗ |
| `/costmap_updates` | 비용도 업데이트 | 선택 | ✗ |

### 가장 중요한 누락: TF (Transform)

**문제점**:
```
로봇의 TF 발행 (DOMAIN_ID=11/13):
- map -> odom
- odom -> base_link
- base_link -> lidar

Main PC에서 접근 불가 ✗
→ Nav2가 좌표계 변환 실패
→ 경로 계획 불가능
```

### 2-1. TF 브릿징 추가

```yaml
# domain_bridge.yaml 수정

# pinky1 TF
- from_domain: 11
  to_domain: 0
  topics:
    /tf:
      type: tf2_msgs/msg/TFMessage
    /tf_static:
      type: tf2_msgs/msg/TFMessage

# pinky3 TF
- from_domain: 13
  to_domain: 0
  topics:
    /tf:
      type: tf2_msgs/msg/TFMessage
    /tf_static:
      type: tf2_msgs/msg/TFMessage
```

**주의**: TF는 절대 namespace로 격리하면 안됨. TF 트리의 연속성 때문에 `[robot_id]_` 접두사 추가 필요:

```bash
# 로봇 측 (launch 파일)
ros2 launch tf_broadcaster.py  # TF 프레임 발행
  # 프레임 네이밍: pinky1_map -> pinky1_odom -> pinky1_base_link
```

---

## 3. 필수 Action 서비스 브릿징

### 현재 설정 분석

```yaml
services:
  /navigate_to_pose/_action/send_goal:
    type: nav2_msgs/action/NavigateToPose
  /navigate_to_pose/_action/cancel_goal:
    type: action_msgs/srv/CancelGoal
  /navigate_to_pose/_action/get_result:
    type: nav2_msgs/action/NavigateToPose
```

### 문제점

1. **Action 피드백 누락**:
   ```
   /navigate_to_pose/_action/feedback - 누락 ✗
   /navigate_to_pose/_action/status - 누락 ✗
   ```

2. **Action 클라이언트 타임아웃 위험**:
   ```python
   # fms_node.py line 124
   self.nav_clients[robot_id] = ActionClient(self, NavigateToPose, action_name)
   # 다른 DOMAIN_ID이면 timeout 발생
   ```

### 3-1. Action 서비스 완벽 브릿징

```yaml
# pinky1 (DOMAIN_ID=11) -> Main PC (DOMAIN_ID=0)
- from_domain: 0
  to_domain: 11
  topics:
    /initialpose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
    /goal_pose:
      type: geometry_msgs/msg/PoseStamped
  services:
    # Goal 전송
    /navigate_to_pose/_action/send_goal:
      type: nav2_msgs/action/NavigateToPose
    # Goal 취소
    /navigate_to_pose/_action/cancel_goal:
      type: action_msgs/srv/CancelGoal
    # 결과 조회
    /navigate_to_pose/_action/get_result:
      type: nav2_msgs/action/NavigateToPose

# 역방향: 피드백 및 상태 (로봇 → Main PC)
- from_domain: 11
  to_domain: 0
  topics:
    # Action 피드백 (로봇이 발행)
    /navigate_to_pose/_action/feedback:
      type: nav2_msgs/action/NavigateToPose
    # Action 상태
    /navigate_to_pose/_action/status:
      type: action_msgs/msg/GoalStatus
```

---

## 4. QoS (Quality of Service) 설정 필요성

### 현재 문제점

domain_bridge.yaml에 **QoS 정책이 없음**:

```yaml
# 현재 (기본값 사용)
topics:
  /amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    # qos: 미지정 → 기본 Best Effort 사용
```

### 권장 QoS 설정

```yaml
# 개선된 domain_bridge.yaml

# pinky1 (DOMAIN_ID=11) -> Main PC (DOMAIN_ID=0)
- from_domain: 11
  to_domain: 0
  topics:
    # 위치 정보: 신뢰성 중요 (Reliable)
    /pinky1/amcl_pose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
      qos:
        reliability: "RELIABLE"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 10

    # 주행 거리계: 빈번한 업데이트 (Best Effort)
    /pinky1/odom:
      type: nav_msgs/msg/Odometry
      qos:
        reliability: "BEST_EFFORT"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 5

    # 스캔 데이터: 고주파 (Best Effort)
    /pinky1/scan:
      type: sensor_msgs/msg/LaserScan
      qos:
        reliability: "BEST_EFFORT"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 2

    # 배터리 상태: 중요 정보 (Reliable)
    /pinky1/battery/voltage:
      type: std_msgs/msg/Float32
      qos:
        reliability: "RELIABLE"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 10

# Main PC -> pinky1: Goal 전송 (Reliable)
- from_domain: 0
  to_domain: 11
  topics:
    /pinky1/initialpose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
      qos:
        reliability: "RELIABLE"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 5
    /pinky1/goal_pose:
      type: geometry_msgs/msg/PoseStamped
      qos:
        reliability: "RELIABLE"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 5
```

### QoS 정책 가이드

| 토픽 | Reliability | Durability | History | Depth | 이유 |
|------|-------------|-----------|---------|-------|------|
| `/amcl_pose` | RELIABLE | VOLATILE | KEEP_LAST | 10 | 로봇 위치 손실 불가 |
| `/odom` | BEST_EFFORT | VOLATILE | KEEP_LAST | 5 | 고주파 업데이트 |
| `/scan` | BEST_EFFORT | VOLATILE | KEEP_LAST | 2 | 매우 고주파 센서 |
| `/battery/voltage` | RELIABLE | VOLATILE | KEEP_LAST | 10 | 배터리 상태 중요 |
| `initialpose` | RELIABLE | VOLATILE | KEEP_LAST | 5 | 위치 초기화 중요 |
| `goal_pose` | RELIABLE | VOLATILE | KEEP_LAST | 5 | 목표 지점 손실 불가 |

---

## 5. Action 서비스 브릿징 방식 검토

### 현재 구조의 문제

```python
# fms_node.py line 121-125
current_domain = int(os.environ.get('ROS_DOMAIN_ID', 0))
for robot_id, domain_info in self.robot_domains.items():
    if domain_info['domain_id'] == current_domain:
        action_name = '/navigate_to_pose'
        self.nav_clients[robot_id] = ActionClient(self, NavigateToPose, action_name)
```

**문제**:
1. FMS가 DOMAIN_ID=0에서만 실행되므로, 다른 DOMAIN_ID의 로봇과 통신 불가
2. `_send_robot_to_pickup()` (line 702)에서 action client 사용 시:
   - domain_id 11/13인 로봇 → client 없음 → navigation 실패

### 권장: TCP 기반 Action 클라이언트 (대안)

Option A: Fast-DDS ROS_DOMAIN_ID 기반 통신 (현재 접근법)

```bash
# 로봇: DOMAIN_ID=11
export ROS_DOMAIN_ID=11
ros2 launch pinky_navigation nav2_bringup.launch.xml

# FMS Main PC: DOMAIN_ID=0
export ROS_DOMAIN_ID=0
ros2 launch fms_system fms_bringup.launch.xml

# Domain Bridge 실행
ros2 run domain_bridge domain_bridge /fms/config/domain_bridge.yaml
```

**장점**:
- Fast-DDS 기본 설정으로 작동
- 자동 NAT 통과 (로컬 네트워크)

**단점**:
- action client가 여전히 timeout 가능성

### Option B: ROS2 Daemon 기반 (권장)

```bash
# 각 로봇에서
export ROS_DAEMON_DOMAIN_ID=11
ros2 daemon start 11

# Main PC에서 모든 로봇 액세스
export ROS_DAEMON_DOMAIN_ID=0,11,13
ros2 action list -t  # 모든 domain 액션 보임
```

### 5-1. Action 서비스 개선 사항

**step 1: domain_bridge.yaml 업데이트**

```yaml
# pinky1 (DOMAIN_ID=11) <- Main PC (DOMAIN_ID=0)
- from_domain: 0
  to_domain: 11
  services:
    /pinky1/navigate_to_pose/_action/send_goal:
      type: nav2_msgs/action/NavigateToPose
    /pinky1/navigate_to_pose/_action/cancel_goal:
      type: action_msgs/srv/CancelGoal
    /pinky1/navigate_to_pose/_action/get_result:
      type: nav2_msgs/action/NavigateToPose
  topics:
    /pinky1/initialpose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped

# pinky1 (DOMAIN_ID=11) -> Main PC (DOMAIN_ID=0)
- from_domain: 11
  to_domain: 0
  topics:
    /pinky1/amcl_pose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
    /pinky1/odom:
      type: nav_msgs/msg/Odometry
```

**step 2: fms_node.py 업데이트**

```python
# fms_node.py _navigate_robot() 수정
def _navigate_robot(self, robot_id: str, goal_pose: Pose):
    """로봇에 내비게이션 목표 전송"""
    # 브릿징되는 action 경로 사용
    domain_info = self.robot_domains.get(robot_id)
    if not domain_info:
        logger.error(f"Robot {robot_id} not configured")
        return

    domain_id = domain_info['domain_id']

    # namespace로 로봇 구분
    action_name = f"/{robot_id}/navigate_to_pose"

    # Action client가 없으면 생성 (지연 초기화)
    if robot_id not in self.nav_clients:
        logger.info(f"Creating action client for {robot_id}: {action_name}")
        self.nav_clients[robot_id] = ActionClient(self, NavigateToPose, action_name)

    nav_client = self.nav_clients[robot_id]

    # 목표 생성
    goal_msg = NavigateToPose.Goal()
    goal_msg.pose = PoseStamped()
    goal_msg.pose.header.frame_id = 'map'
    goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
    goal_msg.pose.pose = goal_pose

    # 타임아웃을 포함한 전송
    try:
        future = nav_client.send_goal_async(goal_msg)
        future.add_done_callback(
            lambda f: self._nav_goal_callback(robot_id, f)
        )
        logger.info(f"Sent navigation goal to {robot_id}: {goal_pose.position}")
    except Exception as e:
        logger.error(f"Failed to send navigation goal: {e}")

def _nav_goal_callback(self, robot_id: str, future):
    """내비게이션 목표 응답 처리"""
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
        logger.error(f"Navigation goal error for {robot_id}: {e}")

def _nav_result_callback(self, robot_id: str, future):
    """내비게이션 결과 처리"""
    try:
        result = future.result()
        if result.result.status == GoalStatus.STATUS_SUCCEEDED:
            logger.info(f"Navigation succeeded for {robot_id}")
        else:
            logger.warning(f"Navigation failed for {robot_id}, status: {result.result.status}")
    except Exception as e:
        logger.error(f"Navigation result error for {robot_id}: {e}")
```

---

## 6. 전체 개선된 domain_bridge.yaml

```yaml
# Kitchmatics FMS용 Domain Bridge 설정 (개선 버전)
# Main PC (DOMAIN_ID=0) <-> pinky1 (DOMAIN_ID=11), pinky3 (DOMAIN_ID=13)

# ====== PINKY1 (DOMAIN_ID=11) ======

# pinky1 -> Main PC: 센서 및 상태 토픽
- from_domain: 11
  to_domain: 0
  topics:
    # 로컬라이제이션
    /pinky1/amcl_pose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 10

    # 오도메트리
    /pinky1/odom:
      type: nav_msgs/msg/Odometry
      qos:
        reliability: "BEST_EFFORT"
        history: "KEEP_LAST"
        depth: 5

    # LiDAR 스캔
    /pinky1/scan:
      type: sensor_msgs/msg/LaserScan
      qos:
        reliability: "BEST_EFFORT"
        history: "KEEP_LAST"
        depth: 2

    # 배터리 상태
    /pinky1/battery/voltage:
      type: std_msgs/msg/Float32
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 10

    /pinky1/battery/present:
      type: std_msgs/msg/Bool
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 5

    # 좌표 변환 프레임 (TF)
    /tf:
      type: tf2_msgs/msg/TFMessage
      qos:
        reliability: "BEST_EFFORT"
        history: "KEEP_LAST"
        depth: 5

    /tf_static:
      type: tf2_msgs/msg/TFMessage
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 10

# Main PC -> pinky1: 제어 명령
- from_domain: 0
  to_domain: 11
  topics:
    /pinky1/initialpose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 5

    /pinky1/goal_pose:
      type: geometry_msgs/msg/PoseStamped
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 5

  services:
    # 내비게이션 Action 서비스
    /pinky1/navigate_to_pose/_action/send_goal:
      type: nav2_msgs/action/NavigateToPose

    /pinky1/navigate_to_pose/_action/cancel_goal:
      type: action_msgs/srv/CancelGoal

    /pinky1/navigate_to_pose/_action/get_result:
      type: nav2_msgs/action/NavigateToPose

# ====== PINKY3 (DOMAIN_ID=13) ======

# pinky3 -> Main PC: 센서 및 상태 토픽
- from_domain: 13
  to_domain: 0
  topics:
    # 로컬라이제이션
    /pinky3/amcl_pose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 10

    # 오도메트리
    /pinky3/odom:
      type: nav_msgs/msg/Odometry
      qos:
        reliability: "BEST_EFFORT"
        history: "KEEP_LAST"
        depth: 5

    # LiDAR 스캔
    /pinky3/scan:
      type: sensor_msgs/msg/LaserScan
      qos:
        reliability: "BEST_EFFORT"
        history: "KEEP_LAST"
        depth: 2

    # 배터리 상태
    /pinky3/battery/voltage:
      type: std_msgs/msg/Float32
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 10

    /pinky3/battery/present:
      type: std_msgs/msg/Bool
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 5

    # 좌표 변환 프레임 (TF)
    /tf:
      type: tf2_msgs/msg/TFMessage
      qos:
        reliability: "BEST_EFFORT"
        history: "KEEP_LAST"
        depth: 5

    /tf_static:
      type: tf2_msgs/msg/TFMessage
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 10

# Main PC -> pinky3: 제어 명령
- from_domain: 0
  to_domain: 13
  topics:
    /pinky3/initialpose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 5

    /pinky3/goal_pose:
      type: geometry_msgs/msg/PoseStamped
      qos:
        reliability: "RELIABLE"
        history: "KEEP_LAST"
        depth: 5

  services:
    # 내비게이션 Action 서비스
    /pinky3/navigate_to_pose/_action/send_goal:
      type: nav2_msgs/action/NavigateToPose

    /pinky3/navigate_to_pose/_action/cancel_goal:
      type: action_msgs/srv/CancelGoal

    /pinky3/navigate_to_pose/_action/get_result:
      type: nav2_msgs/action/NavigateToPose
```

---

## 7. 개선 제안사항 우선순위

### Priority 1: CRITICAL (즉시 수정)

#### 1-1. 토픽 네이밍 충돌 해결
```
현재 위험: 로봇 간 데이터 혼동
해결책: namespace 기반 격리 추가
추정시간: 2시간
```

#### 1-2. TF 브릿징 추가
```
현재 위험: 좌표계 변환 실패 → Nav2 작동 불가
해결책: /tf, /tf_static 브릿징
추정시간: 1시간
```

#### 1-3. FMS Node 토픽명 업데이트
```
현재 코드:
  /pose, /battery/voltage, /battery/present
수정:
  /pinky1/amcl_pose, /pinky1/battery/voltage
추정시간: 3시간 (테스트 포함)
```

### Priority 2: HIGH (1주 내 수정)

#### 2-1. QoS 설정 추가
```
현재: 기본값 사용
개선: 토픽별 최적 QoS
추정시간: 1시간
```

#### 2-2. Action 서비스 완벽 브릿징
```
누락: /feedback, /status
추가 필요: 모든 action 서비스
추정시간: 2시간
```

#### 2-3. 에러 처리 개선
```
현재: action client timeout 미처리
개선: 타임아웃 감지 및 재시도 로직
추정시간: 2시간
```

### Priority 3: MEDIUM (2주 내 수정)

#### 3-1. 모니터링 및 디버깅 도구
```
추가: Domain Bridge 상태 모니터 스크립트
내용: 활성 브릿지, 토픽 통계, 에러율
추정시간: 3시간
```

#### 3-2. 로깅 강화
```
Domain Bridge 버전 확인
상세 통신 로그 추가
추정시간: 2시간
```

---

## 8. 설정 마이그레이션 계획

### Step 1: 백업 및 계획
```bash
# 현재 설정 백업
cp /fms/config/domain_bridge.yaml /fms/config/domain_bridge.yaml.backup
```

### Step 2: 개선된 설정 적용
```bash
# 개선된 domain_bridge.yaml 적용
# 이 파일에 제공된 "6. 전체 개선된 domain_bridge.yaml" 사용
```

### Step 3: FMS Node 코드 업데이트
필요한 파일 수정:
- `/fms/fms/fms_node.py` - 토픽명 업데이트
- `/fms/fms/fleet_controller.py` - 필요시 확인

### Step 4: 테스트
```bash
# 1. Domain Bridge 시작
ros2 run domain_bridge domain_bridge /fms/config/domain_bridge.yaml

# 2. 토픽 확인
ros2 topic list | grep pinky

# 3. 통신 테스트
ros2 topic echo /pinky1/amcl_pose
ros2 topic echo /pinky3/amcl_pose

# 4. FMS 시작
ros2 launch fms_system fms_bringup.launch.xml
```

### Step 5: 모니터링
```bash
# Domain Bridge 상태 확인
ros2 topic hz /pinky1/amcl_pose
ros2 topic hz /pinky3/amcl_pose
```

---

## 9. 체크리스트

### 적용 전 점검
- [ ] domain_bridge.yaml 백업 완료
- [ ] 개선된 설정 검토 완료
- [ ] FMS Node 코드 검토 완료
- [ ] 테스트 계획 수립

### 적용 후 검증
- [ ] 로봇 1 (`pinky1`) 토픽 정상 브릿징 확인
- [ ] 로봇 2 (`pinky3`) 토픽 정상 브릿징 확인
- [ ] TF 트리 정상 발행 확인
- [ ] FMS Node 정상 구독 확인
- [ ] Navigation action 정상 작동 확인
- [ ] 배터리 상태 정상 수집 확인

---

## 10. 참고 자료

### Domain Bridge 관련
- [ROS2 Domain Bridge 문서](https://github.com/ros2/domain_bridge)
- [Fast-DDS 멀티 도메인 설정](https://fast-dds.docs.eprosima.com/)

### Nav2 통신
- [Nav2 네트워킹 가이드](https://navigation.ros.org/)
- [ROS2 QoS 정책](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html)

### 관련 이슈
- 멀티 로봇 좌표계: TF 프레임 namespace 필요
- 네트워크 지연: QoS reliability 설정 필수
- 액션 타임아웃: 비동기 핸들러 구현
