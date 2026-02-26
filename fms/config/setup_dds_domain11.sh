#!/bin/bash
# Main PC DDS Setup for accessing pinky1 (domain 11)
# Use this to test connection to pinky1

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
export ROS_DOMAIN_ID=11

echo "Main PC -> pinky1 DDS Environment Set:"
echo "  RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION"
echo "  CYCLONEDDS_URI: $CYCLONEDDS_URI"
echo "  ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
