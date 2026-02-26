# Navigation System Setup Guide
**For Kitchmatics FMS with Pinky Mobile Robots**

---

## Quick Status Check

Run this command to check the navigation system status:

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
bash fms/scripts/diagnose_navigation.sh
```

---

## Problem: Nav2 Stack Not Running on Pinky Robots

### Symptom
- FMS fleet status shows robots at position (0, 0, 0)
- No `/pinky1/amcl_pose` or `/pinky2/amcl_pose` topics
- Cannot send navigation goals to robots
- `/navigate_to_pose` action servers not available

### Root Cause
The Pinky robot bringup is not launching the Nav2 navigation stack. Currently, only the lamp module is being launched.

### Solution

#### Step 1: Identify Robot Bringup Script

SSH to Pinky1 and find the actual bringup script:

```bash
ssh pinky@192.168.1.7

# Check what's currently running
ps aux | grep -i bringup | grep -v grep

# Output should show:
# /bin/bash /home/pinky/pinky_devices/lamp_module_bringup
```

#### Step 2: Modify Bringup to Include Nav2

The bringup script needs to be updated to launch the Nav2 navigation stack. There are two approaches:

**Option A: Create a Master Bringup Script** (Recommended)

Create `/home/pinky/bringup_full.sh`:

```bash
#!/bin/bash
#
# Full Robot Bringup: Lamp Module + Navigation
# Usage: ./bringup_full.sh [robot_name]
#

ROBOT_NAME=${1:-"pinky_b4bc"}
export ROS_DOMAIN_ID=11  # or 12 for pinky2, 13 for pinky3

source /opt/ros/jazzy/setup.bash

# Start lamp module in background
echo "Starting lamp module..."
/home/pinky/pinky_devices/lamp_module_bringup &
LAMP_PID=$!

# Give lamp module time to initialize
sleep 2

# Start Nav2 navigation
echo "Starting Nav2 navigation stack..."
cd /home/pinky/pinky_pro

# Build if needed
if [ ! -d "install" ]; then
    echo "Building packages..."
    colcon build --packages-select pinky_navigation pinky_bringup
fi

# Source the built packages
source install/setup.bash

# Launch navigation
ros2 launch pinky_navigation bringup_launch.xml robot_name:=$ROBOT_NAME

# Cleanup on exit
trap "kill $LAMP_PID" EXIT
```

Save and make executable:
```bash
chmod +x /home/pinky/bringup_full.sh
```

**Option B: Modify Existing Lamp Module Script**

If you want to keep using the existing lamp_module_bringup, you can modify it to also launch Nav2 after lamp initialization.

Edit `/home/pinky/pinky_devices/lamp_module_bringup`:

```bash
#!/bin/bash
# ... existing lamp setup code ...

# After lamp initialization, add:
export ROS_DOMAIN_ID=11
source /opt/ros/jazzy/setup.bash
cd /home/pinky/pinky_pro
source install/setup.bash

# Launch Nav2 in background or foreground
ros2 launch pinky_navigation bringup_launch.xml robot_name:=pinky_b4bc &
```

#### Step 3: Verify Map File Exists

On Pinky1, check that the map file is available:

```bash
ssh pinky@192.168.1.7

ls -la /home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/maps/

# Should show:
# - map.yaml
# - map.pgm (or map.png)
```

If maps don't exist, copy them from main PC:

```bash
# On main PC
scp /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/maps/real.yaml \
    pinky@192.168.1.7:/home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/maps/

scp /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/maps/real.pgm \
    pinky@192.168.1.7:/home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/maps/
```

#### Step 4: Restart Robot with New Bringup

```bash
ssh pinky@192.168.1.7

# Kill existing processes
pkill -f "lamp_module_bringup"
pkill -f "ros2"
pkill -f "pillar"

# Wait for cleanup
sleep 2

# Start with full bringup (Option A)
/home/pinky/bringup_full.sh pinky_b4bc

# Or if using Option B, just restart lamp module
/home/pinky/pinky_devices/lamp_module_bringup
```

#### Step 5: Verify Nav2 is Running

In a new terminal, check the nodes:

```bash
export ROS_DOMAIN_ID=11
source /opt/ros/jazzy/setup.bash

# Check for nav2 nodes
ros2 node list | grep -E "amcl|planner|controller|bt_navigator|map_server"

# Expected output:
# /amcl
# /map_server
# /planner_server
# /controller_server
# /behavior_server
# /bt_navigator
# /velocity_smoother
```

---

## Step 2: Verify Domain Bridge Configuration

The domain bridge is responsible for forwarding navigation topics from Pinky robots (domain 11/12/13) to the main PC (domain 25).

### Check Domain Bridge Status

```bash
# On main PC
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

# Check if bridge is running
ps aux | grep domain_bridge | grep -v grep

# If not running, start it:
ros2 run domain_bridge domain_bridge \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml &
```

### Verify Topic Bridging

```bash
# On main PC, check for Pinky1 topics
ros2 topic list | grep pinky1

# Expected topics:
# /pinky1/amcl_pose
# /pinky1/scan
# /pinky1/odom
# /pinky1/initialpose
# /pinky1/navigate_to_pose/_action/feedback
# /pinky1/navigate_to_pose/_action/status
```

If topics are missing, the domain bridge is not working properly. Check the configuration:

```bash
# Verify domain bridge config
cat /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml | grep -A5 "pinky1"
```

---

## Step 3: Initialize AMCL Localization

Once Nav2 is running and domain bridge is working, you need to set the initial pose for AMCL localization.

### Determine Initial Pose

From `fms/config/fms_config.yaml`, the initial poses are:

```yaml
initial_poses:
  pinky1:
    x: 0.585
    y: 0.085
    theta: 0.0
  pinky2:
    x: 0.585
    y: 0.255
    theta: 0.0
```

### Set Initial Pose via ROS Topic

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# For Pinky1
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {
    frame_id: "map"
  },
  pose: {
    pose: {
      position: {x: 0.585, y: 0.085, z: 0.0},
      orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
    },
    covariance: [
      0.25, 0, 0, 0, 0, 0,
      0, 0.25, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0.06853892326654787
    ]
  }
}' --once

# For Pinky2
ros2 topic pub /pinky2/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {
    frame_id: "map"
  },
  pose: {
    pose: {
      position: {x: 0.585, y: 0.255, z: 0.0},
      orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
    },
    covariance: [
      0.25, 0, 0, 0, 0, 0,
      0, 0.25, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0.06853892326654787
    ]
  }
}' --once
```

### Verify AMCL is Active

```bash
# Check for pose estimates
timeout 5 ros2 topic echo /pinky1/amcl_pose --once

# Expected output: PoseWithCovarianceStamped with position and covariance
```

---

## Step 4: Test Navigation Goals

### Send a Simple Navigation Goal

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# Send goal to table1 (1.785, 0.35)
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{
  pose: {
    header: {frame_id: "map"},
    pose: {
      position: {x: 1.785, y: 0.35, z: 0.0},
      orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
    }
  }
}'
```

### Monitor Navigation Progress

In another terminal:

```bash
# Watch AMCL pose updates (shows current position)
ros2 topic echo /pinky1/amcl_pose

# Watch navigation feedback (shows progress)
ros2 topic echo /pinky1/navigate_to_pose/_action/feedback

# Watch costmap (shows obstacles)
ros2 topic echo /pinky1/local_costmap/costmap
```

---

## Step 5: Enable FMS Auto-Initialization

The FMS can automatically set initial poses when it starts. Check the configuration:

```bash
grep -A5 "auto_set_initial_pose" \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml

# Should show:
# auto_set_initial_pose: true
```

If enabled, the FMS will:
1. Publish initial poses to `/pinky1/initialpose`, `/pinky2/initialpose`
2. Initialize AMCL localization automatically
3. Wait for localization to converge before accepting navigation tasks

---

## Troubleshooting

### Issue 1: Nav2 Nodes Not Appearing

**Symptoms**:
- `/bt_navigator`, `/amcl`, `/planner_server` not in `ros2 node list`
- Error: "Nav2 package not found"

**Solutions**:

A. Build the packages:
```bash
ssh pinky@192.168.1.7
cd /home/pinky/pinky_pro
colcon build --packages-select pinky_navigation pinky_bringup
source install/setup.bash
```

B. Check package paths:
```bash
ros2 pkg list | grep pinky
# Should show: pinky_navigation, pinky_bringup

# If missing, package_xml.xml or setup.py is incorrect
```

C. Verify launch file:
```bash
# Try launching directly
ros2 launch pinky_navigation bringup_launch.xml robot_name:=pinky_b4bc

# Check for errors in output
```

### Issue 2: Domain Bridge Not Forwarding Topics

**Symptoms**:
- `/pinky1/amcl_pose` not available on domain 25
- Topics exist on domain 11 but not 25

**Solutions**:

A. Check domain bridge is running:
```bash
ps aux | grep domain_bridge
# Should see: ros2 run domain_bridge domain_bridge ...
```

B. Restart domain bridge:
```bash
pkill -f domain_bridge
sleep 1

ros2 run domain_bridge domain_bridge \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml &
```

C. Check bridge configuration:
```bash
# Verify pinky1 topics are configured
grep -A20 "from_domain: 11" \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml

# Should show pinky1/* topics
```

### Issue 3: AMCL Not Publishing Poses

**Symptoms**:
- `/pinky1/amcl_pose` topic exists but no messages
- FMS fleet status shows robots at (0,0,0)

**Solutions**:

A. Check if map_server is running:
```bash
export ROS_DOMAIN_ID=11
ros2 node info /map_server
# If error, map not loaded
```

B. Set initial pose:
```bash
export ROS_DOMAIN_ID=25

ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {
    pose: {position: {x: 0.585, y: 0.085}, orientation: {w: 1.0}},
    covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]
  }
}' --once
```

C. Check AMCL parameters:
```bash
ros2 param get /amcl max_particles
ros2 param get /amcl min_particles
# Compare with nav2_params.yaml
```

### Issue 4: Navigation Goals Timeout

**Symptoms**:
- Send goal but action status shows "TIMEOUT"
- Robot doesn't move toward goal

**Solutions**:

A. Check if costmap is initialized:
```bash
timeout 2 ros2 topic echo /pinky1/local_costmap/costmap --once
# Should show valid costmap data
```

B. Check if path planner is working:
```bash
# Monitor planner feedback
ros2 topic echo /pinky1/plan &

# Send goal
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{...}'

# Path should be published to /pinky1/plan
```

C. Check robot can move:
```bash
# Send velocity command directly (if robot supports it)
# This verifies hardware is working
```

### Issue 5: Pinky2 Unreachable

**Symptoms**:
- SSH timeout to 192.168.1.6
- ping doesn't work

**Solutions**:

A. Check network connectivity:
```bash
ping 192.168.1.6
# If fails, network issue

# Check router/WiFi
ping 192.168.1.1  # router
```

B. Check robot power:
- Is Pinky2 powered on?
- Check battery indicator

C. Check robot status:
```bash
# From another Pinky that's online
ssh pinky@192.168.1.7
ping 192.168.1.6  # Try from within network
```

D. Manual recovery:
```bash
# If still fails, physically access Pinky2 and:
# 1. Check if it's on
# 2. Check Ethernet connection
# 3. Restart the robot
# 4. Try SSH again
```

---

## Performance Tuning

Once navigation is working, you can tune performance using these parameters:

### Faster Navigation
```yaml
# In nav2_params.yaml

controller_server:
  FollowPath:
    desired_linear_vel: 0.20        # Increase from 0.15
    max_angular_vel: 1.0             # Increase from 0.8

planner_server:
  GridBased:
    tolerance: 0.04                  # Increase from 0.02
```

### More Precise Navigation
```yaml
# In nav2_params.yaml

controller_server:
  general_goal_checker:
    xy_goal_tolerance: 0.02          # Decrease from 0.05
    yaw_goal_tolerance: 0.05         # Decrease from 0.1
```

### Better Localization
```yaml
# In nav2_params.yaml

amcl:
  max_particles: 4000                # Increase from 3000
  min_particles: 1000                # Increase from 500
```

---

## Success Criteria

Navigation system is working correctly when:

1. ✓ Nav2 nodes appear in `ros2 node list`
2. ✓ `/pinky1/amcl_pose` published on domain 25 (via domain bridge)
3. ✓ `/pinky1/navigate_to_pose` action available
4. ✓ Robots show actual positions in FMS fleet status
5. ✓ Navigation goals complete successfully
6. ✓ Path conflicts resolved by FMS collision avoidance
7. ✓ Both Pinky1 and Pinky2 can navigate simultaneously

---

## Next Steps

1. Implement the bringup script changes from **Step 1**
2. Verify domain bridge from **Step 2**
3. Initialize AMCL from **Step 3**
4. Test goals from **Step 4**
5. Run diagnostic script to verify all systems

```bash
bash /home/gw/kitchmatics/roscamp-repo-1/fms/scripts/diagnose_navigation.sh
```

---

## References

- Navigation Validation Report: `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_VALIDATION_REPORT.md`
- Config Files: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/`
- ROS2 Nav2 Docs: https://nav2.org/

