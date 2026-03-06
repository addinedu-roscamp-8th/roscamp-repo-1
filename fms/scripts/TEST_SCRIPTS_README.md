# FMS 테스트 스크립트 문서

이 디렉토리에는 Kitchmatics 플릿 관리 시스템(FMS) 통신 레이어를 검증하기 위한 종합 테스트 스크립트가 포함되어 있습니다.

## 빠른 시작

### 1. ROS 2 메시지 테스트 (FMS 연동에 가장 중요)
```bash
# 모든 메시지 타입 테스트
python3 test_messages.py --all

# goal_arrived 메시지 발행 테스트 (point13 도착)
python3 test_messages.py --test-goal-arrived

# 플릿 상태 구독 테스트
python3 test_messages.py --test-fleet-status

# 대화형 테스트 모드
python3 test_messages.py --interactive
```

### 2. 외부 팀 모의 테스트 (skip 모드 테스트용)
```bash
# 모든 모의 서비스 시작 (정밀 제어 + 로봇 암)
python3 mock_external_teams.py --start-all

# 정밀 제어 모의 시작 (precision_parked 메시지 시뮬레이션)
python3 mock_external_teams.py --mock-precision

# 로봇 암 모의 시작 (food_loaded 메시지 시뮬레이션)
python3 mock_external_teams.py --mock-arm

# 모의 서비스 대화형 제어
python3 mock_external_teams.py --interactive
```

### 3. TCP 통신 테스트
```bash
# 모든 TCP 포트 테스트
python3 test_tcp_communication.py --test-all

# 특정 포트 접근성 테스트
python3 test_tcp_communication.py --test-ports

# 메시지 형식 및 직렬화 테스트
python3 test_tcp_communication.py --test-message-format

# TCP 에코 서버 시작 (테스트용)
python3 test_tcp_communication.py --echo-server --port 9000

# 에코 서버에 클라이언트로 접속
python3 test_tcp_communication.py --echo-client --host 192.168.1.3 --port 9000
```

## 상세 테스트 스크립트

### test_messages.py

FMS 시스템의 ROS 2 메시지 통신을 테스트합니다.

**테스트 항목:**
1. **goal_arrived 발행** - 로봇이 point13에 도착했을 때 goal_arrived 메시지를 발행할 수 있는지 검증
2. **fleet_status 구독** - FMS가 플릿 상태 업데이트를 수신하고 처리할 수 있는지 확인
3. **로봇별 토픽** - 네임스페이스 격리 확인 (/pinky1/*, /pinky2/*, /pinky3/*)
4. **TCP 메시지 형식** - TCP 메시지 직렬화/역직렬화 검증
5. **네임스페이스 격리** - 로봇 네임스페이스 간 메시지가 교차하지 않는지 확인

**테스트되는 메시지 타입:**
- `OrderRequest` - 메인 서버에서 FMS로의 주문
- `RobotStatus` - 개별 로봇 상태
- `FleetStatus` - 전체 플릿 상태
- `DeliveryComplete` - 고객 GUI에서의 배달 확인
- 커스텀 `goal_arrived` - point13에서의 로봇 도착 (공식 메시지 정의까지 String 타입 사용)

**사용 예제:**
```bash
# goal_arrived 메시지 수동 테스트
python3 test_messages.py --test-goal-arrived

# 플릿 상태 구독 테스트 (FMS가 발행할 때까지 대기)
python3 test_messages.py --test-fleet-status

# 대화형 모드 - 요청 시 메시지 발행
python3 test_messages.py --interactive

# 대화형 모드 명령어:
# > goal_arrived pinky1 point13
# > order 1 M001 1
# > status
# > quit
```

**예상 출력:**
```
[FMS_TEST_NODE] Created publisher: /fms/goal_arrived (using String type)
[FMS_TEST_NODE] Created publisher: /fms/order_request
[FMS_TEST_NODE] Subscribed to: /fms/fleet_status
[GOAL_ARRIVED] Published: pinky1 arrived at point13
[ORDER_REQUEST] Published: ORD-123456 to T01
```

**중요 사항:**
- 먼저 FMS 노드를 시작하세요: `ros2 launch fms fms_launch.py`
- `goal_arrived` 메시지는 fleet_interfaces에 공식 메시지 타입이 정의될 때까지 `std_msgs/String`을 임시로 사용합니다
- 전체 테스트를 위해 다음도 실행하세요: `ros2 launch mobile_robot bringup_launch.py`

---

### mock_external_teams.py

외부 의존성 없이 skip 모드 테스트를 위한 외부 팀 서비스를 모의합니다.

**모의 대상:**

1. **정밀 제어 팀** (domain 14)
   - `/fms/goal_arrived`에서 `goal_arrived` 메시지 수신 대기
   - 정밀 주차 시뮬레이션 (point13 → pickup_spot)
   - 지연 후 `precision_parked` 메시지 발행
   - 설정 가능한 지연 (기본: 2초)

2. **로봇 암 팀** (domain 15)
   - `/fms/food_load_request`에서 `food_load_request` 메시지 수신 대기
   - 로봇에 음식 적재 시뮬레이션
   - 지연 후 `food_loaded` 메시지 발행
   - 설정 가능한 지연 (기본: 3초)

**메시지 흐름:**
```
FMS                  Precision Mock              Robot Arm Mock
 |                         |                           |
 +--goal_arrived----------->|                           |
 |                    (주차 시뮬레이션)                   |
 |<-------precision_parked--|                           |
 |                                                      |
 +--food_load_request-------------------→              |
 |                              (적재 시뮬레이션)         |
 |                         food_loaded-----<-----------+
 |
 (로봇이 테이블로 이동하여 배달 완료)
```

**사용 예제:**
```bash
# 기본 지연으로 두 모의 서비스 시작
python3 mock_external_teams.py --start-all

# 3초 지연으로 정밀 제어 모의 시작
python3 mock_external_teams.py --mock-precision --precision-delay 3

# 5초 지연으로 로봇 암 모의 시작
python3 mock_external_teams.py --mock-arm --arm-delay 5

# 30초간 두 모의 서비스 실행
python3 mock_external_teams.py --start-all --duration 30

# 대화형 모드
python3 mock_external_teams.py --interactive

# 대화형 모드 명령어:
# > start precision 2
# > start arm 3
# > stats
# > stop all
# > quit
```

**예상 출력:**
```
[PRECISION_CONTROL_MOCK] Initialized (delay=2.0s)
[ROBOT_ARM_MOCK] Initialized (delay=3.0s)
[PRECISION_CONTROL_MOCK] [GOAL_ARRIVED] Received from pinky1 at point13
[PRECISION_CONTROL_MOCK] [PRECISION_PARKED] Published: pinky1 parked at pickup_spot
[ROBOT_ARM_MOCK] [FOOD_LOAD_REQUEST] Received for pinky1
[ROBOT_ARM_MOCK] [FOOD_LOADED] Published: pinky1 loaded with ORD-20250225-001

MOCK STATISTICS
Precision Control Mock:
  goal_arrived received:     1
  precision_parked sent:     1
  pending parkings:          0
Robot Arm Mock:
  food_load_request received: 1
  food_loaded sent:           1
  pending loads:              0
```

**FMS와의 연동:**
```bash
# 터미널 1: 모의 외부 팀 시작
python3 mock_external_teams.py --start-all

# 터미널 2: skip 모드로 FMS 시작
ros2 launch fms fms_launch.py skip_robot_arm:=true

# 터미널 3: 테스트 주문 전송
python3 send_order.py --table 1

# 예상 흐름:
# 1. FMS가 주문 수신
# 2. FMS가 pinky를 point13으로 내비게이션
# 3. FMS가 goal_arrived 발행
# 4. 정밀 제어 모의가 precision_parked 발행 (2초 지연)
# 5. FMS가 로봇 암에 적재 요청 (일반 모드에서는 food_loaded 대기)
# 6. 로봇 암 모의가 food_loaded 발행 (3초 지연)
# 7. FMS가 pinky를 table1로 내비게이션
# 8. FMS가 수동 배달 완료 대기
# 9. FMS가 pinky를 주차 위치로 복귀
```

---

### test_tcp_communication.py

폐쇄 네트워크 "kitchmatics"에서 TCP 통신을 테스트합니다.

**테스트 항목:**

1. **포트 접근성** - 설정된 모든 포트에 접근 가능한지 확인
2. **메시지 형식** - TCP 메시지 직렬화/역직렬화 검증
3. **메시지 파싱** - 다양한 메시지 형식의 JSON 파싱 테스트
4. **메시지 크기** - 다양한 페이로드 크기의 메시지 처리 테스트
5. **네트워크 연결** - 네트워크 설정이 올바른지 확인

**테스트 포트:**
- 마스터 FMS: 192.168.1.3:9000
- 메인 서버: 192.168.1.3:9999
- 로봇 클라이언트: 192.168.1.7,6,11:9001 (pinky1,2,3)
- 로봇 암 클라이언트: 192.168.1.4,10:9002 (cobot1,2)
- PostgreSQL: 127.0.0.1:5432

**사용 예제:**
```bash
# 모든 포트 테스트
python3 test_tcp_communication.py --test-all

# 포트 접근성만 테스트
python3 test_tcp_communication.py --test-ports

# 메시지 형식 검증 테스트
python3 test_tcp_communication.py --test-message-format

# 테스트용 TCP 에코 서버 시작
python3 test_tcp_communication.py --echo-server --host 0.0.0.0 --port 9000

# 에코 서버에 클라이언트로 접속
python3 test_tcp_communication.py --echo-client --host 192.168.1.3 --port 9000

# 커스텀 포트로 테스트
python3 test_tcp_communication.py --echo-server --port 9999
```

**테스트되는 메시지 타입:**
- CONNECT - 로봇 연결 설정
- ROBOT_STATUS - 개별 로봇 상태 업데이트
- TASK_ASSIGN - 로봇에 작업 할당
- TASK_COMPLETE - 작업 완료 알림
- FLEET_STATUS - 전체 플릿 상태
- HEARTBEAT - 주기적 하트비트 메시지
- EMERGENCY_STOP - 비상 정지 명령

**포트 테스트 예상 출력:**
```
TEST 1: TCP Port Accessibility
Testing port accessibility (3s timeout per port):
  [Master FMS] OPEN
  [Main Server] CLOSED
  [pinky1 Client] CLOSED
  [pinky2 Client] CLOSED
  [pinky3 Client] CLOSED
  [cobot1 Client] CLOSED
  [cobot2 Client] CLOSED
  [PostgreSQL] OPEN

Summary: 2/8 ports open
```

**메시지 형식 테스트 예상 출력:**
```
TEST 2: TCP Message Format Validation
Testing message serialization/deserialization:
  [CONNECT] OK (87 bytes)
  [ROBOT_STATUS] OK (156 bytes)
  [TASK_ASSIGN] OK (168 bytes)
  [TASK_COMPLETE] OK (96 bytes)
  [FLEET_STATUS] OK (187 bytes)
  [HEARTBEAT] OK (105 bytes)
  [EMERGENCY_STOP] OK (102 bytes)

Result: OK
```

---

## 네트워크 설정 참조

### WiFi 네트워크: "kitchmatics" (폐쇄 네트워크)

```
Master PC (192.168.1.3)
├── FMS Server: port 9000
├── Main Server: port 9999
└── PostgreSQL: port 5432

Mobile Robots (pinky_pro):
├── pinky1: 192.168.1.7:9001
├── pinky2: 192.168.1.6:9001
└── pinky3: 192.168.1.11:9001

Robot Arms (JetCobot):
├── cobot1: 192.168.1.4:9002
└── cobot2: 192.168.1.10:9002
```

### ROS 2 토픽 구조 (현재 - 네임스페이스)

```
글로벌 토픽:
├── /fms/order_request (OrderRequest)
├── /fms/fleet_status (FleetStatus)
├── /fms/delivery_complete (DeliveryComplete)
├── /fms/goal_arrived (String - 커스텀)
├── /fms/precision_parked (String - 커스텀)
├── /fms/food_loaded (String - 커스텀)
└── /fms/food_load_request (String - 커스텀)

로봇별 토픽 (네임스페이스):
├── /pinky1/*
│   ├── /pose
│   ├── /battery/voltage
│   ├── /battery/present
│   └── /navigate_to_pose (action)
├── /pinky2/*
│   └── (pinky1과 동일)
└── /pinky3/*
    └── (pinky1과 동일)
```

### ROS 2 Domain ID (향후 - CLAUDE.md 요구사항)

**참고: 다음은 CLAUDE.md 요구사항에 기반한 마이그레이션 계획입니다:**

```
Domain 11: pinky1 (모바일 로봇)
Domain 12: pinky2 (모바일 로봇)
Domain 13: pinky3 (모바일 로봇)
Domain 14: robot_arm_1 (정밀 제어)
Domain 15: robot_arm_2 (정밀 제어)
Domain 0:  마스터 FMS 노드
```

---

## 테스트 체크리스트

### 전체 시스템 테스트 전

- [ ] 모든 ROS 2 메시지 타입이 `fleet_interfaces/msg/`에 올바르게 정의됨
- [ ] TCP 통신 경로 테스트 완료
- [ ] "kitchmatics" WiFi에서 네트워크 연결 확인
- [ ] 로봇 클라이언트가 설정된 포트로 접근 가능
- [ ] 메인 서버와 FMS 노드가 오류 없이 시작됨

### 통신 검증

- [ ] `test_messages.py --test-goal-arrived` 통과
- [ ] `test_messages.py --test-fleet-status` 메시지 수신
- [ ] `test_tcp_communication.py --test-all`에서 모든 중요 포트 개방 확인
- [ ] `test_tcp_communication.py --test-message-format`에서 모든 메시지 타입 검증
- [ ] TCP 에코 서버와 클라이언트가 양방향 통신 가능

### skip 모드 테스트 (외부 의존성 없음)

- [ ] 모의 외부 팀이 오류 없이 시작됨: `mock_external_teams.py --start-all`
- [ ] 모의 서비스가 메시지를 올바르게 수신하고 응답
- [ ] FMS가 모의 `precision_parked` 메시지를 처리
- [ ] FMS가 모의 `food_loaded` 메시지를 처리
- [ ] 전체 배달 흐름 완료: 주문 → 픽업 → 배달 → 복귀

### 전체 통합 테스트

- [ ] 올바른 순서로 모든 구성 요소 시작:
  1. 각 도메인의 로봇과 로봇 암
  2. skip 모드 비활성화된 FMS 노드
  3. 메인 서버 노드
  4. `send_order.py`로 테스트 주문 전송
- [ ] 모든 터미널에서 메시지 흐름 모니터링
- [ ] 배달 전 과정에서 데이터베이스 업데이트 확인
- [ ] 관리자 GUI에서 플릿 상태 업데이트 확인

---

## 문제 해결

### ROS 2 토픽이 나타나지 않음

**문제:** `test_messages.py`가 fleet_status 메시지를 수신하지 못함

**해결 방법:**
1. FMS 노드 실행 확인: `ros2 node list`
2. 토픽 가용성 확인: `ros2 topic list`
3. 메시지 타입 확인: `ros2 topic type /fms/fleet_status`
4. 메시지 검사: `ros2 topic echo /fms/fleet_status`

### TCP 포트 닫힘

**문제:** 포트 테스트에서 모든 로봇 포트가 닫혀 있음

**해결 방법:**
1. `network_config.yaml`에서 로봇 IP가 올바른지 확인
2. "kitchmatics" 네트워크에 WiFi 연결 확인
3. 로봇 전원이 켜져 있고 네트워크가 활성화되어 있는지 확인
4. 마스터 PC의 방화벽 규칙 확인
5. 연결 테스트: `ping 192.168.1.7`

### 메시지 파싱 오류

**문제:** "Failed to parse goal_arrived message"

**해결 방법:**
1. 발행된 메시지의 JSON 형식 확인
2. 필수 필드가 모두 있는지 확인
3. 특정 필드 문제에 대한 오류 로그 검토
4. `ros2 topic echo /fms/goal_arrived`로 원시 메시지 검사

### 모의 서비스가 응답하지 않음

**문제:** 모의 서비스가 시작되었지만 메시지를 수신하지 못함

**해결 방법:**
1. FMS 노드가 올바른 토픽에 발행하는지 확인
2. ROS 2 도메인 ID 일치 확인 (현재 도메인 격리 없음)
3. 모의 서비스 출력에서 구독 확인 모니터링
4. 메시지 형식이 예상 구조와 일치하는지 확인
5. ROS 2 네트워크 설정 확인

---

## 파일 위치

- 테스트 스크립트: `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/`
- FMS 설정: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/`
- 메시지 정의: `/home/gw/kitchmatics/roscamp-repo-1/fleet_interfaces/msg/`
- FMS 노드: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py`
- 메인 서버: `/home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/`
- TCP 통신: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/tcp_communication.py`

---

## 구현 참고사항

### 누락된 메시지 타입 (CLAUDE.md 요구사항)

세 가지 커스텀 메시지 타입이 현재 `std_msgs/String`으로 모의되고 있습니다:
1. `goal_arrived` - point13에서의 로봇 도착
2. `precision_parked` - 정밀 주차 완료
3. `food_loaded` - 음식 적재 완료

**공식 메시지 타입 구현 방법:**

1. `fleet_interfaces/msg/`에 메시지 파일 생성:
   ```
   GoalArrived.msg
   PrecisionParked.msg
   FoodLoaded.msg
   ```

2. `fleet_interfaces/CMakeLists.txt`에 새 메시지 포함하도록 업데이트

3. 테스트 스크립트에서 String 대신 공식 메시지 타입 사용하도록 업데이트

4. 인터페이스 재빌드: `colcon build --packages-select fleet_interfaces`

### 네임스페이스에서 Domain ID로의 마이그레이션

현재 구현은 **네임스페이스** (`/pinky1`, `/pinky2`, `/pinky3`)를 사용합니다.

**CLAUDE.md는 ROS_DOMAIN_ID로의 마이그레이션을 요구합니다:**
- 폐쇄 네트워크에서 로봇 간 격리된 통신을 가능하게 함
- 각 로봇이 네임스페이스 오버헤드 없이 별도 도메인에서 운영
- 런치 파일과 FMS 노드 구현 업데이트 필요

---

## 연락처 및 지원

- 프로덕트 기획: 팀 리드
- 통신 검증 담당: 메시지 형식 및 프로토콜 검토
- 상세 구현 요구사항: `/home/gw/kitchmatics/roscamp-repo-1/CLAUDE.md` 참조
