#!/bin/bash
# FMS 실행 스크립트 - fleet_interfaces 의존성 포함

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 1. roscamp-repo-1의 fleet_interfaces 포함
source "$REPO_ROOT/install/setup.bash"

# 2. FMS 워크스페이스
source "$REPO_ROOT/fms/install/setup.bash"

# 3. ROS2 Domain ID 설정 및 실행
export ROS_DOMAIN_ID=25
ros2 run fms fms_node "$@"
