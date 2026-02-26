# SC-71: 장애물 회피 네비게이션 구현

## 개요

ROS2 Nav2 스택을 사용하여 Pinky 로봇의 동적 장애물 회피 기능을 구현합니다.

## 구현 범위

| 태스크 | 번호 | 내용 | 상태 |
|--------|------|------|------|
| 센서 데이터 수집 | SC-179/317 | LiDAR → Local Costmap 설정 | ✅ 완료 |
| 장애물 감지 알고리즘 | SC-180/318 | Obstacle Layer 최적화 | ✅ 완료 |
| 회피 경로 계획 | SC-181/319 | Planner + Controller 튜닝 | ✅ 완료 |
| 안전 정지 및 재경로 | SC-182/320 | Recovery Behaviors + FMS 알림 | 진행중 |

## 1. 센서 데이터 수집 (SC-179/317)

### LiDAR 스캔 데이터 흐름

```
Physical LiDAR (20Hz)
    ↓
ROS2 /scan 토픽 (LaserScan)
    ↓
local_costmap (ObstacleLayer)
    ↓
controller_server (RegulatedPurePursuitController)
    ↓
cmd_vel (속도 명령)
```

### 설정 파일 위치

**`mobile_robot/params/nav2_params.yaml`** (프로젝트 루트 기준)

```yaml
local_costmap:
  local_costmap:
    ros__parameters:
      update_frequency: 30.0  # 30Hz 처리 (센서 데이터 빠른 반응)
      publish_frequency: 20.0  # 20Hz 발행
      resolution: 0.01  # 1cm 해상도 (고정밀)
      
      obstacle_layer:
        observation_sources: scan
        scan:
          topic: /scan  # LiDAR 스캔 토픽
          expected_update_rate: 20.0  # 스캔 20Hz
          observation_persistence: 0.0  # 최신 스캔만 사용 (빠른 반응)
```

### 검증 명령어

```bash
# 1. LiDAR 스캔 데이터 확인
ros2 topic echo /scan -n 3

# 2. Local Costmap 업데이트 확인
ros2 topic echo /pinky1/local_costmap/costmap -n 1

# 3. LiDAR 가시화
ros2 run rviz2 rviz2 -d nav2_default_view.rviz
```

## 2. 장애물 감지 알고리즘 (SC-180/318)

### Obstacle Layer 동작 원리

Obstacle Layer는 LiDAR 스캔 데이터를 비용맵으로 변환합니다.

**2가지 모드:**

1. **Marking** (장애물 표시)
   - 레이저 빔이 장애물을 감지하면 비용 255 (occupied)로 표시
   - 새로운 장애물 감지

2. **Clearing** (자유공간 표시)
   - 레이저 빔이 통과한 공간을 비용 0 (free)으로 표시
   - 사라진 장애물 감지 (동적 장애물)

### 설정 파라미터

```yaml
obstacle_layer:
  plugin: "nav2_costmap_2d::ObstacleLayer"
  enabled: True
  
  scan:
    topic: /scan
    clearing: True  # 동적 장애물 감지
    marking: True   # 새 장애물 감지
    
    # 광선 추적 범위 (raytrace)
    raytrace_max_range: 0.8  # 80cm (좁은 공간)
    raytrace_min_range: 0.0
    
    # 장애물 감지 범위
    obstacle_max_range: 0.5  # 50cm (가까운 장애물)
    obstacle_min_range: 0.0
```

### 비용맵 해석

```
비용값 (Cost Value)
  0     : 자유 공간 (Free)
  1-127 : 팽창 영역 (Lethal boundary)
  128   : 팽창 공간 경계
  254   : 장애물 (Lethal)
  255   : 미지영역 (Unknown)
```

### 테스트 시나리오

```bash
# 1. 정적 장애물 테스트
#    - 로봇 앞에 고정 장애물 배치
#    - 로봇이 우회 경로로 회피

# 2. 동적 장애물 테스트
#    - 로봇 이동 중 사람이 경로 차단
#    - 로봇이 안전하게 정지 후 재경로 계획

# 3. 좁은 통로 테스트
#    - 로봇 반경보다 약간 넓은 통로 (20cm)
#    - 로봇이 안전하게 통과
```

## 3. 회피 경로 계획 (SC-181/319)

### Regulated Pure Pursuit Controller 설정

경로 추종 중 장애물을 우회하는 로직:

```yaml
FollowPath:
  plugin: "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
  
  # 속도 제어 (좁은 공간)
  desired_linear_vel: 0.15  # 15cm/s
  max_linear_accel: 0.1     # 10cm/s²
  max_angular_vel: 0.8      # 0.8rad/s (약 45도/s)
  
  # 장애물 근처에서 속도 감소
  use_approach_velocity_scaling: true      # 활성화
  min_approach_linear_velocity: 0.05       # 5cm/s 최소
  use_cost_regulated_linear_velocity_scaling: true  # 비용 기반 속도 조절
  cost_scaling_dist: 0.3                   # 30cm 내 비용 계산
  cost_scaling_gain: 2.0                   # 비용 스케일 팩터
```

**동작 원리:**

1. **경로 추종** (일반상황)
   - desired_linear_vel = 15cm/s로 이동
   
2. **장애물 근처** (30cm 이내)
   - 비용맵 비용에 따라 속도 감소
   - 가까울수록: vel = min_vel + (desired_vel - min_vel) * (1 - cost)
   
3. **임박한 충돌** (5cm 이내)
   - min_approach_linear_velocity = 5cm/s로 제한
   - 천천히 회피

### Planner 경로 재계획

```yaml
planner_server:
  expected_planner_frequency: 20.0  # 20Hz 재계획
  costmap_update_timeout: 0.5       # 500ms 대기 (빠른 반응)
```

**재계획 시나리오:**
- Local costmap 업데이트 (새로운 장애물)
- 기존 경로가 장애물과 충돌
- Planner가 새로운 경로 계산
- Controller가 새 경로로 업데이트

## 4. 안전 정지 및 재경로 탐색 (SC-182/320)

### Recovery Behaviors (복구 동작)

장애물로 인한 네비게이션 실패 시 자동 복구:

```yaml
behavior_server:
  behavior_plugins: ["wait", "backup", "spin", "drive_on_heading"]
  
  wait:        # 장애물 소멸 대기 (2초)
  backup:      # 후진 회피 (5cm)
  spin:        # 제자리 회전 (90도)
  drive_on_heading:  # 특정 방향 전진
```

**실행 순서:**

```
Navigation Failure
    ↓
1. Wait (2초 대기) → 장애물 소멸?
    ↓ (실패)
2. Backup (5cm 후진)
    ↓
3. Spin (90도 회전)
    ↓
4. Retry Path Planning
    ↓
5. If still failed → Send error to FMS
```

### FMS 에러 처리 (진행중)

**nav2_params.yaml 추가 필요:**

```yaml
# BT Navigator - 재경로 탐색 설정
bt_navigator:
  ros__parameters:
    # Nav2 기본 제공 트리 사용 (재경로 탐색 포함)
    default_nav_to_pose_bt_xml: "nav2_bt_navigator/navigate_to_pose_w_replanning_and_recovery.xml"
```

**에러 알림 (FMS에서 구현예정):**

```python
def _handle_navigation_failure(self, robot_id: str, error_msg: str):
    """
    경로 계획 실패 시 FMS에 알림
    """
    logger.error(f"Navigation failure for {robot_id}: {error_msg}")
    
    # 에러 발행
    error_alert = ErrorAlert()
    error_alert.robot_id = robot_id
    error_alert.error_type = "NAVIGATION_FAILURE"
    error_alert.error_message = error_msg
    self.error_alert_pub.publish(error_alert)
    
    # 재시도 (지수 백오프)
    retry_delay = 2.0
    threading.Timer(retry_delay, lambda: self._retry_navigation(robot_id)).start()
```

## 파라미터 정리

### Local Costmap (장애물 감지)
| 파라미터 | 값 | 설명 |
|---------|-----|------|
| update_frequency | 30Hz | 센서 데이터 처리 빈도 |
| resolution | 0.01m | 1cm 해상도 |
| width/height | 100 | 1m × 1m 로컬 맵 |
| obstacle_max_range | 0.5m | 50cm 내 장애물 감지 |
| raytrace_max_range | 0.8m | 80cm 광선 추적 |

### Inflation Layer (안전 여유)
| 파라미터 | 값 | 설명 |
|---------|-----|------|
| inflation_radius | 0.08m | 8cm 팽창 (로봇 5.5cm + 여유) |
| cost_scaling_factor | 1.0 | 선형 비용 증가 |

### Controller (경로 추종)
| 파라미터 | 값 | 설명 |
|---------|-----|------|
| desired_linear_vel | 0.15m/s | 목표 속도 15cm/s |
| cost_scaling_dist | 0.3m | 30cm 내 비용 계산 |
| min_approach_linear_velocity | 0.05m/s | 최소 5cm/s |

## 테스트 계획

### 1단계: 센서 데이터 검증
```bash
# LiDAR 스캔 확인
ros2 topic echo /scan

# Local Costmap 시각화
ros2 run rviz2 rviz2
# Add: LocalCostmap (topic: /pinky1/local_costmap/costmap)
```

### 2단계: 장애물 감지 테스트
```bash
# 로봇 앞에 박스 배치 (20cm 거리)
# costmap에서 obstacle로 표시되는지 확인
# 장애물 제거 후 costmap에서 제거되는지 확인
```

### 3단계: 경로 회피 테스트
```bash
# 목표 지점으로 네비게이션 시작
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{
  pose: {
    header: {frame_id: "map"},
    pose: {position: {x: 1.0, y: 0.5}, orientation: {w: 1.0}}
  }
}'

# 이동 중 장애물 배치
# 로봇이 우회 경로로 회피하는지 확인
```

### 4단계: 동적 장애물 테스트
```bash
# 로봇 경로 중간에 사람 이동
# 로봇이 안전하게 정지 후 재경로 계획하는지 확인
```

## 파라미터 튜닝 가이드

### 속도가 너무 느린 경우
- `desired_linear_vel` 증가 (0.15 → 0.20)
- `cost_scaling_dist` 감소 (0.3 → 0.2)

### 좁은 통로에서 막히는 경우
- `inflation_radius` 감소 (0.08 → 0.07)
- `cost_scaling_factor` 증가 (1.0 → 1.5)

### 좌우로 진동하는 경우
- `lookahead_dist` 증가 (0.08 → 0.10)
- `max_angular_vel` 감소 (0.8 → 0.6)

### 장애물 감지 안 되는 경우
- `obstacle_max_range` 확인 (0.5m 이상?)
- `raytrace_max_range` 증가 (0.8 → 1.0)

## 관련 파일

- **설정**: `mobile_robot/params/nav2_params.yaml`
- **Launch**: `mobile_robot/launch/bringup_launch.py`
- **FMS** (연동): `fms/fms/fms_node.py`

## ROS2 디버깅 명령어

```bash
# 1. Node 상태 확인
ros2 node list

# 2. Topic 모니터링
ros2 topic echo /pinky1/local_costmap/costmap
ros2 topic echo /pinky1/controller_server/computed_plan

# 3. Service 호출
ros2 service call /pinky1/global_costmap/get_costmap nav2_msgs/srv/GetCostmap {}

# 4. TF 트리 확인
ros2 run tf2_tools view_frames.py

# 5. Parameter 확인
ros2 param get /pinky1/controller_server desired_linear_vel

# 6. Log 실시간 모니터링
ros2 run rclcpp_components component_container --ros-args -l debug
```

## 결론

Nav2의 Obstacle Layer, Planner, Controller를 조합하여 동적 장애물 회피가 가능합니다.

- **센서**: LiDAR 데이터 30Hz 처리
- **감지**: 50cm 이내 장애물 감지
- **회피**: 비용 기반 속도 조절 + 경로 재계획
- **안전**: Recovery behaviors로 자동 복구

모든 파라미터는 `nav2_params.yaml`에서 관리되며, 실시간 튜닝이 가능합니다.
