#!/bin/bash
#
# Navigation System Diagnostic Script
# Purpose: Quickly identify navigation system issues
# Usage: ./diagnose_navigation.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Navigation System Diagnostic Tool${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Source ROS2 environment
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SOURCE_DIR/install/setup.bash"

# ============================================================================
# 1. Check Main PC Environment
# ============================================================================
echo -e "${BLUE}[1] Main PC Environment (Domain 25)${NC}"
echo "ROS_DOMAIN_ID: $ROS_DOMAIN_ID"
timeout 3 ros2 node list 2>/dev/null || echo -e "${RED}✗ Cannot list nodes${NC}"
echo ""

# ============================================================================
# 2. Check FMS Status
# ============================================================================
echo -e "${BLUE}[2] FMS Fleet Status${NC}"
timeout 3 ros2 topic echo /fms/fleet_status --once 2>/dev/null | head -30 || \
  echo -e "${RED}✗ No FMS fleet status${NC}"
echo ""

# ============================================================================
# 3. Check Domain Bridge Status
# ============================================================================
echo -e "${BLUE}[3] Domain Bridge Status${NC}"
ps aux | grep "domain_bridge" | grep -v grep && echo -e "${GREEN}✓ Domain Bridge running${NC}" || \
  echo -e "${RED}✗ Domain Bridge NOT running${NC}"
echo ""

# ============================================================================
# 4. Check Pinky1 Navigation Topics (Should be bridged from domain 11)
# ============================================================================
echo -e "${BLUE}[4] Pinky1 Navigation Topics (Domain 25 - Bridged)${NC}"
echo "Expected topics:"
for topic in "/pinky1/amcl_pose" "/pinky1/navigate_to_pose/_action/status" "/pinky1/odom"; do
    if ros2 topic list 2>/dev/null | grep -q "^${topic}$"; then
        echo -e "  ${GREEN}✓${NC} $topic"
    else
        echo -e "  ${RED}✗${NC} $topic (MISSING)"
    fi
done
echo ""

# ============================================================================
# 5. Check Pinky1 via SSH
# ============================================================================
echo -e "${BLUE}[5] Pinky1 Remote Status (Domain 11)${NC}"
if ssh -o ConnectTimeout=3 pinky@192.168.1.7 "exit" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} SSH connected to Pinky1"
    ssh pinky@192.168.1.7 "
        export ROS_DOMAIN_ID=11
        source /opt/ros/jazzy/setup.bash

        echo 'Pinky1 Nodes:'
        timeout 3 ros2 node list 2>/dev/null | sort || echo 'No nodes'

        echo ''
        echo 'Nav2 Status:'
        if timeout 3 ros2 node info /bt_navigator 2>/dev/null >/dev/null; then
            echo 'Found bt_navigator'
        else
            echo -e '${RED}✗ Missing bt_navigator (CRITICAL)${NC}'
        fi

        if timeout 3 ros2 node info /amcl 2>/dev/null >/dev/null; then
            echo 'Found amcl'
        else
            echo -e '${RED}✗ Missing amcl (CRITICAL)${NC}'
        fi

        echo ''
        echo 'Launch Status:'
        ps aux | grep -E 'nav2|bringup' | grep -v grep | head -5 || echo 'No nav2 processes'
    " 2>/dev/null
else
    echo -e "${RED}✗${NC} Cannot SSH to Pinky1 (192.168.1.7)"
fi
echo ""

# ============================================================================
# 6. Check Pinky2 via SSH
# ============================================================================
echo -e "${BLUE}[6] Pinky2 Remote Status (Domain 12)${NC}"
if ssh -o ConnectTimeout=3 pinky@192.168.1.6 "exit" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} SSH connected to Pinky2"
    ssh pinky@192.168.1.6 "
        export ROS_DOMAIN_ID=12
        source /opt/ros/jazzy/setup.bash

        echo 'Pinky2 Nodes:'
        timeout 3 ros2 node list 2>/dev/null || echo 'No nodes'

        echo ''
        echo 'Nav2 Status:'
        timeout 3 ros2 node info /bt_navigator 2>/dev/null >/dev/null && \
            echo 'Found bt_navigator' || echo -e '${RED}✗ Missing bt_navigator${NC}'
    " 2>/dev/null
else
    echo -e "${RED}✗${NC} Cannot SSH to Pinky2 (192.168.1.6)"
fi
echo ""

# ============================================================================
# 7. Test Navigation Goal (if pinky1 has nav2)
# ============================================================================
echo -e "${BLUE}[7] Navigation Goal Test${NC}"
if ros2 action list 2>/dev/null | grep -q "/pinky1/navigate_to_pose"; then
    echo -e "${GREEN}✓${NC} /pinky1/navigate_to_pose action available"
    echo "Test: Would send goal to (1.0, 0.5)"
else
    echo -e "${RED}✗${NC} /pinky1/navigate_to_pose action NOT available"
    echo "Reason: Nav2 stack likely not running on Pinky1"
fi
echo ""

# ============================================================================
# 8. Summary and Recommendations
# ============================================================================
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Diagnostic Summary${NC}"
echo -e "${BLUE}========================================${NC}"

NAV_RUNNING=false
BRIDGE_WORKING=false
AMCL_ACTIVE=false

if ssh -o ConnectTimeout=3 pinky@192.168.1.7 "
  export ROS_DOMAIN_ID=11
  source /opt/ros/jazzy/setup.bash
  timeout 3 ros2 node info /bt_navigator 2>/dev/null >/dev/null
" 2>/dev/null; then
    NAV_RUNNING=true
fi

if ros2 topic list 2>/dev/null | grep -q "/pinky1/amcl_pose"; then
    BRIDGE_WORKING=true
fi

if timeout 2 ros2 topic echo /pinky1/amcl_pose --once 2>/dev/null | grep -q "pose"; then
    AMCL_ACTIVE=true
fi

echo ""
echo "Status Summary:"
echo -e "  Nav2 Running on Pinky1: $([ "$NAV_RUNNING" = true ] && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}")"
echo -e "  Domain Bridge Working: $([ "$BRIDGE_WORKING" = true ] && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}")"
echo -e "  AMCL Active: $([ "$AMCL_ACTIVE" = true ] && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}")"
echo ""

if [ "$NAV_RUNNING" = false ]; then
    echo -e "${RED}CRITICAL ISSUE:${NC} Nav2 not running on Pinky1"
    echo "Action: SSH to Pinky1 and run:"
    echo "  $ export ROS_DOMAIN_ID=11"
    echo "  $ source /opt/ros/jazzy/setup.bash"
    echo "  $ ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml"
    echo ""
fi

if [ "$BRIDGE_WORKING" = false ] && [ "$NAV_RUNNING" = true ]; then
    echo -e "${RED}BRIDGE ISSUE:${NC} Domain bridge not forwarding Nav2 topics"
    echo "Action: Check domain bridge configuration and restart"
    echo ""
fi

if [ "$AMCL_ACTIVE" = false ] && [ "$BRIDGE_WORKING" = true ]; then
    echo -e "${YELLOW}LOCALIZATION ISSUE:${NC} AMCL not publishing poses"
    echo "Action: Set initial pose on Pinky1"
    echo "  $ ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{...}'"
    echo ""
fi

echo -e "${BLUE}========================================${NC}"
echo "For detailed analysis, see:"
echo "  /home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_VALIDATION_REPORT.md"
echo -e "${BLUE}========================================${NC}"
