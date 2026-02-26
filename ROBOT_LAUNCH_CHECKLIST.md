# Kitchmatics 로봇 실행 체크리스트

## 개요
이 문서는 Kitchmatics FMS 통합 테스트를 위한 모든 로봇의 실행 절차를 안내합니다.

## 네트워크 구성 확인
```
Main PC (gw):        192.168.1.3  (ROS_DOMAIN_ID=25)
pinky1 (b4bc):       192.168.1.7  (ROS_DOMAIN_ID=11)
pinky2 (e2a8):       192.168.1.6  (ROS_DOMAIN_ID=12)
pinky3 (d29d):       192.168.1.11 (ROS_DOMAIN_ID=13)
armA (jetcobot_aa1f): 192.168.1.4  (ROS_DOMAIN_ID=25)
armB (jetcobot_aa85): 192.168.1.10 (ROS_DOMAIN_ID=25)
```

---

## 1단계: Pinky 로봇 실행 (SSH 접속)

### Pinky1 (192.168.1.7)

**터미널 1 - SSH 접속:**
```bash
ssh pinky@192.168.1.7
# 비밀번호: pinky1234
```

**터미널 1 - Bringup 실행:**
```bash
cd ~
source /opt/ros/humble/setup.bash
ros2 launch pinky_bringup bringup_robot.launch.xml
```

**터미널 2 - SSH 접속 (새 창):**
```bash
ssh pinky@192.168.1.7
```

**터미널 2 - 내비게이션 실행:**
```bash
cd ~
source /opt/ros/humble/setup.bash
ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml
```

**✓ 확인 명령어 (터미널 3에서):**
```bash
ssh pinky@192.168.1.7
export ROS_DOMAIN_ID=11
source /opt/ros/humble/setup.bash
ros2 node list | grep -E "robot_state_publisher|amcl|controller_server|bt_navigator"
ros2 topic echo /pinky1/odom --once
ros2 topic echo /pinky1/amcl_pose --once
```

예상 출력:
- `/pinky1/robot_state_publisher`
- `/pinky1/amcl`
- `/pinky1/controller_server`
- `/pinky1/bt_navigator`

---

### Pinky2 (192.168.1.6)

**터미널 1 - SSH 접속:**
```bash
ssh pinky@192.168.1.6
# 비밀번호: pinky1234
```

**터미널 1 - Bringup 실행:**
```bash
cd ~
source /opt/ros/humble/setup.bash
ros2 launch pinky_bringup bringup_robot.launch.xml
```

**터미널 2 - SSH 접속 (새 창):**
```bash
ssh pinky@192.168.1.6
```

**터미널 2 - 내비게이션 실행:**
```bash
cd ~
source /opt/ros/humble/setup.bash
ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml
```

**✓ 확인 명령어 (터미널 3에서):**
```bash
ssh pinky@192.168.1.6
export ROS_DOMAIN_ID=12
source /opt/ros/humble/setup.bash
ros2 node list | grep -E "robot_state_publisher|amcl|controller_server|bt_navigator"
ros2 topic echo /pinky2/odom --once
ros2 topic echo /pinky2/amcl_pose --once
```

---

### Pinky3 (192.168.1.11) - 선택사항

**터미널 1 - SSH 접속:**
```bash
ssh pinky@192.168.1.11
# 비밀번호: pinky1234
```

**터미널 1 - Bringup 실행:**
```bash
cd ~
source /opt/ros/humble/setup.bash
ros2 launch pinky_bringup bringup_robot.launch.xml
```

**터미널 2 - SSH 접속 (새 창):**
```bash
ssh pinky@192.168.1.11
```

**터미널 2 - 내비게이션 실행:**
```bash
cd ~
source /opt/ros/humble/setup.bash
ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml
```

**✓ 확인 명령어 (터미널 3에서):**
```bash
ssh pinky@192.168.1.11
export ROS_DOMAIN_ID=13
source /opt/ros/humble/setup.bash
ros2 node list | grep -E "robot_state_publisher|amcl|controller_server|bt_navigator"
ros2 topic echo /pinky3/odom --once
ros2 topic echo /pinky3/amcl_pose --once
```

---

## 2단계: Robot Arm 실행 (수동 실행 필요)

### ArmA - Sandwich Station (192.168.1.4)

**물리적 접근 필요 - 모니터/키보드 연결**

**터미널 1 - Arm Controller 실행:**
```bash
cd /home/jetcobot/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25
ros2 launch robot_arm arm_bringup.launch.py robot_name:=armA
```

**✓ 확인 명령어 (같은 터미널 또는 새 터미널):**
```bash
export ROS_DOMAIN_ID=25
source /home/jetcobot/roscamp-repo-1/install/setup.bash
ros2 node list | grep armA
ros2 topic list | grep armA
ros2 topic echo /armA/joint_states --once
```

예상 출력:
- `/armA/arm_controller_node`
- `/armA/joint_states`
- `/armA/command`

---

### ArmB - Sauce Station (192.168.1.10)

**물리적 접근 필요 - 모니터/키보드 연결**

**터미널 1 - Arm Controller 실행:**
```bash
cd /home/jetcobot/roscamp-repo-1
source install/setup.bash
export ROS_DOMAIN_ID=25
ros2 launch robot_arm arm_bringup.launch.py robot_name:=armB
```

**✓ 확인 명령어 (같은 터미널 또는 새 터미널):**
```bash
export ROS_DOMAIN_ID=25
source /home/jetcobot/roscamp-repo-1/install/setup.bash
ros2 node list | grep armB
ros2 topic list | grep armB
ros2 topic echo /armB/joint_states --once
```

---

## 3단계: 전체 시스템 확인 (Main PC에서)

모든 로봇 실행이 완료되면, Main PC에서 다음 명령어로 확인:

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash

# Pinky1 확인 (Domain 11)
export ROS_DOMAIN_ID=11 && ros2 topic list | grep pinky1

# Pinky2 확인 (Domain 12)
export ROS_DOMAIN_ID=12 && ros2 topic list | grep pinky2

# Pinky3 확인 (Domain 13)
export ROS_DOMAIN_ID=13 && ros2 topic list | grep pinky3

# Arm 확인 (Domain 25)
export ROS_DOMAIN_ID=25 && ros2 topic list | grep -E "armA|armB"
```

---

## 체크리스트 요약

- [ ] **Pinky1** Bringup 실행 완료
- [ ] **Pinky1** Navigation 실행 완료
- [ ] **Pinky1** 노드 확인 완료 (amcl, controller, bt_navigator)
- [ ] **Pinky2** Bringup 실행 완료
- [ ] **Pinky2** Navigation 실행 완료
- [ ] **Pinky2** 노드 확인 완료
- [ ] **Pinky3** Bringup 실행 완료 (선택)
- [ ] **Pinky3** Navigation 실행 완료 (선택)
- [ ] **Pinky3** 노드 확인 완료 (선택)
- [ ] **ArmA** (Sandwich) Controller 실행 완료
- [ ] **ArmA** 토픽 확인 완료
- [ ] **ArmB** (Sauce) Controller 실행 완료
- [ ] **ArmB** 토픽 확인 완료
- [ ] **Main PC** 에서 모든 도메인 접근 확인 완료

---

## 다음 단계

모든 체크리스트 항목이 완료되면, Claude에게 알려주세요:

```
"모든 로봇 실행 완료했습니다. 다음 단계로 진행해주세요."
```

그러면 Main PC에서 Domain Bridge와 FMS를 실행합니다.

---

## 문제 해결

### SSH 연결 실패
```bash
# 핑 테스트
ping 192.168.1.7

# SSH 재시도
ssh -v pinky@192.168.1.7
```

### 노드가 보이지 않음
```bash
# ROS_DOMAIN_ID 재확인
echo $ROS_DOMAIN_ID

# ROS2 데몬 재시작
ros2 daemon stop
ros2 daemon start
```

### 토픽이 보이지 않음
```bash
# DDS 설정 확인
echo $CYCLONEDDS_URI

# 방화벽 확인
sudo ufw status
```

### Navigation 실행 실패
```bash
# 맵 파일 경로 확인
ls ~/maps/real.yaml

# 파라미터 파일 확인
ls ~/pinky_navigation/params/nav2_params.yaml
```
