#!/bin/bash
# FMS 전체 시스템 재시작 스크립트
# 사용법: ./restart_fms.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Kitchmatics FMS 시스템 재시작"
echo "=========================================="

# 종료
echo ""
echo ">>> 기존 프로세스 종료 중..."
"$SCRIPT_DIR/stop_fms.sh"

sleep 2

# 시작
echo ""
echo ">>> 시스템 재시작 중..."
"$SCRIPT_DIR/start_fms.sh"
