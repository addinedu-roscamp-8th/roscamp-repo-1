# Task Scheduler 통합 가이드

## 개요

`TaskScheduler`는 다중 로봇 작업 할당 및 픽업 지점 접근 제어를 관리합니다. 이 모듈은 핵심 문제를 해결합니다: **여러 로봇이 동시에 pickup_spot에 도착할 경우 물리적으로 같은 공간을 점유할 수 없습니다**.

## 아키텍처

### 구성 요소

1. **TaskScheduler**: 메인 코디네이터
   - 작업 큐 관리 (FIFO)
   - 로봇-작업 할당 로직
   - 작업 상태 추적

2. **PickupSlotManager**: 픽업 접근 제어
   - 단일 픽업 슬롯 (한 번에 1대의 로봇만 허용)
   - 큐 관리 (FIFO)
   - 대기 구역 할당
   - 타임아웃 처리

### 작업 상태

```
PENDING
  ↓
ASSIGNED → MOVING_TO_PICKUP
  ↓
WAITING_FOR_PICKUP (대기열에 등록됨)
  ↓
AT_PICKUP (슬롯 접근 권한 보유)
  ↓
LOADED
  ↓
MOVING_TO_TABLE → AT_TABLE → COMPLETED

FAILED (오류 발생)
```

## 사용 패턴

### 1. 초기화

```python
from fms.task_scheduler import TaskScheduler
from fms.zone_manager import ZoneManager

# FMS 노드 __init__에서:
self.zone_manager = ZoneManager()
self.task_scheduler = TaskScheduler(self.zone_manager)
```

### 2. 신규 주문 처리

```python
def on_order_received(self, order_msg):
    # 주문으로부터 작업 생성
    task = Task(
        order_id=order_msg.order_id,
        menu_id=order_msg.menu_id,
        table_number=order_msg.table_number,
        quantity=order_msg.quantity,
        sauce_type=order_msg.sauce_type,
        voice_order=order_msg.voice_order
    )

    # 스케줄러 큐에 추가
    task_id = self.task_scheduler.add_task(task)
    logger.info(f"Order {order_msg.order_id} queued as task {task_id}")
```

### 3. 유휴 로봇에 작업 할당

주기적으로 호출하여 (예: 2 Hz) 대기 중인 작업과 유휴 로봇을 매칭합니다:

```python
def assign_tasks_timer(self):
    # 플릿 컨트롤러에서 유휴 로봇 목록 가져오기
    idle_robots = [
        robot.robot_id for robot in self.fleet_controller.get_all_robots()
        if robot.is_available()
    ]

    # 대기 중인 작업을 유휴 로봇에 할당
    for robot_id in idle_robots:
        task = self.task_scheduler.assign_task_to_robot(robot_id)
        if task:
            # 로봇에 작업 전송 (pickup_spot으로 이동)
            self.send_navigate_goal(robot_id, 'pickup_spot')
            logger.info(f"Robot {robot_id} assigned task {task.task_id}")
```

### 4. 로봇이 픽업 지점에 도착한 경우

로봇이 pickup_spot에 도착했을 때:

```python
def on_robot_reached_pickup(self, robot_id: str):
    task = self.task_scheduler.get_robot_task(robot_id)
    if not task:
        logger.warning(f"Robot {robot_id} reached pickup but has no task")
        return

    # 픽업 슬롯 접근 요청
    is_granted = self.task_scheduler.request_pickup_access(
        robot_id, task.task_id
    )

    if is_granted:
        # 로봇이 즉시 적재 가능
        logger.info(f"Robot {robot_id} has pickup access, loading...")
        # goal_arrived 메시지 발행
        self.publish_goal_arrived(robot_id, task.order_id)
    else:
        # 로봇이 대기해야 함
        waiting_zone = self.task_scheduler.get_next_waiting_zone(robot_id)
        logger.info(f"Robot {robot_id} waiting, moving to {waiting_zone}")
        # 로봇을 대기 구역으로 이동 (다음 순서인 경우 point13)
        self.send_navigate_goal(robot_id, waiting_zone)
```

### 5. 로봇 적재 완료

음식 적재가 완료되었을 때:

```python
def on_food_loaded(self, robot_id: str, order_id: str):
    task = self.task_scheduler.get_robot_task(robot_id)
    if not task:
        logger.warning(f"Robot {robot_id} has no current task")
        return

    # 픽업 슬롯 해제 및 큐의 다음 로봇 진입
    self.task_scheduler.robot_loaded(robot_id, task.task_id)

    # 로봇을 테이블로 이동
    table_location = self.get_table_location(task.table_number)
    self.send_navigate_goal(robot_id, table_location)

    # 큐의 다음 로봇이 진입 가능한지 확인
    self.check_pickup_queue_and_advance()
```

### 6. 배달 완료

```python
def on_delivery_complete(self, robot_id: str, order_id: str):
    task = self.task_scheduler.get_robot_task(robot_id)
    if not task:
        return

    # 작업 완료 처리
    self.task_scheduler.robot_delivered(robot_id, task.task_id)

    # 로봇을 주차 지점으로 복귀
    parking_spot = self.fleet_controller.parking_spots.get(robot_id)
    self.send_navigate_goal(robot_id, parking_spot)
```

### 7. 주기적 큐 진행

자주 호출하여 (예: 10 Hz) 픽업 큐를 진행시킵니다:

```python
def check_pickup_queue_timer(self):
    queue_status = self.task_scheduler.get_pickup_queue_status()

    # 타임아웃 확인 (로봇이 최대 픽업 시간 초과)
    if self.task_scheduler.pickup_manager.check_slot_timeout():
        logger.warning("Pickup slot timeout, forcing release")
        next_robot = self.task_scheduler.pickup_manager.force_release_slot()
        if next_robot:
            # 다음 로봇에게 진입 가능 알림
            task = self.task_scheduler.get_robot_task(next_robot)
            if task:
                self.send_navigate_goal(next_robot, 'pickup_spot')

    # 대기열이 있을 경우 상태 로깅
    if queue_status['queue_length'] > 0:
        logger.debug(f"Pickup queue: {queue_status['waiting_robots']}")
```

### 8. 오류 처리

```python
def on_robot_error(self, robot_id: str, error_msg: str):
    logger.error(f"Robot {robot_id}: {error_msg}")

    # 스케줄러가 정리 작업 수행:
    # - 픽업 슬롯 해제
    # - 큐에서 제거
    # - 작업 실패 처리 후 큐로 반환
    # - 다음 로봇에게 픽업 접근 권한 부여
    self.task_scheduler.handle_robot_error(robot_id, error_msg)

    # 큐 진행 가능 여부 확인
    self.check_pickup_queue_and_advance()
```

## 예시 워크플로우: 3건의 동시 주문

### 시나리오

모든 로봇이 유휴 상태일 때 3건의 주문이 동시에 도착:

| 시점 | 이벤트 | 상태 |
|------|--------|------|
| T0 | 3건의 주문 도착 | 큐: [order1, order2, order3] |
| T1 | pinky1, pinky2, pinky3 할당 | 활성: 3건, 대기: 0건 |
| T2 | pinky1 픽업 도착 | pinky1 슬롯 보유, pinky2/3 픽업으로 이동 중 |
| T3 | pinky2 픽업 도착 | pinky2 대기열 등록 (point13에서 대기) |
| T4 | pinky3 픽업 도착 | pinky3 대기열 등록 (parking_spot에서 대기) |
| T5 | pinky1 적재 완료, 출발 | pinky2 슬롯 획득, 대기 로봇 = 1 |
| T6 | pinky2 적재 완료, 출발 | pinky3 슬롯 획득, 대기 로봇 = 0 |
| T7 | pinky3 적재 완료, 출발 | 모든 로봇 테이블로 배달 중 |
| T8+ | 배달 완료 | 모든 로봇 주차 지점으로 복귀 |

### 코드 흐름

```python
# T0-T1: 주문 도착 및 할당
for order in orders:
    fms.on_order_received(order)
for robot_id in available_robots:
    fms.assign_tasks_to_available_robots(robot_id)

# T2: pinky1 픽업 도착
fms.on_robot_reached_pickup('pinky1')
# → 픽업 접근 요청
# → 승인됨 (대기열 비어 있음)
# → goal_arrived 발행

# T3: pinky2 픽업 도착 (다른 시점)
# 내비게이션 진행 중, pinky1 아직 적재 중
fms.on_robot_reached_pickup('pinky2')
# → 픽업 접근 요청
# → 승인 거부 (pinky1이 슬롯 점유 중)
# → pinky2 대기열 등록
# → 대기 구역(point13)으로 이동

# T4: pinky3 픽업 도착
fms.on_robot_reached_pickup('pinky3')
# → 픽업 접근 요청
# → 승인 거부 (pinky1이 여전히 점유 중)
# → pinky3 대기열 등록
# → 대기 구역(pinky3_spot - 더 이상 필요 없는 주차 지점)으로 이동

# T5: pinky1 적재 완료
fms.on_food_loaded('pinky1', task1.task_id)
# → 슬롯 해제
# → pinky2에게 접근 권한 알림
# → pinky2 pickup_spot으로 이동

# T6: pinky2 적재 완료
fms.on_food_loaded('pinky2', task2.task_id)
# → 슬롯 해제
# → pinky3에게 접근 권한 알림
# → pinky3 pickup_spot으로 이동

# ... 이하 동일
```

## 대기 구역 전략

### Point13 vs 주차 지점

로봇이 픽업 슬롯을 기다리는 경우:

1. **대기열 첫 번째**: `point13`으로 이동 (pickup_spot에 가장 가까움)
   - 슬롯이 열리면 즉시 픽업으로 이동 가능
   - 최소 지연 (~0.5초 내비게이션)

2. **나머지 대기열**: parking_spot에 머무르거나 이동
   - 첫 번째 대기열의 로봇이 완료될 때까지 대기
   - 첫 번째 순서가 되면 point13으로 이동

### 설정

`PickupSlotManager`에서 대기 구역을 수정합니다:

```python
self.waiting_zone_positions = {
    'point13': {'x': 0.585, 'y': 0.63, 'zone_id': 'zone_point13'},
    'pinky1_spot': {'x': 0.585, 'y': 0.085, 'zone_id': 'zone_parking1'},
    'pinky2_spot': {'x': 0.585, 'y': 0.255, 'zone_id': 'zone_parking2'},
    'pinky3_spot': {'x': 0.585, 'y': 0.915, 'zone_id': 'zone_parking3'},
}
```

## 상태 모니터링

### 현재 상태 조회

```python
# 종합 상태
status = task_scheduler.get_scheduler_status()
print(f"Pending: {status['pending_tasks']}")
print(f"Active: {status['active_tasks']}")
print(f"Waiting for pickup: {status['robots_waiting_for_pickup']}")
print(f"Queue: {status['pickup_queue']}")

# 상태별 작업 요약
summary = task_scheduler.get_task_summary()
print(f"Pending: {summary['PENDING']}")
print(f"At pickup: {summary['AT_PICKUP']}")
print(f"Loaded: {summary['LOADED']}")
print(f"Completed: {summary['COMPLETED']}")

# 픽업 큐 상세 정보
queue = task_scheduler.get_pickup_queue_status()
print(f"Current holder: {queue['current_holder']}")
print(f"Waiting robots: {queue['waiting_robots']}")
print(f"Queue positions: {queue['queue_positions']}")
```

### 모니터링용 퍼블리셔

```python
def publish_scheduler_status(self):
    status = self.task_scheduler.get_scheduler_status()
    # /fms/scheduler_status로 발행
    self.scheduler_status_pub.publish(status)
```

## 타임아웃 처리

### 시나리오: 픽업 지점의 로봇이 제한 시간 초과

기본 타임아웃: 60초

```python
def check_pickup_queue_timer(self):
    if self.task_scheduler.pickup_manager.check_slot_timeout():
        logger.warning("Pickup timeout exceeded")
        next_robot = self.task_scheduler.pickup_manager.force_release_slot()
        # 기존 로봇이 강제 퇴출되고, 다음 로봇이 접근 권한 획득
```

### 커스터마이징

```python
# 커스텀 타임아웃 설정 (예: 30초)
task_scheduler.pickup_manager.holding_timeout = 30.0
```

## 테스트

### 통합 예제 실행

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
python3 -m fms.fms.scheduler_integration_example
```

3건의 동시 주문에 대한 워크플로우 타임라인을 출력합니다:

```
=== WORKFLOW: 3 Simultaneous Orders ===

T0: 3 orders arrive
Queue size: 3

T1: Assign tasks to 3 available robots
Assignments: 3
Pending: 0
Active: 3

T2: pinky1 reaches pickup_spot
Pickup queue: 0 waiting

T3: pinky2 reaches pickup_spot
Pickup queue: 1 waiting
pinky2 waiting zone: point13

T4: pinky3 reaches pickup_spot
Pickup queue: 2 waiting
pinky3 waiting zone: pinky3_spot

T5: pinky1 finishes loading
Pickup queue: 1 waiting
Next robot: pinky2

...
```

## 통합 체크리스트

FMS 노드에 통합할 때:

- [ ] TaskScheduler 및 Task 클래스 임포트
- [ ] FMS.__init__()에서 스케줄러 초기화
- [ ] 작업 생성이 포함된 주문 처리 메서드 작성
- [ ] 할당 타이머 생성 (2 Hz)
- [ ] 로봇 픽업 도착 이벤트 연결
- [ ] 음식 적재 완료 이벤트 연결
- [ ] 배달 완료 이벤트 연결
- [ ] 로봇 오류 이벤트 연결
- [ ] 픽업 큐 확인 타이머 생성 (10 Hz)
- [ ] 상태 퍼블리셔 생성
- [ ] skip_robot_arm=True 모드로 테스트
- [ ] 다중 동시 주문으로 테스트
- [ ] 로그에서 큐 상태 모니터링

## ROS 2 토픽 통합

```python
# 구독자
self.order_request_sub = self.create_subscription(
    OrderRequest,
    '/fms/order_request',
    self.on_order_received,
    10
)

self.delivery_complete_sub = self.create_subscription(
    DeliveryComplete,
    '/fms/delivery_complete',
    self.on_delivery_complete,
    10
)

# 스케줄러 상태 퍼블리셔
self.scheduler_status_pub = self.create_publisher(
    Dict,  # 커스텀 메시지 타입 사용
    '/fms/scheduler_status',
    10
)

# 타이머
self.assign_tasks_timer = self.create_timer(0.5, self.assign_tasks_timer)  # 2 Hz
self.queue_check_timer = self.create_timer(0.1, self.check_pickup_queue_timer)  # 10 Hz
```

## 성능 고려사항

- **큐 연산**: O(1) FIFO (deque)
- **작업 조회**: O(1) dict 사용
- **구역 연산**: O(n), n = 구역 수
- **일반적인 경우**: 대기 로봇 1~3대, 오버헤드 무시 가능

로봇 3대, 대기 작업 10~20건 기준:
- 메모리: 작업당 ~1 KB
- CPU: 큐 연산에 1% 미만

## 문제 해결

### 문제: 로봇이 픽업 지점에서 멈춤

**확인**: 픽업 슬롯 타임아웃이 60초를 초과하고 있는가?

```python
queue = task_scheduler.get_pickup_queue_status()
print(f"Current holder: {queue['current_holder']}")
print(f"Arrival time: {queue['holder_arrival_time']}")
```

**해결**: check_pickup_queue_timer()에서 강제 해제

### 문제: 큐가 진행되지 않음

**확인**: 다음 로봇이 픽업으로 이동하라는 알림을 받고 있는가?

```python
queue = task_scheduler.get_pickup_queue_status()
next_robot = queue['waiting_robots'][0]
# 로봇이 pickup_spot으로의 내비게이션 목표를 수신하고 있는지 확인
```

**해결**: on_food_loaded()에서 check_pickup_queue_and_advance()를 호출하는지 확인

### 문제: 작업이 WAITING_FOR_PICKUP 상태에서 멈춤

**확인**: point13에 있는 로봇이 큐 진행 시 pickup_spot으로 이동하라는 명령을 받고 있는가?

```python
robot_task = task_scheduler.get_robot_task(robot_id)
print(f"Task state: {task_scheduler.get_task_state(robot_task.task_id)}")
```

**해결**: 로봇이 큐에서 해제될 때 콜백 구현

## 다음 단계

1. **fms_node.py에 통합**: scheduler_integration_example.py의 패턴 활용
2. **토픽 발행 추가**: 모니터링을 위한 scheduler_status 발행
3. **단위 테스트 추가**: 큐 관리 및 타임아웃 테스트
4. **대기 구역 조정**: point13 거리 및 주차 지점 대안 최적화
5. **GUI 표시 구현**: 운영자에게 픽업 큐 상태 표시
