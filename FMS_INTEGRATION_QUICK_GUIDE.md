# FMS Zone Manager & Task Scheduler 통합 - 빠른 가이드

## 📋 통합된 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|---------|------|------|
| **Zone Manager** | `zone_manager.py` | 충돌 회피, Zone 예약/점유 |
| **Task Scheduler** | `task_scheduler.py` | Task 큐, Pickup 슬롯 관리 |
| **FMS Node** | `fms_node.py` | 메인 통합 로직 |

## 🔄 Delivery Flow (개선됨)

```
주문 수신
    ↓
Task Scheduler에 추가
    ↓
Robot 할당
    ↓
┌─ Pickup Zone 예약? ─ YES → Pickup으로 이동
│                    └─ NO → Waiting Zone으로 이동
│
Pickup 도착
    ├─ Pickup Slot 요청? ─ YES → 즉시 진입 (Occupation)
    │                   └─ NO → Waiting Zone으로 이동
    │
Precision Parking & Food Loading
    ↓
Pickup Zone 해제
    ↓
대기 Queue 처리 → 다음 Robot 진입 허용
    ↓
Table로 이동
    ↓
배송 완료
    ↓
Parking으로 복귀
```

## 🎯 핵심 메서드

### 1. Task 할당 프로세스
```python
# process_pending_tasks() 에서
task = self.task_scheduler.assign_task_to_robot(robot_id)

if self.zone_manager.reserve_zone(robot_id, 'zone_pickup'):
    # Zone 예약 성공
    self._send_robot_to_pickup(robot_id)
else:
    # Zone 예약 실패 → 대기
    waiting_zone = self.task_scheduler.get_next_waiting_zone(robot_id)
    self._send_robot_to_waiting_zone(robot_id, waiting_zone)
```

### 2. Pickup 도착 처리
```python
# _check_navigation_status() 에서
if robot.status == RobotState.STATUS_MOVING_TO_PICKUP:
    can_enter = self.task_scheduler.request_pickup_access(robot_id, task.task_id)

    if can_enter:
        # Slot 획득 → 점유
        self.zone_manager.occupy_zone(robot_id, 'zone_pickup')
    else:
        # Slot 대기 → waiting zone으로
        self._send_robot_to_waiting_zone(robot_id, waiting_zone)
```

### 3. Food Loading 완료
```python
# loading_complete_callback() → notify_food_loaded() 에서
self.task_scheduler.robot_loaded(robot_id, task_id)
self.zone_manager.leave_zone(robot_id, 'zone_pickup')
self._process_pickup_queue()  # 다음 Robot 진입
```

### 4. 배송 완료
```python
# delivery_complete_callback() 에서
self.task_scheduler.robot_delivered(robot_id, task_id)
self.fleet_controller.robot_complete_delivery(robot_id)
self._send_robot_to_parking(robot_id)
```

## 📍 Zone 타입

| Zone | 설명 | ID |
|------|------|-----|
| **zone_pickup** | Pickup spot (0.47, 0.63) | 한 번에 1개 로봇만 |
| **zone_point13** | 첫 대기 위치 (0.585, 0.63) | Pickup에 가장 가까움 |
| **zone_parking1/2/3** | Robot 주차 위치 | 2순위 대기 위치 |
| **zone_table1-8** | 테이블 위치 | Table delivery |

## ⏱️ Timing (1 초마다)

| 타이머 | 주기 | 역할 |
|-------|------|------|
| `status_timer` | 1.0s | Fleet status 발행 |
| `assignment_timer` | 0.5s | Pending task 할당 |
| `pickup_queue_timer` | 0.1s | 대기 Queue 처리 |
| `cleanup_timer` | 1.0s | 만료 예약 정리 |

## 📊 Task State (Scheduler)

```
PENDING (할당 대기)
    ↓
ASSIGNED (로봇에 할당)
    ↓
MOVING_TO_PICKUP (Pickup으로 이동)
    ↓
┌─ AT_PICKUP (직접 진입) ── 가장 빠름
│   ↓
│ LOADED
│
└─ WAITING_FOR_PICKUP (슬롯 대기) ── 다른 로봇이 사용 중
    ↓ (슬롯 획득)
    AT_PICKUP
    ↓
    LOADED
    ↓
MOVING_TO_TABLE
    ↓
AT_TABLE
    ↓
COMPLETED
```

## 🔌 Integration Points

### 1. Order Request Callback
```python
# Zone Manager: No direct interaction
# Task Scheduler: add_task(task)
```

### 2. Pickup Arrival Detection
```python
# Zone Manager: request_pickup_access() 전 check
# Task Scheduler: request_pickup_access(robot_id, task_id)
```

### 3. Zone Management
```python
# Reserve: 로봇이 이동하기 전 (task 할당 시)
# Occupy: 로봇이 실제로 진입할 때 (request_pickup_access 성공 후)
# Leave: 로봇이 떠날 때 (food_loaded 시)
```

## 🚨 Error Handling

### Pickup Zone Reservation 실패
```
→ Waiting Zone으로 이동
→ Queue에 추가
→ 다른 로봇 완료 대기
```

### Pickup Slot Timeout (60s)
```
→ 강제로 Slot 해제
→ 다음 대기 로봇 진입
```

### Zone Reservation Timeout (30s)
```
→ 자동으로 예약 취소
→ 다른 로봇이 Zone 사용 가능
```

## 📈 Multi-Robot Example

### 3개 로봇, 3개 주문 시나리오

```
시간 0초:
  Order1 → Robot1 할당 → Pickup Zone 예약 ✓
  Order2 → Robot2 할당 → Pickup Zone 예약 ✗ → point13 대기
  Order3 → Robot3 할당 → Pending (queue)

시간 3초:
  Robot1: Pickup에서 로딩 중
  Robot2: point13에서 대기 (Queue Pos 1)
  Robot3: Parking에서 대기 (Queue Pos 2)

시간 8초:
  Robot1: 로딩 완료 → Zone 해제
  → _process_pickup_queue() 실행
  → Robot2에게 Pickup Slot 할당
  → Robot2가 point13에서 → Pickup으로 이동

시간 11초:
  Robot2: Pickup Zone 점유
  Robot3: point13으로 이동 (Queue Pos 1 승격)

시간 15초:
  Robot2: 로딩 완료 → Zone 해제
  → Robot3에게 Pickup Slot 할당
```

## 🔍 디버깅 팁

### 로그 확인
```bash
# FMS 로그 (Zone/Scheduler 상태)
ros2 topic echo /fms/fleet_status

# 상세 로그 (5초 간격)
grep -i "scheduler\|zone\|pickup" /tmp/fms.log
```

### Queue 상태 확인
```python
# 코드에서
status = self.task_scheduler.get_scheduler_status()
print(status['pickup_queue'])

# Output:
{
  'current_holder': 'pinky1',
  'queue_length': 2,
  'waiting_robots': ['pinky2', 'pinky3'],
  'queue_positions': {'pinky1': 0, 'pinky2': 1, 'pinky3': 2}
}
```

### Zone 상태 확인
```python
zone_status = self.zone_manager.get_zone_status('zone_pickup')
# {
#   'zone_id': 'zone_pickup',
#   'occupied_by': 'pinky1',
#   'reserved_by': None,
#   'available': False
# }
```

## 💡 Best Practices

### 1. Task Scheduler 사용
- 항상 `task_scheduler` 사용 (더 정확함)
- `task_manager`는 legacy 호환성용

### 2. Zone 예약/점유 순서
```python
# ✅ 올바른 순서
1. Task 할당 전 → reserve_zone()
2. Robot 진입 시 → occupy_zone()
3. Robot 떠날 때 → leave_zone()

# ❌ 잘못된 순서
- occupy_zone() 없이 leave_zone() 호출
- reserve 후 timeout 확인 없음
```

### 3. Waiting Zone 할당
```python
# ✅ 올바른 방법
waiting_zone = self.task_scheduler.get_next_waiting_zone(robot_id)
self._send_robot_to_waiting_zone(robot_id, waiting_zone)

# ❌ 피해야 할 방법
# 직접 'point13'로 하드코딩
```

## 📝 Configuration

### Zone 정의 (zone_manager.py)
```python
# Default zones (자동 초기화됨)
'zone_pickup': (0.47, 0.63) # Pickup spot
'zone_point13': (0.585, 0.63) # Waiting zone 1
'zone_parking1/2/3': Robot parking spots
```

### Waiting Strategy (task_scheduler.py)
```python
# Pickup Queue Position → Waiting Zone Mapping
Position 0: 현재 점유 중
Position 1: point13 (다음 예정)
Position 2+: parking_spot (그 다음)
```

### Timeout Settings
```python
# zone_manager.py
reservation_timeout = 30.0  # Zone 예약 30초

# task_scheduler.py
holding_timeout = 60.0  # Pickup slot 60초
```

## 🔄 State Transitions Summary

```python
# Task Manager (기존)
PENDING → ASSIGNED → IN_PROGRESS → COMPLETED

# Task Scheduler (신규, 더 상세함)
PENDING → ASSIGNED → MOVING_TO_PICKUP
         → (WAITING_FOR_PICKUP 또는 AT_PICKUP)
         → LOADED → MOVING_TO_TABLE → AT_TABLE → COMPLETED

# Robot Status (Fleet Controller)
IDLE → MOVING_TO_PICKUP → AT_PICKUP
    → WAITING_FOR_ROBOT_ARM → MOVING_TO_TABLE
    → AT_TABLE → RETURNING → IDLE

# Zone Status (Zone Manager)
AVAILABLE → RESERVED (waiting for robot)
         → OCCUPIED (robot inside)
         → AVAILABLE (robot left)
```

## 🎓 학습 순서

1. **Zone Manager** 이해
   - Zone 개념 (예약, 점유, 해제)
   - Timeout 처리

2. **Task Scheduler** 이해
   - Task State 머신
   - Pickup Slot Manager
   - Waiting Zone 할당

3. **Integration** 이해
   - order_request_callback
   - process_pending_tasks
   - _check_navigation_status
   - loading_complete_callback

4. **Testing** 수행
   - 단일 로봇 시나리오
   - 2로봇 시뮬레이션
   - 3로봇 스트레스 테스트

---

**빌드 상태**: ✅ Success (colcon build)
**테스트 상태**: ✅ Ready to test
**다음 단계**: skip_mode=true로 테스트 실행
