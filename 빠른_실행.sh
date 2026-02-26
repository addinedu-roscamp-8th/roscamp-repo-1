#!/bin/bash
# Kitchmatics FMS 빠른 실행 스크립트
# FMS, Domain Bridge, GUI를 위한 별도 터미널에서 실행하세요

set -e

# 출력 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 색상 없음

# 사용법 표시 함수
usage() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}Kitchmatics FMS 빠른 실행${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""
    echo "사용법: $0 [fms|bridge|gui|check]"
    echo ""
    echo "명령어:"
    echo "  fms     - FMS 노드 시작 (터미널 1)"
    echo "  bridge  - Domain bridge 시작 (터미널 2)"
    echo "  gui     - Customer GUI 시작 (터미널 3)"
    echo "  check   - 시스템 준비 상태 확인"
    echo ""
    echo "예제:"
    echo "  # 터미널 1"
    echo "  ./빠른_실행.sh fms"
    echo ""
    echo "  # 터미널 2"
    echo "  ./빠른_실행.sh bridge"
    echo ""
    echo "  # 터미널 3"
    echo "  ./빠른_실행.sh gui"
    echo ""
    exit 1
}

# 사전 요구사항 확인 함수
check_system() {
    echo -e "${BLUE}시스템 준비 상태 확인 중...${NC}"
    echo ""

    # ROS 설치 확인
    if [ -f "/opt/ros/jazzy/setup.bash" ]; then
        echo -e "${GREEN}✓${NC} ROS Jazzy 설치됨"
    else
        echo -e "${RED}✗${NC} /opt/ros/jazzy에서 ROS Jazzy를 찾을 수 없습니다"
        exit 1
    fi

    # 워크스페이스 확인
    if [ -d "/home/gw/kitchmatics/roscamp-repo-1" ]; then
        echo -e "${GREEN}✓${NC} 워크스페이스 발견"
    else
        echo -e "${RED}✗${NC} /home/gw/kitchmatics/roscamp-repo-1에서 워크스페이스를 찾을 수 없습니다"
        exit 1
    fi

    # 빌드 확인
    if [ -d "/home/gw/kitchmatics/roscamp-repo-1/install" ]; then
        echo -e "${GREEN}✓${NC} 워크스페이스 빌드됨"
    else
        echo -e "${YELLOW}⚠${NC} 워크스페이스가 빌드되지 않았습니다. 실행하세요: colcon build --symlink-install"
    fi

    # Domain bridge 설정 확인
    if [ -f "/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml" ]; then
        echo -e "${GREEN}✓${NC} Domain bridge 설정 발견"
    else
        echo -e "${RED}✗${NC} Domain bridge 설정을 찾을 수 없습니다"
        exit 1
    fi

    # 네트워크 연결 확인
    echo ""
    echo -e "${BLUE}네트워크 연결 확인 중...${NC}"

    if ping -c 1 -W 1 192.168.1.7 &> /dev/null; then
        echo -e "${GREEN}✓${NC} pinky1 (192.168.1.7) 접근 가능"
    else
        echo -e "${YELLOW}⚠${NC} pinky1 (192.168.1.7) 접근 불가"
    fi

    if ping -c 1 -W 1 192.168.1.6 &> /dev/null; then
        echo -e "${GREEN}✓${NC} pinky2 (192.168.1.6) 접근 가능"
    else
        echo -e "${YELLOW}⚠${NC} pinky2 (192.168.1.6) 접근 불가"
    fi

    if ping -c 1 -W 1 192.168.1.4 &> /dev/null; then
        echo -e "${GREEN}✓${NC} jetcobot A (192.168.1.4) 접근 가능"
    else
        echo -e "${YELLOW}⚠${NC} jetcobot A (192.168.1.4) 접근 불가"
    fi

    if ping -c 1 -W 1 192.168.1.10 &> /dev/null; then
        echo -e "${GREEN}✓${NC} jetcobot B (192.168.1.10) 접근 가능"
    else
        echo -e "${YELLOW}⚠${NC} jetcobot B (192.168.1.10) 접근 불가"
    fi

    echo ""
    echo -e "${GREEN}시스템 확인 완료!${NC}"
    echo ""
    echo -e "${BLUE}다음 단계:${NC}"
    echo "  1. 터미널 1: ./빠른_실행.sh fms"
    echo "  2. 터미널 2: ./빠른_실행.sh bridge"
    echo "  3. 터미널 3: ./빠른_실행.sh gui"
    echo ""
}

# FMS 노드 시작 함수
start_fms() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}FMS 노드 시작 (터미널 1)${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""

    cd /home/gw/kitchmatics/roscamp-repo-1

    if [ ! -d "install" ]; then
        echo -e "${RED}에러: 워크스페이스가 빌드되지 않았습니다!${NC}"
        echo "실행하세요: colcon build --symlink-install --packages-select fleet_interfaces fms"
        exit 1
    fi

    source install/setup.bash
    export ROS_DOMAIN_ID=25

    echo -e "${GREEN}ROS_DOMAIN_ID를 25로 설정${NC}"
    echo -e "${GREEN}FMS 실행 중...${NC}"
    echo ""

    ros2 launch fms fms_closed_network.launch.py
}

# Domain bridge 시작 함수
start_bridge() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}Domain Bridge 시작 (터미널 2)${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""

    cd /home/gw/kitchmatics/roscamp-repo-1

    if [ ! -f "fms/config/domain_bridge_complete.yaml" ]; then
        echo -e "${RED}에러: Domain bridge 설정을 찾을 수 없습니다!${NC}"
        exit 1
    fi

    source install/setup.bash
    export ROS_DOMAIN_ID=25

    echo -e "${GREEN}ROS_DOMAIN_ID를 25로 설정${NC}"
    echo -e "${GREEN}Domain Bridge 실행 중...${NC}"
    echo ""
    echo -e "${YELLOW}참고: FMS가 로봇과 통신하려면 Domain bridge가 반드시 실행 중이어야 합니다${NC}"
    echo ""

    ros2 run domain_bridge domain_bridge fms/config/domain_bridge_complete.yaml
}

# GUI 시작 함수
start_gui() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}Customer GUI 시작 (터미널 3)${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""

    cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui

    if [ ! -d "$HOME/pyqt_venv" ]; then
        echo -e "${RED}에러: ~/pyqt_venv에서 PyQt 가상환경을 찾을 수 없습니다${NC}"
        echo "먼저 생성하거나 이 스크립트의 경로를 조정하세요"
        exit 1
    fi

    source ~/pyqt_venv/bin/activate

    echo -e "${GREEN}가상환경 활성화됨${NC}"
    echo -e "${GREEN}Customer GUI 실행 중...${NC}"
    echo ""
    echo -e "${YELLOW}192.168.1.3:9000에서 FMS에 연결 중${NC}"
    echo ""

    python src/main_fms_direct.py
}

# 메인 스크립트
case "$1" in
    fms)
        start_fms
        ;;
    bridge)
        start_bridge
        ;;
    gui)
        start_gui
        ;;
    check)
        check_system
        ;;
    *)
        usage
        ;;
esac
