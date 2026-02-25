# Main Server Testing Checklist
**Backend/Main Server Lead**
**목적**: 로컬 환경에서 Main Server 기능 검증

---

## Pre-Testing Setup

### 1. Database Setup
```bash
□ PostgreSQL 설치 확인
  psql --version

□ Database 생성
  cd /home/gw/kitchmatics/roscamp-repo-1/database
  ./setup_database.sh

□ 연결 테스트
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "SELECT 1"

□ database.env 설정 확인
  cd /home/gw/kitchmatics/roscamp-repo-1/app/backend/config
  cat database.env
  # DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD 확인
```

### 2. ROS 2 Environment
```bash
□ ROS 2 Jazzy 설치 확인
  ros2 --version

□ Workspace 빌드
  cd /home/gw/kitchmatics/roscamp-repo-1
  colcon build --packages-select fleet_interfaces main_server

□ Environment source
  source install/setup.bash

□ fleet_interfaces 확인
  ros2 interface list | grep fleet_interfaces
  # OrderRequest, CookingOrder, LoadingComplete 등 확인
```

### 3. Test Tools
```bash
□ TCP 테스트 클라이언트 실행 권한
  cd /home/gw/kitchmatics/roscamp-repo-1/app/backend/tests
  chmod +x tcp_test_client.py

□ 도구 테스트
  ./tcp_test_client.py --help
```

---

## Test Phase 1: Standalone Components

### 1.1 Database Manager (10분)

```bash
□ Python 인터프리터에서 테스트
  cd /home/gw/kitchmatics/roscamp-repo-1
  python3

□ Import 테스트
  >>> from app.backend.main_server.database_manager import DatabaseManager
  >>> db = DatabaseManager(
        db_host='localhost',
        db_port=5432,
        db_name='kitchmatic',
        db_user='kitchmatic_user',
        db_password='your_password'
      )

□ 연결 테스트
  >>> db.connect()
  # True 반환 확인

□ Order 생성 테스트
  >>> order_id = db.create_order('T01', 'M001', quantity=1)
  >>> print(order_id)
  # UUID 반환 확인

□ Order 조회 테스트
  >>> order = db.get_order(order_id)
  >>> print(order.status)
  # 'PENDING' 확인

□ Order 상태 업데이트 테스트
  >>> db.update_order_status(str(order_id), 'CONFIRMED')
  >>> order = db.get_order(order_id)
  >>> print(order.status)
  # 'CONFIRMED' 확인

□ ❌ CRITICAL 버그 검증
  >>> db.update_order_status(str(order_id), 'AT_POINT13')
  # CheckViolation 에러 발생 예상 (버그 확인)
  # 수정 후: 정상 작동 확인

□ Menu 조회 테스트
  >>> menu = db.get_menu('M001')
  >>> print(menu.name, menu.available)

□ 정리
  >>> db.close()
  >>> exit()
```

### 1.2 TCP Server (15분)

**Terminal 1: TCP Server**
```bash
□ TCP Server 단독 실행 (main_server 대신 간단한 테스트 서버)
  # Note: 실제로는 main_server를 실행해야 함
  # 여기서는 개념적 테스트
```

**Terminal 2: TCP Client**
```bash
□ Netcat으로 연결 테스트
  echo '{"type":"fleet_status_query","data":{}}' | nc localhost 9999

□ 잘못된 JSON 전송
  echo 'invalid json' | nc localhost 9999
  # 에러 응답 확인: {"status":"error","message":"Invalid JSON format"}

□ 미지원 메시지 타입
  echo '{"type":"unknown_type","data":{}}' | nc localhost 9999
  # 에러 응답 확인: {"status":"error","message":"Unknown message type"}

□ 복수 메시지 전송
  (echo '{"type":"fleet_status_query","data":{}}';
   echo '{"type":"fleet_status_query","data":{}}') | nc localhost 9999
  # 두 개의 응답 확인 (버퍼링 테스트)
```

### 1.3 ROS Bridge (20분)

**Terminal 1: ROS Bridge (main_server 일부)**
```bash
□ Main Server 실행 (skip mode)
  cd /home/gw/kitchmatics/roscamp-repo-1
  source install/setup.bash
  ros2 run main_server main_server --ros-args -p skip_mode:=true
```

**Terminal 2: Monitor Topics**
```bash
□ ROS topics 확인
  ros2 topic list | grep -E "fms|robot_arm"

  Expected topics:
  /fms/order_request
  /fms/delivery_complete
  /fms/pickup_arrival
  /fms/precision_parked
  /robot_arm/cooking_order
  /robot_arm/loading_complete

□ OrderRequest subscriber 확인
  ros2 topic info /fms/order_request
  # Subscription Count: 0 (FMS 없으므로)

□ CookingOrder publisher 확인
  ros2 topic info /robot_arm/cooking_order
  # Publisher Count: 1 (Main Server)
```

**Terminal 3: Manual ROS Messages**
```bash
□ Manual PickupArrival 전송
  ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "
  robot_id: 'pinky1'
  order_id: '12345678-1234-1234-1234-123456789012'
  current_pose:
    position: {x: 0.47, y: 0.63, z: 0.0}
    orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
  arrived_at: {sec: 0, nanosec: 0}
  "

□ CookingOrder 수신 확인 (Terminal 2)
  ros2 topic echo /robot_arm/cooking_order --once

□ PrecisionParked 수신 확인 (skip mode, 2초 후)
  ros2 topic echo /fms/precision_parked --once

□ LoadingComplete 자동 전송 확인 (skip mode, 3초 후)
  # ❌ 현재 버그: 자동 전송 안 됨
  # 수정 후: 자동 전송 확인
```

---

## Test Phase 2: Integrated System

### 2.1 Full Main Server Start (10분)

**Terminal 1: Main Server**
```bash
□ Main Server 실행
  cd /home/gw/kitchmatics/roscamp-repo-1
  source install/setup.bash
  ros2 run main_server main_server --ros-args -p skip_mode:=true

□ 시작 로그 확인
  [INFO] Initializing Main Server components (skip_mode=True)
  [INFO] Database connection established successfully
  [INFO] TCP Server started on 0.0.0.0:9999
  [INFO] ROS Bridge initialized (skip_mode=True)
  [INFO] Main Server initialized successfully
  [INFO] Main Server is running...

□ 에러 없이 시작 확인
```

**Terminal 2: Monitor**
```bash
□ Process 확인
  ps aux | grep main_server

□ Port 확인
  netstat -tuln | grep 9999
  # 0.0.0.0:9999 LISTEN 확인

□ Database 연결 확인
  netstat -tuln | grep 5432
```

### 2.2 TCP Communication Test (15분)

```bash
□ Fleet status 조회
  cd /home/gw/kitchmatics/roscamp-repo-1/app/backend/tests
  ./tcp_test_client.py --host localhost --port 9999 fleet

  Expected:
  {
    "status": "success",
    "data": {
      "robots": [],
      "pending_orders": 0,
      "active_orders": 0
    }
  }

□ Order 생성
  ./tcp_test_client.py order --table T01 --menu M001 --quantity 1 --sauce mayo

  Expected:
  {
    "status": "success",
    "data": {
      "order_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "estimated_time": 120
    }
  }

□ Order ID 저장
  ORDER_ID=$(./tcp_test_client.py order --table T01 --menu M001 | grep order_id | grep -oP '"[0-9a-f-]{36}"' | tr -d '"')
  echo $ORDER_ID

□ Order 상태 조회
  ./tcp_test_client.py status --order-id $ORDER_ID

  Expected status: CONFIRMED

□ Database 확인
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "SELECT id, table_number, status FROM orders WHERE id = '$ORDER_ID';"
```

### 2.3 ROS Communication Test (20분)

**Terminal 3: ROS Monitor**
```bash
□ OrderRequest 모니터링
  ros2 topic echo /fms/order_request &

□ CookingOrder 모니터링
  ros2 topic echo /robot_arm/cooking_order &

□ PrecisionParked 모니터링
  ros2 topic echo /fms/precision_parked &
```

**Terminal 4: Send PickupArrival**
```bash
□ PickupArrival 전송
  ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "
  robot_id: 'pinky1'
  order_id: '$ORDER_ID'
  current_pose:
    position: {x: 0.47, y: 0.63, z: 0.0}
    orientation: {w: 1.0}
  arrived_at: {sec: 0, nanosec: 0}
  "

□ Main Server 로그 확인 (Terminal 1)
  [INFO] Received pickup arrival: robot=pinky1, order=...
  [INFO] Loading complete handler called
  [INFO] Order ... marked as AT_POINT13
  [INFO] Published cooking order to Robot Arm: ...

□ CookingOrder 수신 확인 (Terminal 3)
  # order_id, menu_id, quantity, sauce_type, assigned_robot_id 확인

□ 2초 후 PrecisionParked 확인 (Terminal 3)
  [INFO] Skip mode: Sending mock precision_parked for pinky1
  # PrecisionParked 메시지 수신 확인

□ ❌ 3초 후 LoadingComplete 확인 (현재 버그)
  # 수정 후: LoadingComplete callback 호출 확인

□ Database 상태 확인
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "SELECT status FROM orders WHERE id = '$ORDER_ID';"
  # ❌ 현재: AT_POINT13 (DB 에러 가능)
  # 수정 후: READY
```

### 2.4 Delivery Complete Test (10분)

```bash
□ Delivery complete 전송
  ./tcp_test_client.py complete --order-id $ORDER_ID --table T01

  Expected:
  {
    "status": "success",
    "data": {
      "message": "Order completed successfully"
    }
  }

□ DeliveryComplete ROS 메시지 확인
  ros2 topic echo /fms/delivery_complete --once

□ Database 상태 확인
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "SELECT status, completed_at FROM orders WHERE id = '$ORDER_ID';"
  # status: COMPLETED
  # completed_at: not null
```

---

## Test Phase 3: Integration Testing

### 3.1 Full Order Flow (30분)

**자동화 스크립트 사용**
```bash
□ Integration test 실행
  cd /home/gw/kitchmatics/roscamp-repo-1/app/backend/tests
  chmod +x integration_test.sh
  ./integration_test.sh

□ 테스트 결과 확인
  Summary:
    Order ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    Final Status: COMPLETED
    Test Result: PASS / PARTIAL

□ 실패 시 로그 확인
  tail -100 /var/log/main_server/server.log
```

**수동 검증 (스크립트 사용 안 할 경우)**
```bash
□ Step 1: Order 생성
  ORDER_ID=$(./tcp_test_client.py order --table T01 --menu M001 | grep -oP '"order_id": "\K[^"]+')

□ Step 2: 상태 확인 (CONFIRMED)
  ./tcp_test_client.py status --order-id $ORDER_ID | grep status

□ Step 3: PickupArrival 전송
  ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "..."

□ Step 4: 5초 대기 (precision + loading delay)
  sleep 5

□ Step 5: 상태 확인 (READY)
  ./tcp_test_client.py status --order-id $ORDER_ID | grep status

□ Step 6: Delivery complete
  ./tcp_test_client.py complete --order-id $ORDER_ID --table T01

□ Step 7: 최종 상태 확인 (COMPLETED)
  ./tcp_test_client.py status --order-id $ORDER_ID | grep status
```

### 3.2 Error Handling Test (15분)

```bash
□ Invalid menu order
  ./tcp_test_client.py order --table T01 --menu M999
  # Expected: error response

□ Non-existent order query
  ./tcp_test_client.py status --order-id "00000000-0000-0000-0000-000000000000"
  # Expected: error response

□ Duplicate order complete
  ./tcp_test_client.py complete --order-id $ORDER_ID --table T01
  # 이미 COMPLETED 상태
  # Expected: success (idempotent)

□ Database connection loss simulation
  # Stop PostgreSQL
  sudo systemctl stop postgresql
  ./tcp_test_client.py order --table T01 --menu M001
  # Expected: error response
  # Restart PostgreSQL
  sudo systemctl start postgresql
```

### 3.3 Concurrent Orders Test (20분)

**Terminal 1-5: 동시 주문**
```bash
□ Terminal 1
  ORDER1=$(./tcp_test_client.py order --table T01 --menu M001 | grep -oP '"order_id": "\K[^"]+')

□ Terminal 2
  ORDER2=$(./tcp_test_client.py order --table T02 --menu M002 | grep -oP '"order_id": "\K[^"]+')

□ Terminal 3
  ORDER3=$(./tcp_test_client.py order --table T03 --menu M001 | grep -oP '"order_id": "\K[^"]+')

□ 모든 주문 생성 확인
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "SELECT id, table_number, status FROM orders WHERE id IN ('$ORDER1', '$ORDER2', '$ORDER3');"

□ 각 주문에 대해 PickupArrival 전송
  # 각 터미널에서 동시에 실행
  ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "robot_id: 'pinky1', order_id: '$ORDER1', ..."
  ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "robot_id: 'pinky2', order_id: '$ORDER2', ..."
  ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "robot_id: 'pinky3', order_id: '$ORDER3', ..."

□ 모든 주문 상태 확인 (5초 후)
  sleep 5
  ./tcp_test_client.py status --order-id $ORDER1
  ./tcp_test_client.py status --order-id $ORDER2
  ./tcp_test_client.py status --order-id $ORDER3

□ 모든 주문 완료
  ./tcp_test_client.py complete --order-id $ORDER1 --table T01
  ./tcp_test_client.py complete --order-id $ORDER2 --table T02
  ./tcp_test_client.py complete --order-id $ORDER3 --table T03
```

---

## Test Phase 4: Bug Verification

### 4.1 AT_POINT13 상태 버그 (CRITICAL)

```bash
□ Order 생성
  ORDER_ID=$(./tcp_test_client.py order --table T01 --menu M001 | grep -oP '"order_id": "\K[^"]+')

□ PickupArrival 전송
  ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "robot_id: 'pinky1', order_id: '$ORDER_ID', ..."

□ Main Server 로그에서 에러 확인
  # ❌ 버그: CheckViolation 에러 발생 예상
  # ✅ 수정 후: 에러 없이 AT_POINT13 상태 저장

□ Database 확인
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "SELECT status FROM orders WHERE id = '$ORDER_ID';"
  # ✅ 수정 후: AT_POINT13
```

### 4.2 LoadingComplete 자동 전송 버그 (CRITICAL)

```bash
□ Skip mode 활성화 확인
  # Main Server 시작 시 로그 확인
  [INFO] ROS Bridge initialized (skip_mode=True)

□ PickupArrival 전송
  ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "..."

□ PrecisionParked 자동 전송 확인 (2초 후)
  ros2 topic echo /fms/precision_parked --once
  # ✅ 작동 확인

□ LoadingComplete 자동 호출 확인 (3초 후)
  # Main Server 로그 확인
  # ❌ 버그: 자동 호출 안 됨
  # ✅ 수정 후: [INFO] Skip mode: Sending mock loading_complete...

□ Order 상태 확인
  ./tcp_test_client.py status --order-id $ORDER_ID
  # ✅ 수정 후: status = READY
```

### 4.3 skip_mode 파라미터 전달 버그 (CRITICAL)

```bash
□ skip_mode 없이 실행
  ros2 run main_server main_server
  # ROS Bridge 로그 확인
  # ❌ 버그: skip_mode=False (기본값) 또는 에러

□ skip_mode=true로 실행
  ros2 run main_server main_server --ros-args -p skip_mode:=true
  # ❌ 버그: 파라미터 무시됨
  # ✅ 수정 후: [INFO] skip_mode=True 확인

□ PickupArrival 후 자동 처리 확인
  # ✅ 수정 후: PrecisionParked, LoadingComplete 자동 전송
```

### 4.4 TCP 메시지 구분자 버그 (MEDIUM)

```bash
□ 큰 메시지 전송 (>4096 bytes)
  # Create large JSON message
  python3 -c "
import json
import socket
data = {'type': 'order_request', 'data': {'table_number': 'T01', 'menu_id': 'M001', 'extra': 'x' * 5000}}
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 9999))
s.sendall(json.dumps(data).encode('utf-8') + b'\n')
response = s.recv(4096)
print(response)
s.close()
"

□ 여러 메시지 동시 전송
  (echo '{"type":"fleet_status_query","data":{}}';
   echo '{"type":"fleet_status_query","data":{}}';
   echo '{"type":"fleet_status_query","data":{}}') | nc localhost 9999
  # ❌ 버그: 첫 메시지만 처리, 나머지 무시
  # ✅ 수정 후: 3개 모두 응답
```

---

## Test Phase 5: Performance & Stress

### 5.1 Database Performance (10분)

```bash
□ 100개 주문 생성
  for i in {1..100}; do
    ./tcp_test_client.py order --table T0$((i%8+1)) --menu M001 > /dev/null &
  done
  wait

□ 쿼리 속도 확인
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "
  EXPLAIN ANALYZE
  SELECT * FROM orders WHERE status = 'CONFIRMED';
  "
  # Index scan 확인

□ Database 크기 확인
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "
  SELECT pg_size_pretty(pg_database_size('kitchmatic'));
  "
```

### 5.2 TCP Connection Load (10분)

```bash
□ 10개 동시 연결
  for i in {1..10}; do
    ./tcp_test_client.py fleet &
  done
  wait

□ Main Server 로그 확인
  # Thread 생성/종료 로그
  # 에러 없이 모든 요청 처리 확인

□ Connection pool 확인
  netstat -an | grep 9999 | wc -l
```

### 5.3 ROS Message Load (10분)

```bash
□ 빠른 메시지 전송
  for i in {1..50}; do
    ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "robot_id: 'pinky1', order_id: '$(uuidgen)', ..." &
  done
  wait

□ Main Server CPU/Memory 확인
  top -p $(pgrep -f main_server)

□ 메시지 유실 확인
  # CookingOrder 전송 횟수 확인
  ros2 topic hz /robot_arm/cooking_order
```

---

## Post-Testing Cleanup

### Database Cleanup
```bash
□ 테스트 데이터 삭제
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "DELETE FROM orders WHERE table_number LIKE 'T%';"

□ Robot 상태 초기화
  psql -h localhost -U kitchmatic_user -d kitchmatic -c "UPDATE robots SET status = 'IDLE';"
```

### Process Cleanup
```bash
□ Main Server 종료
  # Ctrl+C in Terminal 1
  # Graceful shutdown 로그 확인:
  # [INFO] Received signal 2
  # [INFO] Shutting down Main Server...
  # [INFO] TCP Server stopped
  # [INFO] Main Server shutdown complete

□ Background processes 종료
  killall ros2 topic 2>/dev/null
```

### Log Review
```bash
□ Error 로그 확인
  grep ERROR /var/log/main_server/server.log

□ Warning 로그 확인
  grep WARNING /var/log/main_server/server.log

□ 로그 아카이브
  mv /var/log/main_server/server.log /var/log/main_server/server_$(date +%Y%m%d_%H%M%S).log
```

---

## Test Result Summary

### Pass Criteria

| Category | Test Items | Pass | Fail | Notes |
|----------|-----------|------|------|-------|
| Database | Connection | ☐ | ☐ | |
| Database | Order CRUD | ☐ | ☐ | |
| Database | AT_POINT13 status | ☐ | ☐ | CRITICAL bug |
| TCP | Connection | ☐ | ☐ | |
| TCP | JSON parsing | ☐ | ☐ | |
| TCP | Message routing | ☐ | ☐ | |
| TCP | Buffer handling | ☐ | ☐ | MEDIUM bug |
| ROS | Publishers | ☐ | ☐ | |
| ROS | Subscribers | ☐ | ☐ | |
| ROS | Skip mode - Precision | ☐ | ☐ | |
| ROS | Skip mode - Loading | ☐ | ☐ | CRITICAL bug |
| Integration | Full order flow | ☐ | ☐ | |
| Integration | Error handling | ☐ | ☐ | |
| Integration | Concurrent orders | ☐ | ☐ | |
| Performance | Database queries | ☐ | ☐ | |
| Performance | TCP load | ☐ | ☐ | |
| Performance | ROS load | ☐ | ☐ | |

### Expected Results

**Before Fixes:**
- ❌ AT_POINT13 status: DB constraint violation
- ❌ Skip mode LoadingComplete: Not triggered
- ❌ skip_mode parameter: Not passed to main()
- ⚠️ TCP buffer: May fail on large/multiple messages

**After Fixes:**
- ✅ All order statuses work correctly
- ✅ Skip mode fully automated (pickup → precision → loading)
- ✅ skip_mode parameter correctly passed
- ✅ TCP handles all message sizes/counts

---

## Quick Reference Commands

```bash
# Start Main Server
ros2 run main_server main_server --ros-args -p skip_mode:=true

# Send order
./tcp_test_client.py order --table T01 --menu M001

# Query status
./tcp_test_client.py status --order-id <ORDER_ID>

# Send pickup arrival
ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "robot_id: 'pinky1', order_id: '<ORDER_ID>', current_pose: {position: {x: 0.47, y: 0.63, z: 0.0}, orientation: {w: 1.0}}, arrived_at: {sec: 0, nanosec: 0}"

# Complete delivery
./tcp_test_client.py complete --order-id <ORDER_ID> --table T01

# Database query
psql -h localhost -U kitchmatic_user -d kitchmatic -c "SELECT * FROM orders ORDER BY created_at DESC LIMIT 5;"

# Monitor ROS topics
ros2 topic echo /robot_arm/cooking_order
ros2 topic echo /fms/precision_parked

# Integration test
./integration_test.sh
```

---

**테스트 완료 후 BACKEND_VALIDATION_REPORT.md의 "문제점 종합 리스트" 업데이트**
