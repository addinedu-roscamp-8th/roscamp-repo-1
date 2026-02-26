#!/bin/bash
#
# Setup Navigation on Pinky Robots
# This script prepares Pinky1 and Pinky2 for navigation
#
# Usage:
#   ./setup_pinky_navigation.sh pinky1
#   ./setup_pinky_navigation.sh pinky2
#   ./setup_pinky_navigation.sh all
#

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ $# -eq 0 ]; then
    echo "Usage: $0 [pinky1|pinky2|all]"
    echo ""
    echo "Examples:"
    echo "  $0 pinky1           # Setup Pinky1 only"
    echo "  $0 pinky2           # Setup Pinky2 only"
    echo "  $0 all              # Setup both Pinky1 and Pinky2"
    exit 1
fi

TARGET=$1

# ============================================================================
# Configuration
# ============================================================================

PINKY1_IP="192.168.1.7"
PINKY1_USER="pinky"
PINKY1_DOMAIN="11"
PINKY1_ROBOT_NAME="pinky_b4bc"

PINKY2_IP="192.168.1.6"
PINKY2_USER="pinky"
PINKY2_DOMAIN="12"
PINKY2_ROBOT_NAME="pinky_e2a8"

# Map file locations
MAIN_PC_MAPS_DIR="/home/gw/kitchmatics/roscamp-repo-1/mobile_robot/maps"
PINKY_MAPS_DIR="/home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/maps"

# ============================================================================
# Functions
# ============================================================================

setup_pinky() {
    local IP=$1
    local USER=$2
    local DOMAIN=$3
    local ROBOT_NAME=$4
    local PINKY_NAME=$5

    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Setting up $PINKY_NAME (Domain $DOMAIN, IP: $IP)${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""

    # Check connectivity
    echo -e "${YELLOW}[1/4] Checking connectivity...${NC}"
    if ! ssh -o ConnectTimeout=5 ${USER}@${IP} "exit" 2>/dev/null; then
        echo -e "${RED}✗ Cannot SSH to $IP${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ SSH connected${NC}"
    echo ""

    # Copy maps
    echo -e "${YELLOW}[2/4] Copying map files...${NC}"
    if [ ! -d "$MAIN_PC_MAPS_DIR" ]; then
        echo -e "${RED}✗ Map directory not found: $MAIN_PC_MAPS_DIR${NC}"
        return 1
    fi

    # Create remote map directory if needed
    ssh ${USER}@${IP} "mkdir -p $PINKY_MAPS_DIR" 2>/dev/null

    # Copy maps
    for mapfile in real.yaml real.pgm; do
        if [ -f "$MAIN_PC_MAPS_DIR/$mapfile" ]; then
            scp -q "$MAIN_PC_MAPS_DIR/$mapfile" \
                ${USER}@${IP}:${PINKY_MAPS_DIR}/ && \
                echo -e "${GREEN}✓${NC} Copied $mapfile" || \
                echo -e "${RED}✗${NC} Failed to copy $mapfile"
        fi
    done
    echo ""

    # Build packages
    echo -e "${YELLOW}[3/4] Building packages on $PINKY_NAME...${NC}"
    ssh ${USER}@${IP} "
        export ROS_DOMAIN_ID=$DOMAIN
        cd /home/pinky/pinky_pro

        # Check if already built
        if [ ! -d 'install' ]; then
            echo 'Building navigation packages...'
            colcon build --packages-select pinky_navigation pinky_bringup 2>&1 | tail -5
        else
            echo 'Packages already built'
        fi
    " && echo -e "${GREEN}✓ Build complete${NC}" || echo -e "${RED}✗ Build failed${NC}"
    echo ""

    # Create bringup script
    echo -e "${YELLOW}[4/4] Creating navigation bringup script...${NC}"

    # Create the full bringup script on remote
    ssh ${USER}@${IP} "cat > /home/pinky/start_navigation.sh << 'EOFSCRIPT'
#!/bin/bash
# Navigation Startup Script for $PINKY_NAME (Domain $DOMAIN)

export ROS_DOMAIN_ID=$DOMAIN
source /opt/ros/jazzy/setup.bash
cd /home/pinky/pinky_pro
source install/setup.bash

echo \"Starting Nav2 for $ROBOT_NAME on Domain $DOMAIN...\"

# Launch navigation
ros2 launch pinky_navigation bringup_launch.xml \\
    robot_name:=$ROBOT_NAME \\
    use_sim_time:=false

EOFSCRIPT
chmod +x /home/pinky/start_navigation.sh
echo 'Navigation script created'
" && echo -e "${GREEN}✓ Script created${NC}" || echo -e "${RED}✗ Script creation failed${NC}"
    echo ""

    # Show next steps
    echo -e "${GREEN}Setup for $PINKY_NAME complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. SSH to $PINKY_NAME: ssh ${USER}@${IP}"
    echo "2. Start navigation: /home/pinky/start_navigation.sh"
    echo "3. Verify: ros2 node list | grep -E 'amcl|bt_navigator|planner'"
    echo ""
    return 0
}

# ============================================================================
# Main
# ============================================================================

case "$TARGET" in
    pinky1)
        setup_pinky "$PINKY1_IP" "$PINKY1_USER" "$PINKY1_DOMAIN" "$PINKY1_ROBOT_NAME" "Pinky1"
        ;;
    pinky2)
        setup_pinky "$PINKY2_IP" "$PINKY2_USER" "$PINKY2_DOMAIN" "$PINKY2_ROBOT_NAME" "Pinky2"
        ;;
    all)
        setup_pinky "$PINKY1_IP" "$PINKY1_USER" "$PINKY1_DOMAIN" "$PINKY1_ROBOT_NAME" "Pinky1"
        RESULT1=$?

        setup_pinky "$PINKY2_IP" "$PINKY2_USER" "$PINKY2_DOMAIN" "$PINKY2_ROBOT_NAME" "Pinky2"
        RESULT2=$?

        echo ""
        echo -e "${BLUE}============================================================${NC}"
        echo -e "${BLUE}Setup Summary${NC}"
        echo -e "${BLUE}============================================================${NC}"
        echo "Pinky1: $([ $RESULT1 -eq 0 ] && echo -e "${GREEN}✓ Success${NC}" || echo -e "${RED}✗ Failed${NC}")"
        echo "Pinky2: $([ $RESULT2 -eq 0 ] && echo -e "${GREEN}✓ Success${NC}" || echo -e "${RED}✗ Failed${NC}")"
        echo ""

        if [ $RESULT1 -eq 0 ] && [ $RESULT2 -eq 0 ]; then
            echo -e "${GREEN}All robots setup complete!${NC}"
            echo ""
            echo "Next: Start navigation on each robot"
            echo "  Pinky1: ssh pinky@$PINKY1_IP /home/pinky/start_navigation.sh"
            echo "  Pinky2: ssh pinky@$PINKY2_IP /home/pinky/start_navigation.sh"
        fi
        ;;
    *)
        echo "Unknown target: $TARGET"
        echo "Use: pinky1, pinky2, or all"
        exit 1
        ;;
esac
