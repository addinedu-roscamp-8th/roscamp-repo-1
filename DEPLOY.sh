#!/bin/bash
# Kitchmatics FMS System Deployment Script
# Date: 2026-02-26

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/tmp/kitchmatics_deploy"
mkdir -p "$LOG_DIR"

echo "=========================================="
echo "Kitchmatics FMS System Deployment"
echo "=========================================="
echo "Date: $(date)"
echo "Script: $0"
echo "Log Directory: $LOG_DIR"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_info() { echo "ℹ️  $1"; }

# Step 1: Kill old FMS processes
print_info "Step 1: Stopping old FMS processes..."
pkill -f "fms_tcp_node" 2>/dev/null && print_success "Killed fms_tcp_node" || print_info "No fms_tcp_node running"
pkill -f "fms_node" 2>/dev/null && sleep 2 && print_success "Killed fms_node" || print_info "No fms_node running"

# Step 2: Rebuild FMS
print_info "Step 2: Building FMS package..."
cd "$SCRIPT_DIR"
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select fms > "$LOG_DIR/build_fms.log" 2>&1
if [ $? -eq 0 ]; then
    print_success "FMS build successful"
else
    print_error "FMS build failed - check $LOG_DIR/build_fms.log"
    exit 1
fi

# Step 3: Rebuild Coordinator
print_info "Step 3: Building Sandwich Coordinator..."
cd "$SCRIPT_DIR/fms/coordinator_Ws"
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select sandwich_coordinator > "$LOG_DIR/build_coordinator.log" 2>&1
if [ $? -eq 0 ]; then
    print_success "Coordinator build successful"
else
    print_error "Coordinator build failed - check $LOG_DIR/build_coordinator.log"
    exit 1
fi

# Step 4: Start FMS
print_info "Step 4: Starting FMS..."
cd "$SCRIPT_DIR"
source install/setup.bash
export ROS_DOMAIN_ID=25
nohup ros2 launch fms fms_closed_network.launch.py > "$LOG_DIR/fms.log" 2>&1 &
FMS_PID=$!
echo "$FMS_PID" > "$LOG_DIR/fms.pid"
print_success "FMS started (PID: $FMS_PID)"

# Step 5: Wait and verify
print_info "Step 5: Verifying FMS startup..."
sleep 5

# Check if FMS process is running
if ps -p $FMS_PID > /dev/null; then
    print_success "FMS process is running"
else
    print_error "FMS process died - check $LOG_DIR/fms.log"
    exit 1
fi

# Check port 9000
PORT_CHECK=$(netstat -tlnp 2>/dev/null | grep 9000 | wc -l)
if [ "$PORT_CHECK" -eq 1 ]; then
    print_success "Port 9000 has exactly ONE listener"
elif [ "$PORT_CHECK" -eq 0 ]; then
    print_error "Port 9000 has NO listeners"
    exit 1
else
    print_error "Port 9000 has MULTIPLE listeners ($PORT_CHECK)"
    exit 1
fi

# Step 6: Run integration test
print_info "Step 6: Running integration test..."
cat > /tmp/test_order_deploy.py << 'EOFTEST'
#!/usr/bin/env python3
import socket
import json

def send_with_header(sock, message):
    json_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
    length_header = len(json_data).to_bytes(4, byteorder='big')
    sock.sendall(length_header + json_data)

def recv_with_header(sock):
    length_header = sock.recv(4)
    if not length_header:
        return None
    message_length = int.from_bytes(length_header, byteorder='big')
    data = sock.recv(message_length)
    return json.loads(data.decode('utf-8'))

msg = {
    "command": "new_order",
    "table_number": 99,
    "order": {
        "items": [{"menu_id": "M001", "quantity": 1}]
    }
}

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10.0)
try:
    sock.connect(('192.168.1.3', 9000))
    send_with_header(sock, msg)
    response = recv_with_header(sock)
    if response and response.get('status') == 'success':
        print("SUCCESS")
    else:
        print(f"FAILED: {response}")
        exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
finally:
    sock.close()
EOFTEST

python3 /tmp/test_order_deploy.py > "$LOG_DIR/test.log" 2>&1
if [ $? -eq 0 ]; then
    print_success "Integration test PASSED"
else
    print_error "Integration test FAILED - check $LOG_DIR/test.log"
    exit 1
fi

# Step 7: Summary
echo ""
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
print_success "FMS deployed successfully"
print_info "FMS PID: $FMS_PID"
print_info "FMS Log: $LOG_DIR/fms.log"
print_info "Build Logs: $LOG_DIR/build_*.log"
echo ""
print_warning "MANUAL STEPS REQUIRED:"
echo "  1. Restart Pinky2 Nav2: ssh pinky@192.168.1.6"
echo "  2. Verify Jetcobot A Coordinator: ssh jetcobot@192.168.1.4"
echo "  3. Launch Customer GUI: cd app/gui/customer_gui && python src/main_fms_direct.py"
echo ""
print_info "To stop FMS: kill \$(cat $LOG_DIR/fms.pid)"
echo "=========================================="
