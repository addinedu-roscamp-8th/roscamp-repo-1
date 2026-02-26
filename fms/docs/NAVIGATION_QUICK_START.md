# Navigation System - Quick Start Guide

## Problem Summary

The Kitchmatics FMS navigation system has **critical issues**:
- Nav2 stack NOT running on Pinky robots
- No AMCL localization active
- Domain bridge not forwarding navigation topics
- FMS cannot send navigation goals

**Fix Time**: ~30 minutes per robot

---

## Quick Diagnosis

```bash
# Check system status
bash /home/gw/kitchmatics/roscamp-repo-1/fms/scripts/diagnose_navigation.sh
```

---

## Quick Fix (30 minutes)

### 1. Setup Navigation on Pinky1 and Pinky2

```bash
# From main PC
cd /home/gw/kitchmatics/roscamp-repo-1
bash fms/scripts/setup_pinky_navigation.sh all

# This will:
# ✓ Check connectivity to both robots
# ✓ Copy map files
# ✓ Build navigation packages
# ✓ Create startup scripts
```

### 2. Start Navigation on Each Robot

```bash
# SSH to Pinky1
ssh pinky@192.168.1.7
/home/pinky/start_navigation.sh

# In another terminal, SSH to Pinky2
ssh pinky@192.168.1.6
/home/pinky/start_navigation.sh

# Wait 5-10 seconds for Nav2 to fully initialize
```

### 3. Verify Navigation is Running

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

# Check nodes appeared
ros2 node list | grep -E "pinky|amcl|planner"

# Check topics appeared
ros2 topic list | grep pinky1 | head -5

# Expected output:
# /pinky1/amcl_pose
# /pinky1/scan
# /pinky1/odom
# etc.
```

### 4. Initialize Robot Localization

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# Set initial pose for Pinky1
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {
    pose: {position: {x: 0.585, y: 0.085}, orientation: {w: 1.0}},
    covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]
  }
}' --once

# Set initial pose for Pinky2
ros2 topic pub /pinky2/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {
    pose: {position: {x: 0.585, y: 0.255}, orientation: {w: 1.0}},
    covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]
  }
}' --once
```

### 5. Test Navigation Goal

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# Send navigation goal to table1
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{
  pose: {
    header: {frame_id: "map"},
    pose: {position: {x: 1.785, y: 0.35}, orientation: {w: 1.0}}
  }
}'

# Robot should move toward table1
# Watch progress:
# ros2 topic echo /pinky1/amcl_pose
```

### 6. Verify in FMS

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# Check FMS sees robot positions
ros2 topic echo /fms/fleet_status --once | head -20

# Should show actual coordinates, not (0, 0, 0)
```

---

## Success Indicators

After completing the quick fix:

- [ ] `diagnose_navigation.sh` shows all GREEN
- [ ] `/pinky1/amcl_pose` and `/pinky2/amcl_pose` publish on domain 25
- [ ] `/pinky1/navigate_to_pose` action server available
- [ ] FMS fleet status shows actual robot positions
- [ ] Can send navigation goals and robots move
- [ ] Both Pinky1 and Pinky2 can operate simultaneously

---

## Troubleshooting

### Nav2 Not Starting

**Check the startup script**:
```bash
ssh pinky@192.168.1.7
cat /home/pinky/start_navigation.sh
# Should show ros2 launch pinky_navigation ...
```

**Manually test launch**:
```bash
ssh pinky@192.168.1.7
export ROS_DOMAIN_ID=11
source /opt/ros/jazzy/setup.bash
cd /home/pinky/pinky_pro
source install/setup.bash
ros2 launch pinky_navigation bringup_launch.xml robot_name:=pinky_b4bc
# Watch for errors
```

### Topics Not Appearing on Domain 25

**Check domain bridge**:
```bash
ps aux | grep domain_bridge
# Should show: ros2 run domain_bridge domain_bridge ...
```

**Restart bridge**:
```bash
pkill -f domain_bridge
sleep 2
ros2 run domain_bridge domain_bridge \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml &
```

### Pinky2 Unreachable

**Check network**:
```bash
ping 192.168.1.6
# If fails, check:
# 1. Is Pinky2 powered on?
# 2. Is Ethernet cable connected?
# 3. Is IP correct?
# 4. Router issue?
```

### Robot Doesn't Move

**Check AMCL pose**:
```bash
ros2 topic echo /pinky1/amcl_pose --once
# Should show position, not zeroes
```

**Check costmap**:
```bash
ros2 topic echo /pinky1/local_costmap/costmap --once
# Should show valid costmap
```

**Check robot can move manually**:
- Physically push robot
- Check /pinky1/odom updates
- Verify /tf frame transforms are published

---

## Reference Files

```
Configuration:
  /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/params/nav2_params.yaml
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml

Diagnostic Tools:
  /home/gw/kitchmatics/roscamp-repo-1/fms/scripts/diagnose_navigation.sh
  /home/gw/kitchmatics/roscamp-repo-1/fms/scripts/setup_pinky_navigation.sh

Documentation:
  /home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_VALIDATION_REPORT.md
  /home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_SETUP_GUIDE.md
  /home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_QUICK_START.md
```

---

## Full Timeline

```
0:00   - Run setup script
5:00   - Start navigation on both robots
10:00  - Verify Nav2 nodes running
15:00  - Set initial poses via /initialpose
20:00  - Test single navigation goal
25:00  - Test multi-robot goals
30:00  - Verify FMS fleet coordination
```

---

## Commands Summary

```bash
# Diagnose
bash fms/scripts/diagnose_navigation.sh

# Setup
bash fms/scripts/setup_pinky_navigation.sh all

# Check connectivity
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash
ros2 topic list | grep pinky

# Set pose
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{...}' --once

# Send goal
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{...}'

# Monitor
ros2 topic echo /pinky1/amcl_pose
ros2 topic echo /pinky1/navigate_to_pose/_action/feedback
ros2 topic echo /fms/fleet_status
```

---

## Next Steps

1. **Today**: Run setup scripts and verify navigation works
2. **Tomorrow**: Test multi-robot coordination
3. **Later**: Optimize parameters for speed/precision

See `NAVIGATION_SETUP_GUIDE.md` for detailed instructions.
