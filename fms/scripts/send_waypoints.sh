#!/bin/bash
# Send waypoints to robot via SSH (FollowWaypoints action)
# Usage: ./send_waypoints.sh <robot_id> <waypoints_json>
# Example: ./send_waypoints.sh pinky1 '[{"x":0.78,"y":0.15},{"x":0.78,"y":0.35},{"x":0.585,"y":0.63}]'

ROBOT_ID=$1
WAYPOINTS_JSON=$2

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

# Convert JSON waypoints to ROS2 message format
POSES=$(python3 -c "
import json
waypoints = json.loads('$WAYPOINTS_JSON')
poses = []
for wp in waypoints:
    pose = '{header: {frame_id: \"map\"}, pose: {position: {x: %.3f, y: %.3f, z: 0.0}, orientation: {w: 1.0}}}' % (wp['x'], wp['y'])
    poses.append(pose)
print('[' + ', '.join(poses) + ']')
")

ssh pinky@$IP "source /opt/ros/jazzy/setup.bash && source ~/pinky_pro/install/setup.bash && ROS_DOMAIN_ID=$DOMAIN ros2 action send_goal /follow_waypoints nav2_msgs/action/FollowWaypoints '{poses: $POSES}' --feedback" &

echo "Waypoints sent to $ROBOT_ID"
