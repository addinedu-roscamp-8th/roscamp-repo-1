# Backend Critical Fixes - 구현 가이드
**우선순위**: CRITICAL 문제 해결
**예상 작업 시간**: 4-6시간

---

## Fix #1: DB 제약조건 불일치 (AT_POINT13 상태)

### 문제
```python
# main_server_node.py, line 463
self.db.update_order_status(order_id, 'AT_POINT13')

# database_manager.py, line 165
CheckConstraint("status IN ('PENDING', 'CONFIRMED', ..., 'COMPLETED', ...)")
# ❌ 'AT_POINT13' 없음 → DB 에러 발생
```

### 해결 방법

#### Step 1: database_manager.py 수정

```python
# /home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/database_manager.py
# Line 165 수정

# Before:
CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'COOKING', 'READY', 'INSPECTED', 'DELIVERING', 'DELIVERED', 'COMPLETED', 'CANCELLED', 'HALTED')", name='chk_status'),

# After:
CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'AT_POINT13', 'PRECISION_PARKING', 'COOKING', 'READY', 'INSPECTED', 'DELIVERING', 'DELIVERED', 'COMPLETED', 'CANCELLED', 'HALTED')", name='chk_status'),
```

#### Step 2: Database Migration 생성

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/database/migrations
```

Create file: `002_add_order_statuses.sql`

```sql
-- Migration: Add AT_POINT13 and PRECISION_PARKING order statuses
-- Date: 2026-02-25
-- Author: Backend Lead

BEGIN;

-- Drop existing constraint
ALTER TABLE orders DROP CONSTRAINT IF EXISTS chk_status;

-- Add new constraint with additional statuses
ALTER TABLE orders ADD CONSTRAINT chk_status
  CHECK (status IN (
    'PENDING',
    'CONFIRMED',
    'AT_POINT13',         -- Robot arrived at kitchen pickup point
    'PRECISION_PARKING',  -- Precision parking in progress
    'COOKING',            -- Robot arm cooking food
    'READY',              -- Food loaded, ready to deliver
    'INSPECTED',          -- Quality check passed
    'DELIVERING',         -- Robot navigating to table
    'DELIVERED',          -- Robot arrived at table
    'COMPLETED',          -- Customer confirmed delivery
    'CANCELLED',          -- Order cancelled
    'HALTED'              -- Error occurred
  ));

COMMIT;
```

#### Step 3: Run Migration

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/database

# Backup first
pg_dump -h localhost -U kitchmatic_user kitchmatic > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migration
psql -h localhost -U kitchmatic_user -d kitchmatic -f migrations/002_add_order_statuses.sql
```

#### Step 4: Verify

```bash
# Check constraint
psql -h localhost -U kitchmatic_user -d kitchmatic -c "
SELECT conname, contype, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'orders'::regclass AND conname = 'chk_status';
"
```

---

## Fix #2: Skip Mode - LoadingComplete 자동 전송 추가

### 문제
현재 skip mode에서:
- ✅ PrecisionParked는 자동 전송됨
- ❌ LoadingComplete는 수동으로 보내야 함

### 해결 방법

#### Step 1: ros_bridge.py 수정

Add method to send mock LoadingComplete:

```python
# /home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/ros_bridge.py
# Add after _send_mock_precision_parked method (around line 302)

def _send_mock_loading_complete(self, robot_id: str, order_id: str):
    """
    Send mock LoadingComplete message for skip mode testing

    Args:
        robot_id: Robot ID
        order_id: Order ID
    """
    logger.info(f"Skip mode: Sending mock loading_complete for {robot_id}")

    # Call the callback directly (simulating Robot Arm sending the message)
    if self.on_loading_complete:
        self.on_loading_complete(
            order_id=order_id,
            success=True,
            robot_id=robot_id,
            message="Mock food loading completed (skip mode)",
            completed_at=datetime.utcnow()
        )

    logger.info(f"Skip mode: Mock loading_complete sent for order {order_id}")
```

#### Step 2: Chain precision_parked → loading_complete

Modify `_send_mock_precision_parked`:

```python
# /home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/ros_bridge.py
# Modify _send_mock_precision_parked method (around line 281-301)

def _send_mock_precision_parked(self, robot_id: str, order_id: str, pose):
    """
    Send mock PrecisionParked message for skip mode testing

    Args:
        robot_id: Robot ID
        order_id: Order ID
        pose: Current pose
    """
    logger.info(f"Skip mode: Sending mock precision_parked for {robot_id}")

    msg = PrecisionParked()
    msg.robot_id = robot_id
    msg.order_id = order_id
    msg.success = True
    msg.final_pose = pose
    msg.message = "Mock precision parking completed (skip mode)"
    msg.completed_at = self._datetime_to_ros_time(datetime.utcnow())

    self.precision_parked_pub.publish(msg)
    logger.info(f"Published mock precision_parked: robot={robot_id}, order={order_id}")

    # ✅ ADD THIS: Chain to loading_complete after delay
    if self.skip_mode:
        logger.info(f"Skip mode: Scheduling loading_complete for {robot_id} in {self.food_loading_delay}s")
        self.create_timer(
            self.food_loading_delay,
            lambda: self._send_mock_loading_complete(robot_id, order_id)
        )
```

#### Step 3: Test

```bash
# Terminal 1: Start Main Server with skip mode
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run main_server main_server --ros-args -p skip_mode:=true

# Terminal 2: Monitor topics
ros2 topic echo /fms/precision_parked &
ros2 topic echo /robot_arm/loading_complete &

# Terminal 3: Send order
cd app/backend/tests
./tcp_test_client.py order --table T01 --menu M001

# Terminal 4: Manually trigger pickup arrival (or use Mock FMS)
ros2 topic pub -1 /fms/pickup_arrival fleet_interfaces/msg/PickupArrival "
robot_id: 'pinky1'
order_id: '$(uuidgen)'
current_pose: {position: {x: 0.47, y: 0.63, z: 0.0}, orientation: {w: 1.0}}
arrived_at: {sec: 0, nanosec: 0}
"

# Expected flow:
# 1. PickupArrival received
# 2. CookingOrder sent to /robot_arm/cooking_order
# 3. (2s delay) PrecisionParked auto-sent
# 4. (3s delay) LoadingComplete auto-triggered
# 5. Order status → READY
```

---

## Fix #3: skip_mode 파라미터 전달

### 문제
```python
# main_server_node.py, line 554
def main():
    server = MainServer()  # ❌ skip_mode 전달 안 됨
```

### 해결 방법

#### Option A: ROS 2 Parameter (권장)

```python
# /home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/main_server_node.py
# Modify main() function

import rclpy
from rclpy.node import Node as TempNode

def main():
    """Entry point for Main Server"""
    try:
        # Initialize rclpy first to read parameters
        rclpy.init()

        # Create temporary node to read parameters
        temp_node = TempNode('main_server_param_reader')
        temp_node.declare_parameter('skip_mode', False)
        skip_mode = temp_node.get_parameter('skip_mode').value
        temp_node.destroy_node()

        # Create server with parameter
        server = MainServer(skip_mode=skip_mode)
        server.run()
    except Exception as e:
        logger.error(f"Main Server error: {e}")
        sys.exit(1)
```

**Usage**:
```bash
# Skip mode enabled
ros2 run main_server main_server --ros-args -p skip_mode:=true

# Skip mode disabled (default)
ros2 run main_server main_server
```

#### Option B: Environment Variable

```python
# /home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/main_server_node.py

import os

def main():
    """Entry point for Main Server"""
    try:
        # Read from environment variable
        skip_mode = os.getenv('SKIP_MODE', 'false').lower() == 'true'

        logger.info(f"Main Server starting with skip_mode={skip_mode}")
        server = MainServer(skip_mode=skip_mode)
        server.run()
    except Exception as e:
        logger.error(f"Main Server error: {e}")
        sys.exit(1)
```

**Usage**:
```bash
# Skip mode enabled
SKIP_MODE=true ros2 run main_server main_server

# Skip mode disabled
ros2 run main_server main_server
```

#### Option C: Launch File Parameter

```python
# /home/gw/kitchmatics/roscamp-repo-1/app/backend/launch/main_server_launch.py

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    skip_mode_arg = DeclareLaunchArgument(
        'skip_mode',
        default_value='false',
        description='Enable skip mode for testing without external teams'
    )

    return LaunchDescription([
        skip_mode_arg,

        Node(
            package='main_server',
            executable='main_server',
            name='main_server',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'skip_mode': LaunchConfiguration('skip_mode')
            }]
        ),
    ])
```

**Usage**:
```bash
# Skip mode enabled
ros2 launch main_server main_server_launch.py skip_mode:=true

# Skip mode disabled
ros2 launch main_server main_server_launch.py
```

---

## Fix #4: TCP 메시지 구분자 (버퍼링)

### 문제
```python
# tcp_server.py, line 120
data = client_socket.recv(4096)  # 단일 recv만 사용 → 큰 메시지 잘림 가능
```

### 해결 방법

```python
# /home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/tcp_server.py
# Modify _handle_client method (around line 109-156)

def _handle_client(self, client_socket, client_address):
    """Handle individual client connection"""
    client_id = f"{client_address[0]}:{client_address[1]}"

    # Add to clients dict
    with self.client_lock:
        self.clients[client_id] = client_socket

    # ✅ ADD: Message buffer
    buffer = b''

    try:
        while self.running:
            # Receive data chunk
            try:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break

                # ✅ ADD: Append to buffer
                buffer += chunk

                # ✅ ADD: Process all complete messages in buffer
                while b'\n' in buffer:
                    # Extract one complete message
                    message_data, buffer = buffer.split(b'\n', 1)

                    if not message_data.strip():
                        continue

                    try:
                        # Parse JSON message
                        message = json.loads(message_data.decode('utf-8'))
                        logger.debug(f"Received from {client_id}: {message}")

                        # Handle message
                        response = self._process_message(message)

                        # Send response with newline delimiter
                        if response:
                            response_data = json.dumps(response).encode('utf-8') + b'\n'
                            client_socket.sendall(response_data)

                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON from {client_id}: {e}")
                        error_response = {
                            'status': 'error',
                            'message': 'Invalid JSON format'
                        }
                        client_socket.sendall(json.dumps(error_response).encode('utf-8') + b'\n')

                    except Exception as e:
                        logger.error(f"Error processing message from {client_id}: {e}")

            except socket.timeout:
                continue

    except Exception as e:
        logger.error(f"Error handling client {client_id}: {e}")
    finally:
        # Remove from clients dict
        with self.client_lock:
            if client_id in self.clients:
                del self.clients[client_id]
        client_socket.close()
        logger.info(f"Client {client_id} disconnected")
```

#### Test

```bash
# Test with large message
echo '{"type":"order_request","data":{"table_number":"T01","menu_id":"M001","quantity":1,"sauce_type":"mayo","voice_order":false}}
' | nc localhost 9999

# Test with multiple messages
(echo '{"type":"fleet_status_query","data":{}}'; echo '{"type":"fleet_status_query","data":{}}') | nc localhost 9999
```

---

## Fix #5: Robot 상태 제약조건 추가

### 문제
```python
# database_manager.py, line 143
CheckConstraint("status IN ('IDLE', 'BUSY', 'ERROR', 'HALTED')")
# ❌ NAVIGATING, LOADING, DELIVERING 없음
```

### 해결 방법

#### Step 1: database_manager.py 수정

```python
# /home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/database_manager.py
# Line 143 수정

# Before:
CheckConstraint("status IN ('IDLE', 'BUSY', 'ERROR', 'HALTED')", name='chk_robot_status'),

# After:
CheckConstraint("status IN ('IDLE', 'NAVIGATING', 'LOADING', 'DELIVERING', 'BUSY', 'ERROR', 'HALTED')", name='chk_robot_status'),
```

#### Step 2: Migration 생성

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/database/migrations
```

Create file: `003_add_robot_statuses.sql`

```sql
-- Migration: Add NAVIGATING, LOADING, DELIVERING robot statuses
-- Date: 2026-02-25

BEGIN;

-- Drop existing constraint
ALTER TABLE robots DROP CONSTRAINT IF EXISTS chk_robot_status;

-- Add new constraint
ALTER TABLE robots ADD CONSTRAINT chk_robot_status
  CHECK (status IN (
    'IDLE',        -- Robot is idle, waiting for task
    'NAVIGATING',  -- Robot is moving to destination
    'LOADING',     -- Robot is being loaded with food
    'DELIVERING',  -- Robot is delivering to table
    'BUSY',        -- Robot is busy (generic)
    'ERROR',       -- Robot encountered error
    'HALTED'       -- Robot stopped due to critical error
  ));

COMMIT;
```

#### Step 3: Run Migration

```bash
psql -h localhost -U kitchmatic_user -d kitchmatic -f migrations/003_add_robot_statuses.sql
```

---

## 통합 테스트 스크립트

Create: `/home/gw/kitchmatics/roscamp-repo-1/app/backend/tests/integration_test.sh`

```bash
#!/bin/bash
# Integration test for Main Server with skip mode

set -e

echo "=== Main Server Integration Test ==="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
MAIN_SERVER_HOST="localhost"
MAIN_SERVER_PORT=9999
TEST_TABLE="T01"
TEST_MENU="M001"

echo "1. Checking Main Server connection..."
if nc -z $MAIN_SERVER_HOST $MAIN_SERVER_PORT 2>/dev/null; then
    echo -e "${GREEN}✓ Main Server is running${NC}"
else
    echo -e "${RED}✗ Main Server is not running${NC}"
    echo "Start with: ros2 run main_server main_server --ros-args -p skip_mode:=true"
    exit 1
fi

echo ""
echo "2. Sending order request..."
ORDER_RESPONSE=$(./tcp_test_client.py --host $MAIN_SERVER_HOST --port $MAIN_SERVER_PORT \
    order --table $TEST_TABLE --menu $TEST_MENU --quantity 1 --sauce mayo 2>&1)

ORDER_ID=$(echo "$ORDER_RESPONSE" | grep -oP '"order_id": "\K[^"]+' | head -1)

if [ -z "$ORDER_ID" ]; then
    echo -e "${RED}✗ Failed to get order_id${NC}"
    echo "$ORDER_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Order created: $ORDER_ID${NC}"

echo ""
echo "3. Waiting for order processing (10s)..."
sleep 10

echo ""
echo "4. Querying order status..."
STATUS_RESPONSE=$(./tcp_test_client.py --host $MAIN_SERVER_HOST --port $MAIN_SERVER_PORT \
    status --order-id "$ORDER_ID" 2>&1)

ORDER_STATUS=$(echo "$STATUS_RESPONSE" | grep -oP '"status": "\K[^"]+' | head -1)

echo "Current status: $ORDER_STATUS"

# Expected statuses in skip mode:
# CONFIRMED → AT_POINT13 → COOKING → READY
if [[ "$ORDER_STATUS" == "READY" ]] || [[ "$ORDER_STATUS" == "COOKING" ]] || [[ "$ORDER_STATUS" == "AT_POINT13" ]]; then
    echo -e "${GREEN}✓ Order is progressing${NC}"
else
    echo -e "${YELLOW}⚠ Unexpected status: $ORDER_STATUS${NC}"
fi

echo ""
echo "5. Querying fleet status..."
FLEET_RESPONSE=$(./tcp_test_client.py --host $MAIN_SERVER_HOST --port $MAIN_SERVER_PORT fleet 2>&1)
echo "$FLEET_RESPONSE" | grep -E "robot_id|status|pending_orders|active_orders"

echo ""
echo "6. Sending delivery complete..."
COMPLETE_RESPONSE=$(./tcp_test_client.py --host $MAIN_SERVER_HOST --port $MAIN_SERVER_PORT \
    complete --order-id "$ORDER_ID" --table $TEST_TABLE 2>&1)

if echo "$COMPLETE_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✓ Delivery complete sent${NC}"
else
    echo -e "${RED}✗ Failed to send delivery complete${NC}"
fi

echo ""
echo "7. Verifying final order status..."
sleep 2
FINAL_STATUS=$(./tcp_test_client.py --host $MAIN_SERVER_HOST --port $MAIN_SERVER_PORT \
    status --order-id "$ORDER_ID" 2>&1 | grep -oP '"status": "\K[^"]+' | head -1)

if [[ "$FINAL_STATUS" == "COMPLETED" ]]; then
    echo -e "${GREEN}✓ Order completed successfully${NC}"
else
    echo -e "${YELLOW}⚠ Final status: $FINAL_STATUS (expected: COMPLETED)${NC}"
fi

echo ""
echo -e "${GREEN}=== Integration Test Complete ===${NC}"
echo ""
echo "Summary:"
echo "  Order ID: $ORDER_ID"
echo "  Final Status: $FINAL_STATUS"
echo "  Test Result: $([ "$FINAL_STATUS" == "COMPLETED" ] && echo "PASS" || echo "PARTIAL")"
```

Make executable:
```bash
chmod +x /home/gw/kitchmatics/roscamp-repo-1/app/backend/tests/integration_test.sh
```

---

## 적용 순서

### Phase 1: Database Fixes (30분)
1. ✅ Fix #1: Order 상태 제약조건
2. ✅ Fix #5: Robot 상태 제약조건
3. Run migrations
4. Verify with test data

### Phase 2: Skip Mode Complete (1시간)
1. ✅ Fix #2: LoadingComplete 자동 전송
2. ✅ Fix #3: skip_mode 파라미터 전달
3. Test with integration script

### Phase 3: TCP Stability (30분)
1. ✅ Fix #4: TCP 메시지 구분자
2. Test with multiple/large messages

### Phase 4: Integration Testing (1시간)
1. Run integration_test.sh
2. Monitor all topics
3. Verify database states
4. Document any remaining issues

### Phase 5: Documentation (30분)
1. Update README.md
2. Update IMPLEMENTATION_SUMMARY.md
3. Create testing guide

---

## 검증 체크리스트

- [ ] Database migrations applied successfully
- [ ] Order with AT_POINT13 status saved without error
- [ ] Skip mode: PrecisionParked auto-sent after 2s
- [ ] Skip mode: LoadingComplete auto-triggered after 3s
- [ ] skip_mode parameter passed correctly (ROS parameter)
- [ ] TCP handles multiple messages in single recv()
- [ ] TCP handles large messages (>4096 bytes)
- [ ] Integration test passes end-to-end
- [ ] No ROS 2 node crashes
- [ ] No database constraint violations
- [ ] Logs show correct state transitions

---

**다음 단계**: ROS_DOMAIN_ID 아키텍처 재설계 (FMS 팀과 협의 필요)
