# Kitchmatics Test Code

로봇 시스템 테스트를 위한 독립 실행 스크립트 모음입니다.

## 사전 준비

### 1. 로봇 실행 (각 로봇 PC에서)
```bash
# Pinky Bringup
ros2 launch pinky_bringup bringup_robot.launch.xml

# Navigation
ros2 launch pinky_navigation bringup_launch.xml map:=real.yaml
```

### 2. 로봇팔 실행 (로봇팔 PC에서)
```bash
# Arm A (샌드위치 조리)
cd ~/sandwich_arm_ws
colcon build && source install/setup.bash
ros2 launch mycobot_kitchen_nodes kitchen.launch.py

# Arm B (소스 뿌리기)
cd ~/sauce_arm_ws
colcon build && source install/setup.bash
ros2 launch mycobot_sauce sauce.launch.py
```

### 3. Main PC 실행
```bash
# 터미널 1: Domain Bridge
cd ~/kitchmatics/roscamp-repo-1/fms
source /opt/ros/jazzy/setup.bash
ros2 run domain_bridge domain_bridge config/bridge_pinky1.yaml &
ros2 run domain_bridge domain_bridge config/bridge_pinky2.yaml &
ros2 run domain_bridge domain_bridge config/bridge_arm_a.yaml &
ros2 run domain_bridge domain_bridge config/bridge_arm_b.yaml &
ros2 run domain_bridge domain_bridge config/bridge_arm_a_cmd.yaml &
ros2 run domain_bridge domain_bridge config/bridge_arm_b_cmd.yaml &
ros2 run domain_bridge domain_bridge config/bridge_pinky1_reverse.yaml &
ros2 run domain_bridge domain_bridge config/bridge_pinky2_reverse.yaml &

# 터미널 2: 로봇팔 리셋
source /opt/ros/jazzy/setup.bash && export ROS_DOMAIN_ID=25
ros2 topic pub /arm_a/cmd std_msgs/msg/String "data: 'RESET'" --once
ros2 topic pub /arm_b/cmd std_msgs/msg/String "data: 'RESET'" --once
ros2 topic pub /verify/cmd std_msgs/msg/String "data: 'RESET'" --once

# 터미널 3: Coordinator (조리 테스트용)
cd ~/kitchmatics/roscamp-repo-1/fms/coordinator_Ws
source /opt/ros/jazzy/setup.bash && source install/setup.bash && export ROS_DOMAIN_ID=25
ros2 run sandwich_coordinator sandwich_coordinator
```

---

## 테스트 스크립트

### 1. test_navigation.py - Pinky 네비게이션

원하는 Pinky 로봇을 원하는 waypoint로 이동시킵니다.

```bash
# 환경 설정
cd ~/kitchmatics/roscamp-repo-1
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=25

# 실행
python3 test_code/test_navigation.py `<robot>` `<waypoint>`
```

**Parameters:**
- `<robot>`: `pinky1`, `pinky2`, `pinky3`
- `<waypoint>`: 아래 목록 참조

**Available Waypoints:**
| 이름 | 좌표 (x, y) | 설명 |
|------|------------|------|
| pickup_spot | (0.47, 0.63) | 음식 픽업 위치 |
| pinky1_spot | (0.585, 0.085) | Pinky1 주차 위치 |
| pinky2_spot | (0.585, 0.255) | Pinky2 주차 위치 |
| pinky3_spot | (0.585, 0.915) | Pinky3 주차 위치 |
| table1~table8 | 다양함 | 테이블 위치 |
| point1~point13 | 다양함 | 네비게이션 중간 지점 |

**Examples:**
```bash
# Pinky1을 테이블1로 이동
python3 test_code/test_navigation.py `pinky1` `table1`

# Pinky2를 픽업 위치로 이동
python3 test_code/test_navigation.py `pinky2` `pickup_spot`

# Pinky1을 주차 위치로 복귀
python3 test_code/test_navigation.py `pinky1` `pinky1_spot`
```

---

### 2. test_cooking.py - 로봇팔 조리

원하는 메뉴와 소스로 샌드위치를 조리하고, 검수 후 pickup_spot에 올립니다.

```bash
# 환경 설정
cd ~/kitchmatics/roscamp-repo-1
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=25

# 실행
python3 test_code/test_cooking.py `<menu>` `<sauce>`
```

**Parameters:**
- `<menu>`: 메뉴 ID 또는 레시피 이름
- `<sauce>`: 소스 종류 (빈 문자열 가능)

**Available Menus:**
| Menu ID | Recipe Name | 한글명 | 재료 |
|---------|-------------|--------|------|
| M001 | ham_cheese | 햄치즈샌드위치 | bread, lettuce, cheese, tomato, ham, bread |
| M002 | mushroom | 머쉬룸샌드위치 | bread, mushroom, tomato, cheese, ham, bread |
| M003 | all_in_one | 올인원샌드위치 | bread, tomato, cheese, ham, mushroom, lettuce, bread |

**Available Sauces:**
| Sauce | 한글명 |
|-------|--------|
| mayo | 마요네즈 |
| mustard | 머스터드 |
| ketchup | 케첩 |
| (empty) | 소스 없음 |

**Examples:**
```bash
# 햄치즈 샌드위치 + 마요네즈
python3 test_code/test_cooking.py `ham_cheese` `mayo`

# 머쉬룸 샌드위치 + 머스터드
python3 test_code/test_cooking.py `M002` `mustard`

# 올인원 샌드위치, 소스 없음
python3 test_code/test_cooking.py `all_in_one` ``
```

---

## 조리 프로세스 흐름

```
1. START → Arm A가 샌드위치 조리 시작
2. (소스 있을 경우) PREPARE → Arm B 소스 준비
3. (소스 있을 경우) WAIT_FOR_SAUCE → Arm A 대기
4. (소스 있을 경우) POUR → Arm B 소스 뿌리기
5. RESUME → Arm A 조리 재개
6. DONE → Arm A 조리 완료
7. TRANSPORT_TO_VERIFY → Arm B가 검수 위치로 운반
8. ANALYZE → 검수 노드가 품질 확인
9. (검수 통과) HANDOFF_PINKY → Pinky에 음식 전달
   (검수 실패) DISCARD → 불량품 폐기
10. LoadingComplete → FMS에 완료 알림
```

---

## 트러블슈팅

### "Action server not available"
- Domain Bridge가 실행 중인지 확인
- 로봇의 Nav2가 정상 실행 중인지 확인

### "No subscribers on /cooking/order"
- Coordinator가 실행 중인지 확인
- ROS_DOMAIN_ID=25 설정 확인

### "A_FAIL:busy" 에러
- 로봇팔 리셋 명령 실행:
  ```bash
  ros2 topic pub /arm_a/cmd std_msgs/msg/String "data: 'RESET'" --once
  ```

### "fleet_interfaces not found"
- 워크스페이스 source 필요:
  ```bash
  source ~/kitchmatics/roscamp-repo-1/install/setup.bash
  ```

---

## Domain ID 참조

| 시스템 | Domain ID |
|--------|-----------|
| Pinky1 | 11 |
| Pinky2 | 12 |
| Pinky3 | 13 |
| Arm A | 20 |
| Arm B | 21 |
| Main PC (FMS) | 25 |
