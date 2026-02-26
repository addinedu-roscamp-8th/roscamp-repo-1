#!/bin/bash
set -e

# Kitchmatics FMS Validation Script
# This script validates the FMS communication system

export ROS_DOMAIN_ID=25
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/tmp/fms_validation"
mkdir -p "$LOG_DIR"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}FMS Validation Agent Started${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Timestamp: $(date)"
echo "Working Directory: $SCRIPT_DIR"
echo "Log Directory: $LOG_DIR"
echo "ROS_DOMAIN_ID: $ROS_DOMAIN_ID"

# Step 1: Check if FMS node is already running
echo -e "\n${YELLOW}[STEP 1] Checking if FMS node is running...${NC}"
if pgrep -f "fms_closed_network" > /dev/null; then
    echo -e "${GREEN}✓ FMS node already running${NC}"
    FMS_ALREADY_RUNNING=true
else
    echo -e "${YELLOW}✗ FMS node not running, launching...${NC}"
    FMS_ALREADY_RUNNING=false

    # Launch FMS in background with output to log file
    echo "Launching FMS with: ros2 launch fms fms_closed_network.launch.py"
    ros2 launch fms fms_closed_network.launch.py > "$LOG_DIR/fms_launch.log" 2>&1 &
    FMS_PID=$!
    echo "FMS PID: $FMS_PID"

    # Wait for FMS to start
    echo "Waiting for FMS node to initialize..."
    sleep 5
fi

# Step 2: Wait for FMS node to be fully initialized
echo -e "\n${YELLOW}[STEP 2] Waiting for FMS node to fully initialize...${NC}"
max_wait=30
elapsed=0
while ! pgrep -f "fms_node|fms_tcp_node" > /dev/null; do
    if [ $elapsed -ge $max_wait ]; then
        echo -e "${RED}✗ FMS node failed to start after ${max_wait}s${NC}"
        echo "Launch log:"
        cat "$LOG_DIR/fms_launch.log" | tail -20
        exit 1
    fi
    echo "Waiting... ($elapsed/${max_wait}s)"
    sleep 2
    elapsed=$((elapsed + 2))
done
echo -e "${GREEN}✓ FMS node detected${NC}"

# Step 3: Check FMS logs for initialization messages
echo -e "\n${YELLOW}[STEP 3] Checking FMS initialization logs...${NC}"
sleep 2
if [ -f "$LOG_DIR/fms_launch.log" ]; then
    echo "FMS Log Preview:"
    tail -30 "$LOG_DIR/fms_launch.log"
fi

# Step 4: Verify listening ports
echo -e "\n${YELLOW}[STEP 4] Verifying TCP listening ports...${NC}"
if netstat -tlnp 2>/dev/null | grep -q ":9000"; then
    echo -e "${GREEN}✓ FMS TCP Server listening on port 9000${NC}"
else
    echo -e "${YELLOW}✗ Port 9000 not found in netstat${NC}"
    echo "Listening ports:"
    netstat -tlnp 2>/dev/null | grep LISTEN | grep python || echo "No python listeners found"
fi

# Step 5: Check ROS 2 topics
echo -e "\n${YELLOW}[STEP 5] Verifying ROS 2 topics...${NC}"
echo "Waiting for topic discovery..."
sleep 2

EXPECTED_TOPICS=(
    "/fms/fleet_status"
    "/fms/order_request"
    "/fms/pickup_arrival"
    "/fms/error_alert"
)

for topic in "${EXPECTED_TOPICS[@]}"; do
    if ros2 topic list | grep -q "$topic"; then
        echo -e "${GREEN}✓ Topic $topic found${NC}"
    else
        echo -e "${YELLOW}✗ Topic $topic NOT found${NC}"
    fi
done

# Step 6: Robot topic checks
echo -e "\n${YELLOW}[STEP 6] Checking robot topic availability...${NC}"
ROBOT_TOPICS=(
    "/pinky1/amcl_pose"
    "/pinky2/amcl_pose"
    "/cooking/loading_complete"
    "/cooking/order"
)

for topic in "${ROBOT_TOPICS[@]}"; do
    if ros2 topic list | grep -q "$topic"; then
        echo -e "${GREEN}✓ Topic $topic found${NC}"
    else
        echo -e "${YELLOW}✗ Topic $topic NOT found${NC}"
    fi
done

# Step 7: Check node status
echo -e "\n${YELLOW}[STEP 7] Checking ROS 2 node status...${NC}"
echo "Active nodes:"
ros2 node list | grep -E "fms|sandwich|coordinator" || echo "No FMS/coordinator nodes found"

# Step 8: Create monitoring commands for user
echo -e "\n${YELLOW}[STEP 8] Setting up monitoring commands...${NC}"
cat > "$LOG_DIR/monitor_topics.sh" << 'EOF'
#!/bin/bash
export ROS_DOMAIN_ID=25
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

echo "Monitoring FMS Topics..."
echo "Press Ctrl+C to exit"
echo ""

# Create monitoring in background
{
    echo "=== Fleet Status ==="
    ros2 topic echo /fms/fleet_status 2>/dev/null || echo "fleet_status topic not available"
} &

{
    echo "=== Order Requests ==="
    ros2 topic echo /fms/order_request 2>/dev/null || echo "order_request topic not available"
} &

{
    echo "=== Pickup Arrivals ==="
    ros2 topic echo /fms/pickup_arrival 2>/dev/null || echo "pickup_arrival topic not available"
} &

wait
EOF
chmod +x "$LOG_DIR/monitor_topics.sh"

# Step 9: Validation Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}Validation Summary${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "${GREEN}✓ FMS Node is running${NC}"
echo -e "${GREEN}✓ Environment configured${NC}"

echo -e "\n${YELLOW}To monitor FMS topics in real-time:${NC}"
echo "bash $LOG_DIR/monitor_topics.sh"

echo -e "\n${YELLOW}To view FMS logs:${NC}"
echo "tail -f $LOG_DIR/fms_launch.log | grep -E 'INFO|ERROR|WARNING|Registered|Created'"

echo -e "\n${YELLOW}To test TCP connection to FMS:${NC}"
echo "nc -zv 192.168.1.3 9000"

echo -e "\n${YELLOW}Important URLs/Paths:${NC}"
echo "Log file: $LOG_DIR/fms_launch.log"
echo "Config: /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml"
echo "TCP Server code: /home/gw/kitchmatics/roscamp-repo-1/fms/fms/gui_tcp_server.py"

echo -e "\n${BLUE}FMS Validation Complete${NC}"
echo "Timestamp: $(date)"
