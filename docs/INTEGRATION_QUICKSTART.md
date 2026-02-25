# Kitchmatics FMS - Integration Quick Start

**For:** Precision Control Team, Robot Arm Team, QA Team
**Updated:** 2026-02-25

---

## Quick Links

- **External Interfaces Specification:** [external_interfaces.md](./external_interfaces.md)
  - Complete message format definitions
  - Topic subscriptions and publications
  - Network configuration and ROS Domain IDs
  - Error handling procedures

- **Skip Mode Testing Guide:** [skip_mode_guide.md](./skip_mode_guide.md)
  - How to test without external teams
  - Mock message timing and behavior
  - Testing procedures and troubleshooting
  - CI/CD integration examples

---

## The Delivery Flow (60 Second Overview)

```
Customer Orders Sandwich
    ↓
FMS Receives Order
    ↓
FMS Navigates Robot to point13
    ↓
[Point13 Arrival] → FMS Publishes: goal_arrived
    ↓
PRECISION CONTROL TEAM TAKES OVER
    • Receives: goal_arrived message
    • Task: Move robot from point13 to pickup_spot
    • Publishes: precision_parked message
    ↓
[Precision Parking Complete] → FMS Receives: precision_parked
    ↓
ROBOT ARM TEAM TAKES OVER
    • Receives: precision_parked message (robot is at pickup_spot)
    • Task: Load food onto robot
    • Publishes: food_loaded message
    ↓
[Food Loading Complete] → FMS Receives: food_loaded
    ↓
FMS Navigates Robot to Customer's Table
    ↓
[Table Arrival] → Customer Receives Food
    ↓
Customer Clicks "Delivery Complete" on Kiosk
    ↓
FMS Navigates Robot back to Parking
    ↓
[Parking Arrival] → Task Complete!
```

---

## For: Precision Control Team

### Your Responsibility

**When:** Robot reaches point13
**Input:** FMS publishes `/fms/goal_arrived` message
**Your Job:** Move robot from point13 → pickup_spot with fine precision
**Output:** Publish `/fms/precision_parked` message
**Timing:** Complete within 10 seconds

### Key Messages

```
SUBSCRIBE TO:     /fms/goal_arrived
                  → Signals: Robot at point13, ready for parking

PUBLISH TO:       /fms/precision_parked
                  → Signals: Parking complete, robot at pickup_spot

MONITOR:          /fms/fleet_status (optional, for status visibility)
```

### Typical Test Setup

**With FMS Skip Mode (development):**
```bash
# Terminal 1: FMS with skip precision disabled
ros2 run fms fms_node --ros-args \
    -p skip_precision:=false \
    -p skip_robot_arm:=true

# Terminal 2: Send test order
python3 fms/scripts/send_order.py --table 1

# Terminal 3: Monitor point13 arrival
ros2 topic echo /fms/goal_arrived

# When you see the message, test precision parking algorithm
# Then publish confirmation
ros2 topic pub -1 /fms/precision_parked std_msgs/String "data: 'precision_parked:pinky1'"
```

**Expected Robot Positions:**

| Location | X (meters) | Y (meters) | Theta (radians) | Purpose |
|----------|-----------|-----------|-----------------|---------|
| point13 | 0.585 | 0.63 | 0.0 | FMS arrives here |
| pickup_spot | 0.47 | 0.63 | 3.14159 (π) | You park here |

The robot needs to **rotate 180 degrees** and move **0.115 meters left** to complete parking.

### Critical Constraints

- Must complete within 10 seconds
- Robot must face kitchen (θ ≈ π radians)
- Precision: < 0.05m position error, < 0.05rad angle error
- No collision with kitchen equipment

### Robot Information

- **Robot Type:** PinkyPro (0.11m diameter, ~25cm height)
- **Max Speed:** ~0.5 m/s
- **Localization:** AMCL (±0.2m typical error)
- **Sensors:** Lidar, IMU, encoders

---

## For: Robot Arm Team

### Your Responsibility

**When:** Robot at pickup_spot (after precision parking)
**Input:** FMS/Precision Control publishes `/fms/precision_parked` message
**Your Job:** Load food onto robot
**Output:** Publish `/fms/food_loaded` message
**Timing:** Complete within 60 seconds

### Key Messages

```
SUBSCRIBE TO:     /fms/precision_parked
                  → Signals: Robot at pickup_spot, ready for loading

PUBLISH TO:       /fms/food_loaded
                  → Signals: Food loaded successfully

MONITOR:          /pinky{1,2,3}/pose (optional, to verify robot position)
                  IMPORTANT: Use robot's domain ID to access this
```

### Typical Test Setup

**With FMS Skip Mode (development):**
```bash
# Terminal 1: FMS with skip robot_arm disabled
ros2 run fms fms_node --ros-args \
    -p skip_precision:=true \
    -p skip_robot_arm:=false

# Terminal 2: Send test order
python3 fms/scripts/send_order.py --table 1

# Terminal 3: Monitor precision_parked arrival
ros2 topic echo /fms/precision_parked

# When you see the message, test loading sequence
# Then publish confirmation
ros2 topic pub -1 /fms/food_loaded std_msgs/String "data: 'food_loaded:pinky1'"
```

**Robot Information at Pickup Spot:**

- **Position:** X=0.47m, Y=0.63m (robot center)
- **Orientation:** Facing kitchen (θ ≈ 180°)
- **Tray Height:** Approx 0.3m from ground (typical for PinkyPro)
- **Clearances:** 0.2m safety margin around robot

### Critical Constraints

- Must start within 60 seconds of receiving precision_parked
- Robot remains stationary during loading
- Don't push robot (arm must load cleanly)
- Max load weight: 3 kg
- Verify no obstacles above robot before loading

### Expected Timing

```
precision_parked received
    ↓
Arm approaches robot (2-3 seconds)
    ↓
Arm scans for food tray (1 second)
    ↓
Arm loads food (2-3 seconds)
    ↓
Arm retracts to safe position (1-2 seconds)
    ↓
Publish food_loaded

Total typical time: 8-12 seconds (well within 60s limit)
```

---

## For: QA / Testing Team

### Standard Test Procedure (Complete Flow)

**Setup:** 2 terminals

```bash
# Terminal 1: Start FMS in full skip mode
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run fms fms_node --ros-args \
    -p skip_robot_arm:=true \
    -p skip_precision:=true \
    -p skip_mode_timing:="realistic"

# Terminal 2: Send order and track status
cd /home/gw/kitchmatics/roscamp-repo-1

# In separate sub-terminals:
# 2a: Send order
python3 fms/scripts/send_order.py --table 1

# 2b: Monitor progress (in another terminal)
ros2 topic echo /fms/fleet_status

# 2c: When robot reaches table, publish delivery_complete
ros2 topic pub -1 /fms/delivery_complete fleet_interfaces/DeliveryComplete \
    "order_id: 'order_001' table_number: 'T01'"
```

**Expected Timeline:** ~6 minutes total

| Phase | Expected Duration | Action |
|-------|------------------|--------|
| Navigation to point13 | ~60 seconds | FMS handles |
| Precision parking (mock) | 2 seconds | Automatic |
| Food loading (mock) | 3 seconds | Automatic |
| Navigation to table | ~60 seconds | FMS handles |
| At table (waiting for customer) | Manual | Trigger manually |
| Navigation to parking | ~60 seconds | FMS handles |

### Partial Integration Tests

**Test Precision Control Only:**
```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=false \
    -p skip_robot_arm:=true

# When robot reaches point13:
ros2 topic pub -1 /fms/precision_parked std_msgs/String "data: 'precision_parked:pinky1'"
```

**Test Robot Arm Only:**
```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=true \
    -p skip_robot_arm:=false

# When robot is at pickup_spot:
ros2 topic pub -1 /fms/food_loaded std_msgs/String "data: 'food_loaded:pinky1'"
```

---

## ROS Domain ID Setup

**Critical:** All processes must set ROS_DOMAIN_ID correctly.

### Setting Domain IDs

```bash
# Master PC (FMS) - Domain 0
export ROS_DOMAIN_ID=0
ros2 run fms fms_node ...

# Mobile Robot 1 (pinky1) - Domain 11
export ROS_DOMAIN_ID=11
ros2 launch ... # on robot

# Mobile Robot 2 (pinky2) - Domain 12
export ROS_DOMAIN_ID=12
ros2 launch ... # on robot

# Cobot Arm 1 - Domain 14
export ROS_DOMAIN_ID=14
ros2 launch ... # on arm

# Cobot Arm 2 - Domain 15
export ROS_DOMAIN_ID=15
ros2 launch ... # on arm
```

### Monitoring Across Domains

To monitor a robot's `/pose` topic from the master PC:

```bash
# Terminal 1: FMS runs in domain 0
export ROS_DOMAIN_ID=0
ros2 run fms fms_node ...

# Terminal 2: Switch domain to robot to check its pose
export ROS_DOMAIN_ID=11  # pinky1 domain
ros2 topic echo /pinky1/pose

# Terminal 3: Create bridge to monitor across domains
export ROS_DOMAIN_ID=0   # Use FMS domain for communication
```

---

## Message Format Examples

### Message 1: goal_arrived (FMS → Precision Control)

```bash
# Publisher: FMS
# Topic: /fms/goal_arrived
# Type: std_msgs/String

# Example:
ros2 topic echo /fms/goal_arrived

# Output:
data: 'pinky1_arrived_at_point13'
```

### Message 2: precision_parked (Precision Control → FMS)

```bash
# Subscriber: FMS
# Topic: /fms/precision_parked
# Type: std_msgs/String

# Publish example:
ros2 topic pub -1 /fms/precision_parked std_msgs/String "data: 'precision_parked:pinky1'"
```

### Message 3: food_loaded (Robot Arm → FMS)

```bash
# Subscriber: FMS
# Topic: /fms/food_loaded
# Type: std_msgs/String

# Publish example:
ros2 topic pub -1 /fms/food_loaded std_msgs/String "data: 'food_loaded:pinky1'"
```

### Message 4: delivery_complete (Main Server/GUI → FMS)

```bash
# Subscriber: FMS
# Topic: /fms/delivery_complete
# Type: fleet_interfaces/DeliveryComplete

# Publish example:
ros2 topic pub -1 /fms/delivery_complete fleet_interfaces/DeliveryComplete \
    "order_id: 'order_123' table_number: 'T01' received_at: 'now'"
```

---

## Troubleshooting Quick Reference

### Issue: FMS doesn't receive goal_arrived

**Check:**
1. Is FMS running? `ros2 node list | grep fms`
2. Is robot actually navigating? `ros2 topic echo /fms/fleet_status`
3. Did robot reach point13? Monitor `/pinky1/pose` on robot's domain

---

### Issue: FMS doesn't receive precision_parked

**Check:**
1. Is message being published? `ros2 topic echo /fms/precision_parked`
2. Is topic name exactly `/fms/precision_parked`?
3. Is message format correct? `data: 'precision_parked:pinky1'`

---

### Issue: Robot never leaves point13

**Check:**
1. Did you publish `precision_parked` message?
2. Is skip_precision set correctly?
3. Check FMS logs: `--log-level fms_node:=DEBUG`

---

### Issue: Domain ID mismatch errors

**Check:**
1. All processes have ROS_DOMAIN_ID set: `echo $ROS_DOMAIN_ID`
2. FMS runs in domain 0
3. Robots run in domains 11, 12, 13
4. Arms run in domains 14, 15

---

## Network Checklist

Before running integrated tests:

- [ ] All devices connected to WiFi "kitchmatics"
- [ ] Master PC at 192.168.1.3
- [ ] Robots can ping master PC
- [ ] Master PC can ping robots
- [ ] ROS_DOMAIN_ID environment variables set
- [ ] No firewall blocking ROS 2 ports (7400-7410)
- [ ] All ROS 2 installations same version (Jazzy)

**Quick network test:**
```bash
# From master PC
ping 192.168.1.7  # pinky1
ping 192.168.1.6  # pinky2
ping 192.168.1.4  # robot_arm_1

# All should respond with no packet loss
```

---

## Key Takeaways

### For Precision Control Team

1. Listen for `/fms/goal_arrived` message
2. Execute precision parking algorithm
3. Publish `/fms/precision_parked` when done
4. Must complete within 10 seconds
5. Test without FMS by setting `skip_precision:=false`

### For Robot Arm Team

1. Listen for `/fms/precision_parked` message
2. Execute food loading sequence
3. Publish `/fms/food_loaded` when done
4. Must complete within 60 seconds
5. Test without FMS by setting `skip_robot_arm:=false`

### For Everyone

1. Use ROS_DOMAIN_ID (not namespaces)
2. Test messages with `ros2 topic pub/echo`
3. Run FMS in skip mode during development
4. Verify timing constraints
5. Check logs on failure: `--log-level :=DEBUG`

---

## Next Steps

1. **Read full specifications:**
   - [External Interfaces Specification](./external_interfaces.md) - Complete message and interface definitions
   - [Skip Mode Testing Guide](./skip_mode_guide.md) - Detailed testing procedures

2. **Plan your integration:**
   - Which skip flags do you need?
   - What messages will you publish/subscribe?
   - When can you test?

3. **Schedule coordination:**
   - Book testing time in shared calendar
   - Notify other teams 24 hours before
   - Prepare test hardware/simulation

4. **Validate before going live:**
   - Test with skip mode first
   - Test with partial integration (one team at a time)
   - Test with all teams
   - Document any issues found

---

## Support Resources

- **Slack:** #fms-channel for questions
- **Jira:** File issues with "integration" or "interface" labels
- **Code Location:** `/home/gw/kitchmatics/roscamp-repo-1/docs/`
- **FMS Configuration:** `/home/gw/kitchmatics/roscamp-repo-1/fms/config/`

---

**Created:** 2026-02-25
**Version:** 1.0
**Status:** Ready for use
