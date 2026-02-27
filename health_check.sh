#!/bin/bash
# Kitchmatics FMS Health Check Script
# Date: 2026-02-26

echo "=========================================="
echo "Kitchmatics FMS Health Check"
echo "=========================================="
echo "Time: $(date)"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check FMS process
echo -n "FMS Process: "
FMS_PID=$(pgrep -f "fms_node" | head -1)
if [ -n "$FMS_PID" ]; then
    echo -e "${GREEN}✅ Running (PID: $FMS_PID)${NC}"
else
    echo -e "${RED}❌ Not Running${NC}"
fi

# Check port 9000
echo -n "Port 9000: "
PORT_COUNT=$(netstat -tlnp 2>/dev/null | grep 9000 | wc -l)
if [ "$PORT_COUNT" -eq 1 ]; then
    echo -e "${GREEN}✅ Single Listener${NC}"
elif [ "$PORT_COUNT" -eq 0 ]; then
    echo -e "${RED}❌ No Listeners${NC}"
else
    echo -e "${YELLOW}⚠️  Multiple Listeners ($PORT_COUNT)${NC}"
fi

# Check recent errors in log
echo -n "Recent Errors: "
if [ -f /tmp/fms_fixed.log ]; then
    ERROR_COUNT=$(tail -100 /tmp/fms_fixed.log 2>/dev/null | grep -c "ERROR" || echo 0)
    WARNING_COUNT=$(tail -100 /tmp/fms_fixed.log 2>/dev/null | grep -c "WARNING" || echo 0)
    if [ "$ERROR_COUNT" -eq 0 ]; then
        echo -e "${GREEN}✅ No errors (${WARNING_COUNT} warnings)${NC}"
    else
        echo -e "${YELLOW}⚠️  ${ERROR_COUNT} errors, ${WARNING_COUNT} warnings${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Log file not found${NC}"
fi

# Check fleet status
echo -n "Fleet Status: "
export ROS_DOMAIN_ID=25
cd /home/gw/kitchmatics/roscamp-repo-1 2>/dev/null
source install/setup.bash 2>/dev/null
ROBOT_COUNT=$(timeout 3 ros2 topic echo /fms/fleet_status --once 2>/dev/null | grep "robot_id:" | wc -l)
if [ "$ROBOT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Tracking ${ROBOT_COUNT} robots${NC}"
else
    echo -e "${YELLOW}⚠️  No robots tracked (timeout or not publishing)${NC}"
fi

# Check disk space
echo -n "Disk Space: "
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo -e "${GREEN}✅ ${DISK_USAGE}% used${NC}"
elif [ "$DISK_USAGE" -lt 90 ]; then
    echo -e "${YELLOW}⚠️  ${DISK_USAGE}% used${NC}"
else
    echo -e "${RED}❌ ${DISK_USAGE}% used (critical)${NC}"
fi

echo ""
echo "=========================================="
echo "Health Check Complete"
echo "=========================================="
