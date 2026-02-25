# FMS Zone Manager & Task Scheduler 통합 완료

## 1. 통합 내용

FMS Node에 다음 컴포넌트들을 성공적으로 통합했습니다:

### 1.1 새로운 Imports
```python
from .task_manager import TaskManager, Task
from .task_scheduler import TaskScheduler, PickupSlotManager
```

### 1.2 초기화 (FMSNode.__init__)
```python
# Zone Manager와 Task Scheduler 초기화
self.zone_manager = ZoneManager()
self.task_scheduler = TaskScheduler(self.zone_manager)
```

### 1.3 새로운 타이머들
- **pickup_queue_timer** (0.1s, 10Hz): Pickup 큐 처리
- **cleanup_timer** (1.0s, 1Hz): 만료된 예약 정리

## 2. 주요 변경 사항

### 2.1 Order Request 처리 (order_request_callback)
```python
# Task Manager + Task Scheduler 모두에 추가
task = self.task_manager.create_task(...)
self.task_scheduler.add_task(task)
```

### 2.2 Task 할당 (process_pending_tasks)
기존 로직:
```python
task = self.task_manager.assign_task(robot.robot_id)
```

개선된 로직:
```python
task = self.task_scheduler.assign_task_to_robot(robot.robot_id)

# Zone 예약 시도
if self.zone_manager.reserve_zone(robot.robot_id, 'zone_pickup'):
    # 예약 성공: pickup으로 직진
    self._send_robot_to_pickup(robot.robot_id)
else:
    # 예약 실패: 대기 존으로 이동
    waiting_zone = self.task_scheduler.get_next_waiting_zone(robot.robot_id)
    self._send_robot_to_waiting_zone(robot.robot_id, waiting_zone)
```

### 2.3 Navigation Status 체크 (_check_navigation_status)

**Pickup 도착 시:**
```python
if robot.status == RobotState.STATUS_MOVING_TO_PICKUP:
    # Pickup 슬롯 요청
    can_enter = self.task_scheduler.request_pickup_access(robot_id, task.task_id)

    if can_enter:
        # 즉시 진입 허용
        self.zone_manager.occupy_zone(robot_id, 'zone_pickup')
    else:
        # 대기 존으로 이동
        waiting_zone = self.task_scheduler.get_next_waiting_zone(robot_id)
        self._send_robot_to_waiting_zone(robot_id, waiting_zone)
```

**Waiting Zone 도착 시:**
```python
elif robot.status == RobotState.STATUS_IDLE and robot.target_location:
    # 대기 중인 로봇이 도착
    # Pickup 슬롯 가용성 재확인
    self._process_pickup_queue()
```

### 2.4 Food Loading 완료 (loading_complete_callback → notify_food_loaded)
```python
# Pickup 슬롯 해제
self.task_scheduler.robot_loaded(robot_id, scheduler_task.task_id)
self.zone_manager.leave_zone(robot_id, 'zone_pickup')

# 다음 대기 로봇 진입 허용
self._process_pickup_queue()
```

### 2.5 배송 완료 (delivery_complete_callback)
```python
# Scheduler에서도 task 완료 처리
self.task_scheduler.robot_delivered(task.assigned_robot, task.task_id)
```

## 3. 새로운 메서드들

### 3.1 _send_robot_to_waiting_zone
대기 중인 로봇을 대기 존으로 보냄
```python
def _send_robot_to_waiting_zone(self, robot_id: str, waiting_zone_name: str):
    # 'point13', 'pinky1_spot' 등의 위치로 이동
```

### 3.2 _process_pickup_queue
대기 중인 로봇의 pickup 슬롯 할당
```python
def _process_pickup_queue(self):
    # 대기 로봇이 있고 pickup이 가능하면
    # 다음 로봇에게 슬롯 할당
    # zone 예약 + 네비게이션
```

### 3.3 _cleanup_expired_reservations
만료된 Zone 예약 정리
```python
def _cleanup_expired_reservations(self):
    # 30초 이상 유지된 예약 해제
    # Pickup 슬롯 타임아웃 확인
```

## 4. 상태 머신 개선

### 기존 (단순)
```
IDLE → ASSIGNED → MOVING_TO_PICKUP → WAITING_FOR_ROBOT_ARM → MOVING_TO_TABLE → ...
```

### 개선 (Task Scheduler 적용)
```
IDLE → ASSIGNED → MOVING_TO_PICKUP
         ├─ → AT_PICKUP (직접 진입)
         │   → LOADED → MOVING_TO_TABLE
         │
         └─ → WAITING_FOR_PICKUP (슬롯 대기)
             → (다른 로봇 완료 대기)
             → AT_PICKUP (슬롯 획득)
             → LOADED → MOVING_TO_TABLE
```

**Task Scheduler의 TaskState:**
- PENDING: 할당 대기
- ASSIGNED: 로봇에 할당됨
- MOVING_TO_PICKUP: Pickup 향해 이동
- WAITING_FOR_PICKUP: Pickup 슬롯 대기
- AT_PICKUP: Pickup 진행 중
- LOADED: 음식 로드됨
- MOVING_TO_TABLE: 테이블로 이동
- AT_TABLE: 테이블 도착
- COMPLETED: 배송 완료
- FAILED: 실패

## 5. Zone Manager 통합

### Zone 예약 (Reservation)
- **목적**: 로봇이 움직이기 전에 목적지 Zone을 예약
- **타임아웃**: 30초 (예약된 로봇이 도착하지 않으면 해제)

### Zone 점유 (Occupation)
- **목적**: 로봇이 실제로 Zone에 들어왔을 때 점유
- **해제**: 로봇이 Zone을 떠날 때

### 자동 정리
- 1Hz 타이머로 만료된 예약 자동 정리
- Pickup 슬롯 타임아웃 감지 및 강제 해제

## 6. Pickup Slot Manager 통합

### FIFO 대기열
- 로봇들이 Pickup 접근을 위해 대기
- 한 로봇이 완료되면 다음 로봇에게 자동으로 슬롯 할당

### 대기 Zone 할당
- **Queue Position 1** (다음): `point13` (Pickup에 가장 가까움)
- **Queue Position 2+** (그 다음): Robot의 주차 위치 (`pinky1_spot` 등)

### 타임아웃 처리
- 60초 이상 Pickup 슬롯을 점유한 로봇은 강제 해제
- 다음 대기 로봇이 진입 허용

## 7. Fleet Status 개선

### 기존
```python
fleet_status.pending_orders = self.task_manager.get_pending_count()
fleet_status.active_orders = self.task_manager.get_active_count()
```

### 개선
```python
fleet_status.pending_orders = self.task_scheduler.get_pending_count()
fleet_status.active_orders = self.task_scheduler.get_active_count()
```

더 정확한 스케줄러 상태 반영 + 주기적 상세 로깅

## 8. 호환성

### 기존 코드 유지
- TaskManager 여전히 사용
- FleetController 여전히 사용
- 모든 기존 메서드/속성 유지

### 새로운 기능 추가
- TaskScheduler가 상위 계층에서 작동
- Zone Manager가 충돌 회피 제공
- 기존 코드와 새 코드가 병행

## 9. 테스트 시나리오

### 단일 로봇 (기존과 동일)
```
Order → Robot 할당 → Pickup Zone 예약 → Pickup → Table → Complete
```

### 2개 로봇 동시 주문 (새로운 기능)
```
Order1 → Robot1 할당 → Pickup Zone 예약 ✓ → Pickup 진행
Order2 → Robot2 할당 → Pickup Zone 예약 ✗ → point13 대기

(Robot1 로딩 완료)
         → Zone 해제 → Robot2 Pickup Zone 예약 ✓ → Pickup 진행
```

### 3개 로봇 대기열
```
Order1 → Robot1: Pickup 진행
Order2 → Robot2: point13에서 대기 (Queue Pos 1)
Order3 → Robot3: parking_spot에서 대기 (Queue Pos 2)

(Robot1 완료)
         → Robot2 진입 허용 → Pickup
         → Robot3 point13으로 이동 (Queue Pos 1 승격)

(Robot2 완료)
         → Robot3 진입 허용 → Pickup
```

## 10. 빌드 및 실행

### 빌드
```bash
colcon build --packages-select fms
# 결과: Built fms successfully
```

### 실행
```bash
ros2 launch fms fms_closed_network.launch.py
```

## 11. 로깅 개선

### 새로운 로그 메시지
```
"Zone {zone_id} reserved for robot {robot_id}"
"Robot {robot_id} granted immediate pickup slot access"
"Robot {robot_id} added to pickup queue (position: {N})"
"Robot {robot_id} granted pickup access, entering pickup spot"
"Robot {robot_id} waiting for pickup slot, sending to waiting zone"
"Granting pickup slot to waiting robot {robot_id}"
"Cleaned up {N} expired zone reservations"
```

### 상세 상태 로깅
```python
# 5번마다 (0.5초 × 5 = 5초 간격)
scheduler_status = self.task_scheduler.get_scheduler_status()
# pending_tasks, active_tasks, completed_tasks, pickup_queue 상태 출력
```

## 12. 향후 개선사항

1. **Config 파일 로드**: Zone과 Waiting zone을 config.yaml에서 로드
2. **Advanced Waiting Strategy**: 로봇 배터리/거리 기반 대기 순서 결정
3. **Timeout 처리**: 로봇이 대기 zone에서 움직이지 않으면 에러 처리
4. **스케줄러 통계**: 처리 시간, 대기 시간, 처리량 추적
5. **모니터링 대시보드**: 실시간 Queue, Zone 상태 시각화

## 13. 코드 위치

수정된 파일: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py`

주요 메서드:
- `process_pending_tasks()` (Line 590-620)
- `_send_robot_to_waiting_zone()` (Line 665-678)
- `_check_navigation_status()` (Line 710-770)
- `_process_pickup_queue()` (Line 945-970)
- `_cleanup_expired_reservations()` (Line 972-989)
- `notify_food_loaded()` (Line 890-930)
- `delivery_complete_callback()` (Line 449-471)

## 14. 성능

### 타이머 설정 (권장)
- **Task Assignment**: 0.5s (2Hz) - 적절한 응답성
- **Pickup Queue Processing**: 0.1s (10Hz) - 빠른 대기열 처리
- **Reservation Cleanup**: 1.0s (1Hz) - 배경 작업

### 메모리 사용
- Zone Manager: O(1) per zone (기본 20개 zone)
- Task Scheduler: O(n) where n = pending + active tasks
- Pickup Queue: O(m) where m = waiting robots (일반적으로 < 5)

---

**통합 완료**: 2026-02-25
**빌드 상태**: ✅ Success
**테스트 가능**: ✅ Ready
