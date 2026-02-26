#!/bin/bash
# Deploy CycloneDDS configuration to robots
# This fixes ROS2 discovery issues over WiFi

CONFIG_DIR="/home/gw/kitchmatics/roscamp-repo-1/fms/config"

echo "Deploying CycloneDDS configuration to robots..."

# Deploy to pinky1
echo ""
echo "=== Deploying to pinky1 (192.168.1.7) ==="
scp "$CONFIG_DIR/cyclonedds_pinky1.xml" pinky@192.168.1.7:~/cyclonedds.xml
ssh pinky@192.168.1.7 "cat > ~/setup_dds.sh << 'EOF'
#!/bin/bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/pinky/cyclonedds.xml
export ROS_DOMAIN_ID=11
echo \"pinky1 DDS Environment Set: ROS_DOMAIN_ID=\$ROS_DOMAIN_ID\"
EOF
chmod +x ~/setup_dds.sh
echo 'DDS config deployed. Add this to .bashrc:'
echo 'source ~/setup_dds.sh'"

# Deploy to pinky2
echo ""
echo "=== Deploying to pinky2 (192.168.1.6) ==="
scp "$CONFIG_DIR/cyclonedds_pinky2.xml" pinky@192.168.1.6:~/cyclonedds.xml
ssh pinky@192.168.1.6 "cat > ~/setup_dds.sh << 'EOF'
#!/bin/bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/pinky/cyclonedds.xml
export ROS_DOMAIN_ID=12
echo \"pinky2 DDS Environment Set: ROS_DOMAIN_ID=\$ROS_DOMAIN_ID\"
EOF
chmod +x ~/setup_dds.sh
echo 'DDS config deployed. Add this to .bashrc:'
echo 'source ~/setup_dds.sh'"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "NEXT STEPS:"
echo "1. SSH to each robot and run: echo 'source ~/setup_dds.sh' >> ~/.bashrc"
echo "2. Restart ROS2 nodes on each robot"
echo "3. On Main PC, run: source /home/gw/kitchmatics/roscamp-repo-1/fms/config/setup_dds_domain11.sh"
echo "4. Test with: ros2 topic list"
