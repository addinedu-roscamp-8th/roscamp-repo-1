# ROS2 내비게이션 검증 보고서
**작성일: 2026-02-26**
**시스템: Kitchmatics FMS 및 Pinky 모바일 로봇**

---

## 요약

**상태: 치명적 문제 발견**

Kitchmatics FMS용 ROS2 내비게이션 시스템에 즉각적인 해결이 필요한 치명적 문제가 여러 개 있습니다:

1. **Pinky 로봇에서 Nav2 미실행**: pinky1/pinky2에서 내비게이션 노드가 활성화되지 않음
2. **AMCL 위치 추정 비활성**: AMCL 자세 추정값이 발행되지 않음
3. **Domain Bridge가 내비게이션 토픽을 전달하지 않음**: Nav2 액션 서버에 접근 불가
4. **내비게이션 서비스 사용 불가**: /navigate_to_pose 액션 서버가 응답하지 않음

---

## 현재 시스템 아키텍처

### 인프라
- **메인 PC (Domain ID 25)**:
  - FMS 노드: 실행 중
  - Domain Bridge: 설정됨, 완전히 동작하지 않음
  - Coordinator: 실행 중

- **Pinky1 (Domain ID 11, IP: 192.168.1.7)**:
  - cooking_interface_node: 실행 중
  - kitchmatics_bridge_11: 실행 중
  - **Nav2 스택: 미실행**
  - 예상: /pinky1/navigate_to_pose 액션 서버

- **Pinky2 (Domain ID 12, IP: 192.168.1.6)**:
  - 상태: SSH 접근 불가
  - 예상: /pinky2/navigate_to_pose가 포함된 내비게이션 스택

- **Pinky3 (Domain ID 13, IP: 192.168.1.11)**:
  - 설정에서 비활성화됨

---

## 상세 조사 결과

### 1. 내비게이션 설정 (설정 완료)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/mobile_robot/params/nav2_params.yaml`

**AMCL 설정**:
```yaml
amcl:
  max_particles: 3000        # 소형 로봇에 적합
  min_particles: 500         # 양호
  laser_likelihood_max_dist: 0.5
  transform_tolerance: 0.5   # 500ms 허용
  scan_topic: scan
  set_initial_pose: false    # FMS가 초기 자세 제공
```

**Local Costmap**:
```yaml
local_costmap:
  update_frequency: 30.0     # 30Hz
  robot_radius: 0.055        # 5.5cm
  inflation_radius: 0.08     # 총 8cm 여유 공간
```

**Global Costmap**:
```yaml
global_costmap:
  inflation_radius: 0.10     # 경로 계획용 10cm
```

**컨트롤러 (RPP)**:
```yaml
FollowPath:
  plugin: RegulatedPurePursuitController
  desired_linear_vel: 0.15   # 15cm/s
  lookahead_dist: 0.08       # 8cm (소형 로봇에 맞게 조정)
```

**플래너 (A*를 사용하는 NavFn)**:
```yaml
GridBased:
  plugin: NavfnPlanner
  use_astar: true
  tolerance: 0.02
```

### 상태: 소형 로봇에 적합하게 설정됨

---

### 2. Domain Bridge 설정 (설정 완료, 완전히 동작하지 않음)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml`

**Pinky1 토픽 설정 상태**:
- /pinky1/amcl_pose (11→25, RELIABLE)
- /pinky1/scan (11→25, BEST_EFFORT)
- /pinky1/odom (11→25, BEST_EFFORT)
- /pinky1/initialpose (25→11, RELIABLE)
- /pinky1/navigate_to_pose/_action/* (양방향)

**Pinky2 토픽 설정 상태**:
- Pinky1과 동일하게 모두 설정됨

**Domain Bridge 상태**:
- 메인 PC(Domain ID 25)에서 브리지 실행 중
- 내비게이션 토픽이 제대로 전달되지 않음
- 도메인 25에서 AMCL 자세가 표시되지 않음
- 도메인 25에서 내비게이션 액션 서버에 접근 불가

---

### 3. FMS 플릿 컨트롤러 (부분적으로 동작)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py`

**플릿 상태** (`/fms/fleet_status` 토픽에서):
```
Robot: pinky1
  Status: IDLE
  Position: (0.0, 0.0, 0.0)  ← 실제 자세 없음 (AMCL에서 제공되어야 함)
  Battery: 0.0V (연결 안 됨)

Robot: pinky2
  Status: IDLE
  Position: 사용 불가
```

**문제점**:
- 로봇 위치가 실제 AMCL 자세 대신 (0,0,0)으로 표시됨
- 배터리 전압이 업데이트되지 않음
- 내비게이션 피드백에서 로봇 상태가 업데이트되지 않음

---

### 4. 내비게이션 노드 상태

**Pinky1 (Domain ID 11)**:
```
활성 노드:
  /cooking_interface_node
  /kitchmatics_bridge_11

누락된 노드:
  ✗ /amcl
  ✗ /map_server
  ✗ /planner_server
  ✗ /controller_server
  ✗ /behavior_server
  ✗ /bt_navigator
  ✗ /velocity_smoother
```

**Pinky2 (Domain ID 12)**:
```
상태: 접근 불가
예상 노드가 실행되지 않음
```

---

### 5. AMCL 위치 추정 상태 (비활성)

**예상 흐름**:
```
Pinky1 (Domain 11):
  /scan (LiDAR) → AMCL → /amcl_pose
           ↓
    Domain Bridge (25)
           ↓
      FMS 노드
```

**실제 상태**:
- AMCL 노드 미실행
- 도메인 11에 /amcl_pose 토픽 없음
- 도메인 25에 /pinky1/amcl_pose 없음
- FMS로의 위치 추정 피드백 없음

---

### 6. 액션 서버 상태 (사용 불가)

**예상**:
```
/pinky1/navigate_to_pose/_action/send_goal  (Domain 25)
  ↓ (Domain Bridge)
/navigate_to_pose/_action/send_goal  (Domain 11)
```

**실제**:
- 도메인 11에서 액션 서버를 찾을 수 없음
- 도메인 25에서 브리지된 액션 서버 없음
- FMS가 내비게이션 목표를 전송할 수 없음

---

## 요구사항 검증

### 요구사항 7: /pose 업데이트로 노드 해제 트리거
**상태**: 테스트 불가
- **사유**: AMCL 자세가 발행되지 않음
- **영향**: 노드 해제 메커니즘을 검증할 수 없음
- **필요 조치**: 먼저 Nav2 스택 활성화

### 요구사항 8: 경로 충돌 해결
**상태**: 테스트 불가
- **사유**: 내비게이션 시스템이 동작하지 않음
- **영향**: 다중 로봇 경로 계획이 동작하지 않음
- **필요 조치**: 먼저 단일 로봇 내비게이션 동작 확인

### 요구사항 5: 다중 Pinky 동시 운영
**상태**: 테스트 불가
- **사유**: Pinky2 접근 불가, Pinky1에서 Nav2 미실행
- **영향**: 다중 로봇 연동 테스트 불가
- **필요 조치**: Pinky1 연결 문제 해결 후 Pinky2 처리

---

## 근본 원인 분석

### 문제 1: Nav2 스택이 실행되지 않음

**증거**:
- Pinky1에 bt_navigator, planner_server, controller_server 노드가 없음
- AMCL 노드 미실행
- nav2_params.yaml은 적절히 설정되어 있으나 사용되지 않음

**가능한 원인**:
1. pinky_navigation.launch.py가 호출되지 않음
2. Nav2 패키지 의존성이 설치되지 않음
3. Pinky 로봇 시작에서 런치 파일 경로가 잘못됨
4. 로봇 시작 시 lamp_module만 실행하고 내비게이션은 실행하지 않음

**증거**:
```bash
Pinky1에서 ps aux 결과:
  /bin/bash /home/pinky/pinky_devices/lamp_module_bringup
  → lamp 모듈만 실행, Nav2 시작 없음
```

### 문제 2: Domain Bridge가 Nav2 토픽을 전달하지 않음

**원인**: 브리지할 Nav2 토픽이 도메인 11에 존재하지 않음

**의존 관계**:
1. 먼저 Pinky1에서 Nav2가 실행되어야 함
2. 그러면 Domain Bridge가 토픽을 전달
3. FMS가 도메인 25에서 /pinky1/amcl_pose를 수신

---

## 조치 항목 (우선순위 순)

### 1단계: Pinky1에서 내비게이션 활성화 (긴급)

**Step 1**: Pinky1 시작 스크립트 수정
- 파일: `/home/pinky/pinky_pro/src/pinky_pro/pinky_bringup/...`
- 로봇 시작 순서에 Nav2 실행 추가
- 확인: `ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml`

**Step 2**: Nav2 시작 확인
```bash
ssh pinky@192.168.1.7
export ROS_DOMAIN_ID=11
source /opt/ros/jazzy/setup.bash
ros2 node list | grep -E "amcl|planner|controller|bt_navigator"
```

**Step 3**: Domain Bridge 전달 확인
```bash
# 메인 PC에서 (Domain 25)
ros2 topic list | grep pinky1/amcl_pose
ros2 action list | grep pinky1/navigate_to_pose
```

**Step 4**: 초기 자세 설정
```bash
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {
    pose: {position: {x: 0.585, y: 0.085}, orientation: {w: 1.0}},
    covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]
  }
}'
```

### 2단계: AMCL 위치 추정 테스트 (긴급)

**Step 1**: 자세 발행 확인
```bash
timeout 5 ros2 topic echo /pinky1/amcl_pose --once
```

**Step 2**: 로봇을 수동으로 이동하며 모니터링
- 실제 공간에서 Pinky1을 이동
- /pinky1/amcl_pose 업데이트 확인
- 공분산 수렴 여부 확인

**Step 3**: 자세 공분산 확인
```
예상: <0.1m² (x,y에서 잘 추정된 상태)
초기: ~0.25m² (수렴 중)
```

### 3단계: 내비게이션 목표 테스트 (긴급)

**Step 1**: 간단한 목표 전송
```bash
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{
  pose: {
    header: {frame_id: "map"},
    pose: {position: {x: 1.0, y: 0.5}, orientation: {w: 1.0}}
  }
}'
```

**Step 2**: 내비게이션 모니터링
- /pinky1/navigate_to_pose/_action/feedback 확인
- 코스트맵 업데이트 확인
- 경로 계획 확인

**Step 3**: 경로 실행 확인
- 로봇이 목표를 향해 이동해야 함
- 컨트롤러가 활성화되어 있어야 함
- 정체 시 복구 동작이 트리거되어야 함

### 4단계: Pinky2 활성화 (높음)

**Step 1**: SSH 연결 문제 해결
- 네트워크 확인: `ping 192.168.1.6`
- 방화벽/라우팅 확인
- 라우터 설정 확인

**Step 2**: Pinky2에 Nav2 설정 복제
- 1단계와 동일하지만 도메인 ID 12를 사용
- 초기 자세를 (0.585, 0.255, 0)으로 설정

**Step 3**: Domain Bridge 확인
- 도메인 25에서 /pinky2/amcl_pose 확인
- /pinky2/navigate_to_pose 액션 확인

### 5단계: 다중 로봇 연동 (보통)

**Step 1**: FMS 작업 할당 테스트
- Pinky1에 작업 할당
- 로봇이 수락하고 실행하는지 확인
- FMS fleet_status에서 자세 업데이트 확인

**Step 2**: 경로 충돌 해결 테스트
- Pinky1에 목표 전송
- Pinky2에 충돌하는 목표 전송
- FMS collision_avoidance 동작 확인

**Step 3**: 노드 해제 메커니즘 확인
- /pose 토픽 업데이트 모니터링
- 로봇이 떠날 때 노드가 해제되는지 확인
- 구역 예약 확인

---

## 모니터링할 성능 지표

내비게이션이 동작한 후:

### 내비게이션 성능
```
지표                          목표        예상
목표까지 시간 (1m 거리)        30-45초     < 60초
내비게이션 성공률              95%         100% (작은 공간)
경로 재계획 빈도               2-5 Hz      부드러운 궤적
최대 경로 편차                 0.1m        < 0.15m
```

### AMCL 위치 추정
```
초기화 후 자세 공분산           < 0.01m²    안정적 (5초 후)
공분산 수렴 시간               < 10초      빠른 수렴
자세 추정 안정성               +/- 0.05m   낮은 드리프트
업데이트 빈도                  20 Hz       지속적
```

### 다중 로봇 연동
```
동시 로봇 운영                 3대         간섭 없이 동시 운영
노드 해제 시간                 < 2초       빠른 구역 전환
경로 충돌 해결                 100%        부드러운 재계획
충돌 방지 사고                 0건         완전한 안전
```

---

## 기술 노트

### AMCL 설정 근거
- **min_particles: 500**: 텍스처가 풍부한 작은 공간에 충분
- **max_particles: 3000**: 초기화 중 수렴 가능
- **laser_model_type: likelihood_field**: 구조화된 방에 최적
- **update_min_d: 0.01m**: 1cm 이동마다 AMCL 트리거 (정밀)
- **update_min_a: 0.05rad**: 약 3도 회전마다 AMCL 트리거 (정밀)

### 코스트맵 설정 근거
- **local_costmap inflation: 0.08m**: 로봇(5.5cm) + 2.5cm 안전 여유
- **global_costmap inflation: 0.10m**: 경로 계획 여유
- **raytrace_max_range: 0.8m**: 최대 80cm까지 장애물 감지
- **obstacle_max_range: 0.5m**: 동적 장애물 안전 여유

### 컨트롤러 설정 근거
- **lookahead_dist: 0.08m**: 정밀 경로 추종을 위한 8cm 전방 주시
- **desired_linear_vel: 0.15m/s**: 좁은 공간에서 15cm/s
- **rotate_to_heading: true**: 좁은 구간 전 제자리 회전
- **use_approach_velocity_scaling**: 장애물 근처에서 감속

---

## 네트워크 토폴로지

```
┌─────────────────────────────────────────────────────┐
│           메인 PC (Domain ID 25)                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  FMS 노드                                    │  │
│  │  - 작업 관리자                                │  │
│  │  - 플릿 컨트롤러                              │  │
│  │  - 구역 관리자                                │  │
│  │  - 충돌 회피                                  │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  Domain Bridge                               │  │
│  │  브리지: 11↔25, 12↔25, 13↔25, 20↔25, 21↔25  │  │
│  │  상태: ✗ Nav2 토픽이 아직 브리지되지 않음       │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
        │ Ethernet           │ Ethernet         │ Ethernet
        │ (192.168.1.7)      │ (192.168.1.6)    │ (192.168.1.11)
        │                    │                  │
┌───────────────────┐ ┌──────────────────┐ ┌─────────────────┐
│  Pinky1           │ │ Pinky2           │ │ Pinky3          │
│  Domain ID 11     │ │ Domain ID 12     │ │ Domain ID 13    │
│  ✗ Nav2 미실행     │ │ ? 접근 불가       │ │ 비활성화됨       │
│  ✓ LiDAR/휠 정상  │ │ ? 상태 불명       │ │                 │
└───────────────────┘ └──────────────────┘ └─────────────────┘
```

---

## 권장 다음 단계

1. **Pinky1에 SSH 접속**하여 시작 스크립트 확인
2. 로봇 시작 순서에 **Nav2 실행 추가**
3. **Pinky1 로봇 재시작**
4. 도메인 11에서 **Nav2 노드 확인**
5. **Domain Bridge**가 도메인 25로 토픽을 전달하는지 확인
6. 수동 목표로 **단일 로봇 내비게이션 테스트**
7. Pinky2 복구를 위해 **4단계 실행**
8. **5단계**에 따라 다중 로봇 연동 테스트

---

## 부록: 파일 위치

```
설정 파일:
  /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/params/nav2_params.yaml
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml

런치 파일:
  /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/launch/pinky_navigation.launch.py
  /home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/launch/bringup_launch.xml

FMS 소스:
  /home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py
  /home/gw/kitchmatics/roscamp-repo-1/fms/fms/fleet_controller.py

Domain Bridge:
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml
  ros2 run domain_bridge domain_bridge <config>
```

---

**보고서 상태**: 구현 준비 완료
**다음 검토**: 1단계 완료 후
**작성자**: ROS2 내비게이션 검증기
