#!/bin/bash
# Full Domain Bridge Startup Script for Kitchmatics FMS
# Bridges robot domains to main PC domain with topic remapping

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Kitchmatics Domain Bridge Startup${NC}"
echo -e "${GREEN}========================================${NC}"

# Source ROS2
source /opt/ros/jazzy/setup.bash
source ~/kitchmatics/roscamp-repo-1/install/setup.bash

# Main PC Domain ID
export ROS_DOMAIN_ID=25

# Kill existing domain bridge processes
echo -e "${YELLOW}Stopping existing bridges...${NC}"
pkill -9 -f domain_bridge 2>/dev/null || true
pkill -9 -f "topic_tools relay" 2>/dev/null || true
sleep 1

# Configuration directory
CONFIG_DIR=~/kitchmatics/roscamp-repo-1/fms/config

# Create minimal bridge configs for each robot
echo -e "${YELLOW}Creating bridge configurations...${NC}"

# Pinky1 config (Domain 11)
cat > /tmp/bridge_pinky1.yaml << 'EOF'
name: bridge_pinky1
from_domain: 11
to_domain: 25
wait_for_publisher: true
topics:
  amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
  odom:
    type: nav_msgs/msg/Odometry
  scan:
    type: sensor_msgs/msg/LaserScan
  battery/voltage:
    type: std_msgs/msg/Float32
  battery/present:
    type: std_msgs/msg/Bool
  follow_waypoints/_action/feedback:
    type: nav2_msgs/action/FollowWaypoints_FeedbackMessage
  follow_waypoints/_action/status:
    type: action_msgs/msg/GoalStatusArray
  navigate_to_pose/_action/feedback:
    type: nav2_msgs/action/NavigateToPose_FeedbackMessage
  navigate_to_pose/_action/status:
    type: action_msgs/msg/GoalStatusArray
EOF

# Pinky2 config (Domain 12)
cat > /tmp/bridge_pinky2.yaml << 'EOF'
name: bridge_pinky2
from_domain: 12
to_domain: 25
wait_for_publisher: true
topics:
  amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
  odom:
    type: nav_msgs/msg/Odometry
  scan:
    type: sensor_msgs/msg/LaserScan
  battery/voltage:
    type: std_msgs/msg/Float32
  battery/present:
    type: std_msgs/msg/Bool
  follow_waypoints/_action/feedback:
    type: nav2_msgs/action/FollowWaypoints_FeedbackMessage
  follow_waypoints/_action/status:
    type: action_msgs/msg/GoalStatusArray
  navigate_to_pose/_action/feedback:
    type: nav2_msgs/action/NavigateToPose_FeedbackMessage
  navigate_to_pose/_action/status:
    type: action_msgs/msg/GoalStatusArray
EOF

# Pinky1 reverse (FMS -> Robot)
cat > /tmp/bridge_pinky1_rev.yaml << 'EOF'
name: bridge_pinky1_rev
from_domain: 25
to_domain: 11
topics:
  pinky1/initialpose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
  pinky1/goal_pose:
    type: geometry_msgs/msg/PoseStamped
  pinky1/cmd_vel:
    type: geometry_msgs/msg/Twist
services:
  pinky1/follow_waypoints/_action/send_goal:
    type: nav2_msgs/action/FollowWaypoints_SendGoal
  pinky1/follow_waypoints/_action/cancel_goal:
    type: action_msgs/srv/CancelGoal
  pinky1/follow_waypoints/_action/get_result:
    type: nav2_msgs/action/FollowWaypoints_GetResult
  pinky1/navigate_to_pose/_action/send_goal:
    type: nav2_msgs/action/NavigateToPose_SendGoal
  pinky1/navigate_to_pose/_action/cancel_goal:
    type: action_msgs/srv/CancelGoal
  pinky1/navigate_to_pose/_action/get_result:
    type: nav2_msgs/action/NavigateToPose_GetResult
EOF

# Pinky2 reverse (FMS -> Robot)
cat > /tmp/bridge_pinky2_rev.yaml << 'EOF'
name: bridge_pinky2_rev
from_domain: 25
to_domain: 12
topics:
  pinky2/initialpose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
  pinky2/goal_pose:
    type: geometry_msgs/msg/PoseStamped
  pinky2/cmd_vel:
    type: geometry_msgs/msg/Twist
services:
  pinky2/follow_waypoints/_action/send_goal:
    type: nav2_msgs/action/FollowWaypoints_SendGoal
  pinky2/follow_waypoints/_action/cancel_goal:
    type: action_msgs/srv/CancelGoal
  pinky2/follow_waypoints/_action/get_result:
    type: nav2_msgs/action/FollowWaypoints_GetResult
  pinky2/navigate_to_pose/_action/send_goal:
    type: nav2_msgs/action/NavigateToPose_SendGoal
  pinky2/navigate_to_pose/_action/cancel_goal:
    type: action_msgs/srv/CancelGoal
  pinky2/navigate_to_pose/_action/get_result:
    type: nav2_msgs/action/NavigateToPose_GetResult
EOF

# Robot Arm configs (Domain 20, 21)
cat > /tmp/bridge_arm_a.yaml << 'EOF'
name: bridge_arm_a
from_domain: 20
to_domain: 25
wait_for_publisher: true
topics:
  arm_a/status:
    type: std_msgs/msg/String
EOF

cat > /tmp/bridge_arm_a_rev.yaml << 'EOF'
name: bridge_arm_a_rev
from_domain: 25
to_domain: 20
topics:
  arm_a/cmd:
    type: std_msgs/msg/String
EOF

cat > /tmp/bridge_arm_b.yaml << 'EOF'
name: bridge_arm_b
from_domain: 21
to_domain: 25
wait_for_publisher: true
topics:
  arm_b/status:
    type: std_msgs/msg/String
  verify/status:
    type: std_msgs/msg/String
EOF

cat > /tmp/bridge_arm_b_rev.yaml << 'EOF'
name: bridge_arm_b_rev
from_domain: 25
to_domain: 21
topics:
  arm_b/cmd:
    type: std_msgs/msg/String
  verify/cmd:
    type: std_msgs/msg/String
EOF

# Start domain bridges
echo -e "${GREEN}Starting domain bridges...${NC}"

# Start bridges for Pinky1
ros2 run domain_bridge domain_bridge /tmp/bridge_pinky1.yaml &
sleep 1
ros2 run domain_bridge domain_bridge /tmp/bridge_pinky1_rev.yaml &
sleep 1

# Start bridges for Pinky2
ros2 run domain_bridge domain_bridge /tmp/bridge_pinky2.yaml &
sleep 1
ros2 run domain_bridge domain_bridge /tmp/bridge_pinky2_rev.yaml &
sleep 1

# Start bridges for Robot Arms
ros2 run domain_bridge domain_bridge /tmp/bridge_arm_a.yaml &
ros2 run domain_bridge domain_bridge /tmp/bridge_arm_a_rev.yaml &
ros2 run domain_bridge domain_bridge /tmp/bridge_arm_b.yaml &
ros2 run domain_bridge domain_bridge /tmp/bridge_arm_b_rev.yaml &
sleep 2

# Start topic relays to remap non-namespaced topics to namespaced topics
echo -e "${GREEN}Starting topic relays for namespace mapping...${NC}"

# Pinky1 topic relays: /amcl_pose (from pinky1) -> /pinky1/amcl_pose
ros2 run topic_tools relay /amcl_pose /pinky1/amcl_pose &
ros2 run topic_tools relay /odom /pinky1/odom &
ros2 run topic_tools relay /battery/voltage /pinky1/battery/voltage &
ros2 run topic_tools relay /battery/present /pinky1/battery/present &

# Pinky1 action relays
ros2 run topic_tools relay /follow_waypoints/_action/feedback /pinky1/follow_waypoints/_action/feedback &
ros2 run topic_tools relay /follow_waypoints/_action/status /pinky1/follow_waypoints/_action/status &
ros2 run topic_tools relay /navigate_to_pose/_action/feedback /pinky1/navigate_to_pose/_action/feedback &
ros2 run topic_tools relay /navigate_to_pose/_action/status /pinky1/navigate_to_pose/_action/status &

# Pinky1 reverse relays: /pinky1/initialpose -> /initialpose (to domain 11)
# These need special handling as we need domain-specific relaying
# Skip for now - the reverse bridge should handle /pinky1/* topics directly

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Domain Bridge Started Successfully${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Bridges running:"
echo "  - Pinky1 (Domain 11) <-> Main PC (Domain 25)"
echo "  - Pinky2 (Domain 12) <-> Main PC (Domain 25)"
echo "  - Arm A  (Domain 20) <-> Main PC (Domain 25)"
echo "  - Arm B  (Domain 21) <-> Main PC (Domain 25)"
echo ""
echo "To check topics: ros2 topic list"
echo "To stop: pkill -f domain_bridge && pkill -f 'topic_tools relay'"

# Keep script running
wait
