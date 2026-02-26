# Domain Bridge Configuration Analysis
**Date**: 2026-02-26
**System**: Kitchmatics FMS
**Analyst**: ROS2 Domain Bridge Specialist

---

## 1. Current Environment Configuration

### Robot Network Layout
```
Main PC (FMS):      ROS_DOMAIN_ID=25  (IP: 192.168.1.?)
├── pinky1:         ROS_DOMAIN_ID=11  (IP: 192.168.1.7)
├── pinky2:         ROS_DOMAIN_ID=12  (IP: 192.168.1.6)
├── Robot Arm A:    ROS_DOMAIN_ID=20  (IP: 192.168.1.4)
└── Robot Arm B:    ROS_DOMAIN_ID=21  (IP: 192.168.1.10)
```

### Critical Finding: Domain ID Mismatch
**ISSUE**: Documentation shows inconsistent Main PC domain IDs:
- Your requirement states: `ROS_DOMAIN_ID=0` (default)
- System actually uses: `ROS_DOMAIN_ID=25`

**Evidence**:
- `/home/gw/kitchmatics/roscamp-repo-1/DEPLOY.sh` line 64: `export ROS_DOMAIN_ID=25`
- `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/run_domain_bridges.sh` line 23: `export ROS_DOMAIN_ID=25`
- All domain bridge configs bridge to domain `25`, not `0`

**Recommendation**: Update Main PC to use `ROS_DOMAIN_ID=25` as the standard.

---

## 2. Domain Bridge Configuration Files Analysis

### Available Configuration Files

```bash
/home/gw/kitchmatics/roscamp-repo-1/fms/config/
├── domain_bridge_pinky1.yaml          # Individual robot config
├── domain_bridge_pinky2.yaml          # Individual robot config
├── domain_bridge_pinky3.yaml          # Individual robot config (not active)
├── domain_bridge_nonamespace.yaml     # NO namespace approach (7KB)
├── domain_bridge_v2.yaml              # With remap support (3.7KB)
├── domain_bridge_v3.yaml              # Extended version (13KB)
├── domain_bridge_complete.yaml        # Full system with arms (21KB)
└── domain_bridge_improved.yaml        # Optimized version (7KB)
```

### Current Active Configuration

Based on `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/run_domain_bridges.sh`, the system uses:
- `domain_bridge_pinky1.yaml`
- `domain_bridge_pinky2.yaml`
- `domain_bridge_pinky3.yaml`

**Status**: These are minimal configs, likely missing critical topics.

---

## 3. Namespace vs No-Namespace Strategy

### Your Requirement: "Minimize Namespace Usage"

The system has **TWO conflicting approaches**:

#### Approach A: No Namespace (domain_bridge_nonamespace.yaml)
```yaml
# Robot publishes: /amcl_pose
# Main PC receives: /amcl_pose (same name)
- from_domain: 11
  to_domain: 25
  topics:
    /amcl_pose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
```

**Pros**:
- Simple topic names
- Matches your "minimize namespace" requirement
- Less configuration overhead

**Cons**:
- **CRITICAL ISSUE**: Topic name collision
- pinky1's `/amcl_pose` overwrites pinky2's `/amcl_pose` on Main PC
- Cannot distinguish which robot sent data
- Fleet management becomes impossible

#### Approach B: With Namespace Remapping (domain_bridge_v3.yaml)
```yaml
# Robot publishes: /amcl_pose (no namespace on robot side)
# Main PC receives: /pinky1/amcl_pose (namespace added by bridge)
- from_domain: 11
  to_domain: 25
  topics:
    amcl_pose:
      type: geometry_msgs/msg/PoseWithCovarianceStamped
      remap: pinky1/amcl_pose
```

**Pros**:
- Robots keep simple names (no namespace needed on robot)
- Main PC gets isolated topics per robot
- Fleet management works correctly
- Only the bridge adds namespaces

**Cons**:
- Slightly more complex configuration
- Bridge must handle remapping

---

## 4. Recommended Solution: Hybrid Approach

### Strategy: "No Namespace on Robots, Namespace Only on Main PC"

This satisfies your "minimize namespace" requirement while solving the collision problem:

```
┌─────────────────────────────────────────────────────┐
│  pinky1 (Domain 11)                                 │
│  Publishes: /amcl_pose, /odom, /cmd_vel            │
│  (NO namespace on robot side)                       │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Domain Bridge (with remap)
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  Main PC (Domain 25)                                │
│  Receives: /pinky1/amcl_pose                        │
│           /pinky1/odom                              │
│  Publishes to robot: /pinky1/cmd_vel → /cmd_vel    │
└─────────────────────────────────────────────────────┘
```

**Key Benefit**: Robots remain simple (no namespace), but Main PC can manage multiple robots.

---

## 5. Critical Topics Analysis

### Mobile Robots (pinky1, pinky2)

#### Must-Have Topics (Robot → Main PC)
```yaml
/amcl_pose                    # Robot localization (CRITICAL)
/odom                         # Wheel odometry (CRITICAL)
/scan                         # LiDAR data (HIGH)
/battery/voltage              # Battery status (CRITICAL)
/tf                           # Transform tree (CRITICAL)
/tf_static                    # Static transforms (CRITICAL)
/navigate_to_pose/_action/feedback  # Navigation progress (HIGH)
/navigate_to_pose/_action/status    # Navigation state (HIGH)
```

#### Must-Have Topics (Main PC → Robot)
```yaml
/cmd_vel                      # Velocity commands (CRITICAL)
/initialpose                  # Set robot position (HIGH)
/goal_pose                    # Navigation goal (HIGH)
/navigate_to_pose/_action/send_goal    # Start navigation (CRITICAL)
/navigate_to_pose/_action/cancel_goal  # Stop navigation (HIGH)
/navigate_to_pose/_action/get_result   # Get navigation result (MEDIUM)
```

### Robot Arms (armA at 192.168.1.4, armB at 192.168.1.10)

Based on `coordinator_node.py` analysis:

#### Must-Have Topics (Arm → Main PC)
```yaml
/arm_a/status                 # Arm A state (CRITICAL)
/arm_b/status                 # Arm B state (CRITICAL)
/verify/status                # Verification node (CRITICAL)
/cooking/loading_complete     # Food ready signal (CRITICAL)
```

#### Must-Have Topics (Main PC → Arm)
```yaml
/arm_a/cmd                    # Arm A commands (CRITICAL)
/arm_b/cmd                    # Arm B commands (CRITICAL)
/verify/cmd                   # Verification commands (CRITICAL)
/fms/pickup_arrival           # Robot arrived for pickup (CRITICAL)
/cooking/order                # New cooking order (CRITICAL)
```

---

## 6. Configuration File Recommendations

### Option 1: Use domain_bridge_complete.yaml (Recommended)

**File**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml`

**Pros**:
- Includes all robots (pinky1, pinky2, pinky3, armA, armB)
- Has namespace isolation for mobile robots
- Includes coordinator topics
- Has QoS policies defined
- Most comprehensive (21KB)

**Cons**:
- Uses namespaced topics (e.g., `/pinky1/amcl_pose`)
- Coordinator node needs to run on Domain 25

**Best for**: Production deployment with all robots active.

### Option 2: Use domain_bridge_nonamespace.yaml (Current)

**File**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_nonamespace.yaml`

**Pros**:
- No namespace on Main PC topics
- Simpler topic names
- Matches "minimize namespace" requirement

**Cons**:
- **CRITICAL**: Only works with ONE mobile robot
- Multiple robots will have topic collisions
- Not suitable for fleet management

**Best for**: Single robot testing only.

### Option 3: Create Custom Hybrid Config (Optimal)

Create a new config that:
1. Uses simple names on robot side (no namespace)
2. Uses remap to add namespace on Main PC side
3. Follows `domain_bridge_v3.yaml` structure

This requires the domain bridge package to support the `remap` feature.

---

## 7. Specific Issues Found

### Issue 1: TF Frame Conflicts

**Problem**: Multiple robots publishing to `/tf` will cause frame conflicts on Main PC.

**Current configs handle this differently**:
- `domain_bridge_complete.yaml`: Bridges `/tf` AS-IS (will conflict)
- `domain_bridge_nonamespace.yaml`: Bridges `/tf` AS-IS (will conflict)
- `domain_bridge_v3.yaml`: Does NOT remap `/tf` (will conflict)

**Solution Needed**:
```yaml
# Option A: Don't bridge /tf at all (each robot stays isolated)
# Option B: Use tf2 frame_prefix to add robot name to all frames
# Option C: Run separate tf2 relay nodes with remapping
```

**Recommended**: Option A - Keep TF local to each robot's domain, use only AMCL pose for fleet coordination.

### Issue 2: Coordinator Node Domain ID

**Current**: `coordinator_node.py` uses non-namespaced topics:
```python
self.pub_a = self.create_publisher(String, "/arm_a/cmd", 10)
self.pub_b = self.create_publisher(String, "/arm_b/cmd", 10)
```

**Question**: Which domain does coordinator run on?
- If Domain 25: Needs domain bridge to reach arms
- If Domain 20 or 21: Needs domain bridge for FMS communication

**Recommendation**: Run coordinator on Domain 25 (Main PC), use domain bridge to reach arms.

### Issue 3: Action Service Bridging

**Critical**: Navigation actions need THREE components bridged:
1. Action services (send_goal, cancel_goal, get_result)
2. Feedback topic (`_action/feedback`)
3. Status topic (`_action/status`)

**Current Status**:
- `domain_bridge_complete.yaml`: ✅ Has all three
- `domain_bridge_nonamespace.yaml`: ✅ Has all three
- `domain_bridge_pinky1.yaml`: ❌ Unknown (need to check)

### Issue 4: cmd_vel Topic Direction

**Your requirement**: "/cmd_vel" for velocity commands

**Issue**: cmd_vel should go FROM Main PC TO Robot, but is it bridged?

**Check in configs**:
- `domain_bridge_complete.yaml`: ❌ Missing `/cmd_vel` in Main PC → Robot direction
- `domain_bridge_nonamespace.yaml`: ✅ Has `/cmd_vel` (line 148)
- `domain_bridge_v3.yaml`: ✅ Has `pinky1/cmd_vel` with remap (line 151)

**Recommendation**: Add `/cmd_vel` to ALL configs if using teleop or manual control.

---

## 8. Proposed Configuration (Optimal)

Based on your requirements and system analysis, here's the recommended approach:

### Configuration Strategy

**File to use**: Create `domain_bridge_optimal.yaml` based on `domain_bridge_v3.yaml`

**Key features**:
1. Robot-side topics: NO namespace (simple names)
2. Main PC topics: WITH namespace (per-robot isolation)
3. Robot arm topics: NO namespace (coordinator handles routing)
4. Use remap feature for namespace translation

### Directory Structure
```
Domain 11 (pinky1):  /amcl_pose, /odom, /scan, /cmd_vel
Domain 12 (pinky2):  /amcl_pose, /odom, /scan, /cmd_vel
Domain 20 (armA):    /arm_a/cmd, /arm_a/status
Domain 21 (armB):    /arm_b/cmd, /arm_b/status, /verify/cmd, /verify/status

Domain 25 (Main PC): /pinky1/amcl_pose, /pinky2/amcl_pose,
                     /pinky1/odom, /pinky2/odom,
                     /arm_a/cmd, /arm_a/status,
                     /arm_b/cmd, /arm_b/status,
                     /verify/cmd, /verify/status,
                     /fms/pickup_arrival, /cooking/order, /cooking/loading_complete
```

### Sample Configuration Snippet

```yaml
name: kitchmatics_optimal_bridge

# ============================================
# PINKY1: Domain 11 → Domain 25 (Sensor Data)
# ============================================
topics:
  # Robot publishes /amcl_pose, Main PC gets /pinky1/amcl_pose
  amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    from_domain: 11
    to_domain: 25
    remap: pinky1/amcl_pose
    qos:
      reliability: reliable
      durability: volatile

  odom:
    type: nav_msgs/msg/Odometry
    from_domain: 11
    to_domain: 25
    remap: pinky1/odom
    qos:
      reliability: best_effort
      durability: volatile

  scan:
    type: sensor_msgs/msg/LaserScan
    from_domain: 11
    to_domain: 25
    remap: pinky1/scan
    qos:
      reliability: best_effort
      durability: volatile

  battery/voltage:
    type: std_msgs/msg/Float32
    from_domain: 11
    to_domain: 25
    remap: pinky1/battery/voltage
    qos:
      reliability: reliable
      durability: volatile

  # Navigation action feedback
  navigate_to_pose/_action/feedback:
    type: nav2_msgs/action/NavigateToPose_FeedbackMessage
    from_domain: 11
    to_domain: 25
    remap: pinky1/navigate_to_pose/_action/feedback
    qos:
      reliability: reliable
      durability: volatile

  navigate_to_pose/_action/status:
    type: action_msgs/msg/GoalStatusArray
    from_domain: 11
    to_domain: 25
    remap: pinky1/navigate_to_pose/_action/status
    qos:
      reliability: reliable
      durability: transient_local

# ============================================
# Main PC → PINKY1: Control Commands
# ============================================
  # Main PC publishes /pinky1/cmd_vel, Robot gets /cmd_vel
  pinky1/cmd_vel:
    type: geometry_msgs/msg/Twist
    from_domain: 25
    to_domain: 11
    remap: cmd_vel
    qos:
      reliability: reliable
      durability: volatile

  pinky1/initialpose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    from_domain: 25
    to_domain: 11
    remap: initialpose
    qos:
      reliability: reliable
      durability: volatile

  pinky1/goal_pose:
    type: geometry_msgs/msg/PoseStamped
    from_domain: 25
    to_domain: 11
    remap: goal_pose
    qos:
      reliability: reliable
      durability: volatile

services:
  # Navigation action services
  pinky1/navigate_to_pose/_action/send_goal:
    type: nav2_msgs/action/NavigateToPose_SendGoal
    from_domain: 25
    to_domain: 11
    remap: navigate_to_pose/_action/send_goal

  pinky1/navigate_to_pose/_action/cancel_goal:
    type: action_msgs/srv/CancelGoal
    from_domain: 25
    to_domain: 11
    remap: navigate_to_pose/_action/cancel_goal

  pinky1/navigate_to_pose/_action/get_result:
    type: nav2_msgs/action/NavigateToPose_GetResult
    from_domain: 25
    to_domain: 11
    remap: navigate_to_pose/_action/get_result

# ============================================
# ROBOT ARM A: Domain 20 ↔ Domain 25
# ============================================
  # NO namespace for arm topics (coordinator handles routing)
  arm_a/status:
    type: std_msgs/msg/String
    from_domain: 20
    to_domain: 25
    qos:
      reliability: reliable
      durability: volatile

  arm_a/cmd:
    type: std_msgs/msg/String
    from_domain: 25
    to_domain: 20
    qos:
      reliability: reliable
      durability: volatile

# ============================================
# ROBOT ARM B: Domain 21 ↔ Domain 25
# ============================================
  arm_b/status:
    type: std_msgs/msg/String
    from_domain: 21
    to_domain: 25
    qos:
      reliability: reliable
      durability: volatile

  arm_b/cmd:
    type: std_msgs/msg/String
    from_domain: 25
    to_domain: 21
    qos:
      reliability: reliable
      durability: volatile

  verify/status:
    type: std_msgs/msg/String
    from_domain: 21
    to_domain: 25
    qos:
      reliability: reliable
      durability: volatile

  verify/cmd:
    type: std_msgs/msg/String
    from_domain: 25
    to_domain: 21
    qos:
      reliability: reliable
      durability: volatile

# ============================================
# FMS ↔ Coordinator Communication
# ============================================
  # Main PC (FMS) → Robot Arms (Coordinator)
  fms/pickup_arrival:
    type: fleet_interfaces/msg/PickupArrival
    from_domain: 25
    to_domain: 20  # Also need to bridge to domain 21
    qos:
      reliability: reliable
      durability: volatile

  cooking/order:
    type: fleet_interfaces/msg/CookingOrder
    from_domain: 25
    to_domain: 20  # Also need to bridge to domain 21
    qos:
      reliability: reliable
      durability: volatile

  # Robot Arms (Coordinator) → Main PC (FMS)
  cooking/loading_complete:
    type: fleet_interfaces/msg/LoadingComplete
    from_domain: 21  # Coordinator publishes from domain 21
    to_domain: 25
    qos:
      reliability: reliable
      durability: volatile
```

---

## 9. Action Items

### Immediate (Critical)
1. ✅ **Verify Main PC Domain ID**: Confirm using Domain 25, not 0
2. ⚠️ **Check domain bridge package**: Does it support `remap` feature?
3. ⚠️ **Test current config**: Run with existing configs and log topic collisions
4. ⚠️ **Decide on TF strategy**: Bridge or keep isolated?

### Short-term (This Week)
5. 📝 **Create optimal config**: Based on recommendations above
6. 🧪 **Test with one robot**: Validate bridging works correctly
7. 🧪 **Test with two robots**: Verify no topic collisions
8. 🧪 **Test arm communication**: Verify coordinator topics work

### Medium-term (Next Week)
9. 📊 **Monitor network load**: Check if QoS policies are optimal
10. 🔧 **Optimize QoS**: Adjust reliability/durability based on testing
11. 📚 **Document final config**: Create deployment guide

---

## 10. Testing Checklist

### Test 1: Single Robot (pinky1)
```bash
# Terminal 1: Start domain bridge
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge /path/to/config.yaml

# Terminal 2: Check Main PC topics
ROS_DOMAIN_ID=25 ros2 topic list | grep pinky1

# Terminal 3: Check robot topics (should be NO namespace)
ROS_DOMAIN_ID=11 ros2 topic list

# Terminal 4: Test communication
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose --once
ROS_DOMAIN_ID=25 ros2 topic pub /pinky1/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1}}" --once
```

### Test 2: Multi-Robot Fleet
```bash
# Check both robots visible on Main PC
ROS_DOMAIN_ID=25 ros2 topic list | grep -E "pinky1|pinky2"

# Verify no topic collisions (should see both)
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose &
ROS_DOMAIN_ID=25 ros2 topic echo /pinky2/amcl_pose &
```

### Test 3: Robot Arm Communication
```bash
# Terminal 1: Monitor arm status
ROS_DOMAIN_ID=25 ros2 topic echo /arm_a/status

# Terminal 2: Send arm command
ROS_DOMAIN_ID=25 ros2 topic pub /arm_a/cmd std_msgs/msg/String "data: 'TEST_JOB|pick_ham'"
```

### Test 4: Navigation Action
```bash
# Send navigation goal from Main PC
ROS_DOMAIN_ID=25 ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: 'map'}, pose: {position: {x: 1.0, y: 0.0}}}}"

# Monitor feedback
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/navigate_to_pose/_action/feedback
```

---

## 11. Summary & Recommendations

### Critical Findings
1. ❌ **Domain ID Mismatch**: Documentation says Domain 0, system uses Domain 25
2. ⚠️ **Multiple Config Files**: Unclear which is production vs experimental
3. ⚠️ **Namespace Strategy**: Conflicts between "no namespace" goal and multi-robot reality
4. ❌ **Missing Topics**: cmd_vel not bridged in some configs
5. ⚠️ **TF Conflicts**: No clear strategy for transform frame isolation

### Recommended Path Forward

**Short-term (Use Existing)**:
- Use `domain_bridge_complete.yaml` for full system
- Accept namespaced topics on Main PC
- Update any code expecting non-namespaced topics

**Long-term (Optimize)**:
- Create hybrid config with remap feature
- Keep robots namespace-free
- Use namespace only on Main PC for isolation
- Document and standardize on ONE configuration

### Namespace Philosophy

**Recommendation**: "Namespace at the boundary, not at the source"
- Robots publish simple names: `/amcl_pose`, `/cmd_vel`
- Domain bridge adds namespace when crossing to Main PC
- Main PC sees: `/pinky1/amcl_pose`, `/pinky2/amcl_pose`
- Best of both worlds: simplicity + isolation

---

## 12. Files Referenced

```
/home/gw/kitchmatics/roscamp-repo-1/fms/config/
├── domain_bridge_complete.yaml          [RECOMMENDED: Production use]
├── domain_bridge_v3.yaml                [RECOMMENDED: Template for optimal config]
├── domain_bridge_nonamespace.yaml       [USE ONLY: Single robot testing]
├── domain_bridge_pinky1.yaml            [CURRENTLY ACTIVE: Incomplete]
├── domain_bridge_pinky2.yaml            [CURRENTLY ACTIVE: Incomplete]
└── domain_bridge_pinky3.yaml            [CURRENTLY ACTIVE: Not in use]

/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/
├── run_domain_bridges.sh                [ACTIVE: Launches bridges]
└── run_full_system.sh                   [System launcher]

/home/gw/kitchmatics/roscamp-repo-1/fms/coordinator_Ws/src/sandwich_coordinator/
└── sandwich_coordinator/coordinator_node.py  [Robot arm coordinator]
```

---

**Analysis Complete**
**Next Step**: Review recommendations and decide on configuration strategy
