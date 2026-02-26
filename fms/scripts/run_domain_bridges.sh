#!/bin/bash
# Domain Bridge 실행 스크립트
# 3개 로봇(pinky1, pinky2, pinky3)의 domain bridge를 실행합니다.
#
# 사용법:
#   ./fms/scripts/run_domain_bridges.sh
#
# 또는 launch 파일 사용:
#   ROS_DOMAIN_ID=25 ros2 launch fms domain_bridges.launch.py

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$(dirname "$SCRIPT_DIR")/config"

# ROS2 환경 확인
if ! command -v ros2 &> /dev/null; then
    echo "Error: ros2 command not found. Please source ROS2 setup."
    exit 1
fi

# FMS Domain ID 설정
export ROS_DOMAIN_ID=25

echo "============================================"
echo "Starting Domain Bridges for Kitchmatics FMS"
echo "============================================"
echo "FMS Domain ID: $ROS_DOMAIN_ID"
echo "Config directory: $CONFIG_DIR"
echo ""
echo "Bridges:"
echo "  - pinky1: Domain 11 <-> 25"
echo "  - pinky2: Domain 12 <-> 25"
echo "  - pinky3: Domain 13 <-> 25"
echo "============================================"
echo ""

# 설정 파일 존재 확인
for robot in pinky1 pinky2 pinky3; do
    config_file="$CONFIG_DIR/domain_bridge_${robot}.yaml"
    if [ ! -f "$config_file" ]; then
        echo "Error: Config file not found: $config_file"
        exit 1
    fi
done

# 방법 1: 단일 프로세스로 3개 설정 파일 로드 (권장)
echo "Starting domain_bridge with all 3 robot configs..."
ros2 run domain_bridge domain_bridge \
    "$CONFIG_DIR/domain_bridge_pinky1.yaml" \
    "$CONFIG_DIR/domain_bridge_pinky2.yaml" \
    "$CONFIG_DIR/domain_bridge_pinky3.yaml"

# 방법 2: 개별 프로세스로 실행 (필요시 주석 해제)
# ros2 run domain_bridge domain_bridge "$CONFIG_DIR/domain_bridge_pinky1.yaml" &
# ros2 run domain_bridge domain_bridge "$CONFIG_DIR/domain_bridge_pinky2.yaml" &
# ros2 run domain_bridge domain_bridge "$CONFIG_DIR/domain_bridge_pinky3.yaml" &
# wait
