#!/bin/bash
# Send navigation goal to robot via SSH
# Usage: ./send_nav_goal.sh <robot_id> <x> <y> <theta>

ROBOT_ID=$1
X=$2
Y=$3
THETA=${4:-0.0}

case $ROBOT_ID in
    pinky1)
        IP="192.168.1.7"
        DOMAIN=11
        ;;
    pinky2)
        IP="192.168.1.6"
        DOMAIN=12
        ;;
    pinky3)
        IP="192.168.1.11"
        DOMAIN=13
        ;;
    *)
        echo "Unknown robot: $ROBOT_ID"
        exit 1
        ;;
esac

# Calculate quaternion from theta (rotation around z-axis)
W=$(python3 -c "import math; print(math.cos($THETA/2))")
Z=$(python3 -c "import math; print(math.sin($THETA/2))")

ssh pinky@$IP "source /opt/ros/jazzy/setup.bash && source ~/pinky_pro/install/setup.bash && ROS_DOMAIN_ID=$DOMAIN ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose '{pose: {header: {frame_id: \"map\"}, pose: {position: {x: $X, y: $Y, z: 0.0}, orientation: {z: $Z, w: $W}}}}' --feedback" &

echo "Navigation goal sent to $ROBOT_ID at ($X, $Y, $THETA)"
