# FMS Quick Reference Guide

**Last Updated**: 2026-02-26 17:31 KST
**Status**: ✅ OPERATIONAL

---

## Quick Start

### Start FMS
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25
ros2 launch fms fms_closed_network.launch.py
```

### Stop FMS
```bash
pkill -f "fms_node|fms_tcp_node"
```

---

## System Status

### Check FMS Running
```bash
pgrep -f "fms_node|fms_tcp_node" && echo "Running" || echo "Not running"
```

### Check TCP Server
```bash
netstat -tlnp | grep 9000
# Output should show: tcp 0 0 0.0.0.0:9000 0.0.0.0:* LISTEN
```

### Check ROS Topics
```bash
export ROS_DOMAIN_ID=25
source install/setup.bash
ros2 topic list | grep /fms/
```

---

## TCP Protocol Reference

### Message Format
```json
{
  "type": "message_type",
  "data": { ... },
  "sender_id": "client_id",
  "sequence": 1,
  "timestamp": 1234567890.123
}
```

**Important**: Each message MUST end with newline character (`\n`)

### Example: Robot Connect
```json
{"type": "connect", "data": {"robot_id": "pinky1", "robot_type": "mobile", "ip_address": "192.168.1.7"}, "sender_id": "pinky1", "sequence": 1}
```

### Example: Heartbeat
```json
{"type": "heartbeat", "data": {"robot_id": "pinky1", "battery": 85, "status": "idle"}, "sender_id": "pinky1", "sequence": 2}
```

### Example: Pose Update
```json
{"type": "pose_update", "data": {"robot_id": "pinky1", "x": 1.5, "y": 2.0, "theta": 0.5}, "sender_id": "pinky1", "sequence": 3}
```

### Available Message Types
- `connect` - Robot connection
- `disconnect` - Robot disconnection
- `heartbeat` - Keep-alive
- `robot_status` - Status update
- `pose_update` - Position update
- `nav_status` - Navigation status
- `task_complete` - Task completion
- `error` - Error report
- `ack` - Acknowledgment (server response)

---

## ROS 2 Topics

### Publish (FMS → Others)
```
/fms/fleet_status          - Fleet status
/fms/order_request         - Order distribution
/fms/pickup_arrival        - Pickup arrival notification
/fms/error_alert           - Error alerts
/fms/delivery_complete     - Delivery status
/fms/table_arrival         - Table arrival
/fms/precision_parked      - Parking status
/fms/operator_command      - Operator commands
```

### Subscribe (FMS ← Others)
```
/pinky1/amcl_pose          - Robot 1 position
/pinky2/amcl_pose          - Robot 2 position
/pinky1/battery/voltage    - Robot 1 battery
/pinky2/battery/voltage    - Robot 2 battery
/cooking/loading_complete  - Food loading complete
/cooking/status            - Cooking status
```

---

## Robot Configuration

### Active Robots
| Robot | Domain | IP | Status |
|-------|--------|----|----|
| pinky1 | 11 | 192.168.1.7 | ✅ ACTIVE |
| pinky2 | 12 | 192.168.1.6 | ✅ ACTIVE |
| pinky3 | 13 | 192.168.1.11 | ⊘ DISABLED |

### Robot Parking Positions
```
pinky1_spot: x=0.585, y=0.085, theta=0.0
pinky2_spot: x=0.585, y=0.255, theta=0.0
pinky3_spot: x=0.585, y=0.915, theta=0.0
```

### Dining Tables
```
table1: x=1.785, y=0.35, theta=0.0
table2: x=1.415, y=0.35, theta=0.0
table3: x=1.785, y=0.65, theta=0.0
table4: x=1.415, y=0.65, theta=0.0
table5: x=1.235, y=0.35, theta=0.0
table6: x=0.865, y=0.35, theta=0.0
table7: x=1.235, y=0.65, theta=0.0
table8: x=0.865, y=0.65, theta=0.0
```

### Pickup Location
```
pickup_spot: x=0.47, y=0.63, theta=3.14159
```

---

## Common Issues & Solutions

### FMS Node Won't Start
```bash
# Check if port 9000 is in use
lsof -i :9000

# Kill process using port
pkill -f "fms_node"
lsof -i :9000 | awk 'NR!=1 {print $2}' | xargs kill -9

# Try launching again
ros2 launch fms fms_closed_network.launch.py
```

### ROS Topics Not Visible
```bash
# Set correct domain ID
export ROS_DOMAIN_ID=25

# Source setup
source install/setup.bash

# Check topics
ros2 topic list
```

### TCP Connection Refused
```bash
# Check FMS is running
ps aux | grep fms_node

# Check port is listening
netstat -tlnp | grep 9000

# Check firewall (if needed)
sudo ufw allow 9000
```

### Robot Not Responding
```bash
# Check robot is connected via TCP
# Monitor FMS logs
tail -f /tmp/fms_validation/fms_launch.log

# Send heartbeat from robot
# Check battery level and status
ros2 topic echo /pinky1/battery/voltage
```

---

## Performance Monitoring

### Check CPU & Memory
```bash
# Monitor FMS process
top -p $(pgrep -f fms_node)
```

### Check Message Queue
```bash
# Monitor topic publishing frequency
ros2 topic hz /fms/fleet_status
```

### Check Network
```bash
# Monitor TCP connections
watch -n 1 "netstat -tlnp | grep 9000"
```

---

## File Locations

| Component | Path |
|-----------|------|
| FMS Config | `/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml` |
| Launch File | `/home/gw/kitchmatics/roscamp-repo-1/fms/launch/fms_closed_network.launch.py` |
| FMS Node | `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py` |
| TCP Node | `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_tcp_node.py` |
| TCP Communication | `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/tcp_communication.py` |
| Logs | `/tmp/fms_validation/fms_launch.log` |
| Validation Report | `/home/gw/kitchmatics/roscamp-repo-1/FMS_FINAL_VALIDATION_REPORT.md` |

---

## Development Environment

```
ROS 2: Jazzy
Python: 3.12
Domain: 25 (FMS Master)
Coordinator Domain: 11, 12
Network: Closed WiFi (kitchmatics)
Master IP: 192.168.1.3
TCP Port: 9000
```

---

## Testing Commands

### Run TCP Protocol Test
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
python3 test_tcp_protocol.py
```

### Run Validation
```bash
bash fms_validation.sh
```

### Monitor All Topics
```bash
bash /tmp/fms_validation/monitor_topics.sh
```

---

## Emergency Procedures

### Emergency Stop All Robots
```bash
# Publish emergency stop via ROS
ros2 topic pub /fms/operator_command fleet_interfaces/OperatorCommand "{command: 'emergency_stop'}"

# Or kill FMS
pkill -f fms_node
```

### Reset FMS State
```bash
# Stop FMS
pkill -f "fms_node|fms_tcp_node"

# Wait 2 seconds
sleep 2

# Start FMS
cd /home/gw/kitchmatics/roscamp-repo-1
ros2 launch fms fms_closed_network.launch.py
```

---

## Contact & Support

For issues or questions:
1. Check FMS logs: `tail -f /tmp/fms_validation/fms_launch.log`
2. Review validation report: `/home/gw/kitchmatics/roscamp-repo-1/FMS_FINAL_VALIDATION_REPORT.md`
3. Check ROS topics: `ros2 topic list`
4. Run TCP test: `python3 test_tcp_protocol.py`

---

**Last Validated**: 2026-02-26 17:31 KST ✅
