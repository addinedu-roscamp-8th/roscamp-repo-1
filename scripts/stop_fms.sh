#!/bin/bash
# FMS 전체 시스템 종료 스크립트
# 사용법: ./stop_fms.sh

echo "=========================================="
echo "  Kitchmatics FMS 시스템 종료"
echo "=========================================="

echo ""
echo "[1/3] Coordinator 종료..."
pkill -f "sandwich_coordinator" 2>/dev/null && echo "  -> Coordinator 종료됨" || echo "  -> Coordinator 실행 중 아님"

echo ""
echo "[2/3] FMS 종료..."
pkill -f "fms_tcp_node" 2>/dev/null && echo "  -> FMS TCP Node 종료됨" || echo "  -> FMS 실행 중 아님"
pkill -f "fms_node" 2>/dev/null && echo "  -> FMS Node 종료됨" || echo "  -> FMS Node 실행 중 아님"

echo ""
echo "[3/3] Domain Bridge 종료..."
COUNT=$(pgrep -f "domain_bridge" | wc -l)
pkill -f "domain_bridge" 2>/dev/null && echo "  -> Domain Bridge ${COUNT}개 종료됨" || echo "  -> Domain Bridge 실행 중 아님"

sleep 1

echo ""
echo "=========================================="
echo "  FMS 시스템 종료 완료!"
echo "=========================================="

# 남은 프로세스 확인
REMAINING=$(pgrep -f "domain_bridge|fms_|sandwich_coordinator" | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo ""
    echo "경고: 아직 ${REMAINING}개 프로세스가 남아있습니다."
    echo "강제 종료하려면: pkill -9 -f 'domain_bridge|fms_|sandwich_coordinator'"
fi
