# Kitchmatics FMS 시스템 실행 가이드

## 근본 원인 분석: "A_FAIL:busy" 에러

### 에러 설명
```
[ERROR] [sandwich_coordinator]: A finish failed: A_FAIL:busy
[ERROR] [sandwich_coordinator]: Failed to make sandwich for order ORD-20260226073129-0001
```

### 근본 원인
**위치**: `robot_arm/sandwich_arm_ws/src/mycobot_kitchen_nodes/mycobot_kitchen_nodes/recipe_executor_node.py:343`

**문제점**: Arm A (recipe_executor_node)가 이전 작업을 처리하는 중에 새로운 START 명령을 받으면 즉시 거부합니다.

**코드 분석**:
```python
def _start_internal(self, job_id: str, recipe_name: str, pause_before_last: int, goal_handle=None) -> bool:
    with self._state_lock:
        if self._run_task is not None and not self._run_task.done():
            self._publish_status(job_id, "FAIL", reason="busy")  # ← 에러 발생 지점
            return False
```

### 발생 이유

**시나리오**: 여러 주문이 빠르게 도착하는 경우
1. GUI 주문 1 → FMS가 CookingOrder를 coordinator로 전송
2. Coordinator가 주문 1 처리 시작 (Arm A가 조리 시작)
3. GUI 주문 2가 즉시 도착 → FMS가 또 다른 CookingOrder 전송
4. Coordinator가 주문 2를 시작하려 하지만, Arm A는 여전히 주문 1을 처리 중
5. **결과**: `A_FAIL:busy` 에러 발생

**시스템 플로우**:
```
GUI 주문 → FMS → /cooking/order → Coordinator → START → Arm A (recipe_executor)
                ↓
          pinky를 pickup_spot으로 내비게이션
```

### 해결 방안

**방안 1: Coordinator 큐 처리 수정 (권장)**
새 작업 시작 전 coordinator에 유휴 상태 확인 추가:
- 다음 작업 시작 전 Arm A가 이전 작업을 완료할 때까지 대기
- 활성 작업 확인을 위해 `a_status` 체크
- 에러 처리와 함께 타임아웃 구현

**방안 2: 주문 도착 속도 제한**
- GUI에서 연속 주문 사이에 지연 추가
- 빠른 임시 해결책이지만 견고하지 않음

**방안 3: Recipe Executor에 작업 큐 구현**
- 더 복잡하며, 로봇팔 코드 변경 필요
- 프로덕션에는 더 좋지만 작업량이 많음

---

## 시스템 아키텍처

### 로봇 네트워크 (폐쇄 WiFi)
| 장치 | IP | Domain ID | 역할 |
|--------|-----|-----------|------|
| gw PC | 192.168.1.3 | 25 | FMS 서버 (메인) |
| pinky1 (b4bc) | 192.168.1.7 | 11 | 이동 로봇 |
| pinky2 (e2a8) | 192.168.1.6 | 12 | 이동 로봇 |
| pinky3 (d29d) | 192.168.1.11 | 13 | 이동 로봇 (비활성) |
| jetcobot A (aa1f) | 192.168.1.4 | 20 | 로봇팔 (샌드위치) |
| jetcobot B (aa85) | 192.168.1.10 | 21 | 로봇팔 (소스) |

### 요구되는 워크플로우
1. GUI 주문 → FMS가 사용 가능한 pinky를 `pickup_spot`으로 보내고 동시에 armA로 주문 전송 (병렬)
2. armA가 음식 조리, pinky가 pickup_spot 도착
3. FMS가 `/fms/pickup_arrival`를 통해 armA에 pinky 도착 알림
4. armA가 카메라 검수 수행 후, pinky 위에 음식 배치 (pinky가 있는 경우에만)
5. armA가 음식 탑재 완료 시 `/cooking/loading_complete` 발행
6. Pinky가 테이블로 배달
7. 배달 확인 후, pinky는 `pinky_spot`으로 복귀

---

## 메인 PC 터미널 설정

### 사전 요구사항
```bash
# ROS 설치 확인
source /opt/ros/jazzy/setup.bash
ros2 --version  # ROS 2 Jazzy 표시되어야 함

# 네트워크 연결 확인
ping 192.168.1.7  # pinky1
ping 192.168.1.6  # pinky2
ping 192.168.1.4  # jetcobot A
ping 192.168.1.10 # jetcobot B
```

### 터미널 1: FMS 노드
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25

# FMS 실행 (프로덕션 모드 - 로봇팔 포함)
ros2 launch fms fms_closed_network.launch.py

# 또는 로봇팔 없이 테스트하는 경우 (스킵 모드)
ros2 launch fms fms_closed_network.launch.py skip_robot_arm:=true
```

**예상 출력**:
```
[INFO] [fms_node]: Initializing Fleet Management System...
[INFO] [fms_node]: *** ROBOT ARM MODE ENABLED ***
[INFO] [fms_node]: Registered robot pinky1 on DOMAIN_ID=11
[INFO] [fms_node]: Registered robot pinky2 on DOMAIN_ID=12
[INFO] [fms_node]: FMS running on DOMAIN_ID=25
[INFO] [fms_node]: Created navigation client for pinky1: /pinky1/navigate_to_pose
[INFO] [fms_node]: Created navigation client for pinky2: /pinky2/navigate_to_pose
[INFO] [fms_node]: GUI TCP Server listening on 0.0.0.0:9000
```

### 터미널 2: Domain Bridge
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25

# 멀티 도메인 통신을 위한 domain bridge 실행
ros2 run domain_bridge domain_bridge fms/config/domain_bridge_complete.yaml
```

**예상 출력**:
```
[INFO] [domain_bridge]: Created bridge: 11 -> 25 (pinky1)
[INFO] [domain_bridge]: Created bridge: 12 -> 25 (pinky2)
[INFO] [domain_bridge]: Created bridge: 20 -> 25 (jetcobot A)
[INFO] [domain_bridge]: Created bridge: 21 -> 25 (jetcobot B)
```

### 터미널 3: Customer GUI
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui

# PyQt 가상환경 활성화
source ~/pyqt_venv/bin/activate

# Customer GUI 실행
python src/main_fms_direct.py
```

**예상 출력**:
```
[INFO] Connecting to FMS at 192.168.1.3:9000
[INFO] Connected to FMS successfully
```

---

## 로봇 터미널 설정 (사용자가 수동으로 처리)

사용자가 로봇 터미널을 수동으로 처리한다고 하셨습니다. 참고용입니다:

### Pinky1 (SSH to 192.168.1.7)
```bash
# 터미널 1: Bringup
export ROS_DOMAIN_ID=11
ros2 launch pinky_bringup bringup_robot.launch.xml

# 터미널 2: Navigation
export ROS_DOMAIN_ID=11
ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml
```

### Pinky2 (SSH to 192.168.1.6)
```bash
# 터미널 1: Bringup
export ROS_DOMAIN_ID=12
ros2 launch pinky_bringup bringup_robot.launch.xml

# 터미널 2: Navigation
export ROS_DOMAIN_ID=12
ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml
```

### Jetcobot A (SSH to 192.168.1.4)
```bash
# 터미널 1: Recipe Executor (Arm A)
export ROS_DOMAIN_ID=20
cd ~/sandwich_arm_ws
colcon build
source install/setup.bash
ros2 launch mycobot_kitchen_nodes kitchen.launch.py
```

### Jetcobot B (SSH to 192.168.1.10)
```bash
# 터미널 1: Sauce Node (Arm B)
export ROS_DOMAIN_ID=21
cd ~/sauce_arm_ws
colcon build
source install/setup.bash
ros2 launch mycobot_sauce sauce.launch.py
```

---

## 검증 체크리스트

### 1. Domain Bridge 상태 확인
```bash
# 터미널 2 (domain bridge)에서 에러 확인
# 다음 메시지들 찾기:
# - "Created bridge: X -> 25" (각 도메인별)
# - "Failed to create bridge" 에러가 없어야 함
```

### 2. 토픽 검색 확인
```bash
# 새 터미널
export ROS_DOMAIN_ID=25
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

# FMS가 로봇 토픽을 볼 수 있는지 확인 (domain bridge 경유)
ros2 topic list | grep pinky1
# 표시되어야 함: /pinky1/amcl_pose, /pinky1/odom, /pinky1/scan 등

ros2 topic list | grep arm_a
# 표시되어야 함: /arm_a/cmd, /arm_a/status

ros2 topic list | grep cooking
# 표시되어야 함: /cooking/order, /cooking/loading_complete
```

### 3. 로봇 통신 확인
```bash
# pinky1 pose 확인 (계속 업데이트되어야 함)
ros2 topic echo /pinky1/amcl_pose --once

# Arm A 상태 확인
ros2 topic echo /arm_a/status --once
```

### 4. FMS 상태 확인
```bash
# fleet 상태 확인
ros2 topic echo /fms/fleet_status --once

# 에러 알림 확인
ros2 topic echo /fms/error_alert
```

### 5. GUI 주문 테스트
1. Customer GUI 열기 (터미널 3)
2. 테이블 1 선택
3. 메뉴 항목 추가 (M001: Ham Cheese Sandwich)
4. "주문하기" 클릭

**예상 FMS 로그**:
```
[INFO] [order_handler]: New order received: ORD-... for table 1
[INFO] [order_handler]: Available robot check result: pinky1
[INFO] [order_handler]: [STEP 1] Cooking command sent to robot arm: /cooking/command
[INFO] [order_handler]: [STEP 2] Robot assigned: pinky1
[INFO] [order_handler]: [STEP 3] Navigation started: pinky1 -> pickup_spot
```

**예상 Coordinator 로그** (jetcobot A):
```
[INFO] [sandwich_coordinator]: Received cooking order: order_id=ORD-..., menu_id=M001, sauce=, robot=pinky1
[INFO] [sandwich_coordinator]: Processing order ORD-... for robot pinky1
[INFO] [sandwich_coordinator]: start job=<job_id> recipe=ham_cheese sauce='' pause_before_last=1
[INFO] [sandwich_coordinator]: subscribers ready: A=1 B=1 V=1
```

**주의할 점**:
- `[ERROR] A finish failed: A_FAIL:busy` 표시되면, 주문이 너무 빨리 들어온 것
- 이전 주문이 완료될 때까지 기다린 후 다음 주문
- 또는 coordinator 큐 수정 구현 (위 방안 1 참조)

### 6. Pickup 도착 알림 테스트
```bash
# /fms/pickup_arrival 토픽 모니터링
ros2 topic echo /fms/pickup_arrival

# pinky1이 pickup_spot 도착 시 표시되어야 함:
# robot_id: pinky1
# order_id: ORD-...
# arrived: true
```

**Coordinator가 수신하는지 확인**:
```
[INFO] [sandwich_coordinator]: Pinky arrived at pickup: robot=pinky1, order=ORD-...
[INFO] [sandwich_coordinator]: Waiting for pinky arrival for order ORD-... (timeout=120s)
[INFO] [sandwich_coordinator]: Pinky arrived for order ORD-...
```

### 7. 탑재 완료 알림 테스트
```bash
# /cooking/loading_complete 토픽 모니터링
ros2 topic echo /cooking/loading_complete

# 음식 탑재 후 표시되어야 함:
# order_id: ORD-...
# robot_id: pinky1
# success: true
# message: "Food loaded successfully"
```

**FMS가 수신하는지 확인**:
```
[INFO] [fms_node]: Loading complete for order ORD-..., robot pinky1, success=True
[INFO] [order_handler]: Food loaded for order ORD-...
[INFO] [order_handler]: [SKIP MODE] Waiting 3 seconds before proceeding to table...
[INFO] [order_handler]: [STEP 5] Navigation started: pinky1 -> table1
```

---

## 문제 해결

### 이슈 1: "A_FAIL:busy" 에러
**증상**: Coordinator 로그에 `[ERROR] A finish failed: A_FAIL:busy` 표시

**원인**: 새 주문이 도착했을 때 이전 주문이 여전히 처리 중

**해결책**:
1. **빠른 수정**: 이전 주문이 완료될 때까지 기다린 후 다음 주문
2. **적절한 수정**: 유휴 상태 확인과 함께 coordinator 큐 구현 (위 방안 1 참조)
3. **확인**: 새 주문 전송 전 Arm A 상태 확인

### 이슈 2: Domain Bridge 작동 안 함
**증상**: FMS가 로봇 토픽을 볼 수 없음 (`ros2 topic list | grep pinky1`이 아무것도 반환 안 함)

**원인**: Domain bridge가 실행되지 않았거나 잘못 설정됨

**해결책**:
1. 터미널 2 (domain bridge)에서 에러 확인
2. Domain bridge에 `ROS_DOMAIN_ID=25` 설정 확인
3. Domain bridge 재시작: `Ctrl+C` 후 다시 실행
4. Domain bridge 설정 확인: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml`

### 이슈 3: Pinky가 움직이지 않음
**증상**: Navigation 명령이 전송되었지만 로봇이 움직이지 않음

**원인**: 여러 가능한 원인
1. AMCL이 위치 파악 안 됨 (초기 포즈 미설정)
2. Nav2가 로봇에서 실행되지 않음
3. Domain bridge가 액션 메시지를 전달하지 않음

**해결책**:
```bash
# 로봇의 AMCL pose 확인
ros2 topic echo /pinky1/amcl_pose --once

# 출력 없으면 초기 포즈가 설정되지 않은 것
# FMS가 시작 시 자동으로 초기 포즈 설정해야 함

# 로봇에서 Nav2 상태 확인 (로봇으로 SSH 접속)
ros2 node list | grep bt_navigator

# 액션 서버 가용성 확인
ros2 action list | grep navigate_to_pose
```

### 이슈 4: Pickup 도착 알림 없음
**증상**: Coordinator가 pinky 도착을 받지 못하고 120초 후 타임아웃

**원인**: FMS가 PickupArrival 메시지를 발행하지 않음

**해결책**:
1. FMS 로그에서 "Published PickupArrival" 확인
2. `/fms/pickup_arrival` 토픽 존재 확인: `ros2 topic list | grep pickup_arrival`
3. 토픽 모니터링: `ros2 topic echo /fms/pickup_arrival`
4. Domain bridge 설정에서 `/fms/pickup_arrival`이 domain 20으로 브리징되는지 확인

**Domain bridge 확인**:
```yaml
# domain_bridge_complete.yaml에 다음이 있어야 함:
- from_domain: 25
  to_domain: 20
  topics:
    /fms/pickup_arrival:
      type: fleet_interfaces/msg/PickupArrival
```

### 이슈 5: GUI 연결 실패
**증상**: GUI에 "Connection failed" 또는 타임아웃 표시

**원인**: FMS TCP 서버가 실행되지 않았거나 방화벽이 차단 중

**해결책**:
```bash
# FMS가 포트 9000에서 리스닝 중인지 확인
netstat -tlnp | grep 9000

# 다른 터미널에서 연결 테스트
telnet 192.168.1.3 9000

# 방화벽 확인
sudo ufw status
sudo ufw allow 9000/tcp  # 차단된 경우
```

---

## 중요 발견: Domain Bridge 설정 누락

**중요**: `/fms/pickup_arrival` 토픽이 domain 20 (jetcobot A)으로 브리징되지 않습니다!

**현재 domain_bridge_complete.yaml**은 다음만 브리징:
- Domain 20 → 25: `/arm_a/status`
- Domain 25 → 20: `/arm_a/cmd`

**누락**:
- Domain 25 → 20: `/fms/pickup_arrival`
- Domain 25 → 21: `/fms/pickup_arrival`

**Coordinator가 pinky 도착 알림을 받으려면 추가 필요!**

**수정**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml`에 추가:

```yaml
# Domain 25 -> Domain 20: FMS 알림을 Arm A coordinator로
- from_domain: 25
  to_domain: 20
  topics:
    /fms/pickup_arrival:
      type: fleet_interfaces/msg/PickupArrival
      qos:
        reliability: "RELIABLE"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 10

# Domain 25 -> Domain 21: FMS 알림을 Arm B coordinator로
- from_domain: 25
  to_domain: 21
  topics:
    /fms/pickup_arrival:
      type: fleet_interfaces/msg/PickupArrival
      qos:
        reliability: "RELIABLE"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 10
```

---

## 다음 단계

1. **Domain bridge 설정 수정** (`/fms/pickup_arrival` 추가)
2. **단일 주문 플로우** 종단간 테스트
3. **다중 로봇 조정** 테스트 (pinky1 + pinky2)
4. 필요한 경우 **coordinator 큐 수정 구현**
5. 다른 문제 확인을 위한 **로그 모니터링**

---

## 빌드 상태

✅ FMS 워크스페이스 빌드 성공
✅ Coordinator 워크스페이스 빌드 성공
✅ Domain bridge 설정 검토됨 (`/fms/pickup_arrival` 수정 필요)

**빌드 출력**:
```
fleet_interfaces: [0.47s] ✓
fms: [1.15s] ✓
sandwich_coordinator: [1.16s] ✓
```
