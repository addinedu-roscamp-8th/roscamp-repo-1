# Kitchmatics FMS 통합 테스트 가이드

## 테스트 개요
이 문서는 완전한 End-to-End 통합 테스트를 수행하는 절차를 안내합니다.

---

## Phase 1: 로봇 실행 (사전 준비)

**체크리스트 문서 참조:**
```bash
cat /home/gw/kitchmatics/roscamp-repo-1/ROBOT_LAUNCH_CHECKLIST.md
```

**실행 순서:**
1. Pinky1, Pinky2 (필수) - SSH로 실행
2. Pinky3 (선택) - SSH로 실행
3. ArmA, ArmB (필수) - 물리적 접근으로 실행

**검증:**
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
./scripts/verify_system.sh
```

모든 로봇이 정상 실행되면 다음 단계로 진행하세요.

---

## Phase 2: Main PC 시스템 실행

### 2.1 Domain Bridge 실행 (백그라운드)

**목적:** 서로 다른 ROS_DOMAIN_ID 간 토픽을 브릿지

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25

# 백그라운드 실행
ros2 run domain_bridge domain_bridge fms/config/domain_bridge_complete.yaml > /tmp/domain_bridge.log 2>&1 &

# PID 저장
echo $! > /tmp/domain_bridge.pid
```

**로그 확인:**
```bash
tail -f /tmp/domain_bridge.log
```

**예상 출력:**
```
[INFO] [domain_bridge]: Starting Domain Bridge
[INFO] [domain_bridge]: Bridging from domain 11 to 25: /pinky1/odom
[INFO] [domain_bridge]: Bridging from domain 12 to 25: /pinky2/odom
...
```

---

### 2.2 FMS 실행 (백그라운드)

**목적:** Fleet Management System 실행 및 로봇 관리

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25

# 백그라운드 실행
ros2 launch fms fms_closed_network.launch.py > /tmp/fms.log 2>&1 &

# PID 저장
echo $! > /tmp/fms.pid
```

**로그 확인:**
```bash
tail -f /tmp/fms.log
```

**예상 출력:**
```
[INFO] [fms_node]: FMS Node starting...
[INFO] [fms_node]: Registered robot: pinky1
[INFO] [fms_node]: Registered robot: pinky2
[INFO] [order_handler]: Order handler initialized
[INFO] [fleet_controller]: Fleet controller ready
```

---

## Phase 3: 시스템 검증

### 3.1 Domain Bridge 검증

**토픽 브릿지 확인:**
```bash
export ROS_DOMAIN_ID=25
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

# Pinky 토픽이 Domain 25에서 보이는지 확인
ros2 topic list | grep -E "pinky1|pinky2"

# 예상 출력:
# /pinky1/odom
# /pinky1/amcl_pose
# /pinky1/cmd_vel
# /pinky2/odom
# /pinky2/amcl_pose
# /pinky2/cmd_vel
```

**토픽 데이터 확인:**
```bash
# Pinky1 Odometry
ros2 topic echo /pinky1/odom --once

# Pinky1 AMCL Pose
ros2 topic echo /pinky1/amcl_pose --once

# Pinky2 Odometry
ros2 topic echo /pinky2/odom --once
```

**Cooking 관련 토픽 확인:**
```bash
# FMS → Cooking 토픽
ros2 topic list | grep cooking

# 예상 출력:
# /cooking/order
# /cooking/loading_complete
# /fms/pickup_arrival
```

---

### 3.2 FMS 검증

**Fleet Status 확인:**
```bash
export ROS_DOMAIN_ID=25
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

ros2 topic echo /fms/fleet_status --once
```

**예상 출력 (JSON):**
```json
{
  "robots": [
    {
      "robot_id": "pinky1",
      "status": "idle",
      "battery_level": 85.0,
      "current_position": {"x": 0.0, "y": 0.0, "theta": 0.0}
    },
    {
      "robot_id": "pinky2",
      "status": "idle",
      "battery_level": 90.0,
      "current_position": {"x": 0.0, "y": 0.0, "theta": 0.0}
    }
  ]
}
```

**로봇 등록 확인:**
```bash
# FMS 로그에서 로봇 등록 메시지 확인
grep "Registered robot" /tmp/fms.log

# 예상 출력:
# [INFO] [fms_node]: Registered robot: pinky1
# [INFO] [fms_node]: Registered robot: pinky2
```

---

### 3.3 통합 토픽 플로우 확인

**End-to-End 토픽 체인:**
```
Customer GUI → /fms/order → FMS → /cooking/order → Robot Arm
Robot Arm → /cooking/loading_complete → FMS → /pinky1/navigate_to_pose → Pinky1
Pinky1 → /pinky1/amcl_pose → Domain Bridge → /pinky1/amcl_pose (Domain 25) → FMS
```

**토픽 모니터링 스크립트:**
```bash
#!/bin/bash
export ROS_DOMAIN_ID=25
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

echo "=== FMS 입력 토픽 ==="
ros2 topic info /fms/order

echo "=== FMS 출력 토픽 ==="
ros2 topic info /cooking/order
ros2 topic info /fms/pickup_arrival

echo "=== Pinky 토픽 (브릿지됨) ==="
ros2 topic info /pinky1/odom
ros2 topic info /pinky1/amcl_pose
ros2 topic info /pinky1/cmd_vel
```

---

## Phase 4: 통합 테스트 시나리오

### 시나리오 1: 주문 생성 및 로봇 할당

**1. 주문 발행 (수동):**
```bash
export ROS_DOMAIN_ID=25
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

ros2 topic pub --once /fms/order fleet_interfaces/msg/Order \
  '{order_id: "TEST-001", items: ["sandwich"], table_number: 5, priority: 1}'
```

**2. FMS 로그 확인:**
```bash
tail -f /tmp/fms.log | grep "TEST-001"
```

**예상 출력:**
```
[INFO] [order_handler]: Received order: TEST-001
[INFO] [fleet_controller]: Assigning robot for order TEST-001
[INFO] [fleet_controller]: Assigned pinky1 to order TEST-001
[INFO] [fms_node]: Publishing cooking order for TEST-001
```

**3. Cooking Order 확인:**
```bash
ros2 topic echo /cooking/order
```

**4. Pickup Arrival 확인:**
```bash
# FMS가 로봇을 pickup_spot으로 이동시켰는지 확인
ros2 topic echo /fms/pickup_arrival
```

---

### 시나리오 2: Navigation 명령 테스트

**1. 수동으로 Pinky1에게 목표 전송:**
```bash
export ROS_DOMAIN_ID=11
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

ros2 topic pub --once /pinky1/navigate_to_pose geometry_msgs/msg/PoseStamped \
  '{header: {frame_id: "map"}, pose: {position: {x: 1.0, y: 0.5, z: 0.0}, orientation: {w: 1.0}}}'
```

**2. 로봇 이동 확인:**
```bash
# Pinky1의 현재 위치 모니터링
export ROS_DOMAIN_ID=11
ros2 topic echo /pinky1/amcl_pose
```

**3. FMS에서 위치 확인:**
```bash
# Domain 25에서 브릿지된 토픽 확인
export ROS_DOMAIN_ID=25
ros2 topic echo /pinky1/amcl_pose
```

---

### 시나리오 3: 완전한 Order Flow

**전제조건:**
- Robot Arms (armA, armB) 실행 중
- Pinky 로봇들 대기 위치에 있음

**1. Customer GUI 또는 수동 주문:**
```bash
export ROS_DOMAIN_ID=25
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

ros2 topic pub --once /fms/order fleet_interfaces/msg/Order \
  '{order_id: "FULL-TEST-001", items: ["sandwich", "sauce"], table_number: 3, priority: 1}'
```

**2. 플로우 모니터링:**

**터미널 1 - FMS 로그:**
```bash
tail -f /tmp/fms.log
```

**터미널 2 - Cooking Order:**
```bash
export ROS_DOMAIN_ID=25
ros2 topic echo /cooking/order
```

**터미널 3 - Robot Pose:**
```bash
export ROS_DOMAIN_ID=25
ros2 topic echo /pinky1/amcl_pose
```

**터미널 4 - Fleet Status:**
```bash
export ROS_DOMAIN_ID=25
ros2 topic echo /fms/fleet_status
```

**3. 예상 이벤트 순서:**
```
1. FMS receives order → FULL-TEST-001
2. FMS assigns robot → pinky1
3. FMS publishes cooking order → /cooking/order
4. Robot Arm starts cooking
5. FMS sends pinky1 to pickup_spot
6. Pinky1 arrives at pickup_spot
7. FMS publishes pickup arrival → /fms/pickup_arrival
8. Robot Arm loads food
9. Robot Arm publishes loading_complete → /cooking/loading_complete
10. FMS sends pinky1 to table_3
11. Pinky1 arrives at table_3
12. Customer confirms receipt (GUI)
13. FMS sends pinky1 back to pinky_spot
```

---

## Phase 5: 문제 분석 및 디버깅

### 5.1 Domain Bridge 문제

**증상:** Pinky 토픽이 Domain 25에서 안보임

**진단:**
```bash
# Domain Bridge 로그 확인
grep -i "error\|warn" /tmp/domain_bridge.log

# Domain Bridge 프로세스 확인
ps aux | grep domain_bridge

# 설정 파일 확인
cat /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml
```

**해결:**
```bash
# Domain Bridge 재시작
kill $(cat /tmp/domain_bridge.pid)
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25
ros2 run domain_bridge domain_bridge fms/config/domain_bridge_complete.yaml > /tmp/domain_bridge.log 2>&1 &
echo $! > /tmp/domain_bridge.pid
```

---

### 5.2 FMS 로봇 등록 실패

**증상:** FMS가 로봇을 찾지 못함

**진단:**
```bash
# FMS 로그 확인
grep "Registered robot" /tmp/fms.log

# Fleet Status 확인
ros2 topic echo /fms/fleet_status --once

# 각 Domain에서 로봇 토픽 확인
export ROS_DOMAIN_ID=11 && ros2 topic list | grep pinky1
export ROS_DOMAIN_ID=12 && ros2 topic list | grep pinky2
```

**해결:**
1. Domain Bridge가 실행 중인지 확인
2. 로봇 Navigation이 실행 중인지 확인
3. FMS 설정 파일에서 로봇 정보 확인:
   ```bash
   cat /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml
   ```

---

### 5.3 토픽 연결 문제

**증상:** 토픽은 보이지만 데이터가 안옴

**진단:**
```bash
# 토픽 정보 확인 (publisher/subscriber 수)
export ROS_DOMAIN_ID=25
ros2 topic info /pinky1/odom

# 토픽 Hz 확인
ros2 topic hz /pinky1/odom

# 토픽 Echo 확인
ros2 topic echo /pinky1/odom --once
```

**해결:**
```bash
# ROS2 Daemon 재시작
ros2 daemon stop
ros2 daemon start

# DDS Discovery 확인
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
```

---

### 5.4 Navigation 명령 실패

**증상:** 로봇이 이동 명령을 받지 못함

**진단:**
```bash
# Pinky1에서 직접 확인 (SSH)
ssh pinky@192.168.1.7
export ROS_DOMAIN_ID=11
source /opt/ros/humble/setup.bash

# Nav2 노드 확인
ros2 node list | grep -E "bt_navigator|controller_server|planner_server"

# Goal 토픽 확인
ros2 topic echo /pinky1/navigate_to_pose
```

**해결:**
1. Nav2 노드가 모두 실행 중인지 확인
2. AMCL이 초기화되었는지 확인 (initial pose 설정)
3. Costmap이 정상인지 확인

---

## Phase 6: 테스트 리포트 생성

### 테스트 결과 템플릿

```markdown
# Kitchmatics FMS 통합 테스트 리포트

**날짜:** 2026-02-26
**테스터:** [이름]

## 1. 시스템 구성
- [ ] Pinky1 실행 완료
- [ ] Pinky2 실행 완료
- [ ] Pinky3 실행 완료 (선택)
- [ ] ArmA 실행 완료
- [ ] ArmB 실행 완료
- [ ] Domain Bridge 실행 완료
- [ ] FMS 실행 완료

## 2. Domain Bridge 검증
- [ ] Pinky1 토픽 브릿지 확인
- [ ] Pinky2 토픽 브릿지 확인
- [ ] Cooking 토픽 존재 확인
- [ ] FMS 토픽 존재 확인

## 3. FMS 검증
- [ ] Pinky1 등록 확인
- [ ] Pinky2 등록 확인
- [ ] Fleet Status 정상
- [ ] Order Handler 정상

## 4. 통합 테스트
- [ ] 시나리오 1: 주문 생성 및 할당 - [성공/실패]
- [ ] 시나리오 2: Navigation 명령 - [성공/실패]
- [ ] 시나리오 3: 완전한 Order Flow - [성공/실패]

## 5. 발견된 문제
1. [문제 설명]
   - 원인: [원인 분석]
   - 해결: [해결 방법]

## 6. 개선 사항
1. [개선 제안]

## 7. 결론
- 전체 시스템 상태: [정상/문제있음]
- 다음 단계: [권장사항]
```

---

## 시스템 종료

**순서대로 종료:**

```bash
# 1. FMS 종료
kill $(cat /tmp/fms.pid)

# 2. Domain Bridge 종료
kill $(cat /tmp/domain_bridge.pid)

# 3. 로봇 종료 (각 로봇 SSH 접속 후 Ctrl+C)
# Pinky1, Pinky2, Pinky3, ArmA, ArmB
```

---

## 요약

이 가이드는 완전한 End-to-End 통합 테스트를 위한 모든 단계를 포함합니다:

1. ✅ 로봇 실행 및 검증
2. ✅ Domain Bridge 실행
3. ✅ FMS 실행
4. ✅ 시스템 검증
5. ✅ 통합 테스트 시나리오
6. ✅ 문제 분석 및 디버깅
7. ✅ 테스트 리포트 생성

모든 단계를 순차적으로 진행하면서, 각 단계의 검증을 철저히 수행하세요.
