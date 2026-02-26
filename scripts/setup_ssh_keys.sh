#!/bin/bash
# 모든 로봇에 SSH 키 설정 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo "Kitchmatics 로봇 SSH 키 설정"
echo "======================================${NC}"
echo ""

# SSH 키 생성 (없는 경우)
if [ ! -f ~/.ssh/id_rsa ]; then
    echo -e "${YELLOW}SSH 키가 없습니다. 새로 생성합니다...${NC}"
    ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
    echo -e "${GREEN}✓ SSH 키 생성 완료${NC}"
else
    echo -e "${GREEN}✓ SSH 키가 이미 존재합니다${NC}"
fi

echo ""
echo -e "${BLUE}======================================"
echo "SSH 키를 모든 로봇에 복사합니다"
echo "각 로봇의 비밀번호는 1입니다"
echo "======================================${NC}"
echo ""

# pinky1 (이미 설정되어 있을 수 있음)
echo -e "${YELLOW}[1/5] pinky1 (192.168.1.7) 설정 중...${NC}"
if ssh -o BatchMode=yes -o ConnectTimeout=2 pinky@192.168.1.7 'exit' 2>/dev/null; then
    echo -e "${GREEN}✓ pinky1 SSH 키가 이미 설정되어 있습니다${NC}"
else
    ssh-copy-id -o StrictHostKeyChecking=no pinky@192.168.1.7
    echo -e "${GREEN}✓ pinky1 SSH 키 복사 완료${NC}"
fi

# pinky2 (이미 설정되어 있을 수 있음)
echo ""
echo -e "${YELLOW}[2/5] pinky2 (192.168.1.6) 설정 중...${NC}"
if ssh -o BatchMode=yes -o ConnectTimeout=2 pinky@192.168.1.6 'exit' 2>/dev/null; then
    echo -e "${GREEN}✓ pinky2 SSH 키가 이미 설정되어 있습니다${NC}"
else
    ssh-copy-id -o StrictHostKeyChecking=no pinky@192.168.1.6
    echo -e "${GREEN}✓ pinky2 SSH 키 복사 완료${NC}"
fi

# pinky3 (선택사항)
echo ""
echo -e "${YELLOW}[3/5] pinky3 (192.168.1.11) 설정 중... (선택사항)${NC}"
if ping -c 1 -W 1 192.168.1.11 &> /dev/null; then
    if ssh -o BatchMode=yes -o ConnectTimeout=2 pinky@192.168.1.11 'exit' 2>/dev/null; then
        echo -e "${GREEN}✓ pinky3 SSH 키가 이미 설정되어 있습니다${NC}"
    else
        ssh-copy-id -o StrictHostKeyChecking=no pinky@192.168.1.11 || echo -e "${YELLOW}⚠ pinky3 설정 스킵됨${NC}"
    fi
else
    echo -e "${YELLOW}⚠ pinky3가 오프라인입니다. 스킵합니다.${NC}"
fi

# jetcobot A
echo ""
echo -e "${YELLOW}[4/5] jetcobot A (192.168.1.4) 설정 중...${NC}"
if ssh -o BatchMode=yes -o ConnectTimeout=2 jetcobot@192.168.1.4 'exit' 2>/dev/null; then
    echo -e "${GREEN}✓ jetcobot A SSH 키가 이미 설정되어 있습니다${NC}"
else
    ssh-copy-id -o StrictHostKeyChecking=no jetcobot@192.168.1.4
    echo -e "${GREEN}✓ jetcobot A SSH 키 복사 완료${NC}"
fi

# jetcobot B
echo ""
echo -e "${YELLOW}[5/5] jetcobot B (192.168.1.10) 설정 중...${NC}"
if ssh -o BatchMode=yes -o ConnectTimeout=2 jetcobot@192.168.1.10 'exit' 2>/dev/null; then
    echo -e "${GREEN}✓ jetcobot B SSH 키가 이미 설정되어 있습니다${NC}"
else
    ssh-copy-id -o StrictHostKeyChecking=no jetcobot@192.168.1.10
    echo -e "${GREEN}✓ jetcobot B SSH 키 복사 완료${NC}"
fi

echo ""
echo -e "${BLUE}======================================"
echo "설정 완료! 연결 테스트 중..."
echo "======================================${NC}"
echo ""

# 연결 테스트
test_connection() {
    local user=$1
    local host=$2
    local name=$3

    if ssh -o BatchMode=yes -o ConnectTimeout=2 ${user}@${host} 'exit' 2>/dev/null; then
        echo -e "${GREEN}✅ ${name} 연결 성공${NC}"
        return 0
    else
        echo -e "${RED}❌ ${name} 연결 실패${NC}"
        return 1
    fi
}

test_connection "pinky" "192.168.1.7" "pinky1"
test_connection "pinky" "192.168.1.6" "pinky2"
test_connection "jetcobot" "192.168.1.4" "jetcobot A"
test_connection "jetcobot" "192.168.1.10" "jetcobot B"

echo ""
echo -e "${GREEN}======================================"
echo "✓ 모든 로봇에 비밀번호 없이 SSH 접속 가능!"
echo "======================================${NC}"
echo ""
echo -e "${BLUE}이제 다음 명령어를 실행하여 전체 시스템 테스트를 진행할 수 있습니다:${NC}"
echo ""
echo "  cd /home/gw/kitchmatics/roscamp-repo-1"
echo "  # Claude에게 '준비 완료. 전체 테스트 진행해줘' 라고 알려주세요"
echo ""
