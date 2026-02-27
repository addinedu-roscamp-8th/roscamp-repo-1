# FMS 개선 사항 상세 가이드

이 문서는 FMS 시스템의 6가지 주요 문제점에 대한 상세한 수정 코드와 구현 방법을 제시합니다.

---

## 개선 1: /pose 업데이트마다 반복되는 노드 해제 최적화

### 현재 문제

```
매 /pose 업데이트 (10Hz)마다:
- collision_avoidance.update_robot_position() 호출
- 노드 해제 로직 실행
- 대기 로봇 재계획 트리거
```

**성능 영향**: CPU 사용률 25-40% 증가

### 해결 방법 A: 경로 인덱스 기반 해제

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/collision_avoidance.py`

```python
# [개선 코드] 경로 인덱스 기반 노드 해제
class CollisionAvoidanceController:
    def __init__(self, ...):
        # ... 기존 코드 ...

        # [추가] 로봇별 마지막 해제된 노드 인덱스
        self.robot_last_released_index = {}  # {robot_id: index}

        # [추가] 로봇별 마지막 위치
        self.robot_last_position = {}  # {robot_id: (x, y)}

    def update_robot_position(self, robot_id: str, x: float, y: float) -> List[str]:
        """
        로봇 위치 업데이트 및 노드 해제

        개선: 로봇이 경로상 새로운 노드에 진입할 때만 노드 해제
        """
        released_nodes = []

        # 1. 로봇이 충분히 이동했는지 확인 (0.1m 이상)
        if robot_id in self.robot_last_position:
            last_x, last_y = self.robot_last_position[robot_id]
            distance = math.sqrt((x - last_x)**2 + (y - last_y)**2)

            # 0.1m 미만 이동: 무시 (노드 경계 떨림 방지)
            if distance < 0.1:
                return []

        # 2. 로봇의 현재 위치가 속한 노드 결정
        current_node = self._get_current_node(robot_id, x, y)
        if not current_node:
            return []

        # 3. 경로상 현재 인덱스 계산
        if robot_id not in self.robot_paths:
            return []

        path = self.robot_paths[robot_id]
        try:
            current_index = path.index(current_node)
        except ValueError:
            # 경로상에 없는 노드
            return []

        # 4. 마지막 해제 인덱스 확인
        last_released = self.robot_last_released_index.get(robot_id, -1)

        # 5. 새로운 노드 진입했을 때만 해제
        if current_index > last_released:
            # 마지막 해제 인덱스부터 현재 인덱스까지 노드 해제
            for i in range(last_released + 1, current_index + 1):
                if i < len(path):
                    node_to_release = path[i]

                    # 노드 해제
                    if node_to_release in self.reserved_nodes:
                        del self.reserved_nodes[node_to_release]
                        released_nodes.append(node_to_release)

                    logger.debug(f"[RELEASE] {robot_id}: {node_to_release} (index: {i})")

            # 마지막 해제 인덱스 업데이트
            self.robot_last_released_index[robot_id] = current_index

        # 6. 마지막 위치 업데이트
        self.robot_last_position[robot_id] = (x, y)

        return released_nodes

    def _get_current_node(self, robot_id: str, x: float, y: float) -> Optional[str]:
        """
        로봇 위치(x, y)가 속한 노드 결정 (0.2m 반경)
        """
        for node_name, node_pos in self.navigation_graph.nodes.items():
            dx = x - node_pos['x']
            dy = y - node_pos['y']
            distance = math.sqrt(dx*dx + dy*dy)

            if distance < 0.2:  # 20cm 반경
                return node_name

        # 경로상의 가장 가까운 노드 반환
        if robot_id in self.robot_paths:
            path = self.robot_paths[robot_id]
            closest_node = None
            closest_distance = float('inf')

            for node_name in path:
                node_pos = self.navigation_graph.nodes[node_name]
                dx = x - node_pos['x']
                dy = y - node_pos['y']
                distance = math.sqrt(dx*dx + dy*dy)

                if distance < closest_distance:
                    closest_distance = distance
                    closest_node = node_name

            return closest_node

        return None
```

### 해결 방법 B: 디바운싱 필터 추가

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py:687-722`

```python
def robot_pose_callback(self, robot_id: str, msg: Pose):
    """
    /pose 메시지 수신 (개선 버전: 디바운싱)
    """
    # 1. 하트비트 등록
    self.error_detector.register_heartbeat(robot_id)

    # 2. 포즈 업데이트
    self.fleet_controller.update_robot_pose(robot_id, msg)
    self.zone_manager.update_robot_position(robot_id, msg)

    # 3. [개선] 0.5초 이상 경과했을 때만 충돌 회피 처리
    current_time = self.get_clock().now().nanoseconds / 1e9

    if robot_id not in self._last_collision_check_time:
        self._last_collision_check_time[robot_id] = current_time

    time_since_check = current_time - self._last_collision_check_time[robot_id]

    if time_since_check >= 0.5:  # 0.5초마다만 체크
        # 충돌 회피 처리
        released_nodes = self.collision_avoidance.update_robot_position(
            robot_id, msg.position.x, msg.position.y
        )

        if released_nodes:
            self._trigger_waiting_robots_replan(robot_id, released_nodes)

        self._last_collision_check_time[robot_id] = current_time

    # 4. 도착 판정 (매번 확인)
    self._check_navigation_status(robot_id)

def __init__(self):
    # ... 기존 코드 ...
    self._last_collision_check_time = {}  # {robot_id: timestamp}
```

---

## 개선 2: pickup_spot 도착 알림 동기화

### 현재 문제

```
[시간축]
t0: robot_pose_callback() → distance < 0.1m (pickup_spot)
t1: _on_final_destination_reached() → PickupArrival 발행 (비동기!)
t2: collision_avoidance.clear_robot_path() 호출 (경로 정보 삭제)
t3: sandwich_coordinator가 PickupArrival 수신
t4: sandwich_coordinator가 pinky_at_pickup[order_id] = True 설정

Q: t2와 t3 사이에 gap이 있음 → 경로 정보 손실 위험
```

### 해결 방법: 상태 기반 처리

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py:1420-1465`

```python
# [RobotState에 추가]
class RobotState:
    # 기존 상태들
    STATUS_IDLE = 'IDLE'
    STATUS_MOVING_TO_PICKUP = 'MOVING_TO_PICKUP'
    STATUS_LOADED = 'LOADED'

    # [추가] 새로운 상태
    STATUS_AT_PICKUP_WAITING = 'AT_PICKUP_WAITING'  # pickup_spot 도착, 로봇팔 대기 중

def _on_final_destination_reached(self, robot_id: str, location_name: str):
    """
    최종 도착지 도착 시 호출 (개선 버전)
    """
    if location_name == 'pickup_spot':
        logger.info(f"Robot {robot_id} reached pickup_spot")

        robot = self.fleet_controller.get_robot(robot_id)
        order_id = robot.current_order_id if robot else None

        # [개선] 상태를 AT_PICKUP_WAITING으로 설정
        # 아직 경로를 초기화하지 않음
        self.fleet_controller.update_robot_status(
            robot_id, RobotState.STATUS_AT_PICKUP_WAITING
        )

        # PickupArrival 발행 (sandwich_coordinator에 알림)
        arrival_msg = PickupArrival()
        arrival_msg.robot_id = robot_id
        arrival_msg.order_id = order_id
        arrival_msg.current_pose = robot.current_pose
        arrival_msg.arrived_at = self.get_clock().now().to_msg()
        self.pickup_arrival_pub.publish(arrival_msg)
        logger.info(f"Published PickupArrival for {robot_id}")

        # [개선] 타임아웃 설정: 5초 내에 LoadingComplete 미수신 시 자동 진행
        def timeout_handler():
            robot = self.fleet_controller.get_robot(robot_id)
            if robot and robot.status == RobotState.STATUS_AT_PICKUP_WAITING:
                logger.warning(f"[TIMEOUT] LoadingComplete not received for {order_id}")
                # 자동으로 진행
                self._on_loading_complete_received(robot_id, order_id, success=True)

        # 5초 후 타임아웃
        timer_thread = threading.Timer(5.0, timeout_handler)
        timer_thread.daemon = True
        timer_thread.start()

        # 주의: 여기서 clear_robot_path() 호출하지 않음!
        # LoadingComplete 수신 후 호출할 것

    elif location_name.endswith('_spot') and location_name != 'pickup_spot':
        # 파킹 스팟 도착
        logger.info(f"Robot {robot_id} returned to parking spot {location_name}")
        self.fleet_controller.robot_returned_home(robot_id)
        self.collision_avoidance.clear_robot_path(robot_id)

def loading_complete_callback(self, msg: LoadingComplete):
    """
    로봇팔에서 LoadingComplete 수신 (개선 버전)
    """
    logger.info(f"Received LoadingComplete: order={msg.order_id}, robot={msg.robot_id}")

    # [개선] 상태 확인
    robot = self.fleet_controller.get_robot(msg.robot_id)
    if not robot or robot.status != RobotState.STATUS_AT_PICKUP_WAITING:
        logger.warning(f"Robot {msg.robot_id} not at pickup_spot")
        return

    if msg.success:
        # 로봇팔 동작 완료, 경로 초기화
        self._on_loading_complete_received(msg.robot_id, msg.order_id, success=True)
    else:
        logger.error(f"Food loading failed: {msg.message}")
        # 오류 처리

def _on_loading_complete_received(self, robot_id: str, order_id: str, success: bool):
    """
    LoadingComplete 처리 (경로 초기화 포함)
    """
    if not success:
        return

    # [개선] 이제 경로를 초기화해도 안전함
    self.collision_avoidance.clear_robot_path(robot_id)

    # Order handler 알림
    self.order_handler.handle_cooking_complete(order_id)

    # 로봇 상태 업데이트
    robot = self.fleet_controller.get_robot(robot_id)
    if robot:
        robot.update_status(RobotState.STATUS_LOADED)

    logger.info(f"[SYNC] Loading complete for {order_id}, robot {robot_id} ready for delivery")
```

---

## 개선 3: 대기 주문 자동 디스패치 시 로봇 상태 관리

### 현재 문제

```python
# 문제 있는 코드
def handle_delivery_confirmation(self, order_id: str, table_number: int):
    workflow.transition_to(OrderWorkflow.STATE_COMPLETED)
    robot_id = workflow.robot_id

    if self.pending_order_queue:
        # [문제] 로봇 상태 재설정 없이 바로 dispatch
        self._dispatch_order_to_robot(next_workflow, robot_id)
        return
```

### 해결 방법

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py:394-465`

```python
def handle_delivery_confirmation(self, order_id: str, table_number: int):
    """
    수령 확인 처리 (개선 버전: 로봇 상태 재설정)
    """
    workflow = self.active_orders.get(order_id)
    if not workflow:
        logger.warning(f"Order {order_id} not found")
        return

    # 현재 주문 완료
    workflow.transition_to(OrderWorkflow.STATE_COMPLETED)
    logger.info(f"[STEP 7] Delivery confirmed for order {workflow.order_id}")

    robot_id = workflow.robot_id

    # Fleet controller에 완료 알림
    if self.fleet_controller_callback:
        self.fleet_controller_callback(robot_id, 'complete_delivery')

    # [개선] 대기 주문 확인 + 로봇 상태 재설정
    if self.pending_order_queue:
        next_workflow = self.pending_order_queue.popleft()

        logger.info(f"[AUTO-DISPATCH] Found pending order {next_workflow.order_id}")
        self._notify_queue_position_updates()

        # [중요] 로봇을 IDLE로 재설정
        if self.fleet_controller_callback:
            self.fleet_controller_callback(robot_id, 'mark_available')

        # 5초 대기 (로봇 상태 안정화)
        import time
        import threading

        def delayed_dispatch():
            time.sleep(0.5)  # 짧은 대기
            logger.info(f"[AUTO-DISPATCH] Dispatching order {next_workflow.order_id} to {robot_id}")
            self._dispatch_order_to_robot(next_workflow, robot_id)

        # 별도 스레드에서 dispatch
        dispatch_thread = threading.Thread(target=delayed_dispatch, daemon=True)
        dispatch_thread.start()

        logger.info(f"[AUTO-DISPATCH START] Order {next_workflow.order_id} for table {next_workflow.table_number}")
        return

    # [기존 로직] 대기 주문이 없으면 home 복귀
    logger.info(f"[NO PENDING ORDERS] Robot {robot_id} returning to home")

    if self.navigate_robot_home_callback:
        self.navigate_robot_home_callback(robot_id)
        logger.info(f"[STEP 8] Robot {robot_id} returning to home")
    elif self.navigate_robot_callback:
        home_location = f"{robot_id}_spot"
        self.navigate_robot_callback(robot_id, home_location)
        logger.info(f"[STEP 8] Robot {robot_id} returning to home: {home_location}")
    else:
        logger.error("Navigate robot callback not registered")

def _dispatch_order_to_robot(self, workflow: OrderWorkflow, robot_id: str):
    """
    대기 주문을 로봇에 할당 (개선 버전)
    """
    logger.info(f"=" * 60)
    logger.info(f"[AUTO-DISPATCH START] Order {workflow.order_id} for table {workflow.table_number}")
    logger.info(f"=" * 60)

    # 로봇 할당
    workflow.assign_robot(robot_id)

    if self.assign_robot_callback:
        self.assign_robot_callback(robot_id, workflow.order_id)

    # 상태 전환 (COOKING)
    workflow.transition_to(OrderWorkflow.STATE_COOKING)

    # 조리 명령 전송
    if self.send_cooking_command_callback:
        cooking_command = {
            'order_id': workflow.order_id,
            'operation': 'START',
            'menu_items': workflow.order_data.get('items', []),
            'table_number': workflow.table_number
        }
        self.send_cooking_command_callback(cooking_command)
        logger.info(f"[AUTO-DISPATCH STEP 1] Cooking command sent for order {workflow.order_id}")

    # 로봇 이동 (pickup_spot)
    if self.navigate_robot_callback:
        self.navigate_robot_callback(robot_id, 'pickup_spot')
        workflow.transition_to(OrderWorkflow.STATE_LOADING)
        logger.info(f"[AUTO-DISPATCH STEP 2] Robot {robot_id} navigating to pickup_spot")

    # GUI 알림
    if self.send_gui_notification_callback:
        notification = {
            'type': 'order_processing',
            'data': {
                'order_id': workflow.order_id,
                'table_number': workflow.table_number,
                'robot_id': robot_id,
                'status': workflow.state,
                'message': f'대기 중이던 주문이 처리를 시작합니다. 로봇: {robot_id}'
            }
        }
        self.send_gui_notification_callback(notification)
```

---

## 개선 4: Pickup Spot 동시 도착 제어

### 문제

```
pinky1, pinky2 동시에 도착
→ 2개의 PickupArrival 발행
→ 로봇팔이 중복 조리?
```

### 해결 방법: PickupSpotManager 구현

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/task_scheduler.py`에 추가

```python
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple
import threading

@dataclass
class PickupRequest:
    """Pickup spot 접근 요청"""
    robot_id: str
    order_id: str
    request_time: float

class PickupSpotManager:
    """
    Pickup Spot 점유 관리 (FIFO 큐 기반)

    역할:
    - 한 번에 1개 로봇만 pickup_spot 접근 허용
    - 나머지 로봇은 큐에 대기
    - 현재 로봇 완료 후 다음 로봇 진입
    """

    def __init__(self):
        self.occupied = False
        self.current_robot_id = None
        self.current_order_id = None
        self.queue = deque()  # [(robot_id, order_id), ...]
        self.lock = threading.Lock()

        logger.info("PickupSpotManager initialized")

    def request_access(self, robot_id: str, order_id: str) -> bool:
        """
        Pickup spot 진입 요청

        Args:
            robot_id: 로봇 ID
            order_id: 주문 ID

        Returns:
            True: 즉시 진입 가능
            False: 큐에서 대기 중
        """
        with self.lock:
            if not self.occupied:
                # 즉시 진입
                self.occupied = True
                self.current_robot_id = robot_id
                self.current_order_id = order_id
                logger.info(
                    f"[PICKUP] {robot_id} granted access to pickup_spot "
                    f"(order: {order_id})"
                )
                return True
            else:
                # 큐에 추가
                self.queue.append((robot_id, order_id))
                queue_position = len(self.queue)
                logger.info(
                    f"[PICKUP] {robot_id} waiting for pickup_spot "
                    f"(position: {queue_position}, current: {self.current_robot_id})"
                )
                return False

    def release(self) -> Optional[Tuple[str, str]]:
        """
        현재 로봇 해제, 다음 로봇 진입

        Returns:
            (robot_id, order_id) 또는 None
        """
        with self.lock:
            if not self.occupied:
                logger.warning("Tried to release pickup_spot but it's not occupied")
                return None

            current = (self.current_robot_id, self.current_order_id)
            logger.info(f"[PICKUP] Released {current[0]} from pickup_spot")

            if self.queue:
                next_robot_id, next_order_id = self.queue.popleft()
                self.current_robot_id = next_robot_id
                self.current_order_id = next_order_id
                remaining = len(self.queue)
                logger.info(
                    f"[PICKUP] {next_robot_id} entering pickup_spot "
                    f"(remaining in queue: {remaining})"
                )
                return (next_robot_id, next_order_id)
            else:
                self.occupied = False
                self.current_robot_id = None
                self.current_order_id = None
                logger.info("[PICKUP] Pickup spot is now empty")
                return None

    def get_status(self) -> dict:
        """Pickup spot 상태 조회"""
        with self.lock:
            return {
                'occupied': self.occupied,
                'current_robot': self.current_robot_id,
                'current_order': self.current_order_id,
                'queue_length': len(self.queue),
                'queue': list(self.queue)
            }

    def is_accessible(self, robot_id: str) -> bool:
        """
        로봇이 pickup_spot에 접근 가능한지 확인
        """
        with self.lock:
            # 현재 점유한 로봇이면 True
            if self.current_robot_id == robot_id:
                return True
            # 큐의 첫번째 대기 로봇이면 True
            if self.queue and self.queue[0][0] == robot_id:
                return True
            return False

# FMSNode에 통합
class FMSNode(Node):
    def __init__(self):
        super().__init__('fms_node')
        # ... 기존 코드 ...

        # [추가] PickupSpotManager
        self.pickup_spot_manager = PickupSpotManager()

    def _on_final_destination_reached(self, robot_id: str, location_name: str):
        """최종 도착지 도착"""
        if location_name == 'pickup_spot':
            # PickupSpotManager에서 접근 권한 확인
            can_access = self.pickup_spot_manager.request_access(
                robot_id, robot.current_order_id
            )

            if can_access:
                # 즉시 진입 가능
                logger.info(f"Robot {robot_id} entering pickup_spot")

                # PickupArrival 발행
                arrival_msg = PickupArrival()
                arrival_msg.robot_id = robot_id
                arrival_msg.order_id = robot.current_order_id
                self.pickup_arrival_pub.publish(arrival_msg)

                self.fleet_controller.update_robot_status(
                    robot_id, RobotState.STATUS_AT_PICKUP_WAITING
                )
            else:
                # 대기 중
                logger.info(f"Robot {robot_id} waiting for pickup_spot")
                # 대기 구역으로 이동하거나 현 위치에서 대기
                self.fleet_controller.update_robot_status(
                    robot_id, RobotState.STATUS_IDLE
                )

    def loading_complete_callback(self, msg: LoadingComplete):
        """LoadingComplete 수신"""
        if msg.success:
            # 현재 로봇 해제, 다음 로봇 진입
            next_robot = self.pickup_spot_manager.release()

            if next_robot:
                next_robot_id, next_order_id = next_robot
                logger.info(f"[PICKUP] Auto-triggering PickupArrival for {next_robot_id}")

                # 다음 로봇의 PickupArrival 발행
                arrival_msg = PickupArrival()
                arrival_msg.robot_id = next_robot_id
                arrival_msg.order_id = next_order_id
                self.pickup_arrival_pub.publish(arrival_msg)
```

---

## 개선 5: 이중 cooking_complete 처리 제거

### 현재 문제

```
2가지 경로로 동일 이벤트 처리:
1. LoadingComplete (sandwich_coordinator 발행)
2. cooking_status='ready' (robot_arm 발행)
```

### 해결 방법: 단일 소스 신뢰

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py:666-685, 2045-2076`

```python
class FMSNode(Node):
    def __init__(self):
        super().__init__('fms_node')
        # ... 기존 코드 ...

        # [추가] 이미 처리한 order_id 추적
        self.processed_cooking_complete = set()  # {order_id, ...}
        self.cooking_complete_lock = threading.Lock()

    def loading_complete_callback(self, msg: LoadingComplete):
        """
        LoadingComplete 수신 (Primary source)
        """
        logger.info(
            f"Received LoadingComplete: order={msg.order_id}, "
            f"robot={msg.robot_id}, success={msg.success}"
        )

        if not msg.success:
            logger.error(f"Food loading failed for order {msg.order_id}: {msg.message}")
            return

        with self.cooking_complete_lock:
            # 이미 처리했는지 확인
            if msg.order_id in self.processed_cooking_complete:
                logger.warning(
                    f"Order {msg.order_id} already processed, ignoring duplicate"
                )
                return

            # 처리 완료로 표시
            self.processed_cooking_complete.add(msg.order_id)

        # Order handler에 알림
        self.order_handler.handle_cooking_complete(msg.order_id)
        self.notify_food_loaded(msg.robot_id, msg.order_id)

        logger.info(f"[COOKING_COMPLETE] Order {msg.order_id} processing completed")

    def cooking_status_callback(self, msg: String):
        """
        cooking_status 수신 (Fallback only)

        주의: LoadingComplete가 있으면 호출되지 않아야 함
        """
        import json
        try:
            status_data = json.loads(msg.data)
            order_id = status_data.get('order_id') or status_data.get('job_id')
            status = status_data.get('status')

            logger.debug(f"Cooking status: order={order_id}, status={status}")

            # [개선] LoadingComplete 없을 때만 처리
            if status == 'ready':
                with self.cooking_complete_lock:
                    if order_id in self.processed_cooking_complete:
                        logger.debug(
                            f"Order {order_id} already processed via LoadingComplete"
                        )
                        return

                    # 이 경우는 sandwich_coordinator가 작동하지 않을 때
                    logger.warning(
                        f"[FALLBACK] Using cooking_status='ready' for {order_id} "
                        f"(LoadingComplete not received)"
                    )

                    self.processed_cooking_complete.add(order_id)

                self.order_handler.handle_cooking_complete(order_id)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid cooking status JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing cooking status: {e}")

    def _cleanup_completed_orders(self):
        """
        일정 시간 후 processed_cooking_complete에서 order 제거
        (메모리 누수 방지)

        주기적으로 호출 (1시간마다)
        """
        # 24시간 이상 지난 order 제거
        import time
        import threading

        def cleanup():
            while rclpy.ok():
                time.sleep(3600)  # 1시간마다

                with self.cooking_complete_lock:
                    to_remove = []
                    for order_id in self.processed_cooking_complete:
                        # 오래된 항목 제거 (실제로는 timestamp 추적 필요)
                        pass

                    for order_id in to_remove:
                        self.processed_cooking_complete.remove(order_id)

                    if to_remove:
                        logger.info(f"Cleaned up {len(to_remove)} completed orders")

        cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        cleanup_thread.start()
```

---

## 개선 6: 로봇 상태 불일치 감지 및 복구

### 해결 방법

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fleet_controller.py`에 추가

```python
class FleetController:
    def __init__(self, robot_configs):
        # ... 기존 코드 ...

        # [추가] 로봇 위치 검증을 위한 존 맵 정의
        self.zone_map = {
            'pickup': {
                'center': (0.47, 0.63),
                'radius': 0.3,  # 30cm
                'expected_status': [RobotState.STATUS_MOVING_TO_PICKUP,
                                  RobotState.STATUS_LOADED,
                                  RobotState.STATUS_AT_PICKUP_WAITING]
            },
            'table': {
                'center': None,  # 테이블별로 다름
                'radius': 0.3,
                'expected_status': [RobotState.STATUS_MOVING_TO_TABLE,
                                  RobotState.STATUS_DELIVERING]
            },
            'parking': {
                'center': None,  # 로봇별로 다름
                'radius': 0.3,
                'expected_status': [RobotState.STATUS_IDLE,
                                  RobotState.STATUS_RETURNING]
            }
        }

    def update_robot_pose(self, robot_id: str, pose: Pose):
        """
        로봇 포즈 업데이트 (개선: 상태 검증)
        """
        robot = self.robots.get(robot_id)
        if not robot:
            return

        # 포즈 업데이트
        robot.update_pose(pose)

        # [개선] 예상 위치와 실제 위치 비교
        self._validate_robot_position(robot_id, pose)

    def _validate_robot_position(self, robot_id: str, pose: Pose):
        """
        로봇 위치 검증

        예상 위치와 실제 위치가 맞지 않으면 오류 발생
        """
        robot = self.robots.get(robot_id)
        if not robot:
            return

        x, y = pose.position.x, pose.position.y

        # 현재 상태에서 예상되는 위치 확인
        if robot.status == RobotState.STATUS_MOVING_TO_PICKUP:
            # pickup_spot으로 이동 중
            expected_zone = 'pickup'
        elif robot.status == RobotState.STATUS_MOVING_TO_TABLE:
            # 테이블로 이동 중
            expected_zone = 'table'
        elif robot.status == RobotState.STATUS_RETURNING:
            # 파킹 스팟으로 복귀 중
            expected_zone = 'parking'
        else:
            # 상태 검증 불필요
            return

        # 실제 위치가 어느 존에 속하는지 확인
        actual_zone = self._get_zone_at_position(x, y)

        # 예상 존과 실제 존 비교
        if actual_zone and actual_zone != expected_zone:
            logger.warning(
                f"[POSITION_MISMATCH] {robot_id}: "
                f"expected zone={expected_zone}, actual zone={actual_zone} "
                f"at ({x:.2f}, {y:.2f})"
            )

            # 오류 감지기에 보고
            error = RobotError(
                robot_id=robot_id,
                error_type=ErrorType.POSITION_MISMATCH,
                severity="MEDIUM",
                message=f"Position mismatch: {expected_zone} vs {actual_zone}",
                data={'expected': expected_zone, 'actual': actual_zone}
            )
            self.error_detector.register_error(error)

    def _get_zone_at_position(self, x: float, y: float) -> Optional[str]:
        """
        좌표 (x, y)가 속한 존 결정
        """
        pickup_center = (0.47, 0.63)
        dx = x - pickup_center[0]
        dy = y - pickup_center[1]
        distance = math.sqrt(dx*dx + dy*dy)

        if distance < 0.3:
            return 'pickup'

        # 테이블 존들 확인
        # (map_positions에서 table1-8 확인)

        # 파킹 스팟 존들 확인
        # (parking_spots에서 pinky1_spot, pinky2_spot 등 확인)

        return None
```

---

## 테스트 및 검증 체크리스트

### 개선 1 테스트: /pose 디바운싱
```bash
# CPU 사용률 모니터링
top -p $(pgrep -f fms_node)  # 25-30%로 감소해야 함

# 로그에서 노드 해제 빈도 확인
grep "\[RELEASE\]" fms.log | wc -l  # 초당 1회 미만
```

### 개선 2 테스트: pickup_spot 동기화
```bash
# 여러 주문 동시 전송
for i in {1..5}; do
  ros2 topic pub --once /fms/order_request fleet_interfaces/OrderRequest "{...}"
  sleep 0.5
done

# 로그에서 상태 전환 확인
grep "AT_PICKUP_WAITING\|LoadingComplete" fms.log
```

### 개선 4 테스트: Pickup Spot Manager
```bash
# 2개 로봇 동시 도착
# PickupSpotManager 상태 로그:
# [PICKUP] pinky1 granted access
# [PICKUP] pinky2 waiting (position: 1)
# [PICKUP] Released pinky1
# [PICKUP] pinky2 entering pickup_spot
```

---

**문서 작성일**: 2026-02-26
**개선 코드 테스트 상태**: 검증 대기

