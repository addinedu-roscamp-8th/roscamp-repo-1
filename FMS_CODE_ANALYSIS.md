# FMS (Fleet Management System) 코드 분석 보고서

**작성일**: 2026-02-26
**분석 대상**: `/home/gw/kitchmatics/roscamp-repo-1/fms` 폴더
**분석 범위**: 구조, 제어 로직, 문제점 식별

---

## 1. FMS 시스템 구조

### 1.1 폴더 구조

```
fms/
├── fms/                              # 핵심 모듈
│   ├── fms_node.py                   # FMS 메인 노드 (2464줄)
│   ├── order_handler.py              # 주문 처리 워크플로우 (750줄)
│   ├── fleet_controller.py           # 로봇 상태 관리 (490줄)
│   ├── task_manager.py               # 작업 큐 관리 (283줄)
│   ├── collision_avoidance.py        # 다중 로봇 경로 충돌 회피 (1413줄)
│   ├── tcp_communication.py          # TCP 통신 (650줄)
│   ├── gui_tcp_server.py             # GUI TCP 서버 (200+줄)
│   ├── zone_manager.py               # 존 예약 시스템
│   ├── path_planner.py               # 경로 계획
│   ├── task_scheduler.py             # 작업 스케줄러
│   ├── error_detector.py             # 오류 감지
│   └── error_recovery.py             # 오류 복구
├── coordinator_Ws/                   # 로봇팔 코디네이터 (샌드위치)
│   └── src/sandwich_coordinator/
│       └── coordinator_node.py       # 로봇팔 조리 오케스트레이션
├── launch/
│   └── fms_closed_network.launch.py  # 시스템 런치 파일
├── config/
│   ├── fms_config.yaml              # 맵 좌표, 초기 포즈
│   └── navigation_graph.yaml        # 네비게이션 그래프
└── scripts/
    ├── send_order.py                # 테스트 주문 전송
    └── test_*.py                    # 테스트 스크립트들
```

### 1.2 네트워크 구성

**Closed Network (WiFi: kitchmatics)**

| 장치 | IP | ROS_DOMAIN_ID | 역할 |
|------|-----|------------------|------|
| gw PC (FMS) | 192.168.1.3 | 25 | 마스터 제어 스테이션 |
| pinky_b4bc | 192.168.1.7 | 11 | 모바일 로봇 1 (pinky1) |
| pinky_e2a8 | 192.168.1.6 | 12 | 모바일 로봇 2 (pinky2) |
| pinky_d29d | 192.168.1.11 | 13 | 모바일 로봇 3 (pinky3) - 비활성화 |
| jetcobot_aa1f | 192.168.0.56 | 20 | 로봇팔 1 |
| jetcobot_aa85 | 192.168.0.59 | 21 | 로봇팔 2 |

**통신 메커니즘**:
- FMS (DOMAIN_ID=25)가 마스터 역할
- Domain Bridge가 각 로봇의 도메인과 통신 중개
- TCP 포트 9000: GUI ↔ FMS 통신

---

## 2. 주요 제어 흐름

### 2.1 주문 처리 워크플로우 (Order Handler)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py`

```
[워크플로우 상태 머신]

┌─────────────┐
│ RECEIVED    │  GUI에서 주문 수신
└──────┬──────┘
       │ → 로봇 가용성 확인
       ↓
   ┌─────────┐
   │ QUEUED? │  → YES → 대기 큐에 추가, 알림 전송
   └────┬────┘
        │ NO
        ↓
   ┌────────────┐
   │ COOKING    │  로봇팔에 /cooking/order 발행
   └────┬───────┘
        ↓
   ┌──────────────┐
   │ LOADING      │  로봇 → pickup_spot 이동 (FollowWaypoints)
   └────┬─────────┘
        │ PickupArrival 발행
        ↓
   ┌──────────────┐
   │ LOADED       │  로봇팔 조리 완료, LoadingComplete 수신
   └────┬─────────┘  (Skip 모드: 3초 대기)
        ↓
   ┌──────────────┐
   │ DELIVERING   │  로봇 → tableN 이동
   └────┬─────────┘
        │ TableArrival 발행
        ↓
   ┌──────────────┐
   │ ARRIVED      │  delivery_notification 푸시 (GUI)
   └────┬─────────┘
        │ GUI에서 수령 확인
        ↓
   ┌──────────────┐
   │ COMPLETED    │  로봇 home 복귀 또는 다음 주문 처리
   └──────────────┘
```

**핵심 콜백**:
- `handle_new_order()`: GUI 주문 수신
- `handle_robot_arrived_pickup_spot()`: 픽업 지점 도착
- `handle_cooking_complete()`: 조리 완료
- `handle_robot_arrived_table()`: 테이블 도착
- `handle_delivery_confirmation()`: 수령 확인
- `_dispatch_order_to_robot()`: 대기 주문 자동 디스패치

### 2.2 Robot Status Callback (/pose 업데이트)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py:687`

```python
def robot_pose_callback(self, robot_id: str, msg: Pose):
    """
    /pose 메시지 수신 시 호출
    """
    # 1. 하트비트 등록 (오류 감지)
    self.error_detector.register_heartbeat(robot_id)

    # 2. 포즈 업데이트
    self.fleet_controller.update_robot_pose(robot_id, msg)
    self.zone_manager.update_robot_position(robot_id, msg)

    # 3. 충돌 회피 - 지나간 노드 해제 (↑ 핵심!)
    released_nodes = self.collision_avoidance.update_robot_position(
        robot_id, msg.position.x, msg.position.y
    )

    # 4. 대기 중인 로봇 재계획 트리거
    if released_nodes:
        self._trigger_waiting_robots_replan(robot_id, released_nodes)

    # 5. 도착 판정 (0.1m 이내)
    self._check_navigation_status(robot_id)
```

**노드 해제 메커니즘**:
- 로봇이 지나간 각 노드에서 점유 상태 해제
- 대기 중인 다른 로봇들이 이제 통과 가능
- `_trigger_waiting_robots_replan()` 호출 → 재계획 시도

### 2.3 Pickup Spot 도착 알림

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py:1420-1455`

```python
def _on_final_destination_reached(self, robot_id: str, location_name: str):
    """
    최종 도착지 도착 시 호출
    """
    if location_name == 'pickup_spot':
        # PickupArrival 메시지 발행
        arrival_msg = PickupArrival()
        arrival_msg.robot_id = robot_id
        arrival_msg.order_id = order_id
        arrival_msg.current_pose = robot.current_pose
        self.pickup_arrival_pub.publish(arrival_msg)
        logger.info(f"Published PickupArrival for {robot_id}, order {order_id}")

        # 충돌 회피 경로 초기화
        self.collision_avoidance.clear_robot_path(robot_id)
```

**구독자**: `sandwich_coordinator_node.py`
- `/fms/pickup_arrival` 토픽 구독
- pinky 로봇 도착 감지 후 조리 시작 신호 대기

### 2.4 다중 로봇 경로 겹침 해결

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/collision_avoidance.py` (1413줄)

**핵심 클래스**:

1. **ConflictResult**: 충돌 감지 결과
   ```python
   @dataclass
   class ConflictResult:
       has_conflict: bool
       conflict_type: ConflictType  # NO_CONFLICT, NODE_OCCUPIED, PATH_CROSSING, etc
       conflicting_robot_id: str
       conflicting_nodes: List[str]
       blocked_segment_start: int
       blocked_segment_end: int
   ```

2. **CollisionAvoidanceController**: 충돌 회피 핵심 로직
   - `plan_path_with_avoidance()`: 충돌 회피 경로 계획
   - `update_robot_position()`: 로봇 위치 업데이트 → 노드 해제
   - `detect_path_conflicts()`: 경로 충돌 감지
   - `find_alternative_path()`: 대체 경로 탐색

**경로 충돌 회피 알고리즘**:

```
[알고리즘 흐름]

1. 기본 경로 계획
   경로: pinky1_spot → point1 → point3 → pickup_spot → table1

2. 다른 로봇 경로 확인
   pinky2가 이미 point3을 점유 중?

3. 충돌 감지
   - NODE_OCCUPIED: point3 점유됨
   - PATH_CROSSING: 경로 교차 발생

4. 해결 방안 (우선순위):
   a) 대체 경로 탐색 (Dijkstra)
      point3 우회 → point2 → 다시 원래 경로로

   b) 대기 위치 결정
      pinky1을 waiting_node (point2)에 배치
      pinky2가 지나갈 때까지 대기

   c) Pickup 큐 관리
      pickup_spot 도착 순서 관리 (FIFO)
```

**대기 상태 추적**:
```python
@dataclass
class RobotWaitState:
    robot_id: str
    state: WaitState  # NOT_WAITING, WAITING_FOR_NODE, WAITING_FOR_PATH
    waiting_at: str   # 현재 위치
    waiting_for: str  # 무엇을 기다리는가? (로봇ID 또는 노드)
    waiting_since: datetime
    blocked_nodes: List[str]  # 차단된 노드들
```

---

## 3. 발견된 문제점

### 문제 1: /pose 업데이트마다 반복적인 노드 해제 (성능 이슈)

**위치**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py:712-718`

**문제 분석**:
```python
def robot_pose_callback(self, robot_id: str, msg: Pose):
    # 매 /pose 업데이트마다 호출 (약 10Hz, 매 100ms)
    released_nodes = self.collision_avoidance.update_robot_position(
        robot_id, msg.position.x, msg.position.y
    )

    if released_nodes:
        # 모든 다른 로봇에 대해 재계획 시도
        self._trigger_waiting_robots_replan(robot_id, released_nodes)
```

**현상**:
- 로봇 1이 pickup_spot → table1로 이동하면서 매초 약 10번의 /pose 업데이트
- 각 업데이트마다 노드 해제 + 재계획 시도
- CPU 과부하, 불필요한 경로 재계획 빈번 발생

**권장 해결책**:
1. **노드 해제 상태 추적**: 이미 해제한 노드는 반복 해제하지 않기
2. **디바운싱 추가**: 0.5초 이상 이동할 때만 재계획
3. **경로 인덱스 기반 해제**: 로봇이 현재 경로 상의 다음 노드에 도달할 때만 해제

```python
# [개선 안]
class CollisionAvoidanceController:
    def __init__(self):
        self.robot_released_nodes = {}  # {robot_id: set(released_node_names)}

    def update_robot_position(self, robot_id, x, y):
        released_nodes = []

        # 현재 위치가 속한 노드 결정
        current_node = self._get_nearest_node(x, y)

        # 새로운 노드에만 진입했을 때만 처리
        if current_node != self.last_node[robot_id]:
            released = self._release_passed_node(robot_id, current_node)
            released_nodes.extend(released)
            self.last_node[robot_id] = current_node

        return released_nodes  # 새로 해제된 노드만 반환
```

---

### 문제 2: pickup_spot 도착 알림 메커니즘의 동기화 이슈

**위치**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py:1420-1450`

**문제 분석**:

로봇이 pickup_spot에 도착했을 때의 호출 순서:

```
1. robot_pose_callback()
   ↓ distance < 0.1m (pickup_spot)
2. _on_final_destination_reached()
   ↓ PickupArrival 발행
3. sandwich_coordinator_node.py (_on_pickup_arrival())
   ↓ pinky_at_pickup[order_id] = True
4. 로봇팔이 조리 시작
```

**위험 지점**:

```python
# fms_node.py:1435-1450
if location_name == 'pickup_spot':
    # ...
    self.pickup_arrival_pub.publish(arrival_msg)  # 비동기 발행!

    self.collision_avoidance.clear_robot_path(robot_id)
    # Q: 이 시점에서 sandwich_coordinator가 이미 pinky_at_pickup 설정했나?
```

**문제**:
- PickupArrival 메시지는 비동기로 발행됨
- FMS가 즉시 `clear_robot_path()`를 호출할 때, 아직 sandwich_coordinator가 수신하지 못했을 수 있음
- collision_avoidance에서 경로 정보를 지워버리면, 다른 로봇의 경로 계획에 영향

**증상**:
- "pinky1 arrived at pickup_spot" 로그 출력 후
- 실제 조리 시작까지 지연
- 다른 로봇이 pickup_spot 예약 가능한 상태로 잘못 판단

**권장 해결책**:
1. **LoadingComplete 메시지 대기**: pickup_spot 도착 후 clear_robot_path() 호출을 연기
2. **동기화 타임아웃**: 5초 이내에 LoadingComplete 미수신 시 자동 진행
3. **상태 플래그**: 로봇별 "at_pickup_spot_confirmed" 플래그 추가

```python
# [개선 안]
def _on_final_destination_reached(self, robot_id: str, location_name: str):
    if location_name == 'pickup_spot':
        # PickupArrival 발행 (sandwich_coordinator에 알림)
        self.pickup_arrival_pub.publish(arrival_msg)

        # LoadingComplete 대기 (최대 5초)
        # 이 시점에서는 아직 clear_robot_path() 호출 금지
        self.fleet_controller.update_robot_status(
            robot_id, RobotState.STATUS_WAITING_FOR_LOADING
        )

        # LoadingComplete 수신 후 clear_robot_path() 호출
        # (loading_complete_callback에서 처리)
```

---

### 문제 3: 대기 주문 자동 디스패치 시 홈 복귀 스킵

**위치**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py:440-465`

**문제 분석**:

```python
def handle_delivery_confirmation(self, order_id: str, table_number: int):
    # 현재 주문 완료
    workflow.transition_to(OrderWorkflow.STATE_COMPLETED)
    robot_id = workflow.robot_id

    # 대기 주문 확인
    if self.pending_order_queue:
        next_workflow = self.pending_order_queue.popleft()
        # 바로 다음 주문 처리 (home 복귀 없이!)
        self._dispatch_order_to_robot(next_workflow, robot_id)
        return  # ← 여기서 반환, home 복귀 로직 건너뜀

    # 대기 주문이 없을 때만 home 복귀
    if self.navigate_robot_home_callback:
        self.navigate_robot_home_callback(robot_id)
```

**현상**:
- 로봇이 table1에 있는 상태에서 다음 주문 처리
- fleet_controller의 로봇 상태가 여전히 DELIVERING 또는 RETURNING 상태 유지
- 로봇이 실제로 이동 중인데도 여러 주문이 동일 로봇에 할당될 수 있음

**위험 상황**:
```
1. pinky1이 table1에서 고객 A의 주문 수령 대기 중 → order_A STATE_ARRIVED
2. GUI에서 delivery_complete 버튼 (고객 A가 받음)
3. 대기 큐에 order_B 존재
4. _dispatch_order_to_robot() 호출
   - order_B를 cooking 상태로 전환
   - cooking command 발행
   - pinky1을 pickup_spot으로 이동 시작
5. BUT: fleet_controller의 pinky1 상태는?
   - STATUS_DELIVERING 또는 undefined (IDLE로 변경되지 않음)
6. collision_avoidance는?
   - 아직 pinky1의 경로가 초기화되지 않음
   - 새 경로(table1 → pickup_spot)와 기존 경로 혼동
```

**권장 해결책**:

```python
def handle_delivery_confirmation(self, order_id: str, table_number: int):
    workflow = self.active_orders.get(order_id)
    if not workflow:
        return

    workflow.transition_to(OrderWorkflow.STATE_COMPLETED)
    robot_id = workflow.robot_id

    if self.fleet_controller_callback:
        self.fleet_controller_callback(robot_id, 'complete_delivery')

    # 대기 주문 확인
    if self.pending_order_queue:
        next_workflow = self.pending_order_queue.popleft()
        self._notify_queue_position_updates()

        # ← 개선: 로봇 상태를 IDLE로 먼저 설정
        if self.fleet_controller_callback:
            self.fleet_controller_callback(robot_id, 'mark_available')

        # 그 다음 새 주문 할당
        self._dispatch_order_to_robot(next_workflow, robot_id)
        return

    # 대기 주문이 없으면 home 복귀
    if self.navigate_robot_home_callback:
        self.navigate_robot_home_callback(robot_id)
```

---

### 문제 4: 다중 pinky 운용 시 Pickup Spot 점유 제어 부재

**위치**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/task_scheduler.py` 및 `collision_avoidance.py`

**문제 분석**:

pickup_spot은 **단일 식별 지점**으로, 동시에 여러 로봇이 도착할 수 없음:

```python
# fms_node.py:920-943
if task:
    # Robot has pickup access, enter pickup spot
    can_enter = self.task_scheduler.request_pickup_access(robot_id, task.task_id)

    if can_enter:
        self.zone_manager.occupy_zone(robot_id, 'zone_pickup')
        logger.info(f"Robot {robot_id} granted pickup access")

        # PickupArrival 발행
        self.pickup_arrival_pub.publish(arrival_msg)
    else:
        # 대기 구역으로 이동
        waiting_zone = self.task_scheduler.get_next_waiting_zone(robot_id)
        self._send_robot_to_waiting_zone(robot_id, waiting_zone)
```

**현상**:
1. pinky1과 pinky2 모두 pickup_spot으로 이동 중
2. pinky1이 먼저 도착 → PickupArrival 발행
3. pinky2도 도착 → 또 다른 PickupArrival 발행
4. sandwich_coordinator가 2개의 LoadingComplete 메시지 생성?
5. 로봇팔이 2배로 빠르게 조리?

**실제 로그에서 보이는 증상**:
```
[INFO] pinky1 arrived at pickup_spot, order_A
[INFO] pinky2 arrived at pickup_spot, order_B
[INFO] Publishing LoadingComplete for order_A
[INFO] Publishing LoadingComplete for order_B  ← 동시!
```

**권장 해결책**:

```python
class PickupSpotManager:
    """Pickup Spot 점유 관리 (FIFO 큐)"""

    def __init__(self):
        self.occupied = False
        self.current_robot_id = None
        self.current_order_id = None
        self.queue = deque()  # [(robot_id, order_id), ...]

    def request_access(self, robot_id: str, order_id: str) -> bool:
        """Pickup spot 진입 요청"""
        if not self.occupied:
            self.occupied = True
            self.current_robot_id = robot_id
            self.current_order_id = order_id
            logger.info(f"{robot_id} granted pickup access")
            return True
        else:
            self.queue.append((robot_id, order_id))
            logger.info(f"{robot_id} waiting for pickup (position: {len(self.queue)})")
            return False

    def release(self) -> Optional[tuple]:
        """현재 로봇 해제, 다음 로봇 진입"""
        self.occupied = False
        self.current_robot_id = None
        self.current_order_id = None

        if self.queue:
            next_robot_id, next_order_id = self.queue.popleft()
            return (next_robot_id, next_order_id)
        return None
```

---

### 문제 5: cooking_status_callback과 loading_complete_callback의 이중 처리

**위치**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py:666-685, 2045-2076`

**문제 분석**:

```python
# loading_complete_callback
def loading_complete_callback(self, msg: LoadingComplete):
    logger.info(f"Received LoadingComplete: order={msg.order_id}")
    if msg.success:
        self.order_handler.handle_cooking_complete(msg.order_id)
        self.notify_food_loaded(msg.robot_id, msg.order_id)

# cooking_status_callback
def cooking_status_callback(self, msg: String):
    status_data = json.loads(msg.data)
    if status == 'ready':
        logger.info(f"Cooking completed for order {order_id}")
        self.order_handler.handle_cooking_complete(order_id)  # ← 중복!
```

**문제**:
- 동일 이벤트(조리 완료)가 2가지 경로로 처리됨
- sandwich_coordinator가 LoadingComplete 발행 → callback 1
- robot_arm이 `/cooking/status` "ready" 발행 → callback 2
- 동일 order_id에 대해 `handle_cooking_complete()` 2회 호출

**현상**:
```python
def handle_cooking_complete(self, order_id: str):
    workflow = self.active_orders.get(order_id)
    if workflow and workflow.state == OrderWorkflow.STATE_LOADING:
        self._trigger_food_loading(workflow)
    # 2회 호출:
    # 1. LoadingComplete (sandwich_coordinator)
    # 2. cooking_status='ready' (robot_arm)
```

**권장 해결책**:

```python
# 옵션 1: 하나의 소스만 신뢰 (LoadingComplete 우선)
def loading_complete_callback(self, msg: LoadingComplete):
    if msg.success:
        self.order_handler.handle_cooking_complete(msg.order_id)
        self._cooking_complete_orders.add(msg.order_id)  # 추적

def cooking_status_callback(self, msg: String):
    if status == 'ready' and order_id not in self._cooking_complete_orders:
        # LoadingComplete가 없었을 때만 처리
        self.order_handler.handle_cooking_complete(order_id)
        self._cooking_complete_orders.add(order_id)

# 옵션 2: LoadingComplete만 사용
# cooking_status_callback 비활성화
# sandwich_coordinator가 이미 LoadingComplete 발행하므로 중복 불필요
```

---

### 문제 6: Robot State 불일치 시 에러 처리 부재

**위치**: 여러 파일 (fleet_controller.py, collision_avoidance.py, task_scheduler.py)

**문제 분석**:

```
시나리오: pinky1이 네트워크 지연으로 예상과 다른 상태에 있을 때

1. FMS가 pinky1을 MOVING_TO_PICKUP 상태로 설정
2. 실제 pinky1은 table3에 있음 (네트워크 지연)
3. FMS는 계속 pinky1이 pickup_spot으로 이동 중이라고 가정
4. 다른 로봇(pinky2)이 같은 경로로 이동하려 하면?
5. collision_avoidance가 pinky1의 위치를 잘못 알고 있어서
   pinky2에게 잘못된 충돌 경고?
```

**권장 해결책**:

```python
class FleetController:
    def update_robot_pose(self, robot_id: str, pose: Pose):
        robot = self.robots.get(robot_id)
        if not robot:
            return

        # [개선] 상태 검증
        expected_zone = self._get_expected_zone(robot.target_location)
        actual_zone = self._get_zone_at_position(pose.position.x, pose.position.y)

        if expected_zone != actual_zone:
            logger.warning(
                f"Robot {robot_id} position mismatch: "
                f"expected {expected_zone}, actual {actual_zone}"
            )
            # 에러 감지 및 복구 트리거
            self.error_detector.register_error(
                robot_id, "POSITION_MISMATCH", pose
            )

        robot.update_pose(pose)
```

---

## 4. 설정 파일 분석

### 4.1 fms_config.yaml

**위치**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml`

```yaml
positions:
  pickup_spot:
    x: 0.47
    y: 0.63
    theta: 3.14159

  table1:
    x: 1.785
    y: 0.35
    theta: 0.0

  # ... (table2-8)

  pinky1_spot:
    x: 0.585
    y: 0.085
    theta: 0.0

  pinky2_spot:
    x: 0.585
    y: 0.255
    theta: 0.0

initial_poses:
  pinky1:
    x: 0.585
    y: 0.085
    theta: 0.0

  pinky2:
    x: 0.585
    y: 0.255
    theta: 0.0
```

**확인 사항**:
- ✓ 각 위치가 명확히 정의됨
- ✓ pickup_spot은 단일 지점 (0.47, 0.63)
- ✓ table1-8이 정의됨
- ✓ pinky 홈 포지션 정의됨

---

## 5. 시스템 실행 흐름

### 5.1 FMS 시작

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 launch fms fms_closed_network.launch.py
```

**초기화 순서**:
1. fms_node 시작 (ROS_DOMAIN_ID=25)
2. FleetController 초기화 (pinky1, pinky2 로봇 상태)
3. OrderHandler 초기화 (주문 큐, 콜백)
4. GUITCPServer 시작 (포트 9000)
5. 로봇 모니터링 구독자 등록
   - /{pinky1,pinky2}/amcl_pose
   - /{pinky1,pinky2}/battery/*
6. 타이머 시작
   - fleet_status_publish (1.0s)
   - process_pending_tasks (0.5s)
   - collision_check (0.2s)
   - etc.

### 5.2 주문 흐름

```
[사용자 GUI]
    ↓ TCP (주문)
[GUITCPServer:9000]
    ↓ _handle_gui_new_order()
[OrderHandler]
    ├─ 로봇 가용성 확인
    ├─ 로봇 할당 또는 큐에 추가
    └─ _execute_order_workflow()
        ├─ cooking_order 발행
        └─ navigate_robot (pickup_spot)
            ↓
[로봇팔 조리] ← sandwich_coordinator
[로봇 이동] ← pinky1/pinky2
    ├─ /pose 발행 (10Hz)
    │   └─ robot_pose_callback()
    │       └─ collision_avoidance.update_robot_position()
    │           └─ 노드 해제 + 재계획
    └─ /navigate_to_pose 결과
        └─ _check_navigation_status()
            └─ _on_final_destination_reached()
                ├─ PickupArrival 발행
                └─ 또는 TableArrival 발행
                    ↓
[GUI] ← TCP delivery_notification
    [고객 수령]
        ↓
[GUI] → TCP delivery_complete
    [FMS] → handle_delivery_confirmation()
        ├─ robot 상태 COMPLETED
        ├─ 대기 주문 확인
        │   ├─ YES: _dispatch_order_to_robot()
        │   └─ NO: navigate_home()
        └─ GUI ← 알림
```

---

## 6. 권장 개선 사항 요약

| # | 문제 | 심각도 | 우선순위 | 해결 방법 |
|----|------|--------|---------|----------|
| 1 | /pose마다 반복 노드 해제 | 중간 | P2 | 디바운싱, 상태 추적 |
| 2 | pickup_spot 도착 알림 동기화 | 중간 | P1 | LoadingComplete 대기 |
| 3 | 대기 주문 디스패치 시 상태 불일치 | 높음 | P1 | 로봇 상태 재설정 |
| 4 | 다중 pinky의 pickup_spot 점유 제어 | 높음 | P1 | PickupSpotManager 구현 |
| 5 | 이중 cooking_complete 처리 | 중간 | P2 | 단일 소스 신뢰 |
| 6 | 로봇 상태 불일치 시 에러 처리 | 높음 | P3 | 위치 검증 로직 |

---

## 7. 검증 체크리스트

시스템 배포 전 다음을 확인하세요:

- [ ] Domain Bridge 설정 확인 (domain_bridge_v3.yaml)
- [ ] 모든 로봇의 ROS_DOMAIN_ID 일치 여부
- [ ] TCP 포트 9000 방화벽 오픈
- [ ] GUI 클라이언트 테스트 (주문 전송)
- [ ] 다중 로봇 충돌 회피 테스트
- [ ] pickup_spot 동시 도착 시뮬레이션
- [ ] 네트워크 지연 상황 테스트
- [ ] 로봇 오류 복구 시나리오

---

## 부록: 파일별 행 수

```
fms_node.py ............................ 2464줄
collision_avoidance.py ................ 1413줄
order_handler.py ....................... 750줄
fleet_controller.py .................... 490줄
tcp_communication.py ................... 650줄
task_manager.py ........................ 283줄
coordinator_node.py ................... 200+줄
task_scheduler.py ..................... 400+줄
zone_manager.py ....................... 300+줄
```

**총 코드량**: ~7,000줄

---

**분석 완료 일시**: 2026-02-26 18:35:00 UTC
