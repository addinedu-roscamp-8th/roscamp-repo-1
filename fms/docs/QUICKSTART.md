# FMS GUI Order Integration - Quick Start Guide

## Prerequisites

- ROS2 Humble
- Python 3.10+
- fleet_interfaces package built
- Network: kitchmatics WiFi (192.168.1.x)

## 1. Build FMS Package

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms

# Build
colcon build --packages-select fms

# Source
source install/setup.bash
```

## 2. Start FMS Node

### Terminal 1: FMS Node

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms
source install/setup.bash

# Set ROS_DOMAIN_ID to match pinky1
export ROS_DOMAIN_ID=11

# Run FMS
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
```

**Expected Output**:
```
[INFO] Initializing Fleet Management System...
[INFO] GUI TCP server started on port 9000
[INFO] Order handler callbacks registered
[INFO] FMS Node is running...
```

## 3. Test GUI Order Integration

### Terminal 2: Test Script

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms/scripts

# Test new order
python3 test_gui_order.py new_order
```

**Expected Output**:
```
============================================================
Testing New Order Workflow
============================================================
Connected to FMS at 192.168.1.3:9000

Sending order: {
  "command": "new_order",
  "table_number": 1,
  "order": {
    "items": [
      {"menu_id": "M001", "quantity": 1}
    ]
  }
}

Received response: {
  "status": "success",
  "data": {
    "order_id": "ORD-20260225123456-0001",
    "message": "Order ORD-20260225123456-0001 accepted"
  }
}

Order accepted! Order ID: ORD-20260225123456-0001

Waiting for delivery notification...
(Robot will navigate to point13 -> load food -> navigate to table1)

Received notification: {
  "type": "delivery_notification",
  "data": {
    "order_id": "ORD-20260225123456-0001",
    "table_number": 1,
    "robot_id": "pinky1",
    "status": "arrived"
  }
}

Robot arrived at table1!
Customer can now confirm delivery...

Sending delivery confirmation: {
  "command": "delivery_complete",
  "order_id": "ORD-20260225123456-0001",
  "table_number": 1
}

Confirmation response: {
  "status": "success",
  "data": {
    "message": "Delivery confirmed, robot returning home"
  }
}

Order workflow completed!
Connection closed
```

## 4. Monitor Robot Navigation

### Terminal 3: Monitor pinky1 pose

```bash
export ROS_DOMAIN_ID=11
ros2 topic echo /pose
```

### Terminal 4: Monitor navigation status

```bash
export ROS_DOMAIN_ID=11
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{pose: {header: {frame_id: 'map'}, pose: {position: {x: 0.585, y: 0.63, z: 0.0}}}}"
```

## 5. Monitor Cooking Orders

### Terminal 5: Monitor robot arm commands

```bash
export ROS_DOMAIN_ID=25  # FMS domain
ros2 topic echo /cooking/order
```

**Expected Output**:
```
order_id: 'ORD-20260225123456-0001'
menu_id: 'M001'
quantity: 1
sauce_type: ''
assigned_robot_id: 'pinky1'
```

## 6. Full System Integration Test

### Start All Components

1. **Start pinky1**:
   ```bash
   # On pinky1 robot (DOMAIN_ID=11)
   ros2 launch pinky_navigation pinky_navigation.launch.py
   ```

2. **Start FMS**:
   ```bash
   # On master PC (DOMAIN_ID=25, but monitoring DOMAIN_ID=11)
   export ROS_DOMAIN_ID=11
   ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
   ```

3. **Start Robot Arm Coordinator** (if available):
   ```bash
   export ROS_DOMAIN_ID=25
   ros2 run robot_arm arm_coordinator_node
   ```

4. **Send Test Order**:
   ```bash
   python3 test_gui_order.py new_order
   ```

## 7. Troubleshooting

### Problem: Connection Refused

```
ERROR: Could not connect to FMS at 192.168.1.3:9000
```

**Solution**:
- Check FMS is running: `ps aux | grep fms_node`
- Check port is open: `netstat -tulpn | grep 9000`
- Check IP address: `ip addr show`

### Problem: No delivery notification received

**Solution**:
- Check pinky1 is navigating: `ros2 topic echo /pose`
- Check order status: Look at FMS logs
- Verify map positions in `fms_config.yaml`

### Problem: Robot arm not receiving cooking order

**Solution**:
- Check ROS_DOMAIN_ID=25 for FMS
- Monitor topic: `ros2 topic echo /cooking/order`
- Verify robot arm coordinator is running

## 8. Configuration

### Change TCP Port

Edit `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py`:

```python
self.gui_tcp_server = GUITCPServer(host='0.0.0.0', port=9000)  # Change port here
```

### Change Robot Selection

Edit `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py`:

```python
# In _execute_order_workflow()
robot_id = "pinky1"  # Change to pinky2 or pinky3
```

### Change Map Positions

Edit `/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml`:

```yaml
positions:
  point13:
    x: 0.585
    y: 0.63
    theta: 0.0
  table1:
    x: 1.785
    y: 0.35
    theta: 0.0
```

## 9. API Reference

### TCP Message Format

All messages use 4-byte length header + JSON payload.

#### Request: new_order
```json
{
    "command": "new_order",
    "table_number": 1,
    "order": {
        "items": [
            {"menu_id": "M001", "quantity": 1}
        ]
    }
}
```

#### Response: new_order
```json
{
    "status": "success",
    "data": {
        "order_id": "ORD-20260225123456-0001",
        "message": "Order accepted"
    }
}
```

#### Push Notification: delivery_notification
```json
{
    "type": "delivery_notification",
    "data": {
        "order_id": "ORD-20260225123456-0001",
        "table_number": 1,
        "robot_id": "pinky1",
        "status": "arrived"
    }
}
```

#### Request: delivery_complete
```json
{
    "command": "delivery_complete",
    "order_id": "ORD-20260225123456-0001",
    "table_number": 1
}
```

#### Response: delivery_complete
```json
{
    "status": "success",
    "data": {
        "message": "Delivery confirmed, robot returning home"
    }
}
```

## 10. Development

### Run Unit Tests

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms
pytest tests/
```

### Enable Debug Logging

```python
# In fms_node.py
logging.basicConfig(level=logging.DEBUG)
```

### Add Custom Order Handler

```python
# In fms_node.py
def _handle_custom_command(self, message: Dict[str, Any]) -> Dict[str, Any]:
    # Your custom logic
    return {'success': True, 'data': {}}

# Register handler
self.gui_tcp_server.register_handler('custom_command', self._handle_custom_command)
```

## 11. Next Steps

1. **Integrate with Customer GUI**:
   - Update GUI TCP client to use 4-byte length header protocol
   - Implement delivery notification listener
   - Add order status tracking UI

2. **Add Robot Arm Integration**:
   - Implement robot arm coordinator node
   - Subscribe to `/cooking/order`
   - Publish `/cooking/loading_complete`

3. **Add Multiple Robot Support**:
   - Implement robot selection algorithm
   - Handle concurrent orders
   - Add robot availability checking

4. **Add Persistence**:
   - Save order history to database
   - Implement order recovery on restart
   - Add order query API

## Support

For issues or questions, check:
- FMS logs: `~/.ros/log/`
- Documentation: `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/`
- Test scripts: `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/`
