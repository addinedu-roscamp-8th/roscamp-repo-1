# Domain Bridge 설정 분석 보고서
**날짜**: 2026-02-26
**시스템**: Kitchmatics FMS
**분석자**: ROS2 Domain Bridge Specialist

---

## 요약 (Executive Summary)

현재 시스템은 **namespace 최소화 전략을 올바르게 구현**하고 있습니다. 로봇 측에서는 namespace 없이 `/amcl_pose`를 발행하고, Domain Bridge가 `remap` 기능으로 Main PC에서 `/pinky1/amcl_pose`로 변환합니다.

**핵심 발견사항**:
1. ✅ 현재 설정이 요구사항을 충족함 (namespace 최소화)
2. ⚠️ 일부 필수 토픽 누락 (odom, scan, cmd_vel, tf)
3. ⚠️ 로봇팔 브릿징 설정이 별도 파일에 있음
4. ✅ Action 브릿징이 올바르게 설정됨

---

## 1. 환경 정보

### 네트워크 구성
```
Main PC (FMS):    ROS_DOMAIN_ID=25  (관제 PC)
├── pinky1:       ROS_DOMAIN_ID=11  (IP: 192.168.1.7)
├── pinky2:       ROS_DOMAIN_ID=12  (IP: 192.168.1.6)
├── 로봇팔A:       ROS_DOMAIN_ID=20  (IP: 192.168.1.4)
└── 로봇팔B:       ROS_DOMAIN_ID=21  (IP: 192.168.1.10)
```

### 주의사항
- 요구사항에는 `ROS_DOMAIN_ID=0`이라고 되어 있지만, **실제 시스템은 Domain 25 사용**
- 모든 설정 파일과 스크립트가 Domain 25를 사용하도록 구성됨
- **권장**: Main PC는 계속 Domain 25 사용

---

## 2. 현재 활성 설정 분석

### 사용 중인 파일
```
/home/gw/kitchmatics/roscamp-repo-1/fms/config/
├── domain_bridge_pinky1.yaml   [ACTIVE]
├── domain_bridge_pinky2.yaml   [ACTIVE]
└── domain_bridge_pinky3.yaml   [ACTIVE, but robot not in use]
```

**실행 방법**: `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/run_domain_bridges.sh`

### pinky1 설정 상세 (domain_bridge_pinky1.yaml)

#### 현재 브릿징되는 토픽

**Robot (Domain 11) → Main PC (Domain 25)**:
```yaml
/amcl_pose              → /pinky1/amcl_pose           (위치 추정)
/battery/voltage        → /pinky1/battery/voltage     (배터리 전압)
/battery/present        → /pinky1/battery/present     (배터리 존재 여부)
```

**Main PC (Domain 25) → Robot (Domain 11)**:
```yaml
/pinky1/initialpose     → /initialpose                (초기 위치 설정)
```

**Actions (양방향)**:
```yaml
/pinky1/follow_waypoints   ↔ /follow_waypoints       (경로점 추종)
/pinky1/navigate_to_pose   ↔ /navigate_to_pose       (목표 지점 이동)
```

**Services**:
```yaml
/pinky1/lifecycle_manager_navigation/get_state ↔ /lifecycle_manager_navigation/get_state
```

---

## 3. Namespace 전략 평가

### 현재 구현 방식 (GOOD ✅)

```
┌─────────────────────────────────────┐
│  pinky1 (Domain 11)                 │
│  발행: /amcl_pose (namespace 없음)  │
└────────────┬────────────────────────┘
             │
             │ Domain Bridge (remap 사용)
             │
             ▼
┌─────────────────────────────────────┐
│  Main PC (Domain 25)                │
│  수신: /pinky1/amcl_pose            │
└─────────────────────────────────────┘
```

**장점**:
- ✅ 로봇 측 코드 단순 (namespace 불필요)
- ✅ Main PC에서 여러 로봇 구분 가능
- ✅ Fleet management 가능
- ✅ 요구사항 충족 ("namespace 사용 최소화")

**이 방식이 최적입니다!** 로봇에서는 namespace 없이 동작하고, 브릿지가 Main PC 쪽에만 namespace를 추가합니다.

---

## 4. 문제점 및 누락된 토픽

### 문제 1: 중요 센서 토픽 누락 (CRITICAL)

#### 누락된 토픽들:

**Robot → Main PC** (필수):
```yaml
/odom                    # 주행거리계 (CRITICAL)
/scan                    # LiDAR 데이터 (HIGH)
/tf                      # Transform 트리 (CRITICAL for Nav2)
/tf_static               # 정적 Transform (CRITICAL)
```

**Main PC → Robot** (필수):
```yaml
/cmd_vel                 # 속도 명령 (CRITICAL for teleop/manual control)
/goal_pose               # 목표 위치 (HIGH)
```

#### 해결 방법:

`domain_bridge_pinky1.yaml`에 추가 필요:

```yaml
topics:
  # 기존 토픽들...

  # 주행거리계 추가
  odom:
    type: nav_msgs/msg/Odometry
    remap: pinky1/odom
    qos:
      reliability: best_effort
      durability: volatile

  # LiDAR 추가
  scan:
    type: sensor_msgs/msg/LaserScan
    remap: pinky1/scan
    qos:
      reliability: best_effort
      durability: volatile

  # TF 추가
  tf:
    type: tf2_msgs/msg/TFMessage
    # NOTE: remap 안 함 (TF는 전역)
    qos:
      reliability: best_effort
      durability: volatile

  tf_static:
    type: tf2_msgs/msg/TFMessage
    qos:
      reliability: reliable
      durability: transient_local

  # 속도 명령 추가 (Main PC → Robot)
  pinky1/cmd_vel:
    type: geometry_msgs/msg/Twist
    remap: cmd_vel
    reversed: true
    qos:
      reliability: reliable
      durability: volatile

  # 목표 위치 추가 (Main PC → Robot)
  pinky1/goal_pose:
    type: geometry_msgs/msg/PoseStamped
    remap: goal_pose
    reversed: true
    qos:
      reliability: reliable
      durability: volatile
```

### 문제 2: 로봇팔 브릿징 누락 (HIGH)

현재 `domain_bridge_pinky1.yaml`에는 로봇팔 토픽이 없습니다.

#### 필요한 로봇팔 토픽:

**로봇팔A (Domain 20) ↔ Main PC (Domain 25)**:
```yaml
/arm_a/status            # 팔A 상태 (Robot → Main)
/arm_a/cmd               # 팔A 명령 (Main → Robot)
```

**로봇팔B (Domain 21) ↔ Main PC (Domain 25)**:
```yaml
/arm_b/status            # 팔B 상태 (Robot → Main)
/arm_b/cmd               # 팔B 명령 (Main → Robot)
/verify/status           # 검증 상태 (Robot → Main)
/verify/cmd              # 검증 명령 (Main → Robot)
```

**FMS ↔ Coordinator 통신**:
```yaml
/fms/pickup_arrival           # FMS → Coordinator (로봇 도착 알림)
/cooking/order                # FMS → Coordinator (조리 주문)
/cooking/loading_complete     # Coordinator → FMS (로딩 완료)
```

#### 해결 방법 옵션:

**옵션 A**: 별도 설정 파일 사용 (권장)
```bash
# 모바일 로봇용
domain_bridge_pinky1.yaml
domain_bridge_pinky2.yaml

# 로봇팔용
domain_bridge_arms.yaml  # 새로 생성
```

**옵션 B**: 통합 설정 파일 사용
```bash
# 모든 로봇을 하나의 파일에
domain_bridge_complete.yaml  # 이미 존재함
```

---

## 5. TF (Transform) 브릿징 전략

### 문제: TF Frame 충돌

여러 로봇이 동일한 frame 이름을 사용:
- pinky1: `base_link`, `odom`, `map`
- pinky2: `base_link`, `odom`, `map`

Main PC에 모두 브릿지하면 충돌 발생.

### 해결 방안

#### 방안 A: TF 브릿지하지 않음 (권장)

```yaml
# domain_bridge_pinky1.yaml
# /tf, /tf_static 토픽을 브릿지에서 제외
```

**장점**:
- TF 충돌 없음
- 각 로봇의 TF는 해당 도메인에서만 사용
- Main PC는 `/amcl_pose`로 로봇 위치 파악

**단점**:
- Main PC에서 로봇의 상세 frame 정보 없음
- Rviz에서 로봇 시각화 제한적

#### 방안 B: TF Prefix 사용

각 로봇에 고유 prefix 추가:
```
pinky1: pinky1_base_link, pinky1_odom, pinky1_map
pinky2: pinky2_base_link, pinky2_odom, pinky2_map
```

**장점**:
- 모든 TF를 Main PC에서 사용 가능
- 충돌 없음

**단점**:
- 로봇 측 설정 변경 필요
- Nav2 파라미터 수정 필요

#### 방안 C: Static TF만 브릿지

```yaml
# /tf는 브릿지 안 함
# /tf_static만 브릿지 (센서 위치 등)
tf_static:
  type: tf2_msgs/msg/TFMessage
  # remap 없음 (각 로봇이 다른 센서 이름 사용)
```

**권장**: **방안 A** - TF 브릿지 안 함. Fleet 관리는 `/amcl_pose`만으로 충분.

---

## 6. QoS (Quality of Service) 정책

현재 설정에는 QoS가 명시되지 않음. Domain Bridge는 기본값을 사용.

### 권장 QoS 정책:

```yaml
topics:
  # 위치 정보 (중요, 손실 불가)
  amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    remap: pinky1/amcl_pose
    qos:
      reliability: reliable      # 손실 방지
      durability: volatile       # 최신 데이터만
      history: keep_last
      depth: 10

  # 주행거리계 (고주파, 손실 허용)
  odom:
    type: nav_msgs/msg/Odometry
    remap: pinky1/odom
    qos:
      reliability: best_effort   # 빠른 전송
      durability: volatile
      history: keep_last
      depth: 5

  # LiDAR (매우 고주파, 손실 허용)
  scan:
    type: sensor_msgs/msg/LaserScan
    remap: pinky1/scan
    qos:
      reliability: best_effort   # 빠른 전송
      durability: volatile
      history: keep_last
      depth: 2

  # 배터리 (중요, 손실 불가)
  battery/voltage:
    type: std_msgs/msg/Float32
    remap: pinky1/battery/voltage
    qos:
      reliability: reliable      # 손실 방지
      durability: volatile
      history: keep_last
      depth: 10

  # 명령 토픽 (매우 중요, 손실 불가)
  pinky1/cmd_vel:
    type: geometry_msgs/msg/Twist
    remap: cmd_vel
    reversed: true
    qos:
      reliability: reliable      # 명령 손실 방지
      durability: volatile
      history: keep_last
      depth: 10
```

---

## 7. 권장 설정 파일

### 개선된 domain_bridge_pinky1.yaml

```yaml
# Domain Bridge Configuration for pinky1
# pinky1 (DOMAIN_ID=11) <-> Main PC (DOMAIN_ID=25)
#
# 전략: 로봇 측은 namespace 없음, Main PC는 namespace 있음
#
# 사용법:
#   ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge fms/config/domain_bridge_pinky1.yaml

name: pinky1_bridge
from_domain: 11
to_domain: 25

topics:
  # ============================================
  # Robot → Main PC: 센서 및 상태 토픽
  # ============================================

  # AMCL 위치 추정
  amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    remap: pinky1/amcl_pose
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # 주행거리계
  odom:
    type: nav_msgs/msg/Odometry
    remap: pinky1/odom
    qos:
      reliability: best_effort
      durability: volatile
      history: keep_last
      depth: 5

  # LiDAR 스캔
  scan:
    type: sensor_msgs/msg/LaserScan
    remap: pinky1/scan
    qos:
      reliability: best_effort
      durability: volatile
      history: keep_last
      depth: 2

  # 배터리 전압
  battery/voltage:
    type: std_msgs/msg/Float32
    remap: pinky1/battery/voltage
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # 배터리 존재 여부
  battery/present:
    type: std_msgs/msg/Bool
    remap: pinky1/battery/present
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 5

  # TF는 브릿지 안 함 (충돌 방지)
  # tf:
  #   type: tf2_msgs/msg/TFMessage
  # tf_static:
  #   type: tf2_msgs/msg/TFMessage

  # ============================================
  # Main PC → Robot: 제어 명령 토픽
  # ============================================

  # 초기 위치 설정
  pinky1/initialpose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    remap: initialpose
    reversed: true
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 5

  # 속도 명령
  pinky1/cmd_vel:
    type: geometry_msgs/msg/Twist
    remap: cmd_vel
    reversed: true
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # 목표 위치
  pinky1/goal_pose:
    type: geometry_msgs/msg/PoseStamped
    remap: goal_pose
    reversed: true
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 5

services:
  # Lifecycle 서비스
  pinky1/lifecycle_manager_navigation/get_state:
    type: lifecycle_msgs/srv/GetState
    remap: lifecycle_manager_navigation/get_state
    reversed: true

actions:
  # 경로점 추종 액션
  pinky1/follow_waypoints:
    type: nav2_msgs/action/FollowWaypoints
    remap: follow_waypoints
    reversed: true

  # 목표 지점 이동 액션
  pinky1/navigate_to_pose:
    type: nav2_msgs/action/NavigateToPose
    remap: navigate_to_pose
    reversed: true
```

### 새로운 domain_bridge_arms.yaml (로봇팔용)

```yaml
# Domain Bridge Configuration for Robot Arms
# armA (DOMAIN_ID=20), armB (DOMAIN_ID=21) <-> Main PC (DOMAIN_ID=25)
#
# 사용법:
#   ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge fms/config/domain_bridge_arms.yaml

name: arms_bridge

topics:
  # ============================================
  # ARM A (Domain 20) ↔ Main PC (Domain 25)
  # ============================================

  # Arm A 상태 (Robot → Main)
  arm_a/status:
    type: std_msgs/msg/String
    from_domain: 20
    to_domain: 25
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # Arm A 명령 (Main → Robot)
  arm_a/cmd:
    type: std_msgs/msg/String
    from_domain: 25
    to_domain: 20
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # ============================================
  # ARM B (Domain 21) ↔ Main PC (Domain 25)
  # ============================================

  # Arm B 상태 (Robot → Main)
  arm_b/status:
    type: std_msgs/msg/String
    from_domain: 21
    to_domain: 25
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # Arm B 명령 (Main → Robot)
  arm_b/cmd:
    type: std_msgs/msg/String
    from_domain: 25
    to_domain: 21
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # Verify 상태 (Robot → Main)
  verify/status:
    type: std_msgs/msg/String
    from_domain: 21
    to_domain: 25
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # Verify 명령 (Main → Robot)
  verify/cmd:
    type: std_msgs/msg/String
    from_domain: 25
    to_domain: 21
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # ============================================
  # FMS ↔ Coordinator 통신
  # ============================================

  # FMS → Coordinator: 픽업 도착 알림 (Domain 20, 21 모두)
  fms_pickup_arrival_20:
    topic: fms/pickup_arrival
    type: fleet_interfaces/msg/PickupArrival
    from_domain: 25
    to_domain: 20
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  fms_pickup_arrival_21:
    topic: fms/pickup_arrival
    type: fleet_interfaces/msg/PickupArrival
    from_domain: 25
    to_domain: 21
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # FMS → Coordinator: 조리 주문 (Domain 20, 21 모두)
  cooking_order_20:
    topic: cooking/order
    type: fleet_interfaces/msg/CookingOrder
    from_domain: 25
    to_domain: 20
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  cooking_order_21:
    topic: cooking/order
    type: fleet_interfaces/msg/CookingOrder
    from_domain: 25
    to_domain: 21
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10

  # Coordinator → FMS: 로딩 완료
  cooking/loading_complete:
    type: fleet_interfaces/msg/LoadingComplete
    from_domain: 21  # Coordinator는 domain 21에서 실행
    to_domain: 25
    qos:
      reliability: reliable
      durability: volatile
      history: keep_last
      depth: 10
```

---

## 8. 실행 방법

### 현재 방법 (개별 실행)

```bash
# Terminal 1: pinky1 bridge
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_pinky1.yaml

# Terminal 2: pinky2 bridge
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_pinky2.yaml

# Terminal 3: arms bridge (새로 추가)
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_arms.yaml
```

### 권장 방법 (launch 파일 사용)

기존 `domain_bridges.launch.py` 수정하여 로봇팔 브릿지 추가:

```python
# fms/launch/domain_bridges.launch.py

def generate_launch_description():
    config_dir = ...

    pinky1_config = os.path.join(config_dir, 'domain_bridge_pinky1.yaml')
    pinky2_config = os.path.join(config_dir, 'domain_bridge_pinky2.yaml')
    arms_config = os.path.join(config_dir, 'domain_bridge_arms.yaml')  # 추가

    return LaunchDescription([
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky1_bridge',
            arguments=[pinky1_config],
            output='screen',
            respawn=True,
        ),
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky2_bridge',
            arguments=[pinky2_config],
            output='screen',
            respawn=True,
        ),
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='arms_bridge',
            arguments=[arms_config],  # 추가
            output='screen',
            respawn=True,
        ),
    ])
```

실행:
```bash
ROS_DOMAIN_ID=25 ros2 launch fms domain_bridges.launch.py
```

---

## 9. 테스트 체크리스트

### Phase 1: 단일 로봇 테스트 (pinky1)

```bash
# 1. Domain bridge 시작
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_pinky1.yaml

# 2. Main PC에서 토픽 확인
ROS_DOMAIN_ID=25 ros2 topic list | grep pinky1
# 예상 출력:
#   /pinky1/amcl_pose
#   /pinky1/odom
#   /pinky1/scan
#   /pinky1/battery/voltage
#   /pinky1/battery/present

# 3. 로봇에서 토픽 확인 (namespace 없어야 함)
ROS_DOMAIN_ID=11 ros2 topic list
# 예상 출력:
#   /amcl_pose
#   /odom
#   /scan
#   /battery/voltage
#   /battery/present

# 4. 데이터 수신 확인
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose --once
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/odom --once

# 5. 명령 전송 테스트
ROS_DOMAIN_ID=25 ros2 topic pub /pinky1/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.1}}" --once

# 6. Action 테스트
ROS_DOMAIN_ID=25 ros2 action list | grep pinky1
# 예상 출력:
#   /pinky1/navigate_to_pose
#   /pinky1/follow_waypoints
```

### Phase 2: 다중 로봇 테스트 (pinky1 + pinky2)

```bash
# 1. 두 로봇 모두 토픽 발행 중인지 확인
ROS_DOMAIN_ID=25 ros2 topic hz /pinky1/amcl_pose
ROS_DOMAIN_ID=25 ros2 topic hz /pinky2/amcl_pose

# 2. 토픽 충돌 없는지 확인 (동시에 모니터링)
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose &
ROS_DOMAIN_ID=25 ros2 topic echo /pinky2/amcl_pose &
# 각각 다른 데이터가 출력되어야 함

# 3. 각 로봇에 개별 명령 전송
ROS_DOMAIN_ID=25 ros2 topic pub /pinky1/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.2}}" --once

ROS_DOMAIN_ID=25 ros2 topic pub /pinky2/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.3}}" --once
```

### Phase 3: 로봇팔 통신 테스트

```bash
# 1. Arm A 상태 모니터링
ROS_DOMAIN_ID=25 ros2 topic echo /arm_a/status

# 2. Arm A에 명령 전송
ROS_DOMAIN_ID=25 ros2 topic pub /arm_a/cmd std_msgs/msg/String \
  "data: 'JOB123|pick_ham'" --once

# 3. 로봇팔에서 수신 확인
ROS_DOMAIN_ID=20 ros2 topic echo /arm_a/cmd --once

# 4. FMS → Coordinator 통신 테스트
ROS_DOMAIN_ID=25 ros2 topic pub /fms/pickup_arrival \
  fleet_interfaces/msg/PickupArrival \
  "{robot_id: 'pinky1', location: 'station_a'}" --once

# Domain 20과 21에서 모두 수신되는지 확인
ROS_DOMAIN_ID=20 ros2 topic echo /fms/pickup_arrival --once
ROS_DOMAIN_ID=21 ros2 topic echo /fms/pickup_arrival --once
```

---

## 10. 문제 해결 (Troubleshooting)

### 문제 1: "토픽이 보이지 않음"

```bash
# 증상
ROS_DOMAIN_ID=25 ros2 topic list | grep pinky1
# 아무것도 출력 안 됨

# 원인 1: Domain bridge가 실행 중이 아님
ps aux | grep domain_bridge

# 원인 2: 로봇이 토픽을 발행하지 않음
ROS_DOMAIN_ID=11 ros2 topic list
ROS_DOMAIN_ID=11 ros2 topic hz /amcl_pose

# 원인 3: Domain ID 불일치
# Main PC와 domain bridge가 모두 Domain 25인지 확인
echo $ROS_DOMAIN_ID  # 25여야 함
```

### 문제 2: "데이터가 섞임 (pinky1과 pinky2 구분 안 됨)"

```bash
# 증상: /pinky1/amcl_pose에 pinky2 데이터가 나타남

# 원인: remap 설정 오류 또는 누락
# domain_bridge_pinky1.yaml 확인:
#   remap: pinky1/amcl_pose  (있어야 함)
# domain_bridge_pinky2.yaml 확인:
#   remap: pinky2/amcl_pose  (있어야 함)

# 해결: 각 설정 파일의 remap이 올바른지 확인
```

### 문제 3: "Action 호출 실패"

```bash
# 증상
ROS_DOMAIN_ID=25 ros2 action send_goal /pinky1/navigate_to_pose ...
# Error: Action server not available

# 원인: Action 서버가 다른 domain에 있음
ROS_DOMAIN_ID=11 ros2 action list  # 로봇 측에서 확인

# 해결: domain_bridge_pinky1.yaml에 action 설정 확인
# actions:
#   pinky1/navigate_to_pose:
#     type: nav2_msgs/action/NavigateToPose
#     remap: navigate_to_pose
#     reversed: true
```

### 문제 4: "로봇팔 통신 안 됨"

```bash
# 증상
ROS_DOMAIN_ID=25 ros2 topic list | grep arm
# /arm_a/cmd, /arm_a/status 등이 안 보임

# 원인: 로봇팔용 domain bridge가 실행 중이 아님

# 해결: domain_bridge_arms.yaml 생성 및 실행
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_arms.yaml
```

---

## 11. 최종 권장사항

### 즉시 적용 (이번 주)

1. ✅ **현재 설정 유지**: `domain_bridge_pinky1.yaml`, `domain_bridge_pinky2.yaml`는 올바른 전략 사용 중
2. ⚠️ **누락 토픽 추가**: `odom`, `scan`, `cmd_vel`, `goal_pose` 추가
3. ⚠️ **로봇팔 브릿지 추가**: `domain_bridge_arms.yaml` 생성 및 실행
4. ⚠️ **QoS 정책 추가**: 각 토픽에 적절한 QoS 설정

### 중기 계획 (다음 주)

5. 📊 **성능 모니터링**: 네트워크 대역폭 및 지연 시간 측정
6. 🧪 **통합 테스트**: 모든 로봇 동시 동작 확인
7. 📚 **문서화**: 최종 설정 파일 및 운영 가이드 작성

### 장기 계획 (1개월 내)

8. 🔧 **TF 전략 재검토**: 필요시 TF prefix 방식 도입
9. 🚀 **최적화**: QoS 튜닝, 불필요한 토픽 제거
10. 🔒 **보안 강화**: DDS Security 설정 (선택)

---

## 12. 요약

### 현재 상태 평가

| 항목 | 상태 | 비고 |
|------|------|------|
| Namespace 전략 | ✅ 우수 | 로봇 측 namespace 없음, 브릿지에서 추가 |
| 모바일 로봇 브릿징 | ⚠️ 부분 | 일부 토픽 누락 (odom, scan, cmd_vel) |
| 로봇팔 브릿징 | ❌ 없음 | 별도 설정 파일 필요 |
| Action 브릿징 | ✅ 우수 | navigate_to_pose, follow_waypoints 지원 |
| QoS 정책 | ⚠️ 기본값 | 명시적 설정 필요 |
| TF 브릿징 | ❌ 없음 | 의도된 것일 수 있음 (충돌 방지) |

### 핵심 답변

**질문**: "namespace 사용을 최대한 지양하면서 브릿징하는 방법?"

**답변**: ✅ **현재 시스템이 이미 올바르게 구현하고 있습니다!**

```
로봇 측: namespace 없음 (/amcl_pose, /odom, /cmd_vel)
         ↓
Domain Bridge: remap 기능으로 namespace 추가
         ↓
Main PC: namespace 있음 (/pinky1/amcl_pose, /pinky2/amcl_pose)
```

이 방식이 **최적**입니다:
- 로봇 코드는 단순하게 유지 (namespace 불필요)
- Main PC에서 여러 로봇 구분 가능
- Fleet management 가능

### 필요한 수정사항

1. **domain_bridge_pinky1.yaml에 추가**:
   - odom (주행거리계)
   - scan (LiDAR)
   - cmd_vel (속도 명령)
   - goal_pose (목표 위치)
   - QoS 정책

2. **domain_bridge_arms.yaml 생성**:
   - /arm_a/cmd, /arm_a/status
   - /arm_b/cmd, /arm_b/status
   - /verify/cmd, /verify/status
   - FMS ↔ Coordinator 토픽

3. **domain_bridges.launch.py 수정**:
   - arms_bridge 노드 추가

---

**분석 완료**
**다음 단계**: 권장 설정 파일 적용 및 테스트

파일 위치:
- 분석 보고서: `/home/gw/kitchmatics/roscamp-repo-1/DOMAIN_BRIDGE_REPORT.md`
- 현재 설정: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_pinky1.yaml`
- 개선 템플릿: 이 문서의 섹션 7 참조
