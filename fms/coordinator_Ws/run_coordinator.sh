#!/bin/bash
# Sandwich Coordinator 실행 스크립트
# fleet_interfaces와 coordinator 환경을 모두 소싱합니다

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROSCAMP_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# 1. ROS2 기본 환경
source /opt/ros/jazzy/setup.bash

# 2. 메인 워크스페이스 (fleet_interfaces 포함)
if [ -f "$ROSCAMP_DIR/install/setup.bash" ]; then
    source "$ROSCAMP_DIR/install/setup.bash"
else
    echo "Warning: Main workspace setup not found at $ROSCAMP_DIR/install/setup.bash"
fi

# 3. Coordinator 워크스페이스
if [ -f "$SCRIPT_DIR/install/setup.bash" ]; then
    source "$SCRIPT_DIR/install/setup.bash"
else
    echo "Warning: Coordinator workspace setup not found at $SCRIPT_DIR/install/setup.bash"
fi

# Domain ID 설정 (FMS와 같은 Domain 25)
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-25}

echo "=========================================="
echo "Sandwich Coordinator"
echo "=========================================="
echo "ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
echo "Main workspace: $ROSCAMP_DIR/install"
echo "Coordinator workspace: $SCRIPT_DIR/install"
echo "=========================================="

# Coordinator 실행
exec ros2 run sandwich_coordinator sandwich_coordinator --ros-args -p test_mode:=${TEST_MODE:-false}
