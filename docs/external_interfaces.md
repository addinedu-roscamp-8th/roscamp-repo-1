# Kitchmatics FMS - External Team Interface Specification

**Document Version:** 1.0
**Last Updated:** 2026-02-25
**Audience:** Precision Control Team, Robot Arm Team, FMS Integration Team

---

## Overview

This document defines the interface contracts between the FMS (Fleet Management System) and external teams:
- **Precision Control Team**: Handles precision parking (point13 → pickup_spot)
- **Robot Arm Team**: Handles food loading at the pickup spot

The FMS is responsible for high-level robot navigation and task orchestration. External teams handle specialized operations at specific waypoints.

---

## Architecture Overview

```
                          ┌─────────────────────────────────────────┐
                          │         WiFi: kitchmatics               │
                          └─────────────────────────────────────────┘
                                            │
        ┌───────────────────────────────────┼───────────────────────────────────┐
        │                                   │                                   │
        ▼                                   ▼                                   ▼
┌───────────────┐                  ┌───────────────┐                   ┌───────────────┐
│  Mobile Robot │                  │   Master PC   │                   │  Cobot Arm    │
│  (PinkyPro)   │◄────ROS Topics──►│  192.168.1.3  │◄────ROS Topics───►│  (JetCobot)   │
│  192.168.1.7  │  Domain: 11      │ ROS Domain:0  │  Domain: 14/15    │  192.168.1.4  │
│  192.168.1.6  │  Domain: 12      │   FMS Node    │                   │ 192.168.0.59  │
└───────────────┘  Domain: 13      └───────┬───────┘                   └───────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
        ┌──────────────────┐      ┌──────────────────┐    ┌──────────────────┐
        │ Precision Control│      │   Main Server    │    │  Kiosks/GUI      │
        │     Team         │      │   PostgreSQL     │    │  (8 tables)      │
        └──────────────────┘      └──────────────────┘    └──────────────────┘
```

---

## Network Configuration

### ROS Domain IDs

Each robot operates on a separate ROS domain ID to isolate communication:

| Device | ROS_DOMAIN_ID | IP Address | Role |
|--------|---------------|------------|------|
| FMS Server (Master PC) | 0 | 192.168.1.3 | Central coordinator |
| pinky1 (Mobile Robot) | 11 | 192.168.1.7 | Primary serving robot |
| pinky2 (Mobile Robot) | 12 | 192.168.1.6 | Secondary serving robot |
| pinky3 (Mobile Robot) | 13 | TBD | Tertiary serving robot |
| robot_arm_1 (Cobot) | 14 | 192.168.1.4 | Primary food loader |
| robot_arm_2 (Cobot) | 15 | 192.168.0.59 | Secondary food loader |

### WiFi Network

- **SSID:** kitchmatics
- **Type:** Closed network (no internet required)
- **Connection Requirements:** All devices on same WiFi
- **Firewall:** Allow ROS 2 multicast (UDP 7400-7410)

### Port Usage

| Port | Service | Device | Purpose |
|------|---------|--------|---------|
| 9000 | TCP | Master PC (192.168.1.3) | FMS TCP Server |
| 9001 | TCP | Mobile Robots | Robot-to-FMS communication |
| 9002 | TCP | Cobot Arms | Cobot-to-FMS communication |
| 5432 | PostgreSQL | Master PC | Database access |
| 7400-7410 | ROS 2 Multicast | All devices | ROS 2 DDS communication |

---

## FMS Scope and Responsibilities

### In Scope (FMS Handles)

1. **Navigation to point13** (kitchen pickup point)
   - FMS sends navigation goal to mobile robot
   - Robot navigates using Nav2 + AMCL

2. **Point13 Arrival Detection**
   - FMS detects when robot reaches point13
   - Publishes `goal_arrived` message

3. **Navigation to Customer Table**
   - After receiving `food_loaded` message
   - FMS sends navigation goal to table location

4. **Return to Parking Spot**
   - After delivery completion from customer
   - Robot returns to assigned parking location

### Out of Scope (External Teams Handle)

1. **Precision Parking** (Precision Control Team)
   - Movement from point13 → pickup_spot
   - Must use specialized precision control algorithm
   - FMS waits for `precision_parked` message

2. **Food Loading** (Robot Arm Team)
   - Pickup_spot is shared workspace
   - Robot arm loads food onto mobile robot
   - FMS waits for `food_loaded` message

---

## Delivery Flow and Message Exchange

### Complete Delivery Flow

```
1. GUI Order → FMS
   └─ FMS publishes OrderRequest to task queue

2. FMS Navigates Pinky to point13 ✅ (FMS Scope)
   └─ FMS: navigate_to_pose(/pinky1/navigate_to_pose, point13_location)

3. Point13 Arrival → FMS Detects ✅ (FMS Scope)
   └─ FMS: checks robot odometry/pose against goal_tolerance
   └─ FMS publishes: goal_arrived message

4. Precision Parking point13→pickup_spot ⏭️ (Precision Control Team)
   └─ Precision Control: receives robot at point13
   └─ Precision Control: executes precision parking algorithm
   └─ Precision Control publishes: precision_parked message

5. FMS Receives Precision Parked Confirmation ✅ (FMS Scope)
   └─ FMS subscribes to: /fms/precision_parked
   └─ State transition: POINT13 → PARKING_COMPLETE

6. Robot Arm Loading ⏭️ (Robot Arm Team)
   └─ Robot Arm: detects pinky at pickup_spot via vision/proximity
   └─ Robot Arm: executes food loading sequence
   └─ Robot Arm publishes: food_loaded message

7. FMS Receives Food Loaded Confirmation ✅ (FMS Scope)
   └─ FMS subscribes to: /fms/food_loaded
   └─ State transition: PARKING_COMPLETE → FOOD_LOADED

8. FMS Navigates Pinky to Table ✅ (FMS Scope)
   └─ FMS: navigate_to_pose(/pinky1/navigate_to_pose, table_location)

9. Customer Clicks Delivery Complete ✅ (FMS Scope)
   └─ Main Server publishes: delivery_complete message
   └─ FMS transitions to DELIVERING state

10. Robot Returns to Parking Spot ✅ (FMS Scope)
    └─ FMS: navigate_to_pose(/pinky1/navigate_to_pose, parking_location)
    └─ Task complete
```

---

## ROS 2 Topic Specifications

### Topics Published by FMS

#### `/fms/goal_arrived`
**Message Type:** `std_msgs/String` (temporary) or custom message (recommended)

**Description:** Notifies external teams that robot has arrived at point13.

**Publishing Frequency:** Once per point13 arrival

**Example Message:**
```yaml
data: "pinky1_arrived_at_point13"
```

**Usage:** Precision Control team uses this as signal to start precision parking.

---

#### `/fms/fleet_status`
**Message Type:** `fleet_interfaces/FleetStatus`

**Description:** Publishes fleet state every 1 second.

**Publishing Frequency:** 1 Hz

**Fields:**
```
string[] robot_ids           # ["pinky1", "pinky2", "pinky3"]
string[] robot_status        # ["IDLE", "NAVIGATING", "AT_POINT13", ...]
float64[] battery_levels     # Voltage per robot
string[] assigned_orders     # Current order for each robot
builtin_interfaces/Time timestamp
```

**Usage:** External teams can monitor which robots are available.

---

#### `/fms/order_request`
**Message Type:** `fleet_interfaces/OrderRequest`

**Description:** FMS publishes accepted orders (informational for external teams).

**Publishing Frequency:** Per order received

**Fields:**
```
string order_id              # Unique order identifier
string menu_id               # M001: Ham Cheese, M002: Vegan, etc.
string table_number          # T01 ~ T08
int32 quantity
string sauce_type            # mayo, mustard, ketchup, etc.
bool voice_order
builtin_interfaces/Time created_at
```

---

### Topics Subscribed by FMS

#### `/fms/precision_parked`
**Message Type:** `std_msgs/String` or custom message

**Description:** Precision Control team publishes this after completing precision parking.

**Expected Message Format:**
```yaml
data: "precision_parked:pinky1:pickup_spot"
```

or (recommended custom message):
```yaml
robot_id: "pinky1"
status: "PARKING_COMPLETE"
timestamp: (builtin_interfaces/Time)
x: 0.47    # pickup_spot x coordinate
y: 0.63    # pickup_spot y coordinate
theta: 3.14159  # Facing kitchen (π radians)
```

**Timing:** Expected within 5-10 seconds after `goal_arrived` is published.

**FMS Behavior:**
- Transitions robot state from POINT13 to PARKING_COMPLETE
- Waits for next message: `food_loaded`

---

#### `/fms/food_loaded`
**Message Type:** `std_msgs/String` or custom message

**Description:** Robot Arm team publishes this after completing food loading.

**Expected Message Format:**
```yaml
data: "food_loaded:pinky1"
```

or (recommended custom message):
```yaml
robot_id: "pinky1"
status: "FOOD_LOADED"
load_weight: 2.5   # kg (optional, for logging)
timestamp: (builtin_interfaces/Time)
```

**Timing:** Expected within 30-60 seconds after precision parking.

**FMS Behavior:**
- Transitions robot state from PARKING_COMPLETE to FOOD_LOADED
- Publishes new navigation goal for customer table
- Proceeds with delivery navigation

---

### Per-Robot Topics (by Domain ID)

These topics exist within each robot's domain ID, not in FMS domain:

#### `/{robot_id}/pose`
**Message Type:** `geometry_msgs/PoseStamped`

**Description:** Current robot position and orientation (published by robot's AMCL/localization).

**FMS Usage:** Subscribes in robot's domain context to detect point13 arrival.

**Fields:**
```
header:
  frame_id: "map"
pose:
  position:
    x: (meters)
    y: (meters)
    z: (should be 0)
  orientation: (quaternion)
```

---

#### `/{robot_id}/battery/voltage`
**Message Type:** `std_msgs/Float32`

**Description:** Current battery voltage in volts.

**FMS Usage:** Monitors battery health, triggers parking if low (<11V).

---

#### `/{robot_id}/navigate_to_pose`
**Message Type:** `nav2_msgs/NavigateToPose` (ROS 2 Action)

**Description:** FMS action client that sends navigation goals.

**FMS Usage:** Sends goals for point13, pickup_spot, table, parking locations.

**Action Goal:**
```
pose:  # Target PoseStamped
  position: {x, y}
  orientation: (quaternion for desired yaw angle)
```

---

## Communication Protocol

### FMS-to-External Team Handoff at Point13

**Sequence:**

1. **FMS Action:** Sends navigation goal to point13
   ```
   Action: /pinky1/navigate_to_pose
   Goal: {x: 0.585, y: 0.63, yaw: π}
   ```

2. **FMS Detection:** Monitor `/pinky1/pose` until within goal_tolerance
   ```
   Position error < 0.1 meters
   Angle error < 0.1 radians
   ```

3. **FMS Notification:** Publish arrival signal
   ```
   Topic: /fms/goal_arrived
   Message: "pinky1_arrived_at_point13"
   ```

4. **Precision Control Action:** Receive notification, start parking
   - Precision Control monitors `/pinky1/pose` for fine alignment
   - Precision Control executes closed-loop control to pickup_spot
   - Precision Control adjusts robot orientation to face kitchen (θ ≈ π)

5. **Precision Control Confirmation:** Publish parking complete
   ```
   Topic: /fms/precision_parked
   Message: "precision_parked:pinky1"
   ```

6. **FMS State Update:** Transition to next phase
   - FMS waits for `food_loaded` message
   - FMS monitors timeout (if not received in 60s, raise alert)

### Robot Arm Team Handoff at Pickup Spot

**Sequence:**

1. **Robot Arm Detection:** Receive `precision_parked` message
   - Confirms mobile robot is at pickup_spot
   - Verifies robot orientation (should face kitchen)

2. **Robot Arm Operation:** Execute loading sequence
   - Lower arm to interlock height
   - Scan/identify food tray
   - Load onto robot tray mechanism
   - Retract arm to safe position

3. **Robot Arm Confirmation:** Publish loading complete
   ```
   Topic: /fms/food_loaded
   Message: "food_loaded:pinky1"
   ```

4. **FMS State Update:** Transition to table delivery
   - FMS receives `food_loaded`
   - FMS sends navigation goal to assigned table
   - FMS monitors navigation until table arrival

---

## Message Type Definitions (ROS 2 .msg files)

### Current Missing Message Types

The following custom message types are referenced but not yet defined. External teams should assume these formats:

#### `GoalArrived.msg` (Recommended)
```
string robot_id
string target_location      # e.g., "point13"
geometry_msgs/PoseStamped current_pose
builtin_interfaces/Time timestamp
```

#### `PrecisionParked.msg` (Recommended)
```
string robot_id
string status               # "PARKING_COMPLETE"
geometry_msgs/PoseStamped final_pose
float64 distance_to_target  # meters (should be < 0.05)
float64 angle_error         # radians (should be < 0.05)
builtin_interfaces/Time timestamp
```

#### `FoodLoaded.msg` (Recommended)
```
string robot_id
string status               # "FOOD_LOADED"
float64 load_weight         # kg (optional)
builtin_interfaces/Time timestamp
```

---

## State Machine: Robot Lifecycle

FMS tracks each robot through these states:

```
IDLE
  ├─ (receive order)
  ▼
NAVIGATING_TO_POINT13
  ├─ (position error < 0.1m, angle error < 0.1rad)
  ▼
AT_POINT13
  ├─ (publish goal_arrived)
  ├─ (receive precision_parked)
  ▼
PARKING_COMPLETE
  ├─ (await food_loaded)
  ├─ (timeout after 60s → alert)
  ▼
FOOD_LOADED
  ├─ (publish navigation goal to table)
  ▼
NAVIGATING_TO_TABLE
  ├─ (position error < 0.1m)
  ▼
AT_TABLE
  ├─ (await delivery_complete from GUI)
  ├─ (timeout after 300s → alert)
  ▼
DELIVERING
  ├─ (publish navigation goal to parking)
  ▼
RETURNING_TO_PARKING
  ├─ (position error < 0.1m)
  ▼
IDLE
```

### State Timeouts

| State | Timeout | Action on Timeout |
|-------|---------|-------------------|
| AT_POINT13 | 10 seconds | Retry precision parking request |
| PARKING_COMPLETE | 60 seconds | Alert Precision Control team |
| AT_TABLE | 300 seconds | Alert Main Server/Kiosk |
| RETURNING_TO_PARKING | 60 seconds | Alert operator |

---

## Error Handling and Recovery

### Precision Parking Failure Scenarios

**Scenario 1: Robot doesn't reach point13**
- FMS: Publishes error log
- FMS: Retries navigation to point13 (max 3 attempts)
- Precision Control: N/A (robot didn't arrive)
- Recovery: Manual intervention or task cancellation

**Scenario 2: Precision parking times out**
- FMS: Publishes timeout alert after 10 seconds
- Precision Control: Check robot at point13, debug parking algorithm
- FMS: Waits for manual confirmation or `precision_parked` message
- Recovery: Precision Control fixes issue and sends message

**Scenario 3: Robot gets stuck during parking**
- Precision Control: Robot stops mid-way
- FMS: Detects no progress (via pose monitoring)
- Precision Control: Publishes failure message (format TBD)
- FMS: Cancels task, returns robot to idle
- Recovery: Manual inspection required

### Food Loading Failure Scenarios

**Scenario 1: Robot Arm doesn't detect robot at pickup_spot**
- Robot Arm: Publishes detection failure (format TBD)
- FMS: Receives failure, keeps robot at pickup_spot
- Precision Control: Verifies robot position
- Recovery: Precision Control adjusts position, Robot Arm retries

**Scenario 2: Food loading times out**
- FMS: Publishes timeout alert after 60 seconds
- Robot Arm: Check mechanical status, sensors
- FMS: Can proceed with empty tray (if desired) or cancel delivery
- Recovery: Manual inspection or cancellation

**Scenario 3: Arm collision with robot**
- Robot Arm: Emergency stop, publishes collision alert (format TBD)
- FMS: Receives alert, cancels navigation to table
- Recovery: Manual safety inspection required

---

## Testing Strategies for External Teams

### Precision Control Team Testing

**Standalone Test:**
```bash
# 1. Manually place pinky1 at point13 location
# 2. Publish goal_arrived message manually
ros2 topic pub -1 /fms/goal_arrived std_msgs/String "data: 'pinky1_arrived_at_point13'"

# 3. Test precision parking algorithm with real/sim robot
# 4. Publish precision_parked when complete
ros2 topic pub -1 /fms/precision_parked std_msgs/String "data: 'precision_parked:pinky1'"

# 5. Verify FMS receives message
ros2 topic echo /fms/precision_parked
```

**Integration Test with FMS:**
```bash
# 1. Start FMS with skip_precision=false, skip_robot_arm=true
ros2 run fms fms_node --ros-args -p skip_precision:=false -p skip_robot_arm:=true

# 2. Send test order
python3 fms/scripts/send_order.py --table 1

# 3. Monitor FMS state transitions
ros2 topic echo /fms/fleet_status

# 4. When robot reaches point13, precision parking starts
# 5. Publish precision_parked to complete handoff
ros2 topic pub -1 /fms/precision_parked std_msgs/String "data: 'precision_parked:pinky1'"
```

### Robot Arm Team Testing

**Standalone Test:**
```bash
# 1. Manually place pinky1 at pickup_spot
# 2. Verify arm can detect and approach robot
# 3. Test loading sequence in isolation
# 4. Publish food_loaded when complete
ros2 topic pub -1 /fms/food_loaded std_msgs/String "data: 'food_loaded:pinky1'"

# 5. Verify FMS receives message
ros2 topic echo /fms/food_loaded
```

**Integration Test with FMS:**
```bash
# 1. Start FMS with skip_precision=true, skip_robot_arm=false
ros2 run fms fms_node --ros-args -p skip_precision:=true -p skip_robot_arm:=false

# 2. Send test order
python3 fms/scripts/send_order.py --table 1

# 3. Robot will:
#    - Navigate to point13
#    - Precision parking is mocked (automatic)
#    - Wait for food_loaded message

# 4. When ready, publish food_loaded
ros2 topic pub -1 /fms/food_loaded std_msgs/String "data: 'food_loaded:pinky1'"

# 5. FMS will navigate to table
```

---

## Configuration Files for External Teams

### network_config.yaml (Shared)

Location: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/network_config.yaml`

**Current Status:** Uses namespace-based config (will be migrated to domain IDs)

**For External Teams:**
- Precision Control: Use domain 11, 12, 13 for mobile robots
- Robot Arm: Use domain 14, 15 for cobot arms
- All teams: Ensure ROS_DOMAIN_ID environment variable set before launching

---

### fms_config.yaml (Shared)

Location: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml`

**Key Locations for External Teams:**

```yaml
positions:
  point13:
    x: 0.585   # Kitchen pickup point (before precision parking)
    y: 0.63
    theta: 0.0

  pickup_spot:
    x: 0.47    # Food loading station (after precision parking)
    y: 0.63
    theta: 3.14159  # Face kitchen (π radians)
```

**Usage:**
- Precision Control: Move robot from point13 (0.585, 0.63) to pickup_spot (0.47, 0.63)
- Robot Arm: Load food when robot is at pickup_spot with θ ≈ π

---

## Contact and Support

### Team Roles and Responsibilities

| Team | Responsibility | Lead | Contact Protocol |
|------|----------------|------|------------------|
| FMS Integration (Our Team) | Deliver messages, state machine, navigation to point13 | FMS Lead | Slack #fms-channel |
| Precision Control | Point13 → pickup_spot, closed-loop alignment | Precision Lead | Slack #precision-team |
| Robot Arm | Food loading at pickup_spot | Arm Lead | Slack #robotarm-team |
| Main Server | Order management, GUI coordination | Backend Lead | Slack #backend-channel |

### Key Handoff Points

1. **Point13 Handoff** (FMS → Precision Control)
   - Trigger: `goal_arrived` message published
   - Duration: ~10 seconds
   - Expected Response: `precision_parked` message

2. **Pickup_Spot Handoff** (Precision Control → Robot Arm)
   - Trigger: `precision_parked` message published
   - Duration: ~30-60 seconds
   - Expected Response: `food_loaded` message

3. **Table Delivery Handoff** (FMS → Main Server)
   - Trigger: Robot arrives at table
   - Duration: Variable (customer service time)
   - Expected Response: `delivery_complete` from GUI

### Communication Protocol

**For Critical Issues:**
- Slack broadcast in #fms-channel
- Mention relevant team leads
- Include: error message, robot_id, timestamp

**For Scheduled Testing:**
- Book time in shared calendar
- Notify all teams 24 hours in advance
- Use dedicated test robots (pinky3, robot_arm_2)

**For Message Format Changes:**
- Submit proposal in Jira with "Interface Change" label
- All teams must approve before implementation
- Backward compatibility required for 1 sprint

---

## Appendix A: ROS Domain ID Setup

### Setting ROS_DOMAIN_ID for External Teams

**On Precision Control Node:**
```bash
export ROS_DOMAIN_ID=0  # Run on FMS domain to receive messages
ros2 launch precision_control precision_launch.py
```

**On Robot Arm Node:**
```bash
export ROS_DOMAIN_ID=0  # Run on FMS domain to receive messages
ros2 launch robot_arm arm_launch.py
```

**To Subscribe to Robot Topics (e.g., Robot Domain 11):**
```bash
export ROS_DOMAIN_ID=11  # Switch to robot's domain
ros2 topic echo /pinky1/pose
```

### Multi-Domain Communication Pattern

If external teams need to communicate across domains, create a bridge:

```python
import rclpy
from rclpy.context import Context

# Main context (FMS domain 0)
main_context = Context()
main_context.init(domain_id=0)
node_main = rclpy.create_node('bridge_node', context=main_context)

# Robot context (domain 11)
robot_context = Context()
robot_context.init(domain_id=11)
node_robot = rclpy.create_node('robot_monitor', context=robot_context)
```

---

## Appendix B: Message Format Examples

### Example 1: FMS publishes goal_arrived

```python
# FMS Code
from std_msgs.msg import String

goal_arrived_pub = self.create_publisher(String, '/fms/goal_arrived', 10)

msg = String()
msg.data = f"pinky1_arrived_at_point13"
goal_arrived_pub.publish(msg)
```

### Example 2: Precision Control publishes precision_parked

```python
# Precision Control Code
from std_msgs.msg import String

precision_pub = self.create_publisher(String, '/fms/precision_parked', 10)

msg = String()
msg.data = f"precision_parked:pinky1"
precision_pub.publish(msg)
```

### Example 3: Robot Arm publishes food_loaded

```python
# Robot Arm Code
from std_msgs.msg import String

food_loaded_pub = self.create_publisher(String, '/fms/food_loaded', 10)

msg = String()
msg.data = f"food_loaded:pinky1"
food_loaded_pub.publish(msg)
```

### Example 4: FMS subscribes to precision_parked

```python
# FMS Code
from std_msgs.msg import String

def precision_parked_callback(msg):
    # Parse message: "precision_parked:pinky1"
    parts = msg.data.split(':')
    robot_id = parts[1]
    # Update robot state
    self.robot_states[robot_id] = "PARKING_COMPLETE"

sub = self.create_subscription(String, '/fms/precision_parked',
                               precision_parked_callback, 10)
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-25 | Integration Coordinator | Initial specification |

---

## Acknowledgments

This specification was created to enable seamless coordination between:
- FMS Team (navigation and task orchestration)
- Precision Control Team (fine-grained positioning)
- Robot Arm Team (food loading operations)

All teams are expected to review this specification and provide feedback within 1 week.
