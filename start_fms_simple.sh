#!/bin/bash
# FMS 단순 시작 스크립트 - 중복 실행 방지
# 사용법: ./start_fms_simple.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/tmp"

echo "=========================================="
echo "FMS Simple Start Script"
echo "=========================================="

# 1. 기존 프로세스 종료
echo "[1/4] 기존 FMS 관련 프로세스 종료..."
pkill -9 -f "fms_closed_network" 2>/dev/null || true
pkill -9 -f "ros2 launch fms" 2>/dev/null || true
pkill -9 -f "domain_bridge" 2>/dev/null || true
pkill -9 -f "fms_node" 2>/dev/null || true
pkill -9 -f "sandwich_coordinator" 2>/dev/null || true
sleep 2

# 중복 확인
COUNT=$(ps aux | grep -E "domain_bridge|fms_node|sandwich_coordinator" | grep -v grep | wc -l)
if [ "$COUNT" -gt 0 ]; then
    echo "경고: 일부 프로세스가 아직 실행 중 ($COUNT개). 강제 종료 시도..."
    ps aux | grep -E "domain_bridge|fms_node|sandwich_coordinator" | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
    sleep 2
fi

# 2. 환경 설정
echo "[2/4] ROS2 환경 설정..."
source /opt/ros/jazzy/setup.bash
source "$SCRIPT_DIR/install/setup.bash"
export ROS_DOMAIN_ID=25

# 3. FMS 시작 (launch 파일 사용)
echo "[3/4] FMS 시스템 시작..."
ros2 launch fms fms_closed_network.launch.py > "$LOG_DIR/fms_current.log" 2>&1 &
FMS_PID=$!
echo "FMS Launch PID: $FMS_PID"

sleep 5

# 4. Coordinator 시작
echo "[4/4] Coordinator 시작..."
cd "$SCRIPT_DIR/fms/coordinator_Ws"
bash run_coordinator.sh > "$LOG_DIR/coordinator_current.log" 2>&1 &
COORD_PID=$!
echo "Coordinator PID: $COORD_PID"

sleep 3

# 상태 확인
echo ""
echo "=========================================="
echo "시작 완료! 실행 중인 노드:"
echo "=========================================="
ros2 node list 2>/dev/null | head -20

echo ""
echo "로그 파일:"
echo "  FMS: $LOG_DIR/fms_current.log"
echo "  Coordinator: $LOG_DIR/coordinator_current.log"
echo ""
echo "종료하려면: pkill -f 'fms_closed_network' && pkill -f 'domain_bridge' && pkill -f 'sandwich_coordinator'"
