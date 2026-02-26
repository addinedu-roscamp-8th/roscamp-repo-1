# Navigation System Resources

## Quick Links

### Status & Summary
- **[Executive Summary](./NAVIGATION_VALIDATION_SUMMARY.txt)** - Start here for overview and immediate action items

### Documentation
1. **[Validation Report](./fms/docs/NAVIGATION_VALIDATION_REPORT.md)** - Detailed technical analysis and findings
2. **[Setup Guide](./fms/docs/NAVIGATION_SETUP_GUIDE.md)** - Comprehensive step-by-step instructions
3. **[Quick Start](./fms/docs/NAVIGATION_QUICK_START.md)** - Quick reference for 30-minute fix

### Tools & Scripts
1. **[Diagnostic Script](./fms/scripts/diagnose_navigation.sh)** - Check system status
2. **[Setup Script](./fms/scripts/setup_pinky_navigation.sh)** - Automated robot configuration

## Current Status (2026-02-26)

### Critical Issues
- ✗ Nav2 stack NOT running on Pinky robots
- ✗ AMCL localization inactive
- ✗ Domain bridge not forwarding navigation topics
- ✗ FMS cannot send navigation goals

### Working Components
- ✓ Nav2 configuration files are well-tuned
- ✓ Domain bridge fully configured
- ✓ FMS fleet manager operational
- ✓ Map and parameters ready

## Quick Start (30 minutes to fix)

```bash
# 1. Diagnose current state
bash fms/scripts/diagnose_navigation.sh

# 2. Setup both robots (copies files, builds packages)
bash fms/scripts/setup_pinky_navigation.sh all

# 3. Start navigation on Pinky1 (in SSH terminal)
ssh pinky@192.168.1.7
/home/pinky/start_navigation.sh

# 4. Start navigation on Pinky2 (in separate SSH terminal)
ssh pinky@192.168.1.6
/home/pinky/start_navigation.sh

# 5. Set initial poses to enable localization
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash
source install/setup.bash

# Pinky1 initial pose
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {pose: {position: {x: 0.585, y: 0.085}, orientation: {w: 1.0}},
  covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]}
}' --once

# Pinky2 initial pose
ros2 topic pub /pinky2/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {pose: {position: {x: 0.585, y: 0.255}, orientation: {w: 1.0}},
  covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]}
}' --once

# 6. Test navigation goal
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{
  pose: {
    header: {frame_id: "map"},
    pose: {position: {x: 1.785, y: 0.35}, orientation: {w: 1.0}}
  }
}'
```

## File Locations

### Configuration
```
nav2_params.yaml
  └─ /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/params/nav2_params.yaml

fms_config.yaml
  └─ /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml

domain_bridge_complete.yaml
  └─ /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml
```

### Documentation
```
fms/docs/
  ├─ NAVIGATION_VALIDATION_REPORT.md  (Detailed technical analysis)
  ├─ NAVIGATION_SETUP_GUIDE.md        (Step-by-step instructions)
  └─ NAVIGATION_QUICK_START.md        (Quick reference)
```

### Scripts
```
fms/scripts/
  ├─ diagnose_navigation.sh           (Status checker)
  ├─ setup_pinky_navigation.sh        (Automated setup)
  └─ send_nav_goal.sh                 (Goal sender)
```

### Maps
```
mobile_robot/maps/
  ├─ real.yaml
  ├─ real.pgm
  └─ ...
```

## Key Information

### Robot Configuration
| Robot  | Domain ID | IP Address   | Robot Name | Status |
|--------|-----------|--------------|------------|--------|
| Pinky1 | 11        | 192.168.1.7  | pinky_b4bc | Working (after fix) |
| Pinky2 | 12        | 192.168.1.6  | pinky_e2a8 | Working (after fix) |
| Pinky3 | 13        | 192.168.1.11 | pinky_d29d | Disabled |
| Main   | 25        | localhost    | -          | Running |

### Nav2 Parameters Overview

**AMCL (Localization)**
- Particles: 500-3000 (auto-scales based on confidence)
- Model: DifferentialMotionModel
- Likelihood: likelihood_field
- Update: Every 1cm movement, every 3° rotation

**Costmap (Obstacle Detection)**
- Local: 1m x 1m, 30Hz update, 8cm inflation radius
- Global: Full map, 2Hz update, 10cm inflation radius
- Resolution: 1cm (high precision)

**Controller (Path Following)**
- Type: RegulatedPurePursuitController
- Speed: 15cm/s (safe for narrow spaces)
- Lookahead: 8cm (scaled for small robot)

**Planner (Path Planning)**
- Type: NavfnPlanner with A* algorithm
- Tolerance: 2cm
- Unknown: Avoided

## Testing Checklist

- [ ] Nav2 nodes appear in `ros2 node list`
- [ ] `/pinky1/amcl_pose` and `/pinky2/amcl_pose` published
- [ ] `/pinky1/navigate_to_pose` action server available
- [ ] FMS fleet status shows correct robot positions
- [ ] Can send navigation goals
- [ ] Robots move toward goals
- [ ] Both robots can navigate simultaneously
- [ ] No collisions observed
- [ ] Path conflicts resolved by FMS
- [ ] Zones released correctly

## Performance Targets

**Navigation**
- Time to goal (1m): 30-45 seconds
- Success rate: 95%+ in open space
- Max deviation: 15cm

**Localization**
- Convergence time: < 10 seconds
- Stability: ±5cm
- Update rate: 20Hz

**Multi-Robot**
- Simultaneous operation: 3 robots
- Zone release: < 2 seconds
- Collision prevention: 100%

## Troubleshooting

See detailed troubleshooting in:
- **NAVIGATION_SETUP_GUIDE.md** - "Troubleshooting" section
- **NAVIGATION_QUICK_START.md** - "Troubleshooting" section

Quick fixes:
```bash
# Check status
bash fms/scripts/diagnose_navigation.sh

# Restart domain bridge
pkill -f domain_bridge
ros2 run domain_bridge domain_bridge fms/config/domain_bridge_complete.yaml &

# Test connectivity
ping 192.168.1.7   # Pinky1
ping 192.168.1.6   # Pinky2
```

## Requirements Status

| Requirement | Status | Notes |
|-------------|--------|-------|
| 7: /pose triggers release | BLOCKED | Awaiting active AMCL |
| 8: Path conflict resolution | BLOCKED | Awaiting working navigation |
| 5: Multi-robot operation | BLOCKED | Pinky2 unreachable, Nav2 inactive |

All requirements will be testable after completing the setup steps.

## Next Actions

1. **NOW** (5 min): Read NAVIGATION_VALIDATION_SUMMARY.txt
2. **NEXT** (30 min): Run setup scripts
3. **THEN** (15 min): Start navigation on robots
4. **FINALLY** (15 min): Test with diagnostic script

Total time to full resolution: ~60-75 minutes

---

Generated: 2026-02-26
Status: Ready for Implementation
