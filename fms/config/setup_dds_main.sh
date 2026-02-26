#!/bin/bash
# Main PC DDS Setup for WiFi Network
# Use this before running any ROS2 commands on Main PC

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
export ROS_DOMAIN_ID=25

echo "Main PC DDS Environment Set:"
echo "  RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION"
echo "  CYCLONEDDS_URI: $CYCLONEDDS_URI"
echo "  ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
