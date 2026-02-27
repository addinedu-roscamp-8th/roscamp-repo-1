#!/bin/bash
# FMS 전체 시스템 시작 스크립트
# 사용법: ./start_fms.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
FMS_DIR="$BASE_DIR/fms"
COORDINATOR_DIR="$FMS_DIR/coordinator_Ws"

echo "=========================================="
echo "  Kitchmatics FMS 시스템 시작"
echo "=========================================="

# ROS2 환경 설정
source /opt/ros/jazzy/setup.bash

# 1. Domain Bridge 시작
echo ""
echo "[1/4] Domain Bridge 시작..."
cd "$FMS_DIR"

ros2 run domain_bridge domain_bridge config/bridge_pinky1.yaml &
ros2 run domain_bridge domain_bridge config/bridge_pinky2.yaml &
ros2 run domain_bridge domain_bridge config/bridge_arm_a.yaml &
ros2 run domain_bridge domain_bridge config/bridge_arm_b.yaml &
ros2 run domain_bridge domain_bridge config/bridge_arm_a_cmd.yaml &
ros2 run domain_bridge domain_bridge config/bridge_arm_b_cmd.yaml &
ros2 run domain_bridge domain_bridge config/bridge_pinky1_reverse.yaml &
ros2 run domain_bridge domain_bridge config/bridge_pinky2_reverse.yaml &

sleep 2
echo "  -> Domain Bridge 8개 시작됨"

# 2. 로봇팔 리셋
echo ""
echo "[2/4] 로봇팔 리셋..."
export ROS_DOMAIN_ID=25

ros2 topic pub /arm_a/cmd std_msgs/msg/String "data: 'RESET'" --once &
ros2 topic pub /arm_b/cmd std_msgs/msg/String "data: 'RESET'" --once &
ros2 topic pub /verify/cmd std_msgs/msg/String "data: 'RESET'" --once &
wait

sleep 1
echo "  -> 로봇팔 리셋 완료"

# 3. FMS 시작
echo ""
echo "[3/4] FMS TCP Node 시작..."
cd "$BASE_DIR"
source install/setup.bash
export ROS_DOMAIN_ID=25

ros2 run fms fms_tcp_node &
FMS_PID=$!

sleep 2
echo "  -> FMS 시작됨 (PID: $FMS_PID)"

# 4. Coordinator 시작
echo ""
echo "[4/4] Sandwich Coordinator 시작..."
cd "$COORDINATOR_DIR"
source "$BASE_DIR/install/setup.bash"
source install/setup.bash
export ROS_DOMAIN_ID=25

ros2 run sandwich_coordinator sandwich_coordinator &
COORD_PID=$!

sleep 2
echo "  -> Coordinator 시작됨 (PID: $COORD_PID)"

echo ""
echo "=========================================="
echo "  FMS 시스템 시작 완료!"
echo "=========================================="
echo ""
echo "실행 중인 프로세스:"
echo "  - Domain Bridge: 8개"
echo "  - FMS TCP Node: PID $FMS_PID"
echo "  - Coordinator: PID $COORD_PID"
echo ""
echo "GUI 실행:"
echo "  cd ~/kitchmatics/roscamp-repo-1/app/gui/customer_gui"
echo "  python3 src/main_fms_direct.py --table 1"
echo ""
echo "종료하려면: ./stop_fms.sh"
echo ""

# 프로세스가 종료되지 않도록 대기
wait
