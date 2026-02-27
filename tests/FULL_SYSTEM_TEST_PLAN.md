# Kitchmatics FMS - Full System Test Plan
## 1~10번 요구사항 통합 테스트 계획서

**작성일**: 2026-02-27
**목적**: 1~10번 요구사항이 동시에 동작하는지 검증

---

## 1. 요구사항 vs 테스트 커버리지 매핑

| 요구사항 | 설명 | 관련 테스트 파일 | 커버리지 상태 |
|---------|------|-----------------|--------------|
| 1 | 주문 시 pinky→pickup_spot 이동 + 로봇팔 조리 **동시** 시작 | test_e2e_skip_mode.py, test_integration_scenarios.py | **부분** - 동시성 테스트 필요 |
| 2 | pickup_spot 도착 후 로봇팔이 음식 탑재 | test_e2e_skip_mode.py (skip mode) | **Skip Mode만** - 실제 로봇팔 연동 테스트 필요 |
| 3 | 음식 받은 pinky → 주문 테이블로 이동 | test_e2e_skip_mode.py, test_fms_unit.py | **OK** |
| 4 | 수령완료 버튼 → pinky → 자신의 spot으로 복귀 | test_e2e_skip_mode.py, test_integration_scenarios.py | **OK** |
| 5 | 다중 주문 시 다른 pinky 출발 | test_multi_robot.py | **OK** |
| 6 | 경로 겹침, 주문 대기 문제 해결 | test_collision_avoidance.py, test_zone_manager_reservation.py | **OK** |
| 7 | /pose 업데이트마다 지나간 노드 실시간 해제 | test_zone_manager_reservation.py | **부분** - 실시간 해제 테스트 필요 |
| 8 | pickup_spot 도착 시 FMS → 로봇팔 알림 | test_fms_communication.py | **부분** - 토픽 발행 테스트 필요 |
| 9 | 로봇팔: 카메라 검수 완료 + pinky 존재 확인 후에만 음식 전달 | **미구현** | **누락** |
| 10 | 음식 전달 성공 후 주문 밀림 시 다음 조리 시작 | test_integration_scenarios.py | **OK** - Auto-dispatch 테스트 있음 |

---

## 2. 기존 테스트 파일 분석

### 2.1 핵심 테스트 파일

| 파일 | 위치 | 설명 |
|-----|------|------|
| test_fms_unit.py | /tests/ | Task, TaskManager, RobotState, FleetController 단위 테스트 |
| test_multi_robot.py | /tests/ | 다중 로봇 동시 배달 테스트 |
| test_e2e_skip_mode.py | /tests/ | E2E 배달 흐름 테스트 (Skip Mode) |
| test_zone_manager_reservation.py | /fms/tests/ | Zone 예약 및 충돌 회피 테스트 |
| test_collision_avoidance.py | /fms/fms/tests/ | 충돌 감지 및 대체 경로 테스트 |
| test_integration_scenarios.py | /fms/fms/ | 주문 큐잉, Auto-dispatch 테스트 |
| test_tcp_protocol.py | 루트 | TCP 프로토콜 테스트 |
| test_fms_communication.py | 루트 | FMS 통신 검증 테스트 |
| test_tcp_communication.py | /fms/scripts/ | TCP 포트 및 메시지 형식 테스트 |

### 2.2 수동 테스트 스크립트

| 파일 | 위치 | 설명 |
|-----|------|------|
| test_cooking.py | /test_code/ | 로봇팔 조리 주문 전송 테스트 |
| test_navigation.py | /test_code/ | Pinky 네비게이션 명령 테스트 |

---

## 3. 누락된 테스트 케이스

### 3.1 요구사항 1: 동시 시작 테스트 (High Priority)

**누락 내용**: 주문 접수 시 pinky 이동과 로봇팔 조리가 **정확히 동시에** 시작되는지 검증

```python
# 필요한 테스트:
def test_concurrent_start_on_order():
    """
    주문 접수 시 다음이 동시에 발생하는지 확인:
    1. FMS → Pinky: navigate_to_pose (point13) 명령
    2. FMS → Coordinator: CookingOrder 토픽 발행
    타임스탬프 차이가 100ms 이내인지 검증
    """
    pass
```

### 3.2 요구사항 7: 실시간 노드 해제 테스트 (Medium Priority)

**누락 내용**: /pose 토픽 업데이트 시 지나간 노드가 실시간으로 해제되는지 검증

```python
# 필요한 테스트:
def test_realtime_node_release_on_pose_update():
    """
    로봇이 노드를 통과할 때마다:
    1. ZoneManager에서 해당 노드가 release 되는지 확인
    2. 다른 로봇이 즉시 해당 노드를 reserve 할 수 있는지 확인
    """
    pass
```

### 3.3 요구사항 8: Pickup 도착 알림 테스트 (Medium Priority)

**누락 내용**: pickup_spot 도착 시 /fms/pickup_arrival 토픽이 정확히 발행되는지 검증

```python
# 필요한 테스트:
def test_pickup_arrival_notification():
    """
    Pinky가 pickup_spot에 도착하면:
    1. /fms/pickup_arrival 토픽이 발행되는지 확인
    2. 메시지에 robot_id, order_id가 포함되어 있는지 확인
    3. Coordinator가 이 메시지를 수신하는지 확인
    """
    pass
```

### 3.4 요구사항 9: 로봇팔 음식 전달 조건 테스트 (High Priority - 완전 누락)

**누락 내용**: 로봇팔이 카메라 검수 + pinky 존재 확인 후에만 음식을 전달하는지 검증

```python
# 필요한 테스트:
def test_robot_arm_delivery_conditions():
    """
    로봇팔이 음식을 전달하기 전:
    1. AI 카메라 검수가 완료되었는지 확인 (샌드위치 품질 검증)
    2. Pinky가 pickup_spot에 존재하는지 확인
    3. 두 조건 모두 만족 시에만 음식 전달 동작 수행
    """
    pass

def test_robot_arm_waits_for_pinky():
    """
    조리 완료 후 Pinky가 아직 도착하지 않은 경우:
    1. 로봇팔이 대기 상태를 유지하는지 확인
    2. Pinky 도착 알림 수신 후 음식 전달하는지 확인
    """
    pass
```

---

## 4. 통합 테스트 시나리오

### 4.1 시나리오 A: 단일 주문 완전 흐름

```
[시작 조건]
- Pinky1: pinky1_spot (IDLE)
- Robot Arms: 대기 중
- 주문 없음

[테스트 단계]
1. GUI에서 테이블 1번 주문 접수
2. FMS가 주문 수신 확인
3. FMS → Pinky1: navigate_to_pose(point13) 명령 확인
4. FMS → Coordinator: CookingOrder 발행 확인 (1, 3 동시 발생)
5. Pinky1 이동 중 상태 확인 (STATUS_MOVING_TO_PICKUP)
6. Pinky1 point13 도착 → pickup_spot 도착 확인
7. /fms/pickup_arrival 토픽 발행 확인
8. 로봇팔 조리 완료 + 카메라 검수 완료 확인
9. 로봇팔 → Pinky1 음식 탑재 (/cooking/loading_complete)
10. Pinky1 → 테이블1 이동 (STATUS_MOVING_TO_TABLE)
11. 테이블1 도착 (STATUS_DELIVERING)
12. GUI에서 수령 완료 버튼 클릭
13. Pinky1 → pinky1_spot 복귀 (STATUS_RETURNING)
14. 복귀 완료 (STATUS_IDLE)

[검증 포인트]
- 각 상태 전이가 올바른 순서로 발생
- 타임아웃 없이 완료
- 모든 토픽 메시지 정확히 전송
```

### 4.2 시나리오 B: 다중 동시 주문 (3대 로봇)

```
[시작 조건]
- Pinky1, Pinky2, Pinky3: 각각 parking spot (IDLE)
- Robot Arms: 대기 중

[테스트 단계]
1. GUI에서 테이블 1, 2, 3번 동시 주문 (1초 간격)
2. FMS가 각 주문에 다른 로봇 할당 확인
3. 3대 로봇 모두 동시에 이동 시작 확인
4. 경로 충돌 없이 pickup_spot 순차 접근 확인
5. 각 로봇이 음식 받고 테이블로 이동 확인
6. 모든 배달 완료 후 각자 parking spot 복귀 확인

[검증 포인트]
- 로봇 간 충돌 없음
- Zone 예약/해제 정상 작동
- 주문 대기열 정상 처리
```

### 4.3 시나리오 C: 4번째 주문 큐잉 및 Auto-dispatch

```
[시작 조건]
- Pinky1, Pinky2, Pinky3: 모두 배달 중 (BUSY)

[테스트 단계]
1. GUI에서 테이블 4번 주문 접수
2. FMS가 주문을 pending_order_queue에 추가 확인
3. GUI에 "대기 중" 알림 확인
4. Pinky1 배달 완료 → 수령완료 버튼
5. FMS가 자동으로 대기 주문 dispatch 확인
6. Pinky1이 복귀하지 않고 바로 다음 주문 처리 확인

[검증 포인트]
- 큐 동작 정상
- Auto-dispatch 타이밍 정확
- 로봇 상태 전이 올바름
```

---

## 5. 테스트 실행 명령어

### 5.1 단위 테스트 실행

```bash
cd /home/gw/kitchmatics/roscamp-repo-1

# 전체 테스트 실행
python3 -m pytest tests/ -v

# 특정 테스트 파일 실행
python3 -m pytest tests/test_fms_unit.py -v
python3 -m pytest tests/test_multi_robot.py -v
python3 -m pytest tests/test_e2e_skip_mode.py -v

# FMS 내부 테스트
python3 -m pytest fms/tests/test_zone_manager_reservation.py -v
python3 -m pytest fms/fms/tests/test_collision_avoidance.py -v

# 통합 시나리오 테스트
python3 fms/fms/test_integration_scenarios.py
```

### 5.2 TCP 통신 테스트

```bash
cd /home/gw/kitchmatics/roscamp-repo-1

# TCP 프로토콜 테스트 (FMS 실행 필요)
python3 test_tcp_protocol.py

# FMS 통신 검증 테스트
python3 test_fms_communication.py --test-all

# TCP 포트/메시지 형식 테스트
python3 fms/scripts/test_tcp_communication.py --test-all
```

### 5.3 수동 기능 테스트

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/test_code

# 네비게이션 테스트 (로봇 실행 필요)
python3 test_navigation.py pinky1 table1

# 조리 테스트 (Coordinator 실행 필요)
python3 test_cooking.py ham_cheese mayo
```

---

## 6. 전체 시스템 테스트 절차

### Phase 1: 사전 준비

```bash
# 1. 체크리스트 확인
cat /home/gw/kitchmatics/roscamp-repo-1/ROBOT_LAUNCH_CHECKLIST.md

# 2. 로봇 실행 (SSH)
# Pinky1 (192.168.1.7), Pinky2 (192.168.1.6), Pinky3 (192.168.1.11)

# 3. 로봇팔 실행
# ArmA, ArmB 물리적 실행
```

### Phase 2: Main PC 시스템 실행

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25

# 1. Domain Bridge 실행
ros2 run domain_bridge domain_bridge fms/config/domain_bridge_complete.yaml > /tmp/domain_bridge.log 2>&1 &

# 2. FMS 실행
ros2 launch fms fms_closed_network.launch.py > /tmp/fms.log 2>&1 &

# 3. 시스템 검증
./scripts/verify_system.sh
```

### Phase 3: 통합 테스트 실행

```bash
# 1. 단위 테스트 먼저 실행
python3 -m pytest tests/ -v --tb=short

# 2. 토픽 모니터링 (터미널 4개)
# Terminal 1: ros2 topic echo /fms/order_request
# Terminal 2: ros2 topic echo /cooking/order
# Terminal 3: ros2 topic echo /fms/pickup_arrival
# Terminal 4: ros2 topic echo /cooking/loading_complete

# 3. 수동 테스트 주문
ros2 topic pub --once /fms/order fleet_interfaces/msg/Order \
  '{order_id: "TEST-001", items: ["sandwich"], table_number: 5, priority: 1}'

# 4. 로그 확인
tail -f /tmp/fms.log
```

---

## 7. 검증 체크리스트

### 요구사항 1: 동시 시작
- [ ] 주문 접수 시 pinky 이동 명령 발행 확인
- [ ] 주문 접수 시 cooking_order 발행 확인
- [ ] 두 동작의 타임스탬프 차이 < 100ms

### 요구사항 2: 음식 탑재
- [ ] pickup_spot 도착 시 상태가 STATUS_LOADED로 변경
- [ ] /cooking/loading_complete 토픽 수신 후 다음 단계 진행

### 요구사항 3: 테이블 이동
- [ ] 음식 탑재 후 STATUS_MOVING_TO_TABLE 상태 전이
- [ ] 테이블 도착 시 STATUS_DELIVERING 상태 전이

### 요구사항 4: 복귀
- [ ] 수령완료 버튼 후 STATUS_RETURNING 상태 전이
- [ ] 복귀 완료 후 STATUS_IDLE 상태 전이

### 요구사항 5: 다중 로봇
- [ ] 동시 주문 시 다른 로봇에 할당
- [ ] 3대 로봇 모두 동시 동작 가능

### 요구사항 6: 경로 충돌 해결
- [ ] Zone 예약 시스템 동작 확인
- [ ] 충돌 시 대기 또는 대체 경로 선택

### 요구사항 7: 실시간 노드 해제
- [ ] 로봇 이동 시 지나간 노드 자동 해제
- [ ] 해제된 노드 다른 로봇이 즉시 사용 가능

### 요구사항 8: Pickup 도착 알림
- [ ] /fms/pickup_arrival 토픽 발행 확인
- [ ] Coordinator가 알림 수신 확인

### 요구사항 9: 조건부 음식 전달
- [ ] 카메라 검수 완료 상태 확인
- [ ] Pinky 존재 확인 후 전달

### 요구사항 10: Auto-dispatch
- [ ] 배달 완료 시 대기 주문 자동 dispatch
- [ ] 로봇이 복귀하지 않고 바로 다음 주문 처리

---

## 8. 문제 발생 시 디버깅 가이드

### 8.1 로그 확인 위치

```bash
# FMS 로그
tail -f /tmp/fms.log

# Domain Bridge 로그
tail -f /tmp/domain_bridge.log

# 특정 토픽 모니터링
ros2 topic echo /fms/fleet_status
```

### 8.2 일반적인 문제

| 문제 | 원인 | 해결 |
|-----|------|------|
| 토픽이 안보임 | Domain Bridge 미실행 | Domain Bridge 재시작 |
| 로봇이 안움직임 | Nav2 미실행 | 로봇 SSH 접속 후 Nav2 확인 |
| 주문 큐잉 안됨 | OrderHandler 콜백 미등록 | FMS 재시작 |
| 충돌 발생 | ZoneManager 초기화 실패 | FMS 로그 확인 후 재시작 |

---

## 9. 향후 개선 사항

1. **자동화된 E2E 테스트**: ROS2 테스트 프레임워크를 활용한 완전 자동화
2. **요구사항 9 테스트 구현**: 로봇팔 조건부 전달 테스트 코드 작성
3. **성능 테스트**: 다중 주문 처리 시 응답 시간 측정
4. **스트레스 테스트**: 연속 주문 100건 처리 테스트

---

**문서 끝**
