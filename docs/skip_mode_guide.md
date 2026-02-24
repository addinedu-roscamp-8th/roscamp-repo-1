# Kitchmatics FMS - Skip Mode Testing Guide

**Document Version:** 1.0
**Last Updated:** 2026-02-25
**Audience:** FMS Team, QA Team, External Teams (for integration testing)

---

## Overview

Skip Mode allows testing the complete FMS delivery flow without requiring external teams (Precision Control and Robot Arm teams) to have their systems operational. The FMS automatically mocks the external team operations with realistic timing.

### Use Cases

1. **Development & Debugging**: Test FMS logic independently
2. **Integration Testing**: Verify FMS-to-GUI communication without external systems
3. **Performance Testing**: Load test multiple robots without external bottlenecks
4. **Demonstration**: Show complete delivery flow in action
5. **CI/CD Pipeline**: Automated testing in continuous integration

### When to Use Skip Mode

| Scenario | Use Skip | Notes |
|----------|----------|-------|
| FMS development | Yes | Skip external systems while developing core FMS |
| Precision control development | No | Set skip_precision=false |
| Robot arm development | No | Set skip_robot_arm=false |
| Full system integration test | No | All skip flags = false |
| Demo for stakeholders | Yes | Shows complete happy path |
| Debugging navigation issues | Yes | Skip external delays to focus on nav2 |
| Testing error recovery | Depends | See error scenarios section |

---

## Skip Mode Parameters

### FMS Launch Parameters

**Parameter Name:** `skip_robot_arm`
- **Type:** Boolean
- **Default:** false
- **Valid Values:** true, false
- **Description:** Skip robot arm food loading
- **Effect:** FMS automatically publishes `food_loaded` message after delay

**Parameter Name:** `skip_precision`
- **Type:** Boolean
- **Default:** false
- **Valid Values:** true, false
- **Description:** Skip precision parking
- **Effect:** FMS automatically publishes `precision_parked` message after delay

**Parameter Name:** `skip_mode_timing`
- **Type:** String
- **Default:** "realistic"
- **Valid Values:** "fast" (1s delays), "realistic" (2-3s delays), "slow" (5-10s delays)
- **Description:** Controls mock message delay timing
- **Effect:** Adjusts how quickly external team operations are simulated

### Typical Configurations

#### Configuration 1: Full Skip (Recommended for Demo)

```bash
ros2 run fms fms_node --ros-args \
    -p skip_robot_arm:=true \
    -p skip_precision:=true \
    -p skip_mode_timing:="realistic"
```

**Flow:** Order → Navigation → Point13 → Mock Parking (2s) → Mock Loading (3s) → Table Navigation → Return to Parking

**Duration:** ~90 seconds per complete delivery

---

#### Configuration 2: Skip Precision Only

```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=true \
    -p skip_robot_arm:=false
```

**Use Case:** Testing Robot Arm team integration while FMS is still being developed

**Flow:** FMS handles point13 → FMS mocks precision parking (2s) → Waits for Robot Arm `food_loaded` message → Continues

**Duration:** Depends on actual robot arm loading time

---

#### Configuration 3: Skip Robot Arm Only

```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=false \
    -p skip_robot_arm:=true
```

**Use Case:** Testing Precision Control team integration while FMS is still being developed

**Flow:** FMS handles point13 → Waits for Precision Control `precision_parked` message → FMS mocks robot arm loading (3s) → Continues

**Duration:** Depends on actual precision parking time

---

#### Configuration 4: No Skip (Integration with All Teams)

```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=false \
    -p skip_robot_arm:=false
```

**Use Case:** Full system integration test

**Flow:** All steps handled by respective teams

**Duration:** Depends on actual team implementations

---

## Mock Message Behavior

### Precision Parking Mock

**Activation:** When `skip_precision:=true` AND robot reaches `AT_POINT13` state

**Timing:**
- Fast Mode: 1 second delay
- Realistic Mode: 2 seconds delay
- Slow Mode: 5 seconds delay

**Mock Message Content:**
```
Topic: /fms/precision_parked
Message Type: std_msgs/String
Content: "precision_parked:pinky1"
```

**Simulated Robot State:**
- Robot position: Remains at point13 (0.585, 0.63)
- Robot orientation: Changed to face kitchen (θ ≈ π)
- Simulated final position: pickup_spot (0.47, 0.63, π)

**FMS Response:**
```
1. Publishes mock precision_parked message
2. Updates robot state: AT_POINT13 → PARKING_COMPLETE
3. Waits for next external trigger (food_loaded)
4. Timeout: 60 seconds (will emit warning if not received)
```

**Console Output:**
```
[INFO] [fms_node]: [SKIP MODE] Simulating precision parking for pinky1 (delay: 2.0s)
[INFO] [fms_node]: [SKIP MODE] Publishing mock precision_parked message
[DEBUG] [fms_node]: Robot pinky1 state: PARKING_COMPLETE
```

---

### Food Loading Mock

**Activation:** When `skip_robot_arm:=true` AND robot reaches `PARKING_COMPLETE` state

**Timing:**
- Fast Mode: 1 second delay
- Realistic Mode: 3 seconds delay
- Slow Mode: 10 seconds delay

**Mock Message Content:**
```
Topic: /fms/food_loaded
Message Type: std_msgs/String
Content: "food_loaded:pinky1"
```

**Simulated Robot State:**
- Robot food load: 2.5 kg (simulated)
- Robot position: pickup_spot (0.47, 0.63)
- Loading start time: Logged in FMS state

**FMS Response:**
```
1. Publishes mock food_loaded message
2. Updates robot state: PARKING_COMPLETE → FOOD_LOADED
3. Publishes new navigation goal to assigned table
4. Transitions to NAVIGATING_TO_TABLE state
```

**Console Output:**
```
[INFO] [fms_node]: [SKIP MODE] Simulating food loading for pinky1 (delay: 3.0s)
[INFO] [fms_node]: [SKIP MODE] Publishing mock food_loaded message
[DEBUG] [fms_node]: Robot pinky1 state: FOOD_LOADED
[DEBUG] [fms_node]: Publishing new goal: pinky1 → table1
```

---

## Complete Skip Mode Workflow

### Scenario: Single Robot, Full Delivery (Skip Both)

**Setup:**
```bash
# Terminal 1: Start FMS in skip mode
ros2 run fms fms_node --ros-args \
    -p skip_robot_arm:=true \
    -p skip_precision:=true \
    -p skip_mode_timing:="realistic"

# Terminal 2: Send test order
python3 fms/scripts/send_order.py --table 1
```

**Timeline:**

| Time (s) | Component | Action | Robot State |
|----------|-----------|--------|------------|
| 0-60 | Robot | Navigate to point13 | NAVIGATING_TO_POINT13 |
| 60 | FMS | Robot reaches point13 | AT_POINT13 |
| 60-62 | FMS Mock | Simulate precision parking | AT_POINT13 (waiting) |
| 62 | FMS | Publish precision_parked | PARKING_COMPLETE |
| 62-65 | FMS Mock | Simulate food loading | PARKING_COMPLETE (waiting) |
| 65 | FMS | Publish food_loaded | FOOD_LOADED |
| 65-130 | Robot | Navigate to table1 | NAVIGATING_TO_TABLE |
| 130 | FMS | Robot reaches table1 | AT_TABLE |
| 130-300 | GUI | Customer delivery in progress | AT_TABLE (waiting) |
| 300* | GUI | Customer clicks "Delivery Complete" | DELIVERING |
| 300-360 | Robot | Navigate to parking_spot | RETURNING_TO_PARKING |
| 360 | FMS | Robot reaches parking | IDLE (task complete) |

* Assuming customer completes delivery immediately; timeout is 300 seconds

**Expected Console Output:**
```
[INFO] [fms_node]: FMS Started (skip_precision=true, skip_robot_arm=true)
[DEBUG] [fms_node]: Fleet Status: pinky1=IDLE
[INFO] [fms_node]: Order received: order_001 → table1
[DEBUG] [fms_node]: Assigned pinky1 to order_001
[DEBUG] [fms_node]: Publishing goal: pinky1 → point13
[DEBUG] [fms_node]: Robot pinky1 state: NAVIGATING_TO_POINT13
...
[INFO] [fms_node]: Robot pinky1 reached point13
[DEBUG] [fms_node]: Robot pinky1 state: AT_POINT13
[INFO] [fms_node]: [SKIP MODE] Simulating precision parking for pinky1 (delay: 2.0s)
...
[INFO] [fms_node]: [SKIP MODE] Publishing mock precision_parked message
[DEBUG] [fms_node]: Robot pinky1 state: PARKING_COMPLETE
[INFO] [fms_node]: [SKIP MODE] Simulating food loading for pinky1 (delay: 3.0s)
...
[INFO] [fms_node]: [SKIP MODE] Publishing mock food_loaded message
[DEBUG] [fms_node]: Robot pinky1 state: FOOD_LOADED
[DEBUG] [fms_node]: Publishing goal: pinky1 → table1
[DEBUG] [fms_node]: Robot pinky1 state: NAVIGATING_TO_TABLE
...
[INFO] [fms_node]: Robot pinky1 reached table1
[DEBUG] [fms_node]: Robot pinky1 state: AT_TABLE
[INFO] [fms_node]: Delivery complete for order_001
[DEBUG] [fms_node]: Publishing goal: pinky1 → parking_spot_1
[DEBUG] [fms_node]: Robot pinky1 state: RETURNING_TO_PARKING
...
[INFO] [fms_node]: Robot pinky1 reached parking_spot_1
[DEBUG] [fms_node]: Robot pinky1 state: IDLE
```

---

## Testing Procedures

### Test 1: Verify Mock Precision Parking Delay

**Objective:** Confirm precision parking simulation runs at correct timing

**Steps:**

1. Start FMS with skip_precision=true, skip_robot_arm=false
   ```bash
   ros2 run fms fms_node --ros-args \
       -p skip_precision:=true \
       -p skip_robot_arm:=false \
       -p skip_mode_timing:="realistic"
   ```

2. Send test order
   ```bash
   python3 fms/scripts/send_order.py --table 1
   ```

3. Monitor FMS logs and note timestamp of:
   - Robot reaches point13 (AT_POINT13 state)
   - Mock precision_parked published (PARKING_COMPLETE state)

4. Calculate actual delay: `time_PARKING_COMPLETE - time_AT_POINT13`

**Expected Result:** Delay should be 2.0 ± 0.2 seconds for "realistic" mode

**Pass Criteria:** Actual delay within ±0.2 seconds of configured timing

---

### Test 2: Verify Mock Food Loading Delay

**Objective:** Confirm food loading simulation runs at correct timing

**Steps:**

1. Start FMS with skip_precision=false, skip_robot_arm=true
   ```bash
   ros2 run fms fms_node --ros-args \
       -p skip_precision:=false \
       -p skip_robot_arm:=true \
       -p skip_mode_timing:="realistic"
   ```

2. Manually publish precision_parked when robot reaches point13
   ```bash
   # In separate terminal, wait for point13 arrival then:
   ros2 topic pub -1 /fms/precision_parked std_msgs/String "data: 'precision_parked:pinky1'"
   ```

3. Monitor FMS logs and note timestamp of:
   - Mock precision_parked received (PARKING_COMPLETE state)
   - Mock food_loaded published (FOOD_LOADED state)

4. Calculate actual delay: `time_FOOD_LOADED - time_PARKING_COMPLETE`

**Expected Result:** Delay should be 3.0 ± 0.3 seconds for "realistic" mode

**Pass Criteria:** Actual delay within ±0.3 seconds of configured timing

---

### Test 3: Complete Delivery with Both Skips

**Objective:** Verify full delivery flow from order to parking completion

**Steps:**

1. Start FMS in full skip mode
   ```bash
   ros2 run fms fms_node --ros-args \
       -p skip_precision:=true \
       -p skip_robot_arm:=true \
       -p skip_mode_timing:="realistic"
   ```

2. Monitor fleet status in another terminal
   ```bash
   ros2 topic echo /fms/fleet_status
   ```

3. Send test order
   ```bash
   python3 fms/scripts/send_order.py --table 1
   ```

4. Verify state transitions:
   - IDLE → NAVIGATING_TO_POINT13 → AT_POINT13 → PARKING_COMPLETE → FOOD_LOADED → NAVIGATING_TO_TABLE → AT_TABLE

5. Wait for table arrival, then publish delivery_complete
   ```bash
   # When robot reaches table1, manually trigger completion:
   ros2 topic pub -1 /fms/delivery_complete fleet_interfaces/DeliveryComplete \
       "order_id: 'order_001' table_number: 'T01'"
   ```

6. Verify final transitions:
   - AT_TABLE → DELIVERING → RETURNING_TO_PARKING → IDLE

**Expected Result:** All state transitions occur in correct order with appropriate timing

**Pass Criteria:**
- All states visited in order ✓
- No state transitions skipped ✓
- Timeouts don't occur (except delivery_complete which is manual) ✓

---

### Test 4: Multi-Robot Concurrent Deliveries

**Objective:** Verify skip mode works with multiple robots executing simultaneously

**Steps:**

1. Start FMS with both robots enabled in config
   ```bash
   # Verify fms_config.yaml has pinky1 and pinky2 enabled
   ros2 run fms fms_node --ros-args \
       -p skip_precision:=true \
       -p skip_robot_arm:=true \
       -p skip_mode_timing:="realistic"
   ```

2. Send orders for different tables
   ```bash
   # Terminal 2: Send order for table 1 (pinky1)
   python3 fms/scripts/send_order.py --table 1

   # Wait 10 seconds, then Terminal 3: Send order for table 3 (pinky2)
   python3 fms/scripts/send_order.py --table 3
   ```

3. Monitor fleet status to verify:
   - Both robots navigating concurrently
   - No resource conflicts
   - State transitions for each robot independent

4. When both reach tables, publish delivery_complete for both
   ```bash
   ros2 topic pub -1 /fms/delivery_complete fleet_interfaces/DeliveryComplete \
       "order_id: 'order_001' table_number: 'T01'"

   ros2 topic pub -1 /fms/delivery_complete fleet_interfaces/DeliveryComplete \
       "order_id: 'order_002' table_number: 'T03'"
   ```

**Expected Result:** Both robots execute deliveries concurrently without interference

**Pass Criteria:**
- Both robots reach respective point13 locations ✓
- Both receive mock precision_parked ✓
- Both proceed to different tables ✓
- Both return to parking without conflicts ✓

---

### Test 5: Skip Mode Timing Variations

**Objective:** Verify skip_mode_timing parameter works correctly

**Steps:**

Repeat Test 1 three times with different timing modes:

1. **Fast Mode (1s delays):**
   ```bash
   ros2 run fms fms_node --ros-args \
       -p skip_precision:=true \
       -p skip_robot_arm:=true \
       -p skip_mode_timing:="fast"
   ```
   Expected: Precision parking delay ≈ 1.0s, Food loading delay ≈ 1.0s

2. **Realistic Mode (2-3s delays):**
   ```bash
   ros2 run fms fms_node --ros-args \
       -p skip_precision:=true \
       -p skip_robot_arm:=true \
       -p skip_mode_timing:="realistic"
   ```
   Expected: Precision parking delay ≈ 2.0s, Food loading delay ≈ 3.0s

3. **Slow Mode (5-10s delays):**
   ```bash
   ros2 run fms fms_node --ros-args \
       -p skip_precision:=true \
       -p skip_robot_arm:=true \
       -p skip_mode_timing:="slow"
   ```
   Expected: Precision parking delay ≈ 5.0s, Food loading delay ≈ 10.0s

**Pass Criteria:** Each timing mode produces delays within ±20% of expected values

---

## Error Scenarios in Skip Mode

### Scenario 1: Robot Fails to Navigate to Point13

**Setup:**
- Skip mode enabled
- Robot path blocked or navigation failed

**Expected Behavior:**
```
[ERROR] [fms_node]: Robot pinky1 failed to reach point13 (timeout after 120s)
[ERROR] [fms_node]: Navigating to point13 failed with status: ABORTED
[DEBUG] [fms_node]: Robot pinky1 state: IDLE (task cancelled)
```

**Skip Mode Behavior:** FMS does NOT publish mock messages (correct - external teams shouldn't respond to failed operations)

**Recovery:** Manually clear obstacle and resend order

---

### Scenario 2: Delivery Timeout at Table

**Setup:**
- Skip mode enabled
- Customer doesn't click delivery_complete within timeout (300s)

**Expected Behavior:**
```
[WARN] [fms_node]: Robot pinky1 at table1 timeout (waiting >300s for delivery_complete)
[WARN] [fms_node]: Cancelling delivery task order_001
[DEBUG] [fms_node]: Robot pinky1 state: IDLE (task cancelled due to timeout)
```

**Skip Mode Behavior:** FMS waits for manual delivery_complete; skip mode doesn't auto-complete delivery (correct - customer interaction is real)

**Recovery:** Publish delivery_complete manually or cancel task

---

### Scenario 3: Multiple Orders Exceed Fleet Capacity

**Setup:**
- Skip mode enabled with 2 robots
- Send 4 orders simultaneously

**Expected Behavior:**
```
[INFO] [fms_node]: Order 1 → assigned to pinky1
[INFO] [fms_node]: Order 2 → assigned to pinky2
[INFO] [fms_node]: Order 3 → queued (no available robots)
[INFO] [fms_node]: Order 4 → queued (no available robots)
...
[INFO] [fms_node]: Order 3 → assigned to pinky1 (now available)
```

**Skip Mode Behavior:** Queuing works normally; mock messages still apply per robot

**Recovery:** No intervention needed; FMS automatically assigns queued orders as robots become available

---

## Debugging Skip Mode

### Enable Debug Logging

```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=true \
    -p skip_robot_arm:=true \
    --log-level fms_node:=DEBUG
```

### Monitor Specific Topics

```bash
# Monitor fleet status
ros2 topic echo /fms/fleet_status --field-depth 0

# Monitor all FMS publications
ros2 topic list | grep /fms | xargs -I {} ros2 topic echo {} --once

# Monitor robot pose (switch to robot domain first)
export ROS_DOMAIN_ID=11  # pinky1 domain
ros2 topic echo /pinky1/pose
```

### Check FMS Node Parameters

```bash
# List all FMS node parameters
ros2 param list | grep fms_node

# Get specific parameter values
ros2 param get /fms_node skip_precision
ros2 param get /fms_node skip_robot_arm
ros2 param get /fms_node skip_mode_timing
```

### Log File Analysis

```bash
# Find FMS log files
find ~/.ros/log -name "fms_node*" -type f

# Search logs for specific events
grep "SKIP MODE" ~/.ros/log/*/fms_node/stdout.log
grep "ERROR" ~/.ros/log/*/fms_node/stdout.log
```

---

## Continuous Integration (CI) Testing

### Skip Mode for Automated Tests

Skip mode is ideal for CI/CD pipelines because:
- No external system dependencies
- Deterministic timing
- Fast execution
- No hardware required

### Example GitHub Actions Workflow

```yaml
name: FMS Skip Mode Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v2

      - name: Setup ROS 2
        run: |
          source /opt/ros/jazzy/setup.bash

      - name: Build FMS
        run: |
          cd roscamp-repo-1
          colcon build --packages-select fms
          source install/setup.bash

      - name: Run Skip Mode Test (Full Flow)
        run: |
          ros2 run fms fms_node --ros-args \
              -p skip_precision:=true \
              -p skip_robot_arm:=true \
              -p skip_mode_timing:="fast" &
          sleep 2

          python3 fms/scripts/send_order.py --table 1

          # Wait for delivery completion
          sleep 120

          # Publish delivery complete
          ros2 topic pub -1 /fms/delivery_complete \
              fleet_interfaces/DeliveryComplete \
              "order_id: 'test_001' table_number: 'T01'"

          # Wait for robot to return to parking
          sleep 60
```

---

## Troubleshooting Skip Mode

### Issue: Mock Messages Not Being Published

**Symptom:**
```
[DEBUG] [fms_node]: Robot pinky1 state: AT_POINT13
# ... nothing happens, no precision_parked published
```

**Diagnosis:**
1. Verify skip_precision=true is set
   ```bash
   ros2 param get /fms_node skip_precision
   ```
2. Check if robot actually reached AT_POINT13 state
   ```bash
   ros2 topic echo /fms/fleet_status
   ```

**Solution:**
- Ensure parameter is set before launching FMS
- Verify navigation completed successfully (not stuck)
- Check FMS logs for errors: `--log-level fms_node:=DEBUG`

---

### Issue: Inconsistent Mock Message Timing

**Symptom:** Delays vary significantly (e.g., 2.1s, 2.8s, 2.2s when expecting 2.0s)

**Diagnosis:**
1. FMS node CPU usage might be high
2. ROS 2 middleware latency
3. System load from other processes

**Solution:**
1. Check system load
   ```bash
   top -b -n1 | head -20
   ```
2. Close unnecessary applications
3. Use "fast" mode for testing to reduce sensitivity to timing variance

---

### Issue: Skip Mode Works but Navigation Still Fails

**Symptom:**
```
[INFO] [fms_node]: [SKIP MODE] Publishing mock precision_parked message
# But robot never navigates to table (stuck at point13)
```

**Diagnosis:** Navigation system issue, not skip mode issue

**Solution:**
- Check Nav2 status independently
- Verify map is loaded correctly
- Check AMCL localization
- See /home/gw/kitchmatics/roscamp-repo-1/README.md troubleshooting section

---

## Best Practices for Skip Mode Testing

### Do's

✓ Use skip mode during FMS development
✓ Use skip mode for rapid iteration/debugging
✓ Document which skip flags you use for each test
✓ Use realistic timing mode for demo to stakeholders
✓ Combine skip mode with real navigation for hybrid testing
✓ Monitor logs to understand state transitions

### Don'ts

✗ Don't assume skip mode tests verify external team integration
✗ Don't ship code without testing with skip_precision/skip_robot_arm=false
✗ Don't use skip mode to mask navigation problems
✗ Don't test external team APIs without turning skip flags off
✗ Don't modify skip mode implementation without coordinating with team

---

## Migration from Skip Mode to Live Systems

### Step 1: Test with One Team (Precision Control)

```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=false \
    -p skip_robot_arm:=true \
    -p skip_mode_timing:="realistic"
```

**Coordination:**
- Notify Precision Control team of test schedule
- Ask them to monitor `/fms/goal_arrived` topic
- They manually publish `/fms/precision_parked` when ready

**Verification:**
- FMS correctly handles real precision_parked messages
- Timing constraints are met (precision parking within 10s)

---

### Step 2: Test with Other Team (Robot Arm)

```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=true \
    -p skip_robot_arm:=false \
    -p skip_mode_timing:="realistic"
```

**Coordination:**
- Notify Robot Arm team of test schedule
- FMS will publish mock precision_parked automatically
- Robot Arm team monitors `/fms/precision_parked` topic
- They manually publish `/fms/food_loaded` when ready

**Verification:**
- FMS correctly handles real food_loaded messages
- Timing constraints are met (food loading within 60s)

---

### Step 3: Full Integration Test

```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=false \
    -p skip_robot_arm:=false
```

**Coordination:**
- Schedule with both Precision Control and Robot Arm teams
- All teams have systems running and monitoring
- Pre-agreed timeout values and error procedures
- Dedicated communication channel (Slack) for real-time issues

**Verification:**
- Complete delivery flow works end-to-end
- All timing constraints met
- No message format mismatches
- Error recovery procedures effective

---

## Appendix A: Skip Mode Parameter Reference

```yaml
# FMS Launch Parameters for Skip Mode
skip_mode:
  # Skip Precision Control team operations
  skip_precision:
    type: bool
    default: false
    description: "Auto-publish precision_parked message"
    effect: "When enabled, FMS publishes mock precision_parked after delay"

  # Skip Robot Arm team operations
  skip_robot_arm:
    type: bool
    default: false
    description: "Auto-publish food_loaded message"
    effect: "When enabled, FMS publishes mock food_loaded after delay"

  # Control timing of mock messages
  skip_mode_timing:
    type: string
    default: "realistic"
    valid_values: ["fast", "realistic", "slow"]
    timings:
      fast:
        precision_parked_delay: 1.0  # seconds
        food_loaded_delay: 1.0       # seconds
      realistic:
        precision_parked_delay: 2.0  # seconds
        food_loaded_delay: 3.0       # seconds
      slow:
        precision_parked_delay: 5.0  # seconds
        food_loaded_delay: 10.0      # seconds
```

---

## Appendix B: Mock Message Topics Reference

| Topic | Direction | Skip Flag | Message Type | Timing |
|-------|-----------|-----------|--------------|--------|
| `/fms/goal_arrived` | FMS → External | N/A | std_msgs/String | Real (at point13 arrival) |
| `/fms/precision_parked` | FMS → FMS (Mock) | skip_precision | std_msgs/String | Delayed per skip_mode_timing |
| `/fms/food_loaded` | FMS → FMS (Mock) | skip_robot_arm | std_msgs/String | Delayed per skip_mode_timing |
| `/fms/fleet_status` | FMS → All | N/A | FleetStatus | Every 1 second |
| `/fms/delivery_complete` | Main Server → FMS | N/A | DeliveryComplete | Real (from GUI) |

---

## Appendix C: State Diagram with Skip Mode

```
IDLE
  │
  ├─ (receive order)
  ▼
NAVIGATING_TO_POINT13
  │
  ├─ (reach point13, position error < 0.1m)
  ▼
AT_POINT13
  │
  ├─ (skip_precision=false) → Waits for precision_parked message
  ├─ (skip_precision=true) → Publishes mock precision_parked after delay
  ▼
PARKING_COMPLETE
  │
  ├─ (skip_robot_arm=false) → Waits for food_loaded message
  ├─ (skip_robot_arm=true) → Publishes mock food_loaded after delay
  ▼
FOOD_LOADED
  │
  ├─ (publish navigation goal to table)
  ▼
NAVIGATING_TO_TABLE
  │
  ├─ (reach table, position error < 0.1m)
  ▼
AT_TABLE
  │
  ├─ (receive delivery_complete from GUI) ← Always real, never skipped
  ▼
DELIVERING
  │
  ├─ (publish navigation goal to parking)
  ▼
RETURNING_TO_PARKING
  │
  ├─ (reach parking, position error < 0.1m)
  ▼
IDLE
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-25 | Integration Coordinator | Initial guide |

---

## Support and Questions

For questions about skip mode:
- Check FMS logs with DEBUG level
- Review this document's troubleshooting section
- Contact FMS team in #fms-channel Slack
- File issue with "skip_mode" label on Jira
