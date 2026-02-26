# ROS2 DDS Discovery Troubleshooting Guide

## Problem Description

**Symptom**: Main PC cannot see ROS2 topics from robots even though SSH works fine.

**Root Cause**: WiFi networks often block multicast UDP packets, which ROS2 uses for node discovery by default.

**Solution**: Use **unicast peer discovery** with CycloneDDS.

---

## Quick Fix (Step-by-Step)

### Step 1: Deploy DDS Configuration to Robots

```bash
# On Main PC
cd /home/gw/kitchmatics/roscamp-repo-1/fms/scripts
./deploy_dds_config.sh
```

This will:
- Copy CycloneDDS XML config to each robot
- Create `~/setup_dds.sh` on each robot
- Configure unicast peer discovery

### Step 2: Update Robot .bashrc

**On pinky1** (192.168.1.7):
```bash
ssh pinky@192.168.1.7
echo 'source ~/setup_dds.sh' >> ~/.bashrc
source ~/.bashrc
# Restart Nav2 or any ROS2 nodes
```

**On pinky2** (192.168.1.6):
```bash
ssh pinky@192.168.1.6
echo 'source ~/setup_dds.sh' >> ~/.bashrc
source ~/.bashrc
# Restart Nav2 or any ROS2 nodes
```

### Step 3: Test Connection from Main PC

**Test pinky1 (domain 11)**:
```bash
# Terminal 1 - On Main PC
source /home/gw/kitchmatics/roscamp-repo-1/fms/config/setup_dds_domain11.sh
ros2 topic list

# You should now see topics like:
# /amcl_pose
# /cmd_vel
# /odom
# /scan
# /tf
# /tf_static
```

**Test pinky2 (domain 12)**:
```bash
# Terminal 2 - On Main PC
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
export ROS_DOMAIN_ID=12
ros2 topic list
```

### Step 4: Run Domain Bridge

Once discovery works, start the domain bridge:

```bash
# On Main PC (domain 25)
source /home/gw/kitchmatics/roscamp-repo-1/fms/config/setup_dds_main.sh
ros2 run domain_bridge domain_bridge /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml
```

---

## Technical Details

### What Changed?

**Before** (Multicast Discovery):
- ROS2 used multicast UDP (239.255.0.1) to find nodes
- WiFi routers often drop multicast packets
- Result: Nodes can't discover each other

**After** (Unicast Discovery):
- Each node explicitly knows peer IP addresses
- Uses unicast UDP (direct IP-to-IP)
- Works reliably on WiFi

### Configuration Files

**Main PC**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml`
```xml
<Peers>
  <Peer address="192.168.1.7"/>  <!-- pinky1 -->
  <Peer address="192.168.1.6"/>  <!-- pinky2 -->
</Peers>
```

**Robot (pinky1)**: `~/cyclonedds.xml`
```xml
<Peers>
  <Peer address="192.168.1.3"/>  <!-- Main PC -->
</Peers>
```

### Environment Variables

**Main PC**:
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
export ROS_DOMAIN_ID=25  # or 11, 12, 13 for robot domains
```

**Robot (pinky1)**:
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/pinky/cyclonedds.xml
export ROS_DOMAIN_ID=11
```

---

## Verification Commands

### Check if CycloneDDS is loaded
```bash
ros2 doctor --report | grep rmw
# Should show: rmw_cyclonedds_cpp
```

### Monitor DDS traffic
```bash
# On Main PC
source setup_dds_domain11.sh
ros2 topic hz /odom  # Should show message rate
```

### Check network connectivity
```bash
# Test basic UDP connectivity
nc -u -v 192.168.1.7 7400  # DDS default port range starts at 7400
```

---

## Common Issues

### Issue 1: "rmw_cyclonedds_cpp not found"

**Solution**: Install CycloneDDS
```bash
sudo apt update
sudo apt install ros-humble-rmw-cyclonedds-cpp
```

### Issue 2: Still no topics visible

**Check**:
1. Is the robot's ROS2 node actually running?
   ```bash
   ssh pinky@192.168.1.7
   ros2 node list
   ```

2. Are environment variables set correctly?
   ```bash
   echo $RMW_IMPLEMENTATION
   echo $CYCLONEDDS_URI
   echo $ROS_DOMAIN_ID
   ```

3. Is the XML file readable?
   ```bash
   cat $CYCLONEDDS_URI
   ```

### Issue 3: Topics appear then disappear

**Cause**: Firewall blocking UDP ports

**Solution**: Allow DDS ports (7400-7999)
```bash
sudo ufw allow 7400:7999/udp
```

---

## Permanent Setup

Add to `~/.bashrc` on Main PC:
```bash
# ROS2 DDS Configuration for WiFi
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
export ROS_DOMAIN_ID=25  # Default to FMS domain
```

Add to `~/.bashrc` on each robot:
```bash
source ~/setup_dds.sh
```

---

## Network Diagram

```
Main PC (192.168.1.3, Domain 25)
  │
  ├─ CycloneDDS Peers: [192.168.1.7, 192.168.1.6, 192.168.1.11]
  │
  ├─ pinky1 (192.168.1.7, Domain 11)
  │   └─ CycloneDDS Peer: [192.168.1.3]
  │
  ├─ pinky2 (192.168.1.6, Domain 12)
  │   └─ CycloneDDS Peer: [192.168.1.3]
  │
  └─ pinky3 (192.168.1.11, Domain 13)
      └─ CycloneDDS Peer: [192.168.1.3]
```

---

## References

- [CycloneDDS Configuration Guide](https://github.com/eclipse-cyclonedds/cyclonedds)
- [ROS2 DDS Tuning](https://docs.ros.org/en/humble/How-To-Guides/DDS-tuning.html)
- [WiFi Best Practices](https://docs.ros.org/en/humble/How-To-Guides/Installation-Troubleshooting.html#enable-multicast)
