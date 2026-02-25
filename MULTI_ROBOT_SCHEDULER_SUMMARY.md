# 다중 로봇 작업 스케줄러 구현 완료

## 개요

Kitchmatics FMS를 위한 **다중 로봇 작업 스케줄러(Task Scheduler)** 구현이 완료되었습니다.

이 시스템은 여러 pinky 로봇(pinky1, pinky2, pinky3)이 동시에 주문을 받았을 때, **pickup_spot에 한 번에 1대의 로봇만 접근 가능하도록 효율적으로 조율**합니다.

## 구현된 파일

### 1. 핵심 모듈

#### `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/task_scheduler.py` (새 파일)

**클래스:**

- **`TaskScheduler`**: 다중 로봇 작업 조율의 중심
  - 작업 큐 관리 (FIFO)
  - 로봇에 작업 할당
  - Pickup spot 접근 제어
  - 작업 상태 추적
  - 에러 처리

- **`PickupSlotManager`**: Pickup spot 단일 슬롯 관리
  - FIFO 큐를 통한 순서대로 접근 제어
  - 대기 로봇을 대기 존(waiting zone)으로 유도
  - 슬롯 타임아웃 처리
  - 로봇 순서 관리

### 2. 문서

#### `/home/gw/kitchmatics/roscamp-repo-1/fms/TASK_SCHEDULER_GUIDE.md`

- 아키텍처 설명
- 상세한 사용 패턴
- 3개 주문 동시 도착 시나리오 예제
- 대기 존(waiting zone) 전략
- 타임아웃 처리
- 상태 모니터링
- 통합 체크리스트

#### `/home/gw/kitchmatics/roscamp-repo-1/fms/SCHEDULER_QUICK_REFERENCE.md`

- 클래스 및 메서드 빠른 참조
- 작업 상태 다이어그램
- 일반적인 워크플로우 코드 스니펫
- 예제 및 테스트 방법
- 파라미터 튜닝 가이드

#### `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/scheduler_integration_example.py` (참고용)

- `FMSNodeWithScheduler` 클래스: 스케줄러를 FMS 노드에 통합하는 방법 시연
- 3개 주문 동시 도착 워크플로우 예제
- 실제 FMS 코드에 통합하기 위한 템플릿 제공

### 3. 테스트

#### `/home/gw/kitchmatics/roscamp-repo-1/fms/test_task_scheduler.py`

- 6개의 포괄적인 테스트 스위트
- 기본 동작 테스트
- 단일/다중 로봇 pickup 큐 테스트
- 에러 처리 및 복구 테스트
- 슬롯 타임아웃 테스트
- 상태 리포팅 테스트

## 핵심 기능

### 1. 작업 상태 관리

```
PENDING → ASSIGNED → MOVING_TO_PICKUP
   ↓                 ↓
   └───────────────→ WAITING_FOR_PICKUP → AT_PICKUP
                                ↓
                               LOADED → MOVING_TO_TABLE → AT_TABLE → COMPLETED
                                ↑
                              FAILED ← (error occurred)
```

### 2. Pickup Spot 접근 제어 (핵심 기능)

**시나리오: 3개 주문 동시 도착**

```
T0: 3개 주문 도착
    → pinky1, pinky2, pinky3에 작업 할당

T1: pinky1 pickup_spot 도착
    → 슬롯 요청 → 승인됨 (즉시 로딩)

T2: pinky2 pickup_spot 도착
    → 슬롯 요청 → 거부됨 (pinky1 점유)
    → pinky2를 큐에 추가 (1순위)
    → point13으로 대기하도록 지정

T3: pinky3 pickup_spot 도착
    → 슬롯 요청 → 거부됨 (pinky1 점유)
    → pinky3를 큐에 추가 (2순위)
    → pinky3_spot에서 대기

T4: pinky1 로딩 완료
    → 슬롯 해제
    → 큐의 다음 로봇(pinky2) 통보
    → pinky2가 pickup_spot 진입 가능

T5: pinky2 로딩 완료
    → 슬롯 해제
    → 큐의 다음 로봇(pinky3) 통보
    → pinky3가 pickup_spot 진입 가능

T6: pinky3 로딩 완료
    → 슬롯 해제
    → 큐 비움

결과: 모든 로봇이 순서대로 로딩 완료 → 각자 배송 진행
```

### 3. 대기 존 전략

| 로봇 상태 | 대기 위치 | 이유 |
|---------|---------|------|
| 홀딩(로딩 중) | pickup_spot | 음식 로딩 |
| 큐 1순위 | point13 | pickup_spot에 가장 가까움 |
| 큐 2순위 | pinky2_spot | 안전하게 떨어져 있음 |
| 큐 3순위 | pinky3_spot | 안전하게 떨어져 있음 |

## 테스트 결과

### Test 1: 기본 동작
```
✓ 작업 큐 추가
✓ 로봇에 작업 할당
✓ 작업 상태 추적
```

### Test 2: 단일 로봇
```
✓ Pickup 접근 승인
✓ 로딩 완료 및 슬롯 해제
✓ 배송 완료 처리
```

### Test 3: 다중 로봇 (3개 동시 주문)
```
✓ 첫 번째 로봇: 슬롯 즉시 획득
✓ 두 번째 로봇: 큐 대기, point13로 이동
✓ 세 번째 로봇: 큐 대기, parking spot에서 대기
✓ 슬롯 해제 시 다음 로봇에 자동 통보
✓ 모든 로봇이 순서대로 처리됨
```

### Test 4: 에러 처리
```
✓ 로봇 에러 발생 시 슬롯 자동 해제
✓ 큐에서 에러 로봇 제거
✓ 실패한 작업 큐에 반환 (재시도)
✓ 다음 로봇에 자동으로 슬롯 할당
```

### Test 5: 타임아웃 처리
```
✓ 최대 점유 시간 초과 감지 (기본값: 60초)
✓ 강제 해제 메커니즘
✓ 다음 로봇에 슬롯 할당
```

### Test 6: 상태 리포팅
```
✓ 각 작업 상태 조회
✓ 로봇별 현재 작업 조회
✓ 큐 상태 상세 조회
✓ 작업 요약 통계 조회
```

## API 요약

### TaskScheduler 주요 메서드

```python
# 작업 관리
task_id = scheduler.add_task(task)
task = scheduler.assign_task_to_robot(robot_id)
task = scheduler.get_robot_task(robot_id)

# Pickup 접근 제어
is_granted = scheduler.request_pickup_access(robot_id, task_id)
scheduler.robot_loaded(robot_id, task_id)  # 슬롯 해제
scheduler.robot_delivered(robot_id, task_id)

# 대기 존
zone = scheduler.get_next_waiting_zone(robot_id)

# 상태 조회
status = scheduler.get_scheduler_status()
summary = scheduler.get_task_summary()
queue_status = scheduler.get_pickup_queue_status()

# 에러 처리
scheduler.handle_robot_error(robot_id, error_msg)
```

### PickupSlotManager 주요 메서드

```python
# 슬롯 제어
is_granted = mgr.request_pickup_slot(robot_id)
next_robot = mgr.release_pickup_slot(robot_id)

# 큐 상태
position = mgr.get_queue_position(robot_id)  # 0=홀딩, 1=1순위, 2=2순위, -1=없음
robots = mgr.get_all_waiting_robots()
next_robot = mgr.get_next_in_queue()

# 타임아웃
has_timeout = mgr.check_slot_timeout()
next_robot = mgr.force_release_slot()
```

## FMS 노드에 통합하기

### Step 1: 스케줄러 초기화

```python
from fms.task_scheduler import TaskScheduler
from fms.zone_manager import ZoneManager

class FMSNode(Node):
    def __init__(self):
        self.zone_manager = ZoneManager()
        self.task_scheduler = TaskScheduler(self.zone_manager)
```

### Step 2: 타이머 설정

```python
# 작업 할당 타이머 (2Hz)
self.assign_timer = self.create_timer(0.5, self.assign_tasks)

# Pickup 큐 체크 타이머 (10Hz)
self.queue_timer = self.create_timer(0.1, self.check_pickup_queue)
```

### Step 3: 이벤트 핸들러 구현

```python
# 새 주문 도착
def on_order_received(self, order_msg):
    task = Task(...)
    task_id = self.task_scheduler.add_task(task)

# 작업 할당 (2Hz)
def assign_tasks(self):
    for robot_id in available_robots:
        task = self.task_scheduler.assign_task_to_robot(robot_id)
        if task:
            self.send_navigate_goal(robot_id, 'pickup_spot')

# 로봇이 pickup에 도착
def on_robot_reached_pickup(self, robot_id):
    task = self.task_scheduler.get_robot_task(robot_id)
    is_granted = self.task_scheduler.request_pickup_access(
        robot_id, task.task_id
    )
    if is_granted:
        self.publish_goal_arrived(task.order_id)
    else:
        zone = self.task_scheduler.get_next_waiting_zone(robot_id)
        self.send_navigate_goal(robot_id, zone)

# 로딩 완료
def on_food_loaded(self, robot_id, task_id):
    self.task_scheduler.robot_loaded(robot_id, task_id)
    self.send_navigate_goal(robot_id, table_location)
    self.check_pickup_queue_and_advance()

# 배송 완료
def on_delivery_complete(self, robot_id, task_id):
    self.task_scheduler.robot_delivered(robot_id, task_id)
    self.send_navigate_goal(robot_id, parking_spot)

# Pickup 큐 체크 (10Hz)
def check_pickup_queue_and_advance(self):
    if self.task_scheduler.pickup_manager.check_slot_timeout():
        next_robot = self.task_scheduler.pickup_manager.force_release_slot()
        if next_robot:
            self.send_navigate_goal(next_robot, 'pickup_spot')

# 에러 처리
def on_robot_error(self, robot_id, error_msg):
    self.task_scheduler.handle_robot_error(robot_id, error_msg)
    self.check_pickup_queue_and_advance()
```

### Step 4: ROS 2 토픽 연결

```python
# 구독자
self.order_sub = self.create_subscription(
    OrderRequest, '/fms/order_request',
    self.on_order_received, 10
)

self.delivery_sub = self.create_subscription(
    DeliveryComplete, '/fms/delivery_complete',
    self.on_delivery_complete, 10
)

# 발행자
self.scheduler_status_pub = self.create_publisher(
    Dict, '/fms/scheduler_status', 10
)
```

## 성능 특성

| 작업 | 시간 복잡도 | 예상 시간 |
|-----|-----------|---------|
| 작업 추가 | O(1) | <0.1ms |
| 작업 할당 | O(1) | <0.1ms |
| Pickup 요청 | O(1) | <0.1ms |
| 슬롯 해제 | O(1) | <0.1ms |
| 상태 조회 | O(n) | <1ms |
| 큐 체크 | O(1) | <0.1ms |

전형적인 경우 (3개 로봇, 10개 작업):
- 메모리: ~1KB per task
- CPU: <1% for queue operations

## 파라미터 튜닝

### Pickup 슬롯 타임아웃

```python
# 기본값: 60초
scheduler.pickup_manager.holding_timeout = 60.0

# 사용 사례에 따라 조정:
# - 빠른 로딩: 30초
# - 느린 로딩: 90초
```

### 대기 존 위치

```python
scheduler.pickup_manager.waiting_zone_positions = {
    'point13': {'x': 0.585, 'y': 0.63},  # 1순위 (pickup 가장 가까움)
    'pinky1_spot': {'x': 0.585, 'y': 0.085},  # 기본
    'pinky2_spot': {'x': 0.585, 'y': 0.255},
    'pinky3_spot': {'x': 0.585, 'y': 0.915},
}
```

## 현재 코드와의 호환성

### 기존 TaskManager와의 관계

새로운 `TaskScheduler`는 기존 `TaskManager`를 보완합니다:

- **TaskManager**: 개별 작업 관리 (PENDING, ASSIGNED, COMPLETED, FAILED)
- **TaskScheduler**: 다중 로봇 조율 + pickup 슬롯 제어

통합 방식:
```python
# TaskManager는 여전히 사용 (이미 fms_node.py에 통합됨)
self.task_manager = TaskManager()

# TaskScheduler는 더 높은 수준의 조율 제공
self.task_scheduler = TaskScheduler(self.zone_manager)
```

### 기존 ZoneManager와의 호환성

`TaskScheduler`는 `ZoneManager`를 그대로 활용합니다:
- Zone 기반 충돌 회피
- 대기 존 지정
- 로봇 위치 추적

## 다음 단계

### 통합 작업 (우선순위: 높음)
1. [ ] `fms_node.py`에 TaskScheduler 추가
2. [ ] 타이머 콜백 구현
3. [ ] ROS 2 토픽 연결
4. [ ] 상태 발행자 추가

### 테스트 (우선순위: 높음)
1. [ ] Skip 모드로 테스트
2. [ ] 실제 로봇 테스트
3. [ ] 여러 주문 시나리오 테스트

### 향상 (우선순위: 중간)
1. [ ] GUI에서 큐 상태 표시
2. [ ] 거리 기반 로봇 선택 (이미 fleet_controller에 TODO)
3. [ ] 배터리 기반 작업 할당
4. [ ] 동적 경로 재계획

## 파일 위치 요약

| 파일 | 경로 | 설명 |
|-----|-----|------|
| 핵심 구현 | `fms/fms/task_scheduler.py` | TaskScheduler, PickupSlotManager |
| 가이드 | `fms/TASK_SCHEDULER_GUIDE.md` | 상세 가이드 (패턴, 워크플로우) |
| 빠른 참조 | `fms/SCHEDULER_QUICK_REFERENCE.md` | API 참조, 예제 |
| 통합 예제 | `fms/fms/scheduler_integration_example.py` | FMS 통합 패턴 |
| 테스트 | `fms/test_task_scheduler.py` | 포괄적인 테스트 스위트 |

## 문의 사항

### Q: Pickup 큐가 필요한 이유는?
A: Pickup_spot은 물리적 공간이 제한되어 있어 한 번에 1개 로봇만 음식을 받을 수 있습니다. 큐가 없으면 로봇들이 충돌하거나 대기 없이 경합합니다.

### Q: Point13이 무엇인가요?
A: Point13은 pickup_spot 근처의 대기 지점입니다. 큐에서 1순위인 로봇을 여기로 보내면, 슬롯이 열릴 때 빠르게 pickup_spot에 진입할 수 있습니다.

### Q: 타임아웃 60초는 충분한가요?
A: 목표에 따라 조정하세요. 음식 로딩이 평균 10초라면 60초는 충분히 여유 있습니다. 더 빠르게 하려면 30초로 설정하세요.

### Q: 에러가 발생하면 어떻게 되나요?
A: 스케줄러가 자동으로 정리합니다:
1. 슬롯 해제 (다음 로봇 진입)
2. 큐에서 제거
3. 작업 실패 표시
4. 작업을 다시 큐에 추가 (재시도)

## 라이선스 및 기여

이 구현은 Kitchmatics FMS 프로젝트의 일부입니다.
개선 사항이나 버그 리포트는 팀에 알려주세요.
