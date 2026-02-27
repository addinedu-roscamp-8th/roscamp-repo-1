# Domain Bridge 빠른 실행 가이드

## 현재 상황 요약

### ✅ 좋은 점
- **Namespace 전략이 올바름**: 로봇은 namespace 없이 동작, 브릿지가 Main PC에서만 추가
- **Action 브릿징 구현됨**: navigate_to_pose, follow_waypoints 지원
- **Domain ID 체계 명확**: Main PC=25, pinky1=11, pinky2=12, armA=20, armB=21

### ⚠️ 개선 필요
- **누락 토픽**: odom, scan, cmd_vel, goal_pose 추가 필요
- **로봇팔 브릿징**: 별도 설정 필요
- **QoS 정책**: 명시적 설정 권장

---

## 빠른 시작

### 옵션 1: 현재 설정으로 테스트 (최소 기능)

```bash
# Main PC에서 실행
ROS_DOMAIN_ID=25 ros2 launch fms domain_bridges.launch.py
```

**브릿지되는 토픽**:
- ✅ /pinky1/amcl_pose, /pinky2/amcl_pose
- ✅ /pinky1/battery/voltage, /pinky2/battery/voltage
- ✅ /pinky1/initialpose, /pinky2/initialpose
- ✅ Actions: navigate_to_pose, follow_waypoints
- ❌ odom, scan, cmd_vel (누락)

### 옵션 2: 개선된 설정으로 테스트 (권장)

```bash
# Terminal 1: pinky1 bridge (improved)
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky1_improved.yaml

# Terminal 2: pinky2 bridge (improved)
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky2_improved.yaml

# Terminal 3: Robot arms bridge
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_arms.yaml
```

**브릿지되는 토픽**:
- ✅ 모든 센서 토픽 (amcl_pose, odom, scan, battery)
- ✅ 모든 제어 토픽 (cmd_vel, initialpose, goal_pose)
- ✅ 로봇팔 토픽 (arm_a/cmd, arm_b/cmd, verify/cmd 등)
- ✅ FMS ↔ Coordinator 통신 (cooking/order, loading_complete 등)

---

## 빠른 테스트

### 1. 토픽 확인

```bash
# Main PC에서 모바일 로봇 토픽 확인
ROS_DOMAIN_ID=25 ros2 topic list | grep pinky1

# 예상 출력:
# /pinky1/amcl_pose
# /pinky1/odom
# /pinky1/scan
# /pinky1/battery/voltage
# /pinky1/battery/present
# /pinky1/initialpose
# /pinky1/cmd_vel
# /pinky1/goal_pose

# Main PC에서 로봇팔 토픽 확인
ROS_DOMAIN_ID=25 ros2 topic list | grep arm

# 예상 출력:
# /arm_a/cmd
# /arm_a/status
# /arm_b/cmd
# /arm_b/status
# /verify/cmd
# /verify/status
```

### 2. 데이터 수신 테스트

```bash
# pinky1 위치 데이터 수신
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose --once

# pinky1 주행거리계 수신
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/odom --once

# 배터리 상태 수신
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/battery/voltage --once

# Arm A 상태 수신
ROS_DOMAIN_ID=25 ros2 topic echo /arm_a/status
```

### 3. 명령 전송 테스트

```bash
# pinky1에 속도 명령 전송
ROS_DOMAIN_ID=25 ros2 topic pub /pinky1/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" --once

# Arm A에 명령 전송
ROS_DOMAIN_ID=25 ros2 topic pub /arm_a/cmd std_msgs/msg/String \
  "data: 'TEST_JOB|pick_ham'" --once

# pinky1 초기 위치 설정
ROS_DOMAIN_ID=25 ros2 topic pub /pinky1/initialpose \
  geometry_msgs/msg/PoseWithCovarianceStamped \
  "{header: {frame_id: 'map'}, pose: {pose: {position: {x: 0.0, y: 0.0}}}}" --once
```

### 4. Navigation Action 테스트

```bash
# pinky1에 목표 지점 전송
ROS_DOMAIN_ID=25 ros2 action send_goal /pinky1/navigate_to_pose \
  nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: 'map'}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}}}}"

# Action 리스트 확인
ROS_DOMAIN_ID=25 ros2 action list | grep pinky1
```

---

## 토픽 매핑 참조

### Mobile Robot (pinky1)

| 로봇 측 (Domain 11) | Main PC 측 (Domain 25) | 방향 | 설명 |
|-------------------|---------------------|------|------|
| /amcl_pose | /pinky1/amcl_pose | Robot→Main | 위치 추정 |
| /odom | /pinky1/odom | Robot→Main | 주행거리계 |
| /scan | /pinky1/scan | Robot→Main | LiDAR |
| /battery/voltage | /pinky1/battery/voltage | Robot→Main | 배터리 전압 |
| /battery/present | /pinky1/battery/present | Robot→Main | 배터리 연결 |
| /initialpose | /pinky1/initialpose | Main→Robot | 초기 위치 |
| /cmd_vel | /pinky1/cmd_vel | Main→Robot | 속도 명령 |
| /goal_pose | /pinky1/goal_pose | Main→Robot | 목표 위치 |
| /navigate_to_pose | /pinky1/navigate_to_pose | Main↔Robot | 내비게이션 액션 |
| /follow_waypoints | /pinky1/follow_waypoints | Main↔Robot | 경로 추종 액션 |

### Robot Arms

| 토픽 | Domain | 방향 | 설명 |
|------|--------|------|------|
| /arm_a/cmd | 20 | Main→armA | Arm A 명령 |
| /arm_a/status | 20 | armA→Main | Arm A 상태 |
| /arm_b/cmd | 21 | Main→armB | Arm B 명령 |
| /arm_b/status | 21 | armB→Main | Arm B 상태 |
| /verify/cmd | 21 | Main→armB | 검증 명령 |
| /verify/status | 21 | armB→Main | 검증 상태 |
| /fms/pickup_arrival | 20, 21 | Main→Arms | 픽업 도착 알림 |
| /cooking/order | 20, 21 | Main→Arms | 조리 주문 |
| /cooking/loading_complete | 21 | armB→Main | 로딩 완료 |

---

## 문제 해결

### "토픽이 안 보여요"

```bash
# 1. Domain bridge 실행 확인
ps aux | grep domain_bridge

# 2. Domain ID 확인
echo $ROS_DOMAIN_ID  # 25여야 함

# 3. 로봇이 토픽 발행하는지 확인
ROS_DOMAIN_ID=11 ros2 topic list
ROS_DOMAIN_ID=11 ros2 topic hz /amcl_pose

# 4. Network 연결 확인
ping 192.168.1.7  # pinky1
ping 192.168.1.6  # pinky2
ping 192.168.1.4  # armA
ping 192.168.1.10 # armB
```

### "데이터가 섞여요 (pinky1과 pinky2)"

```bash
# remap 설정 확인
cat fms/config/domain_bridge_pinky1.yaml | grep remap
# 출력: remap: pinky1/amcl_pose

cat fms/config/domain_bridge_pinky2.yaml | grep remap
# 출력: remap: pinky2/amcl_pose

# 두 로봇이 서로 다른 데이터를 보내는지 확인
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose &
ROS_DOMAIN_ID=25 ros2 topic echo /pinky2/amcl_pose &
# 각각 다른 위치 데이터가 출력되어야 함
```

### "Action이 안 돼요"

```bash
# Action 서버가 있는지 확인 (로봇 측)
ROS_DOMAIN_ID=11 ros2 action list

# Main PC 측에서 확인
ROS_DOMAIN_ID=25 ros2 action list | grep pinky1

# domain_bridge_pinky1.yaml에 action 설정 확인
cat fms/config/domain_bridge_pinky1.yaml | grep -A3 "actions:"
```

### "로봇팔 통신 안 돼요"

```bash
# 1. domain_bridge_arms.yaml 실행 확인
ps aux | grep domain_bridge | grep arms

# 2. 로봇팔이 토픽 발행하는지 확인
ROS_DOMAIN_ID=20 ros2 topic list  # armA
ROS_DOMAIN_ID=21 ros2 topic list  # armB

# 3. Coordinator node 실행 확인
ROS_DOMAIN_ID=25 ros2 node list | grep coordinator

# 4. 토픽 에코 테스트
ROS_DOMAIN_ID=25 ros2 topic echo /arm_a/status
```

---

## 다음 단계

### 1단계: 기본 테스트 (30분)
```bash
# 개선된 설정 파일 사용
cd /home/gw/kitchmatics/roscamp-repo-1

# pinky1 테스트
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky1_improved.yaml

# 다른 터미널에서 토픽 확인
ROS_DOMAIN_ID=25 ros2 topic list | grep pinky1
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose --once
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/odom --once
```

### 2단계: 다중 로봇 테스트 (1시간)
```bash
# 모든 브릿지 실행
# Terminal 1
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky1_improved.yaml

# Terminal 2
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky2_improved.yaml

# Terminal 3: 토픽 충돌 없는지 확인
ROS_DOMAIN_ID=25 ros2 topic hz /pinky1/amcl_pose
ROS_DOMAIN_ID=25 ros2 topic hz /pinky2/amcl_pose
```

### 3단계: 로봇팔 통합 (1시간)
```bash
# Terminal 4: 로봇팔 브릿지
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_arms.yaml

# Terminal 5: 로봇팔 통신 테스트
ROS_DOMAIN_ID=25 ros2 topic echo /arm_a/status
ROS_DOMAIN_ID=25 ros2 topic pub /arm_a/cmd std_msgs/msg/String "data: 'TEST'"
```

### 4단계: Launch 파일 통합 (1시간)
```bash
# fms/launch/domain_bridges.launch.py 수정하여
# 로봇팔 브릿지 노드 추가

# 실행
ROS_DOMAIN_ID=25 ros2 launch fms domain_bridges.launch.py
```

---

## 체크리스트

### 설정 파일 준비
- [ ] `domain_bridge_pinky1_improved.yaml` 확인
- [ ] `domain_bridge_pinky2_improved.yaml` 생성 (pinky1 기반 복사)
- [ ] `domain_bridge_arms.yaml` 확인
- [ ] Launch 파일에 arms_bridge 노드 추가

### 네트워크 확인
- [ ] Main PC와 모든 로봇 ping 성공
- [ ] ROS_DOMAIN_ID 환경변수 설정 확인
- [ ] 방화벽/라우터 설정 확인

### 기능 테스트
- [ ] pinky1 토픽 브릿징 확인
- [ ] pinky2 토픽 브릿징 확인
- [ ] 토픽 충돌 없음 확인
- [ ] cmd_vel 양방향 통신 확인
- [ ] Navigation action 동작 확인
- [ ] 로봇팔 통신 확인
- [ ] FMS ↔ Coordinator 통신 확인

### 성능 확인
- [ ] 토픽 주기 정상 (ros2 topic hz)
- [ ] 지연 시간 측정
- [ ] CPU/메모리 사용량 확인
- [ ] 네트워크 대역폭 확인

---

## 참고 파일

```
/home/gw/kitchmatics/roscamp-repo-1/
├── DOMAIN_BRIDGE_REPORT.md           # 상세 분석 보고서
├── DOMAIN_BRIDGE_ANALYSIS.md         # 기술 분석 (영문)
├── DOMAIN_BRIDGE_QUICK_GUIDE.md      # 이 파일
└── fms/config/
    ├── domain_bridge_pinky1.yaml              [현재 사용 중]
    ├── domain_bridge_pinky1_improved.yaml     [개선 버전]
    ├── domain_bridge_pinky2.yaml              [현재 사용 중]
    ├── domain_bridge_arms.yaml                [로봇팔용, 신규]
    ├── domain_bridge_complete.yaml            [통합 버전, 참고용]
    └── domain_bridge_nonamespace.yaml         [실험용]
```

---

**빠른 시작**:
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge fms/config/domain_bridge_pinky1_improved.yaml
```

**문제 발생 시**: DOMAIN_BRIDGE_REPORT.md 섹션 10 참조
