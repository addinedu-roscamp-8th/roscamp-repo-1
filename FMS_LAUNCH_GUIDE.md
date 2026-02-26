# Kitchmatics FMS System Launch Guide

## Root Cause Analysis: "A_FAIL:busy" Error

### Error Description
```
[ERROR] [sandwich_coordinator]: A finish failed: A_FAIL:busy
[ERROR] [sandwich_coordinator]: Failed to make sandwich for order ORD-20260226073129-0001
```

### Root Cause
**Location**: `robot_arm/sandwich_arm_ws/src/mycobot_kitchen_nodes/mycobot_kitchen_nodes/recipe_executor_node.py:343`

**Problem**: When Arm A (recipe_executor_node) receives a new START command while still processing a previous job, it immediately rejects with `FAIL:busy`.

**Code snippet**:
```python
def _start_internal(self, job_id: str, recipe_name: str, pause_before_last: int, goal_handle=None) -> bool:
    with self._state_lock:
        if self._run_task is not None and not self._run_task.done():
            self._publish_status(job_id, "FAIL", reason="busy")  # ← ERROR SOURCE
            return False
```

### Why This Happens

**Scenario**: Multiple Orders Arriving Quickly
1. GUI Order 1 → FMS sends CookingOrder to coordinator
2. Coordinator starts processing Order 1 (Arm A begins cooking)
3. GUI Order 2 arrives immediately → FMS sends another CookingOrder
4. Coordinator tries to start Order 2, but Arm A is still busy with Order 1
5. **Result**: `A_FAIL:busy` error

**System Flow**:
```
GUI Order → FMS → /cooking/order → Coordinator → START → Arm A (recipe_executor)
                ↓
          Navigate pinky to pickup_spot
```

### Solution Options

**Option 1: Fix Coordinator Queue Processing (RECOMMENDED)**
Add idle check in coordinator before starting new job:
- Wait for Arm A to complete previous job before starting next
- Check `a_status` for active jobs
- Implement timeout with error handling

**Option 2: Rate Limit Order Arrival**
- Add delay between consecutive orders in GUI
- Quick workaround but not robust

**Option 3: Implement Job Queue in Recipe Executor**
- More complex, requires changes to robot arm code
- Better for production but more work

---

## System Architecture

### Robot Network (Closed WiFi)
| Device | IP | Domain ID | Role |
|--------|-----|-----------|------|
| gw PC | 192.168.1.3 | 25 | FMS Server (Main) |
| pinky1 (b4bc) | 192.168.1.7 | 11 | Mobile Robot |
| pinky2 (e2a8) | 192.168.1.6 | 12 | Mobile Robot |
| pinky3 (d29d) | 192.168.1.11 | 13 | Mobile Robot (disabled) |
| jetcobot A (aa1f) | 192.168.1.4 | 20 | Robot Arm (Sandwich) |
| jetcobot B (aa85) | 192.168.1.10 | 21 | Robot Arm (Sauce) |

### Required Workflow
1. GUI order → FMS sends available pinky to `pickup_spot` AND sends order to armA (parallel)
2. armA cooks food, pinky arrives at pickup_spot
3. FMS notifies armA that pinky is at pickup_spot via `/fms/pickup_arrival`
4. armA performs camera inspection, then places food on pinky (ONLY if pinky is present)
5. armA publishes `/cooking/loading_complete` when food is loaded
6. Pinky delivers to table
7. After delivery confirmation, pinky returns to `pinky_spot`

---

## Main PC Terminal Setup

### Prerequisites
```bash
# Check ROS installation
source /opt/ros/jazzy/setup.bash
ros2 --version  # Should show ROS 2 Jazzy

# Verify network connectivity
ping 192.168.1.7  # pinky1
ping 192.168.1.6  # pinky2
ping 192.168.1.4  # jetcobot A
ping 192.168.1.10 # jetcobot B
```

### Terminal 1: FMS Node
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25

# Launch FMS (production mode - with robot arm)
ros2 launch fms fms_closed_network.launch.py

# OR if testing without robot arm (skip mode)
ros2 launch fms fms_closed_network.launch.py skip_robot_arm:=true
```

**Expected output**:
```
[INFO] [fms_node]: Initializing Fleet Management System...
[INFO] [fms_node]: *** ROBOT ARM MODE ENABLED ***
[INFO] [fms_node]: Registered robot pinky1 on DOMAIN_ID=11
[INFO] [fms_node]: Registered robot pinky2 on DOMAIN_ID=12
[INFO] [fms_node]: FMS running on DOMAIN_ID=25
[INFO] [fms_node]: Created navigation client for pinky1: /pinky1/navigate_to_pose
[INFO] [fms_node]: Created navigation client for pinky2: /pinky2/navigate_to_pose
[INFO] [fms_node]: GUI TCP Server listening on 0.0.0.0:9000
```

### Terminal 2: Domain Bridge
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25

# Launch domain bridge for multi-domain communication
ros2 run domain_bridge domain_bridge fms/config/domain_bridge_complete.yaml
```

**Expected output**:
```
[INFO] [domain_bridge]: Created bridge: 11 -> 25 (pinky1)
[INFO] [domain_bridge]: Created bridge: 12 -> 25 (pinky2)
[INFO] [domain_bridge]: Created bridge: 20 -> 25 (jetcobot A)
[INFO] [domain_bridge]: Created bridge: 21 -> 25 (jetcobot B)
```

### Terminal 3: Customer GUI
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui

# Activate PyQt virtual environment
source ~/pyqt_venv/bin/activate

# Launch Customer GUI
python src/main_fms_direct.py
```

**Expected output**:
```
[INFO] Connecting to FMS at 192.168.1.3:9000
[INFO] Connected to FMS successfully
```

---

## Robot Terminal Setup (User Handles Manually)

You mentioned you'll handle robot terminals manually. Here's the reference:

### Pinky1 (SSH to 192.168.1.7)
```bash
# Terminal 1: Bringup
export ROS_DOMAIN_ID=11
ros2 launch pinky_bringup bringup_robot.launch.xml

# Terminal 2: Navigation
export ROS_DOMAIN_ID=11
ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml
```

### Pinky2 (SSH to 192.168.1.6)
```bash
# Terminal 1: Bringup
export ROS_DOMAIN_ID=12
ros2 launch pinky_bringup bringup_robot.launch.xml

# Terminal 2: Navigation
export ROS_DOMAIN_ID=12
ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml
```

### Jetcobot A (SSH to 192.168.1.4)
```bash
# Terminal 1: Recipe Executor (Arm A)
export ROS_DOMAIN_ID=20
# Launch recipe_executor_node (arm_a)
```

### Jetcobot B (SSH to 192.168.1.10)
```bash
# Terminal 1: Sauce Node (Arm B)
export ROS_DOMAIN_ID=21
# Launch sauce_node (arm_b)

# Terminal 2: Verify Node
export ROS_DOMAIN_ID=21
# Launch verify_node
```

---

## Validation Checklist

### 1. Domain Bridge Health Check
```bash
# In Terminal 2 (domain bridge), check for errors
# Look for these messages:
# - "Created bridge: X -> 25" for each domain
# - NO "Failed to create bridge" errors
```

### 2. Topic Discovery Check
```bash
# New terminal
export ROS_DOMAIN_ID=25
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

# Check FMS can see robot topics (via domain bridge)
ros2 topic list | grep pinky1
# Should show: /pinky1/amcl_pose, /pinky1/odom, /pinky1/scan, etc.

ros2 topic list | grep arm_a
# Should show: /arm_a/cmd, /arm_a/status

ros2 topic list | grep cooking
# Should show: /cooking/order, /cooking/loading_complete
```

### 3. Robot Communication Check
```bash
# Check pinky1 pose (should update continuously)
ros2 topic echo /pinky1/amcl_pose --once

# Check Arm A status
ros2 topic echo /arm_a/status --once
```

### 4. FMS State Check
```bash
# Check fleet status
ros2 topic echo /fms/fleet_status --once

# Check for error alerts
ros2 topic echo /fms/error_alert
```

### 5. GUI Order Test
1. Open Customer GUI (Terminal 3)
2. Select Table 1
3. Add menu item (M001: Ham Cheese Sandwich)
4. Click "주문하기" (Place Order)

**Expected FMS logs**:
```
[INFO] [order_handler]: New order received: ORD-... for table 1
[INFO] [order_handler]: Available robot check result: pinky1
[INFO] [order_handler]: [STEP 1] Cooking command sent to robot arm: /cooking/command
[INFO] [order_handler]: [STEP 2] Robot assigned: pinky1
[INFO] [order_handler]: [STEP 3] Navigation started: pinky1 -> pickup_spot
```

**Expected Coordinator logs** (on jetcobot A):
```
[INFO] [sandwich_coordinator]: Received cooking order: order_id=ORD-..., menu_id=M001, sauce=, robot=pinky1
[INFO] [sandwich_coordinator]: Processing order ORD-... for robot pinky1
[INFO] [sandwich_coordinator]: start job=<job_id> recipe=ham_cheese sauce='' pause_before_last=1
[INFO] [sandwich_coordinator]: subscribers ready: A=1 B=1 V=1
```

**WATCH FOR**:
- If you see `[ERROR] A finish failed: A_FAIL:busy`, the order came too fast
- Wait for previous order to complete before placing next order
- Or implement the coordinator queue fix (Option 1 above)

### 6. Pickup Arrival Notification Test
```bash
# Monitor /fms/pickup_arrival topic
ros2 topic echo /fms/pickup_arrival

# When pinky1 arrives at pickup_spot, you should see:
# robot_id: pinky1
# order_id: ORD-...
# arrived: true
```

**Check coordinator receives it**:
```
[INFO] [sandwich_coordinator]: Pinky arrived at pickup: robot=pinky1, order=ORD-...
[INFO] [sandwich_coordinator]: Waiting for pinky arrival for order ORD-... (timeout=120s)
[INFO] [sandwich_coordinator]: Pinky arrived for order ORD-...
```

### 7. Loading Complete Notification Test
```bash
# Monitor /cooking/loading_complete topic
ros2 topic echo /cooking/loading_complete

# After food is loaded, you should see:
# order_id: ORD-...
# robot_id: pinky1
# success: true
# message: "Food loaded successfully"
```

**Check FMS receives it**:
```
[INFO] [fms_node]: Loading complete for order ORD-..., robot pinky1, success=True
[INFO] [order_handler]: Food loaded for order ORD-...
[INFO] [order_handler]: [SKIP MODE] Waiting 3 seconds before proceeding to table...
[INFO] [order_handler]: [STEP 5] Navigation started: pinky1 -> table1
```

---

## Troubleshooting

### Issue 1: "A_FAIL:busy" Error
**Symptom**: Coordinator logs show `[ERROR] A finish failed: A_FAIL:busy`

**Cause**: Previous order still processing when new order arrived

**Solution**:
1. **Quick fix**: Wait for previous order to complete before placing next order
2. **Proper fix**: Implement coordinator queue with idle check (see Option 1 above)
3. **Verify**: Check Arm A status before sending new order

### Issue 2: Domain Bridge Not Working
**Symptom**: FMS can't see robot topics (`ros2 topic list | grep pinky1` returns nothing)

**Cause**: Domain bridge not running or misconfigured

**Solution**:
1. Check Terminal 2 (domain bridge) for errors
2. Verify `ROS_DOMAIN_ID=25` is set for domain bridge
3. Restart domain bridge: `Ctrl+C` and relaunch
4. Check domain bridge config: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml`

### Issue 3: Pinky Not Moving
**Symptom**: Navigation command sent but robot doesn't move

**Cause**: Multiple possible causes
1. AMCL not localized (initial pose not set)
2. Nav2 not running on robot
3. Domain bridge not forwarding action messages

**Solution**:
```bash
# Check robot's AMCL pose
ros2 topic echo /pinky1/amcl_pose --once

# If no output, initial pose not set
# FMS should auto-set initial pose on startup

# Check Nav2 status on robot (SSH to robot)
ros2 node list | grep bt_navigator

# Check action server availability
ros2 action list | grep navigate_to_pose
```

### Issue 4: No Pickup Arrival Notification
**Symptom**: Coordinator never receives pinky arrival, times out after 120s

**Cause**: FMS not publishing PickupArrival message

**Solution**:
1. Check FMS logs for "Published PickupArrival"
2. Verify `/fms/pickup_arrival` topic exists: `ros2 topic list | grep pickup_arrival`
3. Monitor topic: `ros2 topic echo /fms/pickup_arrival`
4. Check domain bridge config for `/fms/pickup_arrival` bridging to domain 20

**Domain bridge check**:
```yaml
# In domain_bridge_complete.yaml, this should exist:
- from_domain: 25
  to_domain: 20
  topics:
    /fms/pickup_arrival:
      type: fleet_interfaces/msg/PickupArrival
```

**NOTE**: Currently this is NOT in the domain bridge config! This might be the issue.

### Issue 5: GUI Connection Failed
**Symptom**: GUI shows "Connection failed" or timeout

**Cause**: FMS TCP server not running or firewall blocking

**Solution**:
```bash
# Check FMS is listening on port 9000
netstat -tlnp | grep 9000

# Test connection from another terminal
telnet 192.168.1.3 9000

# Check firewall
sudo ufw status
sudo ufw allow 9000/tcp  # If blocked
```

---

## Critical Finding: Missing Domain Bridge Configuration

**IMPORTANT**: The `/fms/pickup_arrival` topic is NOT bridged to domain 20 (jetcobot A)!

**Current domain_bridge_complete.yaml** only bridges:
- Domain 20 → 25: `/arm_a/status`
- Domain 25 → 20: `/arm_a/cmd`

**Missing**:
- Domain 25 → 20: `/fms/pickup_arrival`
- Domain 25 → 21: `/fms/pickup_arrival`

**This needs to be added** for coordinator to receive pinky arrival notifications!

**Fix**: Add to `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml`:

```yaml
# Domain 25 -> Domain 20: FMS notifications to Arm A coordinator
- from_domain: 25
  to_domain: 20
  topics:
    /fms/pickup_arrival:
      type: fleet_interfaces/msg/PickupArrival
      qos:
        reliability: "RELIABLE"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 10

# Domain 25 -> Domain 21: FMS notifications to Arm B coordinator
- from_domain: 25
  to_domain: 21
  topics:
    /fms/pickup_arrival:
      type: fleet_interfaces/msg/PickupArrival
      qos:
        reliability: "RELIABLE"
        durability: "VOLATILE"
        history: "KEEP_LAST"
        depth: 10
```

---

## Next Steps

1. **Fix domain bridge config** for `/fms/pickup_arrival`
2. **Test single order flow** end-to-end
3. **Test multi-robot coordination** (pinky1 + pinky2)
4. **Implement coordinator queue fix** if needed
5. **Monitor logs** for any other issues

---

## Build Status

✅ FMS workspace built successfully
✅ Coordinator workspace built successfully
✅ Domain bridge config reviewed (needs `/fms/pickup_arrival` fix)

**Build output**:
```
fleet_interfaces: [0.47s] ✓
fms: [1.15s] ✓
sandwich_coordinator: [1.16s] ✓
```
