#!/bin/bash
# =========================================================
# Kitchmatics FMS - Start FMS Server Script
# Closed Network: WiFi kitchmatics
# =========================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
FMS_DIR="$PROJECT_ROOT/fms"

echo -e "${BLUE}==========================================================${NC}"
echo -e "${BLUE}     Kitchmatics FMS - Closed Network Server${NC}"
echo -e "${BLUE}==========================================================${NC}"
echo ""

# Check network connectivity
echo -e "${YELLOW}Checking network connectivity...${NC}"

# Check if connected to kitchmatics WiFi
SSID=$(iwgetid -r 2>/dev/null || echo "")
if [ "$SSID" = "kitchmatics" ]; then
    echo -e "${GREEN}✓ Connected to WiFi: kitchmatics${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Not connected to 'kitchmatics' WiFi (current: $SSID)${NC}"
fi

# Get local IP
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo -e "${GREEN}✓ Local IP: $LOCAL_IP${NC}"

# Check configured robots
echo ""
echo -e "${YELLOW}Checking robot connectivity...${NC}"

# Read robot IPs from config (simple grep approach)
CONFIG_FILE="$FMS_DIR/config/network_config.yaml"

if [ -f "$CONFIG_FILE" ]; then
    # Extract robot IPs and ping them
    echo "Testing connections to configured robots..."

    # PinkyPro robots
    echo -e "\n${BLUE}Mobile Robots (PinkyPro):${NC}"
    PINKY_IPS=$(grep -A2 "pinky_" "$CONFIG_FILE" | grep "ip_address" | awk -F'"' '{print $2}' | grep -v "^$")
    for IP in $PINKY_IPS; do
        if ping -c 1 -W 1 "$IP" &>/dev/null; then
            echo -e "  ${GREEN}✓ $IP - Reachable${NC}"
        else
            echo -e "  ${RED}✗ $IP - Unreachable${NC}"
        fi
    done

    # JetCobot robots
    echo -e "\n${BLUE}Cobot Arms (JetCobot):${NC}"
    COBOT_IPS=$(grep -A2 "jetcobot_" "$CONFIG_FILE" | grep "ip_address" | awk -F'"' '{print $2}' | grep -v "^$")
    for IP in $COBOT_IPS; do
        if ping -c 1 -W 1 "$IP" &>/dev/null; then
            echo -e "  ${GREEN}✓ $IP - Reachable${NC}"
        else
            echo -e "  ${RED}✗ $IP - Unreachable${NC}"
        fi
    done
else
    echo -e "${RED}Config file not found: $CONFIG_FILE${NC}"
fi

echo ""

# =========================================================
# 파일 동기화 (nav2_params.yaml, mapper_params.yaml)
# =========================================================
echo -e "${YELLOW}Syncing parameter files to robots...${NC}"

cd "$PROJECT_ROOT"
python3 fms/scripts/robot_file_sync.py --all --sync 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Parameter files synced successfully${NC}"
else
    echo -e "${YELLOW}⚠ Some files may not have synced (robots offline?)${NC}"
fi

echo ""
echo -e "${YELLOW}Starting FMS TCP Server...${NC}"

# Source ROS 2 environment
if [ -f "/opt/ros/jazzy/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash
elif [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
fi

# Source workspace if available
WORKSPACE="$PROJECT_ROOT"
if [ -f "$WORKSPACE/install/setup.bash" ]; then
    source "$WORKSPACE/install/setup.bash"
fi

# Set Python path
export PYTHONPATH="$FMS_DIR/fms:$PYTHONPATH"

# Run FMS TCP Server
echo -e "${GREEN}Starting server on port 9000...${NC}"
echo ""

cd "$FMS_DIR"
python3 -m fms.tcp_communication --mode server --port 9000

# If using ROS 2 node:
# ros2 run fms fms_tcp_node --ros-args -p tcp_port:=9000
