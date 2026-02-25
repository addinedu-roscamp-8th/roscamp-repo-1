# FMS Test Scripts Documentation

This directory contains comprehensive test scripts for validating the Kitchmatics Fleet Management System (FMS) communication layer.

## Quick Start

### 1. Test ROS 2 Messages (Most Important for FMS Integration)
```bash
# Test all message types
python3 test_messages.py --all

# Test goal_arrived message publishing (point13 arrival)
python3 test_messages.py --test-goal-arrived

# Test fleet status subscription
python3 test_messages.py --test-fleet-status

# Interactive testing mode
python3 test_messages.py --interactive
```

### 2. Test External Team Mocks (For Skip Mode Testing)
```bash
# Start all mocks (precision control + robot arm)
python3 mock_external_teams.py --start-all

# Start precision control mock (simulates precision_parked message)
python3 mock_external_teams.py --mock-precision

# Start robot arm mock (simulates food_loaded message)
python3 mock_external_teams.py --mock-arm

# Interactive control of mocks
python3 mock_external_teams.py --interactive
```

### 3. Test TCP Communication
```bash
# Test all TCP ports
python3 test_tcp_communication.py --test-all

# Test specific port accessibility
python3 test_tcp_communication.py --test-ports

# Test message format and serialization
python3 test_tcp_communication.py --test-message-format

# Start TCP echo server (for testing)
python3 test_tcp_communication.py --echo-server --port 9000

# Connect as client to echo server
python3 test_tcp_communication.py --echo-client --host 192.168.1.3 --port 9000
```

## Detailed Test Scripts

### test_messages.py

Tests ROS 2 message communication for the FMS system.

**What it tests:**
1. **goal_arrived Publishing** - Validates that goal_arrived messages can be published when a robot reaches point13
2. **fleet_status Subscription** - Verifies FMS can receive and process fleet status updates
3. **Per-robot Topics** - Checks namespace isolation (/pinky1/*, /pinky2/*, /pinky3/*)
4. **TCP Message Format** - Validates TCP message serialization/deserialization
5. **Namespace Isolation** - Ensures messages don't cross between robot namespaces

**Message Types Tested:**
- `OrderRequest` - Orders from Main Server to FMS
- `RobotStatus` - Individual robot status
- `FleetStatus` - Overall fleet status
- `DeliveryComplete` - Delivery confirmation from customer GUI
- Custom `goal_arrived` - Robot arrival at point13 (using String type until official message is defined)

**Usage Examples:**
```bash
# Test goal_arrived message manually
python3 test_messages.py --test-goal-arrived

# Test fleet status subscription (wait for FMS to publish)
python3 test_messages.py --test-fleet-status

# Interactive mode - publish messages on demand
python3 test_messages.py --interactive

# Commands in interactive mode:
# > goal_arrived pinky1 point13
# > order 1 M001 1
# > status
# > quit
```

**Expected Output:**
```
[FMS_TEST_NODE] Created publisher: /fms/goal_arrived (using String type)
[FMS_TEST_NODE] Created publisher: /fms/order_request
[FMS_TEST_NODE] Subscribed to: /fms/fleet_status
[GOAL_ARRIVED] Published: pinky1 arrived at point13
[ORDER_REQUEST] Published: ORD-123456 to T01
```

**Important Notes:**
- Start the FMS node first: `ros2 launch fms fms_launch.py`
- The `goal_arrived` message uses `std_msgs/String` as a workaround until an official message type is defined in fleet_interfaces
- For full testing, also run: `ros2 launch mobile_robot bringup_launch.py`

---

### mock_external_teams.py

Mocks external team services for skip mode testing without external dependencies.

**What it mocks:**

1. **Precision Control Team** (domain 14)
   - Listens for `goal_arrived` message on `/fms/goal_arrived`
   - Simulates precision parking (point13 → pickup_spot)
   - Publishes `precision_parked` message after delay
   - Configurable delay (default: 2 seconds)

2. **Robot Arm Team** (domain 15)
   - Listens for `food_load_request` message on `/fms/food_load_request`
   - Simulates food loading onto robot
   - Publishes `food_loaded` message after delay
   - Configurable delay (default: 3 seconds)

**Message Flow:**
```
FMS                  Precision Mock              Robot Arm Mock
 |                         |                           |
 +--goal_arrived----------->|                           |
 |                    (simulate parking)                |
 |<-------precision_parked--|                           |
 |                                                      |
 +--food_load_request-------------------→              |
 |                              (simulate loading)      |
 |                         food_loaded-----<-----------+
 |
 (Robot navigates to table and completes delivery)
```

**Usage Examples:**
```bash
# Start both mocks with default delays
python3 mock_external_teams.py --start-all

# Start precision mock with 3-second delay
python3 mock_external_teams.py --mock-precision --precision-delay 3

# Start arm mock with 5-second delay
python3 mock_external_teams.py --mock-arm --arm-delay 5

# Run both mocks for 30 seconds
python3 mock_external_teams.py --start-all --duration 30

# Interactive mode
python3 mock_external_teams.py --interactive

# Commands in interactive mode:
# > start precision 2
# > start arm 3
# > stats
# > stop all
# > quit
```

**Expected Output:**
```
[PRECISION_CONTROL_MOCK] Initialized (delay=2.0s)
[ROBOT_ARM_MOCK] Initialized (delay=3.0s)
[PRECISION_CONTROL_MOCK] [GOAL_ARRIVED] Received from pinky1 at point13
[PRECISION_CONTROL_MOCK] [PRECISION_PARKED] Published: pinky1 parked at pickup_spot
[ROBOT_ARM_MOCK] [FOOD_LOAD_REQUEST] Received for pinky1
[ROBOT_ARM_MOCK] [FOOD_LOADED] Published: pinky1 loaded with ORD-20250225-001

MOCK STATISTICS
Precision Control Mock:
  goal_arrived received:     1
  precision_parked sent:     1
  pending parkings:          0
Robot Arm Mock:
  food_load_request received: 1
  food_loaded sent:           1
  pending loads:              0
```

**Integration with FMS:**
```bash
# Terminal 1: Start mock external teams
python3 mock_external_teams.py --start-all

# Terminal 2: Start FMS with skip mode
ros2 launch fms fms_launch.py skip_robot_arm:=true

# Terminal 3: Send test order
python3 send_order.py --table 1

# Expected flow:
# 1. FMS receives order
# 2. FMS navigates pinky to point13
# 3. FMS publishes goal_arrived
# 4. Precision mock publishes precision_parked (2s delay)
# 5. FMS requests robot arm to load (would wait for food_loaded in normal mode)
# 6. Arm mock publishes food_loaded (3s delay)
# 7. FMS navigates pinky to table1
# 8. FMS waits for manual delivery complete
# 9. FMS returns pinky to parking
```

---

### test_tcp_communication.py

Tests TCP communication on the closed network "kitchmatics".

**What it tests:**

1. **Port Accessibility** - Checks if all configured ports are reachable
2. **Message Format** - Validates TCP message serialization/deserialization
3. **Message Parsing** - Tests JSON parsing of various message formats
4. **Message Size** - Tests message handling for different payload sizes
5. **Network Connectivity** - Verifies network configuration is correct

**Tested Ports:**
- Master FMS: 192.168.1.3:9000
- Main Server: 192.168.1.3:9999
- Robot Clients: 192.168.1.7,6,11:9001 (pinky1,2,3)
- Arm Clients: 192.168.1.4,10:9002 (cobot1,2)
- PostgreSQL: 127.0.0.1:5432

**Usage Examples:**
```bash
# Test all ports
python3 test_tcp_communication.py --test-all

# Test only port accessibility
python3 test_tcp_communication.py --test-ports

# Test message format validation
python3 test_tcp_communication.py --test-message-format

# Start TCP echo server for testing
python3 test_tcp_communication.py --echo-server --host 0.0.0.0 --port 9000

# Connect to echo server as client
python3 test_tcp_communication.py --echo-client --host 192.168.1.3 --port 9000

# Test with custom port
python3 test_tcp_communication.py --echo-server --port 9999
```

**Message Types Tested:**
- CONNECT - Robot connection setup
- ROBOT_STATUS - Individual robot status updates
- TASK_ASSIGN - Task assignment to robots
- TASK_COMPLETE - Task completion notification
- FLEET_STATUS - Overall fleet status
- HEARTBEAT - Periodic heartbeat messages
- EMERGENCY_STOP - Emergency stop commands

**Expected Output for Port Test:**
```
TEST 1: TCP Port Accessibility
Testing port accessibility (3s timeout per port):
  [Master FMS] OPEN
  [Main Server] CLOSED
  [pinky1 Client] CLOSED
  [pinky2 Client] CLOSED
  [pinky3 Client] CLOSED
  [cobot1 Client] CLOSED
  [cobot2 Client] CLOSED
  [PostgreSQL] OPEN

Summary: 2/8 ports open
```

**Expected Output for Message Format Test:**
```
TEST 2: TCP Message Format Validation
Testing message serialization/deserialization:
  [CONNECT] OK (87 bytes)
  [ROBOT_STATUS] OK (156 bytes)
  [TASK_ASSIGN] OK (168 bytes)
  [TASK_COMPLETE] OK (96 bytes)
  [FLEET_STATUS] OK (187 bytes)
  [HEARTBEAT] OK (105 bytes)
  [EMERGENCY_STOP] OK (102 bytes)

Result: OK
```

---

## Network Configuration Reference

### WiFi Network: "kitchmatics" (Closed Network)

```
Master PC (192.168.1.3)
├── FMS Server: port 9000
├── Main Server: port 9999
└── PostgreSQL: port 5432

Mobile Robots (pinky_pro):
├── pinky1: 192.168.1.7:9001
├── pinky2: 192.168.1.6:9001
└── pinky3: 192.168.1.11:9001

Robot Arms (JetCobot):
├── cobot1: 192.168.1.4:9002
└── cobot2: 192.168.1.10:9002
```

### ROS 2 Topic Structure (Current - Namespaces)

```
Global Topics:
├── /fms/order_request (OrderRequest)
├── /fms/fleet_status (FleetStatus)
├── /fms/delivery_complete (DeliveryComplete)
├── /fms/goal_arrived (String - custom)
├── /fms/precision_parked (String - custom)
├── /fms/food_loaded (String - custom)
└── /fms/food_load_request (String - custom)

Per-Robot Topics (Namespaced):
├── /pinky1/*
│   ├── /pose
│   ├── /battery/voltage
│   ├── /battery/present
│   └── /navigate_to_pose (action)
├── /pinky2/*
│   └── (same as pinky1)
└── /pinky3/*
    └── (same as pinky1)
```

### ROS 2 Domain IDs (Future - CLAUDE.md Requirement)

**Note: The following is the planned migration based on CLAUDE.md requirements:**

```
Domain 11: pinky1 (mobile robot)
Domain 12: pinky2 (mobile robot)
Domain 13: pinky3 (mobile robot)
Domain 14: robot_arm_1 (precision control)
Domain 15: robot_arm_2 (precision control)
Domain 0:  Master FMS node
```

---

## Testing Checklist

### Before Running Full System

- [ ] All ROS 2 message types are correctly defined in `fleet_interfaces/msg/`
- [ ] TCP communication paths are tested
- [ ] Network connectivity verified on "kitchmatics" WiFi
- [ ] Robot clients can be reached on their configured ports
- [ ] Main Server and FMS nodes start without errors

### Communication Validation

- [ ] `test_messages.py --test-goal-arrived` passes
- [ ] `test_messages.py --test-fleet-status` receives messages
- [ ] `test_tcp_communication.py --test-all` shows all critical ports open
- [ ] `test_tcp_communication.py --test-message-format` validates all message types
- [ ] TCP echo server and client can communicate bidirectionally

### Skip Mode Testing (No External Dependencies)

- [ ] Mock external teams start without errors: `mock_external_teams.py --start-all`
- [ ] Mocks correctly receive and respond to messages
- [ ] FMS processes mock `precision_parked` messages
- [ ] FMS processes mock `food_loaded` messages
- [ ] Full delivery flow completes: order → pickup → delivery → return

### Full Integration Testing

- [ ] Start all components in correct order:
  1. Robots and arms on their respective domains
  2. FMS node with skip mode disabled
  3. Main Server node
  4. Send test order via `send_order.py`
- [ ] Monitor message flow in all terminals
- [ ] Verify database updates throughout delivery
- [ ] Check Admin GUI for fleet status updates

---

## Troubleshooting

### ROS 2 Topics Not Appearing

**Problem:** `test_messages.py` doesn't receive fleet_status messages

**Solution:**
1. Verify FMS node is running: `ros2 node list`
2. Check topic availability: `ros2 topic list`
3. Verify message type: `ros2 topic type /fms/fleet_status`
4. Inspect messages: `ros2 topic echo /fms/fleet_status`

### TCP Ports Closed

**Problem:** Port test shows all robot ports closed

**Solution:**
1. Verify robot IPs are correct in `network_config.yaml`
2. Check WiFi connection to "kitchmatics" network
3. Verify robots are powered on and network enabled
4. Check firewall rules on master PC
5. Test connectivity: `ping 192.168.1.7`

### Message Parse Errors

**Problem:** "Failed to parse goal_arrived message"

**Solution:**
1. Check JSON format in published messages
2. Verify all required fields are present
3. Review error logs for specific field issues
4. Use `ros2 topic echo /fms/goal_arrived` to inspect raw messages

### Mock Not Responding

**Problem:** Mocks started but not receiving messages

**Solution:**
1. Verify FMS node is publishing to correct topics
2. Check ROS 2 domain ID matching (currently no domain isolation)
3. Monitor mock output for subscription confirmation
4. Verify message format matches expected structure
5. Check ROS 2 network configuration

---

## File Locations

- Test Scripts: `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/`
- FMS Config: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/`
- Message Definitions: `/home/gw/kitchmatics/roscamp-repo-1/fleet_interfaces/msg/`
- FMS Node: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py`
- Main Server: `/home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/`
- TCP Communication: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/tcp_communication.py`

---

## Implementation Notes

### Missing Message Types (CLAUDE.md Requirements)

Three custom message types are currently mocked using `std_msgs/String`:
1. `goal_arrived` - Robot arrival at point13
2. `precision_parked` - Precision parking completion
3. `food_loaded` - Food loading completion

**To implement official message types:**

1. Create message files in `fleet_interfaces/msg/`:
   ```
   GoalArrived.msg
   PrecisionParked.msg
   FoodLoaded.msg
   ```

2. Update `fleet_interfaces/CMakeLists.txt` to include new messages

3. Update test scripts to use official message types instead of String

4. Rebuild interfaces: `colcon build --packages-select fleet_interfaces`

### Namespace vs Domain ID Migration

Current implementation uses **namespaces** (`/pinky1`, `/pinky2`, `/pinky3`).

**CLAUDE.md requires migration to ROS_DOMAIN_ID:**
- This enables isolated communication between robots in closed network
- Each robot operates on separate domain without namespace overhead
- Requires updating launch files and FMS node implementation

---

## Contact and Support

- Product Planner: Team Lead
- Communication Validator: Reviews message formats and protocols
- For detailed implementation requirements: See `/home/gw/kitchmatics/roscamp-repo-1/CLAUDE.md`
