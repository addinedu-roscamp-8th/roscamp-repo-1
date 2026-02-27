#!/bin/bash
# Complete Domain Bridge Startup Script for Kitchmatics FMS
# Handles all robots with proper namespace remapping

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} Kitchmatics Domain Bridge - Full Setup${NC}"
echo -e "${GREEN}========================================${NC}"

# Source ROS2
source /opt/ros/jazzy/setup.bash
source ~/kitchmatics/roscamp-repo-1/install/setup.bash
export ROS_DOMAIN_ID=25

# Kill existing processes
echo -e "${YELLOW}Stopping existing bridges...${NC}"
pkill -9 -f domain_bridge 2>/dev/null || true
sleep 2

# Create bridge configs
CONFIG_DIR=/tmp/kitchmatics_bridges

mkdir -p $CONFIG_DIR

# ========== PINKY1 (Domain 11 <-> 25) ==========
cat > $CONFIG_DIR/pinky1_to_fms.yaml << 'EOF'
name: pinky1_to_fms
from_domain: 11
to_domain: 25
wait_for_publisher: true
topics:
  amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
  odom:
    type: nav_msgs/msg/Odometry
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

cat > $CONFIG_DIR/fms_to_pinky1.yaml << 'EOF'
name: fms_to_pinky1
from_domain: 25
to_domain: 11
topics:
  pinky1_initialpose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
  pinky1_goal_pose:
    type: geometry_msgs/msg/PoseStamped
services:
  pinky1_fw_send:
    type: nav2_msgs/action/FollowWaypoints_SendGoal
  pinky1_fw_cancel:
    type: action_msgs/srv/CancelGoal
  pinky1_fw_result:
    type: nav2_msgs/action/FollowWaypoints_GetResult
  pinky1_nav_send:
    type: nav2_msgs/action/NavigateToPose_SendGoal
  pinky1_nav_cancel:
    type: action_msgs/srv/CancelGoal
  pinky1_nav_result:
    type: nav2_msgs/action/NavigateToPose_GetResult
EOF

# ========== PINKY2 (Domain 12 <-> 25) ==========
cat > $CONFIG_DIR/pinky2_to_fms.yaml << 'EOF'
name: pinky2_to_fms
from_domain: 12
to_domain: 25
wait_for_publisher: true
topics:
  amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
  odom:
    type: nav_msgs/msg/Odometry
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

cat > $CONFIG_DIR/fms_to_pinky2.yaml << 'EOF'
name: fms_to_pinky2
from_domain: 25
to_domain: 12
topics:
  pinky2_initialpose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
  pinky2_goal_pose:
    type: geometry_msgs/msg/PoseStamped
services:
  pinky2_fw_send:
    type: nav2_msgs/action/FollowWaypoints_SendGoal
  pinky2_fw_cancel:
    type: action_msgs/srv/CancelGoal
  pinky2_fw_result:
    type: nav2_msgs/action/FollowWaypoints_GetResult
  pinky2_nav_send:
    type: nav2_msgs/action/NavigateToPose_SendGoal
  pinky2_nav_cancel:
    type: action_msgs/srv/CancelGoal
  pinky2_nav_result:
    type: nav2_msgs/action/NavigateToPose_GetResult
EOF

# ========== ROBOT ARMS (Domain 20, 21 <-> 25) ==========
cat > $CONFIG_DIR/arm_a_to_fms.yaml << 'EOF'
name: arm_a_to_fms
from_domain: 20
to_domain: 25
wait_for_publisher: true
topics:
  arm_a/status:
    type: std_msgs/msg/String
EOF

cat > $CONFIG_DIR/fms_to_arm_a.yaml << 'EOF'
name: fms_to_arm_a
from_domain: 25
to_domain: 20
topics:
  arm_a/cmd:
    type: std_msgs/msg/String
EOF

cat > $CONFIG_DIR/arm_b_to_fms.yaml << 'EOF'
name: arm_b_to_fms
from_domain: 21
to_domain: 25
wait_for_publisher: true
topics:
  arm_b/status:
    type: std_msgs/msg/String
  verify/status:
    type: std_msgs/msg/String
  cooking/loading_complete:
    type: fleet_interfaces/msg/LoadingComplete
EOF

cat > $CONFIG_DIR/fms_to_arm_b.yaml << 'EOF'
name: fms_to_arm_b
from_domain: 25
to_domain: 21
topics:
  arm_b/cmd:
    type: std_msgs/msg/String
  verify/cmd:
    type: std_msgs/msg/String
  cooking/order:
    type: fleet_interfaces/msg/CookingOrder
  fms/pickup_arrival:
    type: fleet_interfaces/msg/PickupArrival
EOF

echo -e "${GREEN}Starting bridges...${NC}"

# Start Pinky1 bridges with remapping
echo "Starting Pinky1 bridge (Domain 11 -> 25)..."
ros2 run domain_bridge domain_bridge $CONFIG_DIR/pinky1_to_fms.yaml \
  --ros-args \
  -r amcl_pose:=pinky1/amcl_pose \
  -r odom:=pinky1/odom \
  -r battery/voltage:=pinky1/battery/voltage \
  -r battery/present:=pinky1/battery/present \
  -r follow_waypoints/_action/feedback:=pinky1/follow_waypoints/_action/feedback \
  -r follow_waypoints/_action/status:=pinky1/follow_waypoints/_action/status \
  -r navigate_to_pose/_action/feedback:=pinky1/navigate_to_pose/_action/feedback \
  -r navigate_to_pose/_action/status:=pinky1/navigate_to_pose/_action/status &
sleep 1

echo "Starting Pinky1 reverse bridge (Domain 25 -> 11)..."
ros2 run domain_bridge domain_bridge $CONFIG_DIR/fms_to_pinky1.yaml \
  --ros-args \
  -r pinky1_initialpose:=initialpose \
  -r pinky1_goal_pose:=goal_pose \
  -r pinky1_fw_send:=follow_waypoints/_action/send_goal \
  -r pinky1_fw_cancel:=follow_waypoints/_action/cancel_goal \
  -r pinky1_fw_result:=follow_waypoints/_action/get_result \
  -r pinky1_nav_send:=navigate_to_pose/_action/send_goal \
  -r pinky1_nav_cancel:=navigate_to_pose/_action/cancel_goal \
  -r pinky1_nav_result:=navigate_to_pose/_action/get_result &
sleep 1

# Start Pinky2 bridges with remapping
echo "Starting Pinky2 bridge (Domain 12 -> 25)..."
ros2 run domain_bridge domain_bridge $CONFIG_DIR/pinky2_to_fms.yaml \
  --ros-args \
  -r amcl_pose:=pinky2/amcl_pose \
  -r odom:=pinky2/odom \
  -r battery/voltage:=pinky2/battery/voltage \
  -r battery/present:=pinky2/battery/present \
  -r follow_waypoints/_action/feedback:=pinky2/follow_waypoints/_action/feedback \
  -r follow_waypoints/_action/status:=pinky2/follow_waypoints/_action/status \
  -r navigate_to_pose/_action/feedback:=pinky2/navigate_to_pose/_action/feedback \
  -r navigate_to_pose/_action/status:=pinky2/navigate_to_pose/_action/status &
sleep 1

echo "Starting Pinky2 reverse bridge (Domain 25 -> 12)..."
ros2 run domain_bridge domain_bridge $CONFIG_DIR/fms_to_pinky2.yaml \
  --ros-args \
  -r pinky2_initialpose:=initialpose \
  -r pinky2_goal_pose:=goal_pose \
  -r pinky2_fw_send:=follow_waypoints/_action/send_goal \
  -r pinky2_fw_cancel:=follow_waypoints/_action/cancel_goal \
  -r pinky2_fw_result:=follow_waypoints/_action/get_result \
  -r pinky2_nav_send:=navigate_to_pose/_action/send_goal \
  -r pinky2_nav_cancel:=navigate_to_pose/_action/cancel_goal \
  -r pinky2_nav_result:=navigate_to_pose/_action/get_result &
sleep 1

# Start Robot Arm bridges (no remapping needed)
echo "Starting Robot Arm bridges..."
ros2 run domain_bridge domain_bridge $CONFIG_DIR/arm_a_to_fms.yaml &
ros2 run domain_bridge domain_bridge $CONFIG_DIR/fms_to_arm_a.yaml &
ros2 run domain_bridge domain_bridge $CONFIG_DIR/arm_b_to_fms.yaml &
ros2 run domain_bridge domain_bridge $CONFIG_DIR/fms_to_arm_b.yaml &

sleep 3

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN} All Domain Bridges Started!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Bridges running for:"
echo "  - Pinky1 (Domain 11) <-> Main PC (Domain 25)"
echo "  - Pinky2 (Domain 12) <-> Main PC (Domain 25)"
echo "  - Arm A  (Domain 20) <-> Main PC (Domain 25)"
echo "  - Arm B  (Domain 21) <-> Main PC (Domain 25)"
echo ""
echo "Topic mapping:"
echo "  Domain 11: /amcl_pose -> Domain 25: /pinky1/amcl_pose"
echo "  Domain 12: /amcl_pose -> Domain 25: /pinky2/amcl_pose"
echo "  Domain 25: /pinky1/initialpose -> Domain 11: /initialpose"
echo "  Domain 25: /pinky2/initialpose -> Domain 12: /initialpose"
echo ""
echo "To stop all bridges: pkill -f domain_bridge"

# Wait for all background processes
wait
