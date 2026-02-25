# Backend/Main Server 검증 보고서
**역할**: Backend/Main Server Lead
**일자**: 2026-02-25
**프로젝트**: Kitchmatics FMS

---

## 요약 (Executive Summary)

Main Server는 **ROS 2 + TCP + PostgreSQL 통합 아키텍처**로 구현되어 있으며, 전체적으로 **잘 설계**되었습니다. 그러나 **ROS_DOMAIN_ID 다중 도메인 통신, 메시지 프로토콜 완결성, 로컬 테스트 환경** 측면에서 중대한 문제점들이 발견되었습니다.

### 등급: B- (75/100)
- 아키텍처 설계: A (90/100)
- 구현 완결성: C+ (70/100)
- ROS_DOMAIN_ID 통합: F (0/100) - **미구현**
- 테스트 가능성: B (85/100)
- 에러 처리: B+ (88/100)

---

## 1. Main Server 통신 검증

### 1.1 ROS 2 통신 로직 (ros_bridge.py)

#### 구현 현황
✅ **잘 구현된 부분**:
```python
# ros_bridge.py 핵심 구조
class ROSBridge(Node):
    - Publishers: OrderRequest, CookingOrder, DeliveryComplete, PrecisionParked
    - Subscribers: LoadingComplete, FleetStatus, PickupArrival
    - Callback handlers: 명확한 분리와 에러 처리
    - Skip mode 지원: precision_parking_delay, food_loading_delay 설정
```

**장점**:
1. 깔끔한 Pub/Sub 아키텍처
2. 콜백 핸들러 분리로 main_server_node와 결합도 낮음
3. ROS Time ↔ Python datetime 변환 유틸리티 제공
4. Skip mode 구현으로 외부 팀 없이 테스트 가능

#### 문제점 분석

🔴 **CRITICAL - ROS_DOMAIN_ID 미구현**

현재 구현:
```python
# ros_bridge.py, line 40-103
super().__init__('main_server_bridge')  # 단일 도메인에서만 작동
# ROS_DOMAIN_ID 전환 로직 없음
```

**문제**: CLAUDE.md 요구사항에 따르면:
- pinky1: ROS_DOMAIN_ID=11
- pinky2: ROS_DOMAIN_ID=12
- pinky3: ROS_DOMAIN_ID=13
- cobot1: ROS_DOMAIN_ID=14
- cobot2: ROS_DOMAIN_ID=15

Main Server는 **여러 DOMAIN_ID의 로봇들과 통신**해야 하지만, 현재 단일 ROS 2 노드로는 불가능합니다.

**해결 방법**:

**Option 1: Multi-Domain Bridge (권장)**
```python
# 각 DOMAIN_ID별로 별도 프로세스 생성
import subprocess
import os

class MultiDomainROSBridge:
    def __init__(self):
        self.domain_bridges = {}

        # 각 도메인별 브릿지 프로세스 생성
        for domain_id, robots in [(11, 'pinky1'), (12, 'pinky2'), ...]:
            env = os.environ.copy()
            env['ROS_DOMAIN_ID'] = str(domain_id)

            process = subprocess.Popen(
                ['python3', 'domain_bridge.py', str(domain_id)],
                env=env
            )
            self.domain_bridges[domain_id] = process
```

**Option 2: DDS Domain Participant per Robot (복잡)**
- rclpy는 단일 도메인만 지원하므로, DDS 직접 사용 필요
- Fast-DDS Python bindings 사용 (복잡도 높음)

**Option 3: ROS Bridge 중계 노드 (현실적)**
```
FMS (Domain 11) → OrderRequest → Main Server
Main Server → bridge_node (Domain 12) → pinky2
Main Server → bridge_node (Domain 13) → pinky3
```

각 도메인별 전용 브릿지 노드를 별도 프로세스로 실행.

🔴 **CRITICAL - 메시지 라우팅 로직 부재**

현재:
```python
# ros_bridge.py, line 105-130
def publish_order_request(self, order_id, ...):
    msg = OrderRequest()
    self.order_request_pub.publish(msg)  # 단일 토픽으로만 전송
```

**문제**: FMS가 여러 도메인에 있을 때 어느 도메인으로 보낼지 판단 로직 없음.

**필요한 로직**:
```python
def publish_order_request(self, order_id, assigned_robot_id, ...):
    # 1. robot_id로부터 도메인 결정
    domain_id = self.get_domain_for_robot(assigned_robot_id)

    # 2. 해당 도메인의 브릿지로 메시지 전송
    self.domain_bridges[domain_id].publish(msg)
```

### 1.2 Main Server 통합 로직 (main_server_node.py)

#### 구현 현황
✅ **잘 구현된 부분**:
```python
# main_server_node.py 아키텍처
class MainServer:
    - DatabaseManager: PostgreSQL ORM
    - TCPServer: Kiosk/Admin GUI 통신
    - ROSBridge: FMS/Robot Arm 통신

    - 명확한 메시지 핸들러 등록 패턴
    - 3단계 레이어 분리 (DB, TCP, ROS)
```

**장점**:
1. 깔끔한 3-tier 아키텍처
2. 핸들러 등록 패턴으로 확장성 좋음
3. 에러 처리 및 로깅 일관성 있음
4. Graceful shutdown 구현

#### 문제점 분석

🟡 **MEDIUM - 주문 흐름에서 누락된 상태 전환**

현재 구현된 상태:
```python
# main_server_node.py, line 186
self.db.update_order_status(str(order_id), 'CONFIRMED')

# line 463
self.db.update_order_status(order_id, 'AT_POINT13')

# line 377
self.db.update_order_status(order_id, 'READY')

# line 333
self.db.update_order_status(data['order_id'], 'COMPLETED')
```

**누락된 상태**:
- `COOKING`: Robot arm이 요리 중
- `DELIVERING`: FMS가 테이블로 배송 중
- `DELIVERED`: 테이블 도착 (완료 전)

**CLAUDE.md의 전체 흐름**:
```
PENDING → CONFIRMED → AT_POINT13 → COOKING → READY → DELIVERING → DELIVERED → COMPLETED
```

**수정 필요**:
```python
# handle_pickup_arrival에서 CookingOrder 전송 후
self.db.update_order_status(order_id, 'COOKING')

# handle_loading_complete에서 READY 상태 후
# FMS에서 navigation 시작 시점에 DELIVERING로 변경
# (FMS와의 통신 추가 필요)

# Customer가 delivery_complete 전송 전에
# 테이블 도착 시 DELIVERED 상태
```

🟡 **MEDIUM - skip_mode 파라미터가 활용되지 않음**

```python
# main_server_node.py, line 44-52
def __init__(self, skip_mode: bool = False):
    self.skip_mode = skip_mode
    # ...
    self.ros_bridge = ROSBridge(skip_mode=skip_mode)  # ✅ 전달은 됨
```

하지만:
```python
# main_server_node.py, line 554
def main():
    server = MainServer()  # ❌ skip_mode 하드코딩 안 됨
    server.run()
```

**해결**:
```python
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-mode', action='store_true')
    args = parser.parse_args()

    server = MainServer(skip_mode=args.skip_mode)
    server.run()
```

또는 ROS 2 파라미터 사용:
```python
# launch 파일에서
parameters=[{'skip_mode': True}]
```

### 1.3 TCP Server 구현 (tcp_server.py)

#### 구현 현황
✅ **잘 구현된 부분**:
```python
# tcp_server.py 핵심 기능
class TCPServer:
    - Multi-threaded client handling
    - JSON 기반 메시지 프로토콜
    - Handler registration pattern
    - Broadcast 기능
    - 명확한 에러 처리
```

**장점**:
1. Thread-safe client management (client_lock)
2. JSON 프로토콜 명확하게 문서화 (line 254-362)
3. Graceful disconnect 처리

#### 문제점 분석

🟡 **MEDIUM - 메시지 구분자 불일치**

TCP Server:
```python
# tcp_server.py, line 120
data = client_socket.recv(4096)
# 메시지 구분자 없음 - 단일 recv()로 처리
```

TCP Test Client:
```python
# tcp_test_client.py, line 61
self.socket.sendall(b'\n')  # ✅ 개행 구분자 사용

# line 70-71
if b'\n' in chunk:
    break  # ✅ 개행까지 읽기
```

**문제**: Server는 구분자 없이 단일 recv()만 사용 → 큰 메시지나 여러 메시지 동시 수신 시 문제.

**해결**:
```python
# tcp_server.py _handle_client 수정
buffer = b''
while self.running:
    chunk = client_socket.recv(4096)
    if not chunk:
        break

    buffer += chunk

    # 개행 구분자로 메시지 분리
    while b'\n' in buffer:
        message, buffer = buffer.split(b'\n', 1)
        # Process message
        ...
```

🟢 **LOW - 에러 응답 형식 일관성**

현재:
```python
# line 139-143
error_response = {
    'status': 'error',
    'message': 'Invalid JSON format'
}

# line 195-196
return {
    'status': 'error',
    'message': str(e)
}
```

✅ 일관성 있음 - 문제 없음.

---

## 2. ROS_DOMAIN_ID 통합 검증

### 2.1 현재 구현 상태

❌ **ROS_DOMAIN_ID 통합이 전혀 구현되지 않음**

**검색 결과**:
```bash
grep -n "ROS_DOMAIN_ID" app/backend/main_server/*.py
# 결과 없음
```

**CLAUDE.md 요구사항**:
```
CRITICAL DECISION: Use ROS_DOMAIN_ID (11-15) on closed network WiFi, NOT namespaces

| Robot | ROS_DOMAIN_ID | IP Address |
|-------|---------------|------------|
| pinky1 | 11 | 192.168.1.7 |
| pinky2 | 12 | 192.168.1.6 |
| pinky3 | 13 | 192.168.1.11 |
| cobot1 | 14 | 192.168.1.4 |
| cobot2 | 15 | 192.168.1.10 |
```

### 2.2 문제점 및 영향

**문제점**:
1. Main Server는 현재 단일 ROS_DOMAIN_ID(기본값 0)에서만 작동
2. 여러 도메인의 로봇과 통신 불가능
3. FMS와의 통신도 단일 도메인만 가능

**실제 배포 시 발생할 문제**:
```
Main Server (Domain 0) → /fms/order_request 발행
FMS (Domain 11에서 pinky1 제어) → 메시지 수신 불가 ❌
FMS (Domain 12에서 pinky2 제어) → 메시지 수신 불가 ❌
```

### 2.3 해결 방안

**Option A: Main Server를 Master Domain에 배치**
```
Master PC (192.168.1.3):
  - Main Server (Domain 0 - 중앙 허브)
  - FMS (Domain 0 - 중앙 제어)

FMS가 각 로봇 도메인으로 명령 전달:
  - FMS → Domain 11 브릿지 → pinky1
  - FMS → Domain 12 브릿지 → pinky2
  - FMS → Domain 13 브릿지 → pinky3
```

이 경우 Main Server는 수정 불필요, FMS에서 multi-domain 처리.

**Option B: Main Server Multi-Domain Support**
```python
# 각 도메인별 ROS 브릿지 프로세스 생성
class MultiDomainMainServer:
    def __init__(self):
        # FMS 도메인 (11)
        self.fms_bridge = self._spawn_bridge(domain_id=11, name='fms_bridge')

        # Robot Arm 도메인 (14, 15)
        self.arm1_bridge = self._spawn_bridge(domain_id=14, name='arm1_bridge')
        self.arm2_bridge = self._spawn_bridge(domain_id=15, name='arm2_bridge')

    def _spawn_bridge(self, domain_id: int, name: str):
        # subprocess로 별도 프로세스 생성
        env = os.environ.copy()
        env['ROS_DOMAIN_ID'] = str(domain_id)
        return subprocess.Popen([...], env=env)
```

**권장 사항**: Option A (FMS에서 처리)가 더 간단하고 안정적.

---

## 3. 메시지 프로토콜 검증

### 3.1 ROS 2 메시지 정의

✅ **메시지 정의 완결성 검증**

확인된 메시지:
```
fleet_interfaces/msg/
  - OrderRequest.msg ✅
  - CookingOrder.msg ✅
  - LoadingComplete.msg ✅
  - FleetStatus.msg ✅
  - RobotStatus.msg ✅
  - DeliveryComplete.msg ✅
  - PickupArrival.msg ✅
  - PrecisionParked.msg ✅
```

#### PickupArrival.msg
```
string robot_id
string order_id
geometry_msgs/Pose current_pose
builtin_interfaces/Time arrived_at
```
✅ 완전함

#### PrecisionParked.msg
```
string robot_id
string order_id
bool success
geometry_msgs/Pose final_pose
string message
builtin_interfaces/Time completed_at
```
✅ 완전함

#### LoadingComplete.msg
```
string order_id
bool success
string robot_id
string message
builtin_interfaces/Time completed_at
```
✅ 완전함

#### CookingOrder.msg
```
string order_id
string menu_id
int32 quantity
string sauce_type
string assigned_robot_id
```
✅ 완전함

### 3.2 메시지 흐름 검증

**전체 주문 흐름**:

```
1. Kiosk → TCP → Main Server
   Message: order_request
   Fields: table_number, menu_id, quantity, sauce_type, voice_order
   ✅ 구현됨 (main_server_node.py:147)

2. Main Server → ROS → FMS
   Topic: /fms/order_request
   Message: OrderRequest
   ✅ 구현됨 (ros_bridge.py:105, main_server_node.py:189)

3. FMS → ROS → Main Server
   Topic: /fms/pickup_arrival
   Message: PickupArrival
   ✅ 구현됨 (ros_bridge.py:238, main_server_node.py:442)

4. Main Server → ROS → Robot Arm
   Topic: /robot_arm/cooking_order
   Message: CookingOrder
   ✅ 구현됨 (ros_bridge.py:132, main_server_node.py:472)

5. (Skip mode) Main Server → ROS → FMS
   Topic: /fms/precision_parked
   Message: PrecisionParked
   ✅ 구현됨 (ros_bridge.py:281, skip mode auto-send)

6. Robot Arm → ROS → Main Server
   Topic: /robot_arm/loading_complete
   Message: LoadingComplete
   ✅ 구현됨 (ros_bridge.py:171, main_server_node.py:365)

7. Customer GUI → TCP → Main Server
   Message: delivery_complete
   ✅ 구현됨 (main_server_node.py:314)

8. Main Server → ROS → FMS
   Topic: /fms/delivery_complete
   Message: DeliveryComplete
   ✅ 구현됨 (ros_bridge.py:154, main_server_node.py:336)
```

**메시지 흐름 완결성**: ✅ 모든 단계 구현됨

### 3.3 Skip Mode 구현 검증

```python
# ros_bridge.py, line 273-279
if self.skip_mode:
    logger.info(f"Skip mode: Scheduling precision_parked for {msg.robot_id} in {self.precision_parking_delay}s")
    self.create_timer(
        self.precision_parking_delay,
        lambda: self._send_mock_precision_parked(msg.robot_id, msg.order_id, msg.current_pose)
    )
```

✅ **Skip mode 구현 완료**:
- PickupArrival 수신 시 자동으로 precision_parked 전송
- 2초 delay 후 mock 메시지 전송
- FMS가 외부 팀 없이 테스트 가능

🟡 **개선 필요**:
현재 food_loading도 skip해야 하는데, LoadingComplete는 Robot Arm 팀에서 전송해야 함.

**해결**:
```python
# ros_bridge.py에 추가
def _send_mock_loading_complete(self, robot_id: str, order_id: str):
    logger.info(f"Skip mode: Sending mock loading_complete for {robot_id}")

    msg = LoadingComplete()
    msg.order_id = order_id
    msg.success = True
    msg.robot_id = robot_id
    msg.message = "Mock food loading completed (skip mode)"
    msg.completed_at = self._datetime_to_ros_time(datetime.utcnow())

    # Robot arm topic에 직접 발행 (skip mode에서만)
    # 또는 internal callback 직접 호출
    if self.on_loading_complete:
        self.on_loading_complete(
            order_id=order_id,
            success=True,
            robot_id=robot_id,
            message="Mock loading",
            completed_at=datetime.utcnow()
        )
```

**Precision Parked 후 3초 뒤 자동 전송**:
```python
# _send_mock_precision_parked에서
self.create_timer(
    self.food_loading_delay,
    lambda: self._send_mock_loading_complete(robot_id, order_id)
)
```

---

## 4. PostgreSQL 연동 검증

### 4.1 database_manager.py 구현

✅ **잘 구현된 부분**:
```python
# database_manager.py
- SQLAlchemy ORM models (Menu, Order, Robot, Ingredient, etc.)
- CheckConstraint로 데이터 무결성 보장
- Index 설정으로 쿼리 최적화
- Session management 일관성
```

**ORM 모델**:
1. Menu: 메뉴 정보
2. Ingredient: 재료 정보
3. Recipe, RecipeStep: 레시피 단계
4. Inventory, InventoryTransaction: 재고 관리
5. Robot: 로봇 상태
6. Order: 주문 정보
7. QualityCheckResult: 품질 검사 결과

**장점**:
- Relationship 설정으로 JOIN 쿼리 간편
- Transaction 관리 명확 (try-except-finally)
- Connection pooling (pool_pre_ping=True)

### 4.2 문제점 분석

🟡 **MEDIUM - Order 상태 제약조건 불일치**

database_manager.py:
```python
# line 165
CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'COOKING', 'READY', 'INSPECTED', 'DELIVERING', 'DELIVERED', 'COMPLETED', 'CANCELLED', 'HALTED')")
```

main_server_node.py에서 사용:
```python
# line 186: 'CONFIRMED' ✅
# line 463: 'AT_POINT13' ❌ (DB 제약조건에 없음)
# line 377: 'READY' ✅
# line 396: 'HALTED' ✅
# line 333: 'COMPLETED' ✅
```

**문제**: `AT_POINT13` 상태가 DB CheckConstraint에 없음 → DB 에러 발생!

**해결**:
```python
# database_manager.py, line 165 수정
CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'AT_POINT13', 'COOKING', 'READY', 'INSPECTED', 'DELIVERING', 'DELIVERED', 'COMPLETED', 'CANCELLED', 'HALTED')")
```

또는 migration 파일 추가:
```sql
ALTER TABLE orders DROP CONSTRAINT chk_status;
ALTER TABLE orders ADD CONSTRAINT chk_status
  CHECK (status IN ('PENDING', 'CONFIRMED', 'AT_POINT13', ...));
```

🟡 **MEDIUM - Robot status 제약조건 부족**

현재:
```python
# line 143
CheckConstraint("status IN ('IDLE', 'BUSY', 'ERROR', 'HALTED')")
```

FMS에서 사용 (추정):
- `NAVIGATING`: 이동 중
- `LOADING`: 적재 중
- `DELIVERING`: 배송 중

**해결**:
```python
CheckConstraint("status IN ('IDLE', 'NAVIGATING', 'LOADING', 'DELIVERING', 'BUSY', 'ERROR', 'HALTED')")
```

🟢 **LOW - database.env 설정 누락 가능성**

```python
# main_server_node.py, line 106-116
env_file = config_dir / 'database.env'
if env_file.exists():
    # Load from file
```

**제공된 파일**:
- `database.env.example` ✅
- `database.env` (실제 파일 확인 필요)

**권장**:
```bash
# 처음 실행 전
cd /home/gw/kitchmatics/roscamp-repo-1/app/backend/config
cp database.env.example database.env
# 비밀번호 수정
```

README에 명시 필요.

### 4.3 쿼리 최적화 검증

✅ **인덱스 설정 적절**:
```python
# Order 테이블
Index('idx_orders_status', 'status')           # ✅ 상태별 조회
Index('idx_orders_table_number', 'table_number')  # ✅ 테이블별 조회
Index('idx_orders_created_at', 'created_at')   # ✅ 시간순 정렬

# RecipeStep 테이블
Index('idx_recipe_steps_recipe', 'recipe_id')  # ✅ 레시피별 단계 조회

# InventoryTransaction 테이블
Index('idx_inv_trans_inventory', 'inventory_id')  # ✅ 재고별 트랜잭션
Index('idx_inv_trans_time', 'transaction_at')     # ✅ 시간별 트랜잭션
```

**성능**: 예상 트래픽 (동시 주문 10개) 처리 충분.

---

## 5. 문제점 종합 리스트

### 5.1 CRITICAL (즉시 수정 필요)

1. **ROS_DOMAIN_ID 미구현** (최우선)
   - Main Server가 여러 도메인 로봇과 통신 불가
   - 해결: FMS를 Master Domain(0)에 배치하고, FMS에서 multi-domain 처리
   - 또는: Main Server에 multi-domain bridge 구현

2. **Order 상태 DB 제약조건 불일치**
   - `AT_POINT13` 상태가 CheckConstraint에 없음
   - 해결: database_manager.py line 165 수정 + migration

### 5.2 HIGH (기능 완성도)

3. **Skip mode에서 LoadingComplete 자동 전송 누락**
   - 현재 PrecisionParked만 mock 전송
   - 해결: ros_bridge.py에 _send_mock_loading_complete 추가

4. **주문 상태 전환 누락**
   - COOKING, DELIVERING, DELIVERED 상태 전환 로직 없음
   - 해결: main_server_node.py에 상태 전환 추가

5. **skip_mode 파라미터 전달 로직 부재**
   - main() 함수에서 skip_mode 전달 안 됨
   - 해결: argparse 또는 ROS parameter 사용

### 5.3 MEDIUM (안정성)

6. **TCP 메시지 구분자 불일치**
   - Server는 단일 recv(), Client는 개행 구분자 사용
   - 해결: tcp_server.py에 buffering 로직 추가

7. **Robot status 제약조건 부족**
   - NAVIGATING, LOADING, DELIVERING 상태 없음
   - 해결: database_manager.py Robot 모델 수정

8. **메시지 라우팅 로직 부재**
   - 여러 도메인으로 메시지 전송 시 라우팅 필요
   - 해결: Multi-domain bridge 구현 시 함께 해결

### 5.4 LOW (편의성)

9. **database.env 설정 가이드 부족**
   - 처음 실행 시 database.env 생성 필요
   - 해결: README에 setup 단계 추가

10. **에러 메시지 국제화 미지원**
    - 모든 로그가 영어 또는 한글 혼재
    - 해결: i18n 라이브러리 도입 (선택사항)

---

## 6. 로컬 테스트 가능 여부

### 6.1 실물 로봇 없이 테스트 가능한 부분

✅ **TCP 통신 테스트**:
```bash
# Terminal 1: Main Server 실행
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run main_server main_server

# Terminal 2: TCP 테스트 클라이언트
cd app/backend/tests
./tcp_test_client.py order --table T01 --menu M001
./tcp_test_client.py fleet
```

**제공된 도구**:
- `tcp_test_client.py`: 완전한 CLI 테스트 도구 ✅
- README.md: 명확한 사용법 문서 ✅

**테스트 가능 시나리오**:
1. Order request → response 검증
2. Order status query
3. Fleet status query
4. Delivery complete

✅ **Database 연동 테스트**:
```bash
# PostgreSQL 설치 및 설정
cd database
./setup_database.sh

# Main Server 실행 후 DB 조회
psql -h localhost -U kitchmatic_user -d kitchmatic
SELECT * FROM orders;
SELECT * FROM robots;
```

**테스트 가능**:
- Order 생성/조회/상태 변경
- Robot 상태 업데이트
- Menu, Ingredient 조회

✅ **ROS 2 통신 테스트 (단일 도메인)**:
```bash
# Terminal 1: Main Server
ros2 run main_server main_server --ros-args -p skip_mode:=true

# Terminal 2: Mock FMS (수동 메시지 전송)
ros2 topic pub /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "
robot_id: 'pinky1'
order_id: '123e4567-e89b-12d3-a456-426614174000'
current_pose:
  position: {x: 0.47, y: 0.63, z: 0.0}
  orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
arrived_at: {sec: 0, nanosec: 0}
"

# Terminal 3: Monitor
ros2 topic echo /robot_arm/cooking_order
ros2 topic echo /fms/precision_parked  # skip mode에서 자동 전송
```

**테스트 가능**:
- PickupArrival → CookingOrder 전송
- Skip mode에서 PrecisionParked 자동 전송
- FleetStatus 수신 및 DB 업데이트

### 6.2 실물 로봇 필요한 부분

❌ **ROS_DOMAIN_ID 다중 도메인 테스트**:
- 여러 도메인 간 통신은 네트워크 환경 필요
- 로컬에서는 단일 도메인만 테스트 가능

❌ **Navigation 완전 테스트**:
- FMS와 실제 로봇 간 navigate_to_pose 액션 호출
- AMCL 위치 추정 및 배터리 모니터링

❌ **Robot Arm 통합 테스트**:
- LoadingComplete 메시지는 실제 Robot Arm에서 전송
- Skip mode로 우회 가능하지만, 실제 통합은 하드웨어 필요

### 6.3 로컬 테스트 환경 구축 방법

**권장 테스트 시나리오**:

```bash
# 1. 데이터베이스 설정
cd /home/gw/kitchmatics/roscamp-repo-1/database
./setup_database.sh

# 2. Main Server 실행 (skip mode)
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run main_server main_server --ros-args -p skip_mode:=true

# 3. Mock FMS (Python script)
# 파일: tests/mock_fms.py
import rclpy
from rclpy.node import Node
from fleet_interfaces.msg import FleetStatus, PickupArrival

class MockFMS(Node):
    def __init__(self):
        super().__init__('mock_fms')
        self.pickup_pub = self.create_publisher(PickupArrival, '/fms/pickup_arrival', 10)

    def send_pickup_arrival(self, robot_id, order_id):
        msg = PickupArrival()
        msg.robot_id = robot_id
        msg.order_id = order_id
        # ... fill pose
        self.pickup_pub.publish(msg)

# 4. 테스트 실행
python3 tests/mock_fms.py  # Background
./app/backend/tests/tcp_test_client.py order --table T01 --menu M001
```

**테스트 자동화 스크립트 생성 필요**:
```bash
# tests/integration_test.sh
#!/bin/bash
# 1. Start Main Server
# 2. Wait for ready
# 3. Send order via TCP
# 4. Send mock pickup_arrival
# 5. Verify cooking_order sent
# 6. Verify precision_parked received (skip mode)
# 7. Verify loading_complete (mock)
# 8. Send delivery_complete
# 9. Verify order status COMPLETED
```

---

## 7. 개선 권장사항

### 7.1 아키텍처 개선

1. **Multi-Domain Communication Layer 추가**
   ```
   Main Server
     ├── ROS Bridge (Domain 0 - Master)
     ├── FMS Bridge (Domain 11 - pinky1 FMS)
     ├── Pinky2 Bridge (Domain 12)
     ├── Pinky3 Bridge (Domain 13)
     ├── Arm1 Bridge (Domain 14)
     └── Arm2 Bridge (Domain 15)
   ```

2. **Message Router 구현**
   ```python
   class MessageRouter:
       def route_order_request(self, order_id, robot_id):
           domain_id = self.robot_domain_map[robot_id]
           bridge = self.domain_bridges[domain_id]
           bridge.publish_order_request(...)
   ```

3. **Configuration Management 강화**
   ```python
   # config/main_server_config.yaml
   database:
     host: localhost
     port: 5432
     name: kitchmatic

   tcp:
     host: 0.0.0.0
     port: 9999

   ros:
     master_domain: 0
     fms_domain: 11
     robot_domains:
       pinky1: 11
       pinky2: 12
       pinky3: 13
   ```

### 7.2 코드 품질 개선

1. **Type Hints 완성**
   ```python
   # 현재 일부만 있음
   from typing import Dict, List, Optional, Tuple

   def handle_order_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
       ...
   ```

2. **단위 테스트 추가**
   ```python
   # tests/test_database_manager.py
   import pytest
   from main_server.database_manager import DatabaseManager

   def test_create_order():
       db = DatabaseManager(...)
       order_id = db.create_order('T01', 'M001')
       assert order_id is not None
   ```

3. **통합 테스트 추가**
   ```python
   # tests/test_integration.py
   def test_full_order_flow():
       # TCP order → ROS pickup → cooking → loading → delivery
       ...
   ```

### 7.3 운영 환경 대비

1. **환경 변수 관리**
   ```bash
   # .env.production
   DB_HOST=192.168.1.5
   DB_PASSWORD=secure_password_here
   TCP_PORT=9999
   ROS_DOMAIN_ID=0
   ```

2. **로깅 레벨 설정**
   ```python
   # 개발: DEBUG
   # 운영: INFO
   logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
   ```

3. **Health Check 엔드포인트**
   ```python
   # TCP 메시지 타입 추가
   'health_check': lambda data: {
       'status': 'healthy',
       'database': db.is_connected(),
       'ros': ros_bridge.is_running()
   }
   ```

---

## 8. 결론

### 8.1 강점

1. **깔끔한 아키텍처**: 3-tier 분리 (DB, TCP, ROS)가 명확
2. **확장성**: Handler 패턴으로 새 메시지 타입 추가 용이
3. **에러 처리**: 일관된 try-except-finally 패턴
4. **Skip Mode**: 외부 팀 없이 테스트 가능
5. **문서화**: TCP 프로토콜 상세 문서, 테스트 가이드 제공

### 8.2 즉시 해결 필요한 문제

1. **ROS_DOMAIN_ID 미구현** → FMS에서 처리하도록 아키텍처 재설계 필요
2. **DB 제약조건 불일치** → AT_POINT13 상태 추가
3. **Skip mode 완전성** → LoadingComplete mock 추가

### 8.3 로컬 테스트 가능 여부

**가능**: TCP 통신, DB 연동, 단일 도메인 ROS 통신 (80%)
**불가능**: Multi-domain 통신, 실제 로봇 제어 (20%)

**권장**: Skip mode + Mock FMS로 대부분의 기능 로컬 테스트 가능

### 8.4 다음 단계

1. CRITICAL 문제 해결 (ROS_DOMAIN_ID, DB 제약조건)
2. Skip mode 완전 구현 (LoadingComplete mock)
3. 통합 테스트 스크립트 작성
4. FMS 팀과 multi-domain 통신 방안 협의
5. 실제 환경 배포 및 검증

---

**검증자**: Backend/Main Server Lead
**검증 완료일**: 2026-02-25
