#!/bin/bash
# =========================================================
# Kitchmatics - 전체 시스템 실행 스크립트
# Customer GUI → Main Server → FMS → Pinky Robot
# =========================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="/home/gw/kitchmatics/roscamp-repo-1"

echo -e "${BLUE}==========================================================${NC}"
echo -e "${BLUE}     Kitchmatics - 전체 시스템 실행${NC}"
echo -e "${BLUE}==========================================================${NC}"
echo ""
echo -e "${YELLOW}실행 순서:${NC}"
echo "  1. FMS Node (로봇팔 스킵 모드)"
echo "  2. Main Server"
echo "  3. Customer GUI 또는 테스트 스크립트"
echo ""

# ROS 2 환경 설정
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
elif [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
fi

# 워크스페이스 빌드 확인
if [ -f "$PROJECT_ROOT/install/setup.bash" ]; then
    source "$PROJECT_ROOT/install/setup.bash"
else
    echo -e "${YELLOW}워크스페이스가 빌드되지 않았습니다. 빌드를 진행합니다...${NC}"
    cd "$PROJECT_ROOT"
    colcon build --packages-select fleet_interfaces fms main_server
    source install/setup.bash
fi

echo ""
echo -e "${GREEN}터미널을 3개 열어서 다음 명령을 순서대로 실행하세요:${NC}"
echo ""
echo -e "${BLUE}[터미널 1] FMS 실행 (로봇팔 스킵 모드):${NC}"
echo "  cd $PROJECT_ROOT"
echo "  source install/setup.bash"
echo "  ros2 run fms fms_node --ros-args -p skip_robot_arm:=true"
echo ""
echo -e "${BLUE}[터미널 2] Main Server 실행:${NC}"
echo "  cd $PROJECT_ROOT"
echo "  source install/setup.bash"
echo "  ros2 run main_server main_server"
echo ""
echo -e "${BLUE}[터미널 3-A] Customer GUI 실행:${NC}"
echo "  cd $PROJECT_ROOT/app/gui/customer_gui"
echo "  python3 src/main.py"
echo ""
echo -e "${BLUE}[터미널 3-B] 또는 테스트 스크립트 사용:${NC}"
echo "  cd $PROJECT_ROOT"
echo "  python3 fms/scripts/send_order.py --table 1"
echo "  python3 fms/scripts/send_order.py --interactive"
echo ""
echo -e "${YELLOW}==========================================================${NC}"
echo -e "${YELLOW}  로봇팔 스킵 모드:${NC}"
echo -e "${YELLOW}  - Pinky가 pickup_spot 도착 후 3초 뒤 자동으로 테이블로 이동${NC}"
echo -e "${YELLOW}  - 로봇팔 연결 없이 서빙 로봇만 테스트 가능${NC}"
echo -e "${YELLOW}==========================================================${NC}"
