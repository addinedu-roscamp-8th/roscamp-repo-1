#!/bin/bash

# Kitchmatics 토픽 모니터링 스크립트
# Domain Bridge와 FMS가 정상 동작하는지 실시간으로 확인

REPO_PATH="/home/gw/kitchmatics/roscamp-repo-1"
source "${REPO_PATH}/install/setup.bash"
export ROS_DOMAIN_ID=25

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

clear

echo -e "${BLUE}=========================================="
echo "Kitchmatics 실시간 토픽 모니터링"
echo "==========================================${NC}"
echo ""
echo "Domain ID: 25 (Main PC)"
echo "종료: Ctrl+C"
echo ""

# 함수: 토픽 존재 여부 확인
check_topic() {
    local topic=$1
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi
}

# 함수: 토픽 Hz 확인
check_hz() {
    local topic=$1
    local hz=$(timeout 2 ros2 topic hz "$topic" 2>/dev/null | grep "average rate" | awk '{print $3}')
    if [ ! -z "$hz" ]; then
        echo -e "${GREEN}${hz} Hz${NC}"
    else
        echo -e "${YELLOW}0 Hz${NC}"
    fi
}

# 메인 루프
while true; do
    # 커서를 화면 상단으로 이동
    tput cup 7 0

    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}[Mobile Robots - Bridged Topics]${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    printf "%-35s %-10s %-15s\n" "Topic" "Status" "Rate"
    echo "----------------------------------------"

    # Pinky1
    printf "%-35s " "/pinky1/amcl_pose"
    printf "%-10s " "$(check_topic '/pinky1/amcl_pose')"
    printf "%-15s\n" "$(check_hz '/pinky1/amcl_pose')"

    printf "%-35s " "/pinky1/odom"
    printf "%-10s " "$(check_topic '/pinky1/odom')"
    printf "%-15s\n" "$(check_hz '/pinky1/odom')"

    # Pinky2
    printf "%-35s " "/pinky2/amcl_pose"
    printf "%-10s " "$(check_topic '/pinky2/amcl_pose')"
    printf "%-15s\n" "$(check_hz '/pinky2/amcl_pose')"

    printf "%-35s " "/pinky2/odom"
    printf "%-10s " "$(check_topic '/pinky2/odom')"
    printf "%-15s\n" "$(check_hz '/pinky2/odom')"

    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}[FMS <-> Coordinator Topics]${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    printf "%-35s %-10s\n" "Topic" "Status"
    echo "----------------------------------------"

    printf "%-35s " "/cooking/order"
    printf "%-10s\n" "$(check_topic '/cooking/order')"

    printf "%-35s " "/fms/pickup_arrival"
    printf "%-10s\n" "$(check_topic '/fms/pickup_arrival')"

    printf "%-35s " "/cooking/loading_complete"
    printf "%-10s\n" "$(check_topic '/cooking/loading_complete')"

    printf "%-35s " "/fms/fleet_status"
    printf "%-10s\n" "$(check_topic '/fms/fleet_status')"

    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}[Robot Arm Topics]${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    printf "%-35s %-10s\n" "Topic" "Status"
    echo "----------------------------------------"

    printf "%-35s " "/arm_a/cmd"
    printf "%-10s\n" "$(check_topic '/arm_a/cmd')"

    printf "%-35s " "/arm_a/status"
    printf "%-10s\n" "$(check_topic '/arm_a/status')"

    printf "%-35s " "/arm_b/cmd"
    printf "%-10s\n" "$(check_topic '/arm_b/cmd')"

    printf "%-35s " "/arm_b/status"
    printf "%-10s\n" "$(check_topic '/arm_b/status')"

    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "업데이트 시간: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # 2초마다 갱신
    sleep 2
done
