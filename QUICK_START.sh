#!/bin/bash
# Kitchmatics FMS Quick Start Script
# Run this in separate terminals for FMS, Domain Bridge, and GUI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display usage
usage() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}Kitchmatics FMS Quick Start${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""
    echo "Usage: $0 [fms|bridge|gui|check]"
    echo ""
    echo "Commands:"
    echo "  fms     - Start FMS node (Terminal 1)"
    echo "  bridge  - Start domain bridge (Terminal 2)"
    echo "  gui     - Start customer GUI (Terminal 3)"
    echo "  check   - Check system readiness"
    echo ""
    echo "Example:"
    echo "  # Terminal 1"
    echo "  ./QUICK_START.sh fms"
    echo ""
    echo "  # Terminal 2"
    echo "  ./QUICK_START.sh bridge"
    echo ""
    echo "  # Terminal 3"
    echo "  ./QUICK_START.sh gui"
    echo ""
    exit 1
}

# Function to check prerequisites
check_system() {
    echo -e "${BLUE}Checking system readiness...${NC}"
    echo ""

    # Check ROS installation
    if [ -f "/opt/ros/jazzy/setup.bash" ]; then
        echo -e "${GREEN}✓${NC} ROS Jazzy installed"
    else
        echo -e "${RED}✗${NC} ROS Jazzy not found at /opt/ros/jazzy"
        exit 1
    fi

    # Check workspace
    if [ -d "/home/gw/kitchmatics/roscamp-repo-1" ]; then
        echo -e "${GREEN}✓${NC} Workspace found"
    else
        echo -e "${RED}✗${NC} Workspace not found at /home/gw/kitchmatics/roscamp-repo-1"
        exit 1
    fi

    # Check build
    if [ -d "/home/gw/kitchmatics/roscamp-repo-1/install" ]; then
        echo -e "${GREEN}✓${NC} Workspace built"
    else
        echo -e "${YELLOW}⚠${NC} Workspace not built, run: colcon build --symlink-install"
    fi

    # Check domain bridge config
    if [ -f "/home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml" ]; then
        echo -e "${GREEN}✓${NC} Domain bridge config found"
    else
        echo -e "${RED}✗${NC} Domain bridge config not found"
        exit 1
    fi

    # Check network connectivity
    echo ""
    echo -e "${BLUE}Checking network connectivity...${NC}"

    if ping -c 1 -W 1 192.168.1.7 &> /dev/null; then
        echo -e "${GREEN}✓${NC} pinky1 (192.168.1.7) reachable"
    else
        echo -e "${YELLOW}⚠${NC} pinky1 (192.168.1.7) not reachable"
    fi

    if ping -c 1 -W 1 192.168.1.6 &> /dev/null; then
        echo -e "${GREEN}✓${NC} pinky2 (192.168.1.6) reachable"
    else
        echo -e "${YELLOW}⚠${NC} pinky2 (192.168.1.6) not reachable"
    fi

    if ping -c 1 -W 1 192.168.1.4 &> /dev/null; then
        echo -e "${GREEN}✓${NC} jetcobot A (192.168.1.4) reachable"
    else
        echo -e "${YELLOW}⚠${NC} jetcobot A (192.168.1.4) not reachable"
    fi

    if ping -c 1 -W 1 192.168.1.10 &> /dev/null; then
        echo -e "${GREEN}✓${NC} jetcobot B (192.168.1.10) reachable"
    else
        echo -e "${YELLOW}⚠${NC} jetcobot B (192.168.1.10) not reachable"
    fi

    echo ""
    echo -e "${GREEN}System check complete!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Terminal 1: ./QUICK_START.sh fms"
    echo "  2. Terminal 2: ./QUICK_START.sh bridge"
    echo "  3. Terminal 3: ./QUICK_START.sh gui"
    echo ""
}

# Function to start FMS node
start_fms() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}Starting FMS Node (Terminal 1)${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""

    cd /home/gw/kitchmatics/roscamp-repo-1

    if [ ! -d "install" ]; then
        echo -e "${RED}Error: Workspace not built!${NC}"
        echo "Run: colcon build --symlink-install --packages-select fleet_interfaces fms"
        exit 1
    fi

    source install/setup.bash
    export ROS_DOMAIN_ID=25

    echo -e "${GREEN}ROS_DOMAIN_ID set to 25${NC}"
    echo -e "${GREEN}Launching FMS...${NC}"
    echo ""

    ros2 launch fms fms_closed_network.launch.py
}

# Function to start domain bridge
start_bridge() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}Starting Domain Bridge (Terminal 2)${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""

    cd /home/gw/kitchmatics/roscamp-repo-1

    if [ ! -f "fms/config/domain_bridge_complete.yaml" ]; then
        echo -e "${RED}Error: Domain bridge config not found!${NC}"
        exit 1
    fi

    source install/setup.bash
    export ROS_DOMAIN_ID=25

    echo -e "${GREEN}ROS_DOMAIN_ID set to 25${NC}"
    echo -e "${GREEN}Launching Domain Bridge...${NC}"
    echo ""
    echo -e "${YELLOW}NOTE: Domain bridge MUST be running before FMS can communicate with robots${NC}"
    echo ""

    ros2 run domain_bridge domain_bridge fms/config/domain_bridge_complete.yaml
}

# Function to start GUI
start_gui() {
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE}Starting Customer GUI (Terminal 3)${NC}"
    echo -e "${BLUE}================================================================${NC}"
    echo ""

    cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui

    if [ ! -d "$HOME/pyqt_venv" ]; then
        echo -e "${RED}Error: PyQt virtual environment not found at ~/pyqt_venv${NC}"
        echo "Create it first or adjust the path in this script"
        exit 1
    fi

    source ~/pyqt_venv/bin/activate

    echo -e "${GREEN}Virtual environment activated${NC}"
    echo -e "${GREEN}Launching Customer GUI...${NC}"
    echo ""
    echo -e "${YELLOW}Connecting to FMS at 192.168.1.3:9000${NC}"
    echo ""

    python src/main_fms_direct.py
}

# Main script
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
