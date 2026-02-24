# Kitchmatics FMS - Claude Code Project Guide

## Project Overview

**Kitchmatics Fleet Management System (FMS)** is a delivery flow implementation from Customer GUI order to table delivery using autonomous mobile robots (PinkyPro) in a restaurant environment.

### FMS Scope and Responsibilities

**Our Scope (FMS Team):**
- Navigate pinky robots to pickup_spot (kitchen pickup point)
- Send goal_arrived message after pickup_spot arrival
- Navigate to customer table after food loading
- Return robot to parking spot after delivery

**External Team Scope (NOT our responsibility):**
- Robot arm food loading operations - handled by robot arm team
- Precision parking (if implemented separately)

**Test Mode Strategy:**
- Use skip_robot_arm mode to mock robot arm steps for testing
- Skip mode automatically proceeds after pickup_spot arrival
- Test full flow without external team dependencies

### Current Architecture: ROS 2 Namespaces

**DECISION: Use ROS 2 Namespaces (NOT ROS_DOMAIN_ID)**

Each robot operates with a separate namespace in the same ROS domain (domain 0):

| Robot | Namespace | Hardware ID | IP Address | Purpose |
|-------|-----------|-------------|------------|---------|
| pinky1 | /pinky1 | pinky_b4bc | 192.168.1.7 | Mobile serving robot |
| pinky2 | /pinky2 | pinky_e2a8 | 192.168.1.6 | Mobile serving robot |
| pinky3 | /pinky3 | pinky_d29d | 192.168.1.11 | Mobile serving robot |
| cobot1 | /cobot1 | jetcobot_aa1f | 192.168.1.4 | Food loading arm |
| cobot2 | /cobot2 | jetcobot_aa85 | 192.168.1.10 | Food loading arm |

**Why Namespaces over ROS_DOMAIN_ID:**
- All robots communicate on the same ROS 2 domain from the master PC
- Simpler namespace management for multi-robot coordination
- Centralized FMS control on master PC (192.168.1.3)
- Easier cross-robot coordination and collision avoidance
- RewrittenYaml handles namespace-based parameter substitution
- Each robot can be tested individually by changing namespace

**Namespace Implementation:**
- Each robot runs Nav2 stack under its namespace (`/pinky1`, `/pinky2`, etc.)
- FMS subscribes to namespaced topics: `/{namespace}/pose`, `/{namespace}/battery/*`
- Navigation actions: `/{namespace}/navigate_to_pose`
- All nodes configured via `bringup_launch.py` with PushRosNamespace

## Delivery Flow

```
1. GUI order → FMS
2. FMS navigates pinky to pickup_spot ✅ (our scope)
3. Pickup_spot arrival → send goal_arrived message ✅ (our scope)
4. FMS requests robot arm to load food → /robot_arm/cooking_order
5. Robot arm loads food ⏭️ (external team)
6. Receive food_loaded message ⏭️ (skip mode: auto-mocked after 3s)
7. FMS navigates pinky to table ✅ (our scope)
8. Customer clicks delivery complete
9. FMS returns pinky to parking spot ✅ (our scope)
```

## Project Structure

```
roscamp-repo-1/
├── fms/                              # Fleet Management System
│   ├── config/
│   │   ├── fms_config.yaml           # Robot locations, zones, parameters
│   │   ├── network_config.yaml       # Closed Network robot configuration
│   │   └── navigation_graph.yaml     # Waypoint graph for path planning
│   ├── fms/
│   │   ├── fms_node.py               # FMS ROS 2 node (main entry point)
│   │   ├── fleet_controller.py       # Fleet state management
│   │   ├── task_manager.py           # Task queue and assignment
│   │   ├── zone_manager.py           # Collision avoidance zones
│   │   └── tcp_communication.py      # TCP server for closed network
│   ├── scripts/
│   │   ├── send_order.py             # Test order script
│   │   ├── robot_file_sync.py        # Parameter sync to robots
│   │   └── start_fms_server.sh       # FMS server startup
│   └── launch/
│       ├── fms_launch.py             # Standard FMS launch
│       └── fms_closed_network.launch.py  # Closed network variant
│
├── mobile_robot/                     # Mobile Robot Navigation
│   ├── launch/
│   │   └── bringup_launch.py         # Multi-robot Nav2 launch (RewrittenYaml)
│   ├── params/
│   │   ├── nav2_params.yaml          # Nav2 parameters
│   │   └── mapper_params.yaml        # SLAM mapper parameters
│   ├── maps/
│   │   ├── real.yaml                 # Actual restaurant map
│   │   └── real.png                  # Map image
│   └── config/
│       ├── pinky_b4bc.yaml           # Robot-specific config
│       ├── pinky_e2a8.yaml           # Robot-specific config
│       └── pinky_d29d.yaml           # Robot-specific config
│
├── app/
│   ├── backend/
│   │   └── main_server/              # Main Server (ROS2 + TCP + PostgreSQL)
│   │       ├── main_server_node.py   # Main server node
│   │       ├── tcp_server.py         # TCP communication layer
│   │       └── database_manager.py   # PostgreSQL integration
│   └── gui/
│       ├── admin_gui/                # Admin fleet monitoring GUI
│       │   └── src/
│       │       ├── main.py           # Main GUI entry point
│       │       ├── ui_fleet_monitor.py  # Fleet monitoring UI
│       │       └── fleet_client.py   # TCP client for fleet status
│       └── customer_gui/             # Customer ordering GUI
│           └── src/
│               └── main.py
│
├── fleet_interfaces/                 # ROS 2 message definitions
│   └── msg/
│       ├── OrderRequest.msg
│       ├── RobotStatus.msg
│       ├── FleetStatus.msg
│       └── DeliveryComplete.msg
│
├── database/                         # PostgreSQL schemas
│   ├── schema.sql                    # Database schema
│   └── README.md                     # Setup instructions
│
└── README.md                         # User documentation
```

## Key Technologies

- **ROS 2 Jazzy**: Robot communication framework
- **Nav2**: Navigation and path planning
- **AMCL**: Localization via particle filter
- **PostgreSQL**: Order and robot state database
- **TCP Sockets**: GUI ↔ Main Server communication
- **Python 3.10+**: Primary development language

## Navigation and Delivery Locations

### Key Waypoints

Current coordinates in `fms/config/fms_config.yaml`:

**Delivery Locations:**
- `pickup_spot`: Kitchen food pickup point (x: 0.47, y: 0.63)
- `table1` through `table8`: Customer table positions
- `pinky1_spot`, `pinky2_spot`, `pinky3_spot`: Robot parking/charging spots

**Navigation Waypoints:**
- `point1` through `point4`: Left column waypoints
- `point5` through `point8`: Middle column waypoints
- `point9` through `point12`: Right column waypoints

### Navigation Parameters

Located in `mobile_robot/params/nav2_params.yaml`:

**Tuned for small robot (PinkyPro ~0.1m diameter) in confined space (2m × 1m):**
- `inflation_radius`: 0.01m (1cm for tight spaces)
- `xy_goal_tolerance`: 0.02m (2cm arrival precision)
- `lookahead_dist`: 0.08m (for small robot smoothness)
- `robot_radius`: 0.055m (actual PinkyPro radius)

## ROS 2 Topics and Messages

### FMS Node Communication

**Publishers:**
- `/fms/fleet_status` (FleetStatus): Fleet state update, 1Hz
  - All robot statuses, current tasks, fleet metrics

**Subscribers:**
- `/fms/order_request` (OrderRequest): New order from Main Server
  - table_number, menu_id, order_id
- `/fms/delivery_complete` (DeliveryComplete): Delivery confirmation from GUI
  - order_id, robot_id, timestamp

### Per-Robot Topics (Namespaced)

**Important:** Topics are namespaced under each robot (`/pinky1/`, `/pinky2/`, `/pinky3/`)

**Subscribed by FMS:**
- `/{namespace}/pose` (PoseStamped): Current robot position
- `/{namespace}/battery/voltage` (Float32): Battery voltage (V)
- `/{namespace}/battery/present` (Bool): Battery connection status

**Action Servers used by FMS:**
- `/{namespace}/navigate_to_pose` (NavigateToPose action): Send navigation goal
  - Input: target pose (x, y, theta)
  - Output: success/failure, final pose

### Robot Arm Integration Topics

**Published by FMS:**
- `/robot_arm/cooking_order` (CookingOrder): Order details for cooking
  - order_id, table_number, robot_id, menu_id

**Subscribed by FMS:**
- `/robot_arm/loading_complete` (LoadingComplete): Food loaded notification
  - order_id, robot_id, success flag, timestamp

## Configuration Files

### network_config.yaml - Closed Network Setup

Defines all robots in the kitchmatics closed network:

```yaml
master:
  host: "192.168.1.3"
  tcp_port: 9000

mobile_robots:
  pinky_b4bc:
    robot_id: "pinky1"
    namespace: "/pinky1"
    ip_address: "192.168.1.7"
    enabled: true

cobot_arms:
  jetcobot_aa1f:
    robot_id: "cobot1"
    namespace: "/cobot1"
    ip_address: "192.168.1.4"
    enabled: true
```

### fms_config.yaml - FMS Settings

**Robot Configuration:**
```yaml
robots:
  - robot_id: "pinky1"
    namespace: "/pinky1"
    parking_spot: "pinky1_spot"
```

**Map Positions:** All delivery and waypoint coordinates (in meters)

**Zones:** Collision avoidance zones around each position

**Parameters:**
- `assignment_frequency`: 2.0 Hz (robot task assignment)
- `status_publish_frequency`: 1.0 Hz (fleet status)
- `goal_reached_threshold`: 0.1m (arrival distance)
- `low_battery_threshold`: 20.0V

### bringup_launch.py - Multi-Robot Navigation Launch

Launches Nav2 for a specific robot namespace:

```bash
# On robot or via SSH from master:
ros2 launch ~/roscamp-repo-1/mobile_robot/launch/bringup_launch.py \
  namespace:=pinky1 \
  map:=~/real.yaml
```

**Features:**
- Uses `RewrittenYaml` to dynamically insert namespace into Nav2 parameters
- Supports pinky1, pinky2, pinky3 with same configuration file
- No robot code changes needed, all config in roscamp-repo-1

## Database Schema

### Orders Table

```sql
CREATE TABLE orders (
    order_id UUID PRIMARY KEY,
    table_number VARCHAR(3),
    menu_id VARCHAR(10),
    status VARCHAR(20),  -- PENDING, COOKING, READY, DELIVERING, COMPLETED
    assigned_robot VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Robots Table

```sql
CREATE TABLE robots (
    robot_id VARCHAR(20) PRIMARY KEY,  -- pinky1, pinky2, pinky3
    type VARCHAR(20),                  -- SERVING_BOT_1, SERVING_BOT_2, etc.
    ip_address VARCHAR(15),
    status VARCHAR(20),                -- IDLE, NAVIGATING, LOADING, DELIVERING, ERROR
    battery_voltage FLOAT,
    last_heartbeat TIMESTAMP
);
```

## Current Issues and TODOs

### High Priority - Active Development

1. **FMS → Robot Navigation Integration**
   - [x] Namespace-based topic subscriptions
   - [x] NavigateToPose action client creation per robot
   - [ ] Test with actual robot hardware
   - [ ] Validate goal_reached_threshold tuning

2. **Skip Mode Implementation**
   - [x] skip_robot_arm parameter added to FMS
   - [x] Auto-transition after pickup_spot arrival
   - [ ] Test with full delivery flow
   - [ ] Validate food_loaded mock timing

3. **Configuration File Loading**
   - [ ] Load robot configs from fms_config.yaml (currently hardcoded)
   - [ ] Load positions from YAML (currently hardcoded)
   - [ ] Load zones from YAML (currently hardcoded)

### Medium Priority - Testing

4. **End-to-End Testing**
   - [ ] Test full order → delivery → parking flow with skip mode
   - [ ] Test multi-robot scenarios (2-3 simultaneous orders)
   - [ ] Test collision avoidance with zones
   - [ ] Test error recovery (navigation failure, robot unreachable)

5. **Hardware Testing**
   - [ ] Coordinate coordinates on actual map
   - [ ] Validate AMCL localization on each robot
   - [ ] Test battery monitoring
   - [ ] Stress test with sustained operation

### Lower Priority - Enhancements

6. **Advanced Features**
   - [ ] Implement distance-based robot selection
   - [ ] Add battery-aware task assignment
   - [ ] Implement dynamic path replanning
   - [ ] Add teleoperation fallback mode

## Development Guidelines

### Code Style

- Follow PEP 8 for Python code
- Use type hints for function signatures
- Add docstrings for all classes and public methods
- Keep functions focused and under 50 lines

### Logging Standards

Use Python logging with context:

```python
import logging
logger = logging.getLogger(__name__)

# At appropriate levels:
logger.debug(f"Robot {robot_id} at ({x}, {y})")
logger.info(f"Order {order_id} assigned to {robot_id}")
logger.warning(f"Low battery: {robot_id} at {voltage}V")
logger.error(f"Navigation failed for {robot_id}: {error_msg}")
```

### Testing Strategy

1. **Unit tests:** Individual components (task_manager, fleet_controller)
2. **Integration tests:** FMS ↔ Main Server communication via ROS topics
3. **System tests:** Full delivery flow with skip mode enabled
4. **Hardware tests:** Real robot navigation (after software validation)

### Error Handling

- Always handle ROS action failures (ABORTED, CANCELED)
- Implement retry logic with exponential backoff
- Log all errors with context (robot_id, order_id, current state)
- Gracefully degrade on battery low or obstacle

## Skip Mode Testing

To test without robot arm and precision control:

```bash
# Terminal 1: FMS with skip mode
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true

# Terminal 2: Send test order
python3 fms/scripts/send_order.py --table 1

# Expected behavior:
# 1. Robot navigates to pickup_spot
# 2. FMS publishes goal_arrived
# 3. After 3s, food_loaded is automatically triggered
# 4. Robot navigates to table1
# 5. Manual delivery complete (or auto via script)
# 6. Robot returns to parking_spot
```

## Network Environment

**WiFi:** kitchmatics (closed network)

**Master PC:** 192.168.1.3 (FMS server location)

**Robot Connectivity:**
```
Master PC (192.168.1.3)
    ├── pinky1 (192.168.1.7) - /pinky1 namespace
    ├── pinky2 (192.168.1.6) - /pinky2 namespace
    ├── pinky3 (192.168.1.11) - /pinky3 namespace
    ├── cobot1 (192.168.1.4) - /cobot1 namespace
    └── cobot2 (192.168.1.10) - /cobot2 namespace
```

**Port Usage:**
- 9000: FMS TCP Server (master PC)
- 9001: Mobile robot TCP client (each robot)
- 9002: Robot arm TCP client (each arm)
- 5432: PostgreSQL
- 9999: Main Server TCP (legacy compatibility)

## Important Notes for Developers

1. **DO NOT implement robot arm logic** - handled by external team
2. **DO implement skip_robot_arm mode** - enables testing without robot arm
3. **DO use namespaces** - not ROS_DOMAIN_ID for this architecture
4. **DO test with skip mode first** - validate FMS scope independently
5. **DO keep CLAUDE.md and README.md in sync** - single source of truth
6. **DO ask questions** - especially about Jira requirements and external interfaces

## Quick Start for New Developers

1. **Clone and build:**
   ```bash
   cd /home/gw/kitchmatics/roscamp-repo-1
   colcon build
   source install/setup.bash
   ```

2. **Run FMS in skip mode:**
   ```bash
   ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
   ```

3. **Send test order:**
   ```bash
   python3 fms/scripts/send_order.py --table 1
   ```

4. **Monitor fleet status:**
   ```bash
   ros2 topic echo /fms/fleet_status
   ```

5. **Check robot topics:**
   ```bash
   ros2 topic list | grep pinky
   ```

## Resources

- **Project Documentation:** `/home/gw/kitchmatics/roscamp-repo-1/README.md`
- **Network Configuration:** `fms/config/network_config.yaml`
- **FMS Configuration:** `fms/config/fms_config.yaml`
- **Nav2 Parameters:** `mobile_robot/params/nav2_params.yaml`
- **Database Setup:** `database/README.md`
- **TODO Tracking:** `TODO.md`
