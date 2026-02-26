# ROS2 Navigation Validation Report
**Generated: 2026-02-26**
**System: Kitchmatics FMS with Pinky Mobile Robots**

---

## Executive Summary

**Status: CRITICAL ISSUES IDENTIFIED**

The ROS2 navigation system for the Kitchmatics FMS has several critical issues that need immediate resolution:

1. **Nav2 Not Running on Pinky Robots**: Navigation nodes are not active on pinky1/pinky2
2. **AMCL Localization Not Active**: No AMCL pose estimates being published
3. **Domain Bridge Not Forwarding Navigation Topics**: Nav2 action servers not accessible
4. **Navigation Services Unavailable**: /navigate_to_pose action servers not responding

---

## Current System Architecture

### Infrastructure
- **Main PC (Domain ID 25)**:
  - FMS Node: RUNNING
  - Domain Bridge: Configured but not fully working
  - Coordinator: RUNNING

- **Pinky1 (Domain ID 11, IP: 192.168.1.7)**:
  - cooking_interface_node: RUNNING
  - kitchmatics_bridge_11: RUNNING
  - **Nav2 Stack: NOT RUNNING**
  - Expected: /pinky1/navigate_to_pose action server

- **Pinky2 (Domain ID 12, IP: 192.168.1.6)**:
  - Status: SSH Not Accessible
  - Expected: Navigation stack with /pinky2/navigate_to_pose

- **Pinky3 (Domain ID 13, IP: 192.168.1.11)**:
  - Disabled in configuration

---

## Detailed Findings

### 1. Navigation Configuration (✓ Configured)

**File**: `/home/gw/kitchmatics/roscamp-repo-1/mobile_robot/params/nav2_params.yaml`

**AMCL Configuration**:
```yaml
amcl:
  max_particles: 3000        # Adequate for small robot
  min_particles: 500         # Good
  laser_likelihood_max_dist: 0.5
  transform_tolerance: 0.5   # 500ms tolerance
  scan_topic: scan
  set_initial_pose: false    # FMS provides initial pose
```

**Local Costmap**:
```yaml
local_costmap:
  update_frequency: 30.0     # 30Hz
  robot_radius: 0.055        # 5.5cm
  inflation_radius: 0.08     # 8cm total clearance
```

**Global Costmap**:
```yaml
global_costmap:
  inflation_radius: 0.10     # 10cm for path planning
```

**Controller (RPP)**:
```yaml
FollowPath:
  plugin: RegulatedPurePursuitController
  desired_linear_vel: 0.15   # 15cm/s
  lookahead_dist: 0.08       # 8cm (scaled for small robot)
```

**Planner (NavFn with A*)**:
```yaml
GridBased:
  plugin: NavfnPlanner
  use_astar: true
  tolerance: 0.02
```

### Status: ✓ Configuration appears well-tuned for small robots

---

### 2. Domain Bridge Configuration (✓ Configured, ✗ Not Fully Working)

**File**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml`

**Pinky1 Topics Configured**:
- ✓ /pinky1/amcl_pose (11→25, RELIABLE)
- ✓ /pinky1/scan (11→25, BEST_EFFORT)
- ✓ /pinky1/odom (11→25, BEST_EFFORT)
- ✓ /pinky1/initialpose (25→11, RELIABLE)
- ✓ /pinky1/navigate_to_pose/_action/* (bi-directional)

**Pinky2 Topics Configured**:
- ✓ All same as Pinky1

**Domain Bridge Status**:
- Bridge is running on main PC (Domain ID 25)
- Bridge is NOT forwarding navigation topics properly
- AMCL pose not appearing on domain 25
- Navigation action servers not accessible on domain 25

---

### 3. FMS Fleet Controller (✓ Partially Working)

**File**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py`

**Fleet Status** (from `/fms/fleet_status` topic):
```
Robot: pinky1
  Status: IDLE
  Position: (0.0, 0.0, 0.0)  ← NO REAL POSE (Expected from AMCL)
  Battery: 0.0V (Not connected)

Robot: pinky2
  Status: IDLE
  Position: Not available
```

**Issues**:
- Robots showing position (0,0,0) instead of actual AMCL poses
- Battery voltage not being updated
- Robot states are not being updated from navigation feedback

---

### 4. Navigation Nodes Status

**Pinky1 (Domain ID 11)**:
```
Active Nodes:
  /cooking_interface_node
  /kitchmatics_bridge_11

Missing Nodes:
  ✗ /amcl
  ✗ /map_server
  ✗ /planner_server
  ✗ /controller_server
  ✗ /behavior_server
  ✗ /bt_navigator
  ✗ /velocity_smoother
```

**Pinky2 (Domain ID 12)**:
```
Status: UNREACHABLE
Expected nodes not running
```

---

### 5. AMCL Localization Status (✗ Not Active)

**Expected Flow**:
```
Pinky1 (Domain 11):
  /scan (LiDAR) → AMCL → /amcl_pose
           ↓
    Domain Bridge (25)
           ↓
      FMS Node
```

**Actual Status**:
- No AMCL node running
- No /amcl_pose topic on domain 11
- No /pinky1/amcl_pose on domain 25
- No localization feedback to FMS

---

### 6. Action Server Status (✗ Not Available)

**Expected**:
```
/pinky1/navigate_to_pose/_action/send_goal  (Domain 25)
  ↓ (Domain Bridge)
/navigate_to_pose/_action/send_goal  (Domain 11)
```

**Actual**:
- No action servers found on domain 11
- No bridged action servers on domain 25
- FMS cannot send navigation goals

---

## Requirements Validation

### Requirement 7: /pose Updates Trigger Node Release
**Status**: ✗ NOT TESTABLE
- **Reason**: No AMCL pose being published
- **Impact**: Node release mechanism cannot be verified
- **Action Needed**: Activate Nav2 stack first

### Requirement 8: Path Conflict Resolution
**Status**: ✗ NOT TESTABLE
- **Reason**: Navigation system not operational
- **Impact**: Multi-robot path planning not working
- **Action Needed**: Get single-robot navigation working first

### Requirement 5: Multiple Pinkys Simultaneous Operation
**Status**: ✗ NOT TESTABLE
- **Reason**: Pinky2 unreachable, Nav2 not running on Pinky1
- **Impact**: Cannot test multi-robot coordination
- **Action Needed**: Fix Pinky1 connectivity, then address Pinky2

---

## Root Cause Analysis

### Issue 1: Nav2 Stack Not Launched

**Evidence**:
- No bt_navigator, planner_server, or controller_server nodes on Pinky1
- No AMCL node running
- nav2_params.yaml is well-configured but not being used

**Likely Causes**:
1. pinky_navigation.launch.py not being called
2. Nav2 package dependencies not installed
3. Launch file path incorrect in pinky robot bringup
4. Robot bringup only launching lamp_module, not navigation

**Evidence**:
```bash
ps aux on Pinky1 shows:
  /bin/bash /home/pinky/pinky_devices/lamp_module_bringup
  → Only lamp module, NO Nav2 bringup
```

### Issue 2: Domain Bridge Not Forwarding Nav2 Topics

**Reason**: Nav2 topics don't exist on domain 11 to bridge

**Dependencies**:
1. Nav2 must be running on Pinky1 first
2. Then domain bridge will forward topics
3. FMS will receive /pinky1/amcl_pose on domain 25

---

## Action Items (Priority Order)

### Phase 1: Activate Navigation on Pinky1 (CRITICAL)

**Step 1**: Modify Pinky1 Bringup
- File: `/home/pinky/pinky_pro/src/pinky_pro/pinky_bringup/...`
- Add Nav2 launch to robot bringup sequence
- Ensure: `ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml`

**Step 2**: Verify Nav2 Startup
```bash
ssh pinky@192.168.1.7
export ROS_DOMAIN_ID=11
source /opt/ros/jazzy/setup.bash
ros2 node list | grep -E "amcl|planner|controller|bt_navigator"
```

**Step 3**: Check Domain Bridge Forwarding
```bash
# On main PC (Domain 25)
ros2 topic list | grep pinky1/amcl_pose
ros2 action list | grep pinky1/navigate_to_pose
```

**Step 4**: Set Initial Pose
```bash
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {
    pose: {position: {x: 0.585, y: 0.085}, orientation: {w: 1.0}},
    covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]
  }
}'
```

### Phase 2: Test AMCL Localization (CRITICAL)

**Step 1**: Verify Pose Publishing
```bash
timeout 5 ros2 topic echo /pinky1/amcl_pose --once
```

**Step 2**: Move Robot Manually and Monitor
- Move Pinky1 in actual room
- Watch /pinky1/amcl_pose for updates
- Check covariance for convergence

**Step 3**: Check Pose Covariance
```
Expected: <0.1m² in x,y (well-localized)
Initial: ~0.25m² (converging)
```

### Phase 3: Test Navigation Goals (CRITICAL)

**Step 1**: Send Simple Goal
```bash
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{
  pose: {
    header: {frame_id: "map"},
    pose: {position: {x: 1.0, y: 0.5}, orientation: {w: 1.0}}
  }
}'
```

**Step 2**: Monitor Navigation
- Watch /pinky1/navigate_to_pose/_action/feedback
- Check costmap updates
- Verify path planning

**Step 3**: Verify Path Execution
- Robot should move toward goal
- Controller should be active
- Behavior recovery should trigger if stuck

### Phase 4: Activate Pinky2 (HIGH)

**Step 1**: Fix SSH Connectivity
- Check network: `ping 192.168.1.6`
- Check firewall/routing
- Verify router configuration

**Step 2**: Replicate Nav2 Setup on Pinky2
- Same as Phase 1, but for domain ID 12
- Set initial pose to (0.585, 0.255, 0)

**Step 3**: Verify Domain Bridge
- Check /pinky2/amcl_pose on domain 25
- Verify /pinky2/navigate_to_pose action

### Phase 5: Multi-Robot Coordination (MEDIUM)

**Step 1**: Test FMS Task Assignment
- Assign task to Pinky1
- Verify robot accepts and executes
- Check pose updates in FMS fleet_status

**Step 2**: Test Path Conflict Resolution
- Send goal to Pinky1
- Send conflicting goal to Pinky2
- Watch FMS collision_avoidance behavior

**Step 3**: Verify Node Release Mechanism
- Monitor /pose topic updates
- Verify nodes are released when robot leaves
- Check zone reservations

---

## Performance Metrics to Monitor

Once navigation is operational:

### Navigation Performance
```
Metric                          Target      Expected
Time to goal (1m distance)      30-45s      < 60s
Navigation success rate         95%         100% (small space)
Path replanning frequency       2-5 Hz      Smooth trajectories
Max path deviation              0.1m        < 0.15m
```

### AMCL Localization
```
Pose covariance after init      < 0.01m²    Stable after 5s
Covariance convergence time     < 10s       Fast convergence
Pose estimate stability         +/- 0.05m   Low drift
Update frequency                20 Hz       Continuous
```

### Multi-Robot Coordination
```
Simultaneous robot operations   3 robots    Both without interference
Node release time               < 2s        Quick zone handover
Path conflict resolution        100%        Smooth re-planning
Collision prevention incidents  0           Full safety
```

---

## Technical Notes

### AMCL Configuration Rationale
- **min_particles: 500**: Sufficient for well-textured small space
- **max_particles: 3000**: Allows convergence during initialization
- **laser_model_type: likelihood_field**: Best for structured rooms
- **update_min_d: 0.01m**: Triggers AMCL on every 1cm movement (precise)
- **update_min_a: 0.05rad**: Triggers AMCL on every ~3° rotation (precise)

### Costmap Rationale
- **local_costmap inflation: 0.08m**: Robot (5.5cm) + 2.5cm safety margin
- **global_costmap inflation: 0.10m**: Path planning clearance
- **raytrace_max_range: 0.8m**: Detects obstacles up to 80cm
- **obstacle_max_range: 0.5m**: Safety margin for dynamic obstacles

### Controller Rationale
- **lookahead_dist: 0.08m**: 8cm look-ahead for precision path following
- **desired_linear_vel: 0.15m/s**: 15cm/s for narrow spaces
- **rotate_to_heading: true**: Turn in place before tight maneuvers
- **use_approach_velocity_scaling**: Slow near obstacles

---

## Network Topology

```
┌─────────────────────────────────────────────────────┐
│           Main PC (Domain ID 25)                    │
│  ┌──────────────────────────────────────────────┐  │
│  │  FMS Node                                    │  │
│  │  - Task Manager                             │  │
│  │  - Fleet Controller                         │  │
│  │  - Zone Manager                             │  │
│  │  - Collision Avoidance                      │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  Domain Bridge                               │  │
│  │  Bridges: 11↔25, 12↔25, 13↔25, 20↔25, 21↔25│  │
│  │  Status: ✗ Nav2 topics not bridging yet      │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
        │ Ethernet           │ Ethernet         │ Ethernet
        │ (192.168.1.7)      │ (192.168.1.6)    │ (192.168.1.11)
        │                    │                  │
┌───────────────────┐ ┌──────────────────┐ ┌─────────────────┐
│  Pinky1           │ │ Pinky2           │ │ Pinky3          │
│  Domain ID 11     │ │ Domain ID 12     │ │ Domain ID 13    │
│  ✗ Nav2 NOT RUN   │ │ ? UNREACHABLE    │ │ Disabled        │
│  ✓ LiDAR/Wheel OK │ │ ? Unknown        │ │                 │
└───────────────────┘ └──────────────────┘ └─────────────────┘
```

---

## Recommended Next Steps

1. **SSH into Pinky1** and check bringup script
2. **Add Nav2 launch** to robot startup sequence
3. **Restart Pinky1** robots
4. **Verify Nav2 nodes** appear on domain 11
5. **Check domain bridge** forwards topics to domain 25
6. **Test single-robot navigation** with manual goals
7. **Run Phase 4** to restore Pinky2
8. **Test multi-robot coordination** per Phase 5

---

## Appendix: File Locations

```
Configuration Files:
  /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/params/nav2_params.yaml
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml

Launch Files:
  /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/launch/pinky_navigation.launch.py
  /home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/launch/bringup_launch.xml

FMS Source:
  /home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py
  /home/gw/kitchmatics/roscamp-repo-1/fms/fms/fleet_controller.py

Domain Bridge:
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml
  ros2 run domain_bridge domain_bridge <config>
```

---

**Report Status**: Ready for implementation
**Next Review**: After Phase 1 completion
**Prepared by**: ROS2 Navigation Validator
