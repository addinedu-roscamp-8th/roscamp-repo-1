# Main Server TCP Test Scripts

This directory contains test scripts for the Kitchmatics Main Server TCP interface.

## TCP Test Client

`tcp_test_client.py` provides a command-line interface for testing Main Server TCP communication.

### Prerequisites

Make sure the Main Server is running:

```bash
# Start Main Server
cd /home/gw/kitchmatics/roscamp-repo-1
ros2 run app main_server_node
```

### Usage Examples

#### 1. Send Order Request

```bash
# Order M001 (햄치즈샌드위치) for table T01
./tcp_test_client.py order --table T01 --menu M001 --quantity 1 --sauce mayo

# Order M002 (비건샌드위치) for table T05 with mustard sauce
./tcp_test_client.py order --table T05 --menu M002 --sauce mustard

# Voice order
./tcp_test_client.py order --table T03 --menu M001 --voice
```

#### 2. Query Order Status

```bash
# Query status of specific order
./tcp_test_client.py status --order-id <ORDER_UUID>
```

#### 3. Query Fleet Status

```bash
# Get current fleet status (all robots)
./tcp_test_client.py fleet
```

#### 4. Send Delivery Complete

```bash
# Mark order as delivered
./tcp_test_client.py complete --order-id <ORDER_UUID> --table T01
```

#### 5. Connect to Remote Server

```bash
# Connect to Main Server on different host
./tcp_test_client.py --host 192.168.1.3 --port 9999 order --table T01
```

### Expected Responses

#### Order Request Response

```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "estimated_time": 120
}
```

#### Order Status Query Response

```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "AT_POINT13",
  "table_number": "T01",
  "menu_id": "M001",
  "quantity": 1,
  "created_at": "2026-02-25T10:30:00",
  "updated_at": "2026-02-25T10:32:15"
}
```

#### Fleet Status Query Response

```json
{
  "robots": [
    {
      "robot_id": "pinky1",
      "status": "NAVIGATING",
      "battery_voltage": 12.4,
      "battery_present": true
    },
    {
      "robot_id": "pinky2",
      "status": "IDLE",
      "battery_voltage": 11.8,
      "battery_present": true
    }
  ],
  "pending_orders": 2,
  "active_orders": 1
}
```

#### Delivery Complete Response

```json
{
  "message": "Order completed successfully"
}
```

### Error Handling

If the server returns an error, you'll see:

```json
{
  "error": "Order not found"
}
```

Common errors:
- Connection refused: Main Server is not running
- Timeout: Network issue or server overload
- Invalid order_id: Order does not exist in database
- Menu not available: Menu item is unavailable

### Integration Testing Flow

Full order flow test:

```bash
# 1. Send order
ORDER_ID=$(./tcp_test_client.py order --table T01 --menu M001 | grep order_id | cut -d'"' -f4)

# 2. Wait for processing (or use skip mode for faster testing)
sleep 10

# 3. Check order status
./tcp_test_client.py status --order-id $ORDER_ID

# 4. Check fleet status
./tcp_test_client.py fleet

# 5. Mark delivery complete
./tcp_test_client.py complete --order-id $ORDER_ID --table T01

# 6. Verify completion
./tcp_test_client.py status --order-id $ORDER_ID
```

### Order Status Values

- `CONFIRMED`: Order received and confirmed
- `AT_POINT13`: Robot arrived at kitchen pickup point
- `LOADING`: Robot arm is cooking/loading food
- `READY`: Food loaded, ready to deliver
- `DELIVERING`: Robot is navigating to table
- `COMPLETED`: Order delivered to customer
- `HALTED`: Error occurred, order stopped

### Notes

- All timestamps are in ISO 8601 format (UTC)
- Order IDs are UUIDs (36 characters)
- Table numbers are T01-T08
- Menu IDs are M001 (햄치즈샌드위치), M002 (비건샌드위치)
- Sauce types: mayo, mustard, ketchup

### Troubleshooting

**Cannot connect to server:**
```bash
# Check if Main Server is running
ps aux | grep main_server_node

# Check if port is open
netstat -tuln | grep 9999
```

**Database connection errors:**
```bash
# Verify database configuration
cat /home/gw/kitchmatics/roscamp-repo-1/app/backend/config/database.env

# Test database connection
psql -h localhost -U kitchmatic_user -d kitchmatic
```

**ROS 2 communication issues:**
```bash
# Check ROS 2 topics
ros2 topic list

# Monitor FMS topics
ros2 topic echo /fms/order_request
ros2 topic echo /fms/pickup_arrival
```

### Skip Mode Testing

For testing without external teams (precision control, robot arm):

```bash
# Start Main Server with skip mode
ros2 run app main_server_node --ros-args -p skip_mode:=true

# Test order flow (precision parking and loading will be mocked)
./tcp_test_client.py order --table T01 --menu M001
```

In skip mode:
- Precision parking is auto-completed after 2 seconds
- Food loading is auto-completed after 3 seconds
- Full flow can be tested without external team dependencies
