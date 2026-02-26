#!/bin/bash

# Kitchmatics 시스템 검증 스크립트
# 모든 로봇과 노드가 정상 실행되었는지 확인

set -e

REPO_PATH="/home/gw/kitchmatics/roscamp-repo-1"
source "${REPO_PATH}/install/setup.bash"

echo "=========================================="
echo "Kitchmatics 시스템 검증 시작"
echo "=========================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_domain() {
    local domain_id=$1
    local robot_name=$2
    local expected_topics=$3

    echo -e "${YELLOW}[검증] Domain ${domain_id} - ${robot_name}${NC}"

    export ROS_DOMAIN_ID=${domain_id}

    # 토픽 목록 가져오기
    local topics=$(ros2 topic list 2>/dev/null | grep "${robot_name}" | wc -l)

    if [ $topics -gt 0 ]; then
        echo -e "${GREEN}✓ ${robot_name} 토픽 발견: ${topics}개${NC}"
        ros2 topic list | grep "${robot_name}" | head -5

        # 핵심 토픽 확인
        for topic in $expected_topics; do
            if ros2 topic list | grep -q "${topic}"; then
                echo -e "${GREEN}  ✓ ${topic}${NC}"
            else
                echo -e "${RED}  ✗ ${topic} - 누락${NC}"
            fi
        done
        return 0
    else
        echo -e "${RED}✗ ${robot_name} 토픽 없음${NC}"
        return 1
    fi
    echo ""
}

# Pinky1 확인 (Domain 11)
check_domain 11 "pinky1" "/pinky1/odom /pinky1/amcl_pose /pinky1/cmd_vel"

echo ""

# Pinky2 확인 (Domain 12)
check_domain 12 "pinky2" "/pinky2/odom /pinky2/amcl_pose /pinky2/cmd_vel"

echo ""

# Pinky3 확인 (Domain 13) - 선택사항
echo -e "${YELLOW}[검증] Domain 13 - pinky3 (선택사항)${NC}"
export ROS_DOMAIN_ID=13
pinky3_topics=$(ros2 topic list 2>/dev/null | grep "pinky3" | wc -l)
if [ $pinky3_topics -gt 0 ]; then
    echo -e "${GREEN}✓ Pinky3 실행 중${NC}"
else
    echo -e "${YELLOW}⚠ Pinky3 실행 안됨 (선택사항)${NC}"
fi

echo ""

# Robot Arms 확인 (Domain 25)
echo -e "${YELLOW}[검증] Domain 25 - Robot Arms${NC}"
export ROS_DOMAIN_ID=25

# ArmA 확인
if ros2 topic list 2>/dev/null | grep -q "armA"; then
    echo -e "${GREEN}✓ ArmA (Sandwich Station) 실행 중${NC}"
    ros2 topic list | grep "armA" | head -3
else
    echo -e "${RED}✗ ArmA 실행 안됨${NC}"
fi

echo ""

# ArmB 확인
if ros2 topic list 2>/dev/null | grep -q "armB"; then
    echo -e "${GREEN}✓ ArmB (Sauce Station) 실행 중${NC}"
    ros2 topic list | grep "armB" | head -3
else
    echo -e "${RED}✗ ArmB 실행 안됨${NC}"
fi

echo ""
echo "=========================================="
echo "네트워크 연결 확인"
echo "=========================================="

# 핑 테스트
for ip in "192.168.1.7:pinky1" "192.168.1.6:pinky2" "192.168.1.11:pinky3" "192.168.1.4:armA" "192.168.1.10:armB"; do
    IFS=':' read -r addr name <<< "$ip"
    if ping -c 1 -W 1 "$addr" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ ${name} (${addr}) 연결됨${NC}"
    else
        echo -e "${RED}✗ ${name} (${addr}) 연결 실패${NC}"
    fi
done

echo ""
echo "=========================================="
echo "검증 완료"
echo "=========================================="
echo ""
echo "모든 로봇이 정상 실행되었다면, 다음 단계로 진행하세요:"
echo "  1. Domain Bridge 실행"
echo "  2. FMS 실행"
echo "  3. 통합 테스트 시작"
