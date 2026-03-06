# 내비게이션 시스템 설정 가이드
**Kitchmatics FMS와 Pinky 모바일 로봇용**

---

## 빠른 상태 확인

다음 명령어로 내비게이션 시스템 상태를 확인하세요:

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
bash fms/scripts/diagnose_navigation.sh
```

---

## 문제: Pinky 로봇에서 Nav2 스택이 실행되지 않음

### 증상
- FMS 플릿 상태에서 로봇 위치가 (0, 0, 0)으로 표시됨
- `/pinky1/amcl_pose` 또는 `/pinky2/amcl_pose` 토픽이 없음
- 로봇에 내비게이션 목표를 전송할 수 없음
- `/navigate_to_pose` 액션 서버를 사용할 수 없음

### 근본 원인
Pinky 로봇 시작 과정에서 Nav2 내비게이션 스택이 실행되지 않습니다. 현재는 lamp 모듈만 실행되고 있습니다.

### 해결 방법

#### 1단계: 로봇 시작 스크립트 확인

Pinky1에 SSH로 접속하여 실제 시작 스크립트를 확인합니다:

```bash
ssh pinky@192.168.1.7

# 현재 실행 중인 프로세스 확인
ps aux | grep -i bringup | grep -v grep

# 다음과 같이 출력되어야 합니다:
# /bin/bash /home/pinky/pinky_devices/lamp_module_bringup
```

#### 2단계: Nav2를 포함하도록 시작 스크립트 수정

시작 스크립트에 Nav2 내비게이션 스택 실행을 추가해야 합니다. 두 가지 방법이 있습니다:

**방법 A: 통합 시작 스크립트 생성** (권장)

`/home/pinky/bringup_full.sh`를 생성합니다:

```bash
#!/bin/bash
#
# 전체 로봇 시작: Lamp 모듈 + 내비게이션
# 사용법: ./bringup_full.sh [robot_name]
#

ROBOT_NAME=${1:-"pinky_b4bc"}
export ROS_DOMAIN_ID=11  # pinky2는 12, pinky3는 13

source /opt/ros/jazzy/setup.bash

# 백그라운드에서 lamp 모듈 시작
echo "Starting lamp module..."
/home/pinky/pinky_devices/lamp_module_bringup &
LAMP_PID=$!

# lamp 모듈 초기화 대기
sleep 2

# Nav2 내비게이션 시작
echo "Starting Nav2 navigation stack..."
cd /home/pinky/pinky_pro

# 필요시 빌드
if [ ! -d "install" ]; then
    echo "Building packages..."
    colcon build --packages-select pinky_navigation pinky_bringup
fi

# 빌드된 패키지 소싱
source install/setup.bash

# 내비게이션 실행
ros2 launch pinky_navigation bringup_launch.xml robot_name:=$ROBOT_NAME

# 종료 시 정리
trap "kill $LAMP_PID" EXIT
```

저장 후 실행 권한 부여:
```bash
chmod +x /home/pinky/bringup_full.sh
```

**방법 B: 기존 Lamp 모듈 스크립트 수정**

기존 lamp_module_bringup을 계속 사용하면서 lamp 초기화 후 Nav2도 함께 실행하도록 수정할 수 있습니다.

`/home/pinky/pinky_devices/lamp_module_bringup`을 편집합니다:

```bash
#!/bin/bash
# ... 기존 lamp 설정 코드 ...

# lamp 초기화 후 다음을 추가:
export ROS_DOMAIN_ID=11
source /opt/ros/jazzy/setup.bash
cd /home/pinky/pinky_pro
source install/setup.bash

# Nav2를 백그라운드 또는 포그라운드로 실행
ros2 launch pinky_navigation bringup_launch.xml robot_name:=pinky_b4bc &
```

#### 3단계: 맵 파일 존재 여부 확인

Pinky1에서 맵 파일이 있는지 확인합니다:

```bash
ssh pinky@192.168.1.7

ls -la /home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/maps/

# 다음 파일이 있어야 합니다:
# - map.yaml
# - map.pgm (또는 map.png)
```

맵이 없는 경우 메인 PC에서 복사합니다:

```bash
# 메인 PC에서 실행
scp /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/maps/real.yaml \
    pinky@192.168.1.7:/home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/maps/

scp /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/maps/real.pgm \
    pinky@192.168.1.7:/home/pinky/pinky_pro/src/pinky_pro/pinky_navigation/maps/
```

#### 4단계: 새 시작 스크립트로 로봇 재시작

```bash
ssh pinky@192.168.1.7

# 기존 프로세스 종료
pkill -f "lamp_module_bringup"
pkill -f "ros2"
pkill -f "pillar"

# 정리 대기
sleep 2

# 통합 시작으로 실행 (방법 A)
/home/pinky/bringup_full.sh pinky_b4bc

# 또는 방법 B를 사용하는 경우, lamp 모듈만 재시작
/home/pinky/pinky_devices/lamp_module_bringup
```

#### 5단계: Nav2 실행 확인

새 터미널에서 노드를 확인합니다:

```bash
export ROS_DOMAIN_ID=11
source /opt/ros/jazzy/setup.bash

# Nav2 노드 확인
ros2 node list | grep -E "amcl|planner|controller|bt_navigator|map_server"

# 예상 출력:
# /amcl
# /map_server
# /planner_server
# /controller_server
# /behavior_server
# /bt_navigator
# /velocity_smoother
```

---

## 2단계: Domain Bridge 설정 확인

Domain Bridge는 Pinky 로봇(도메인 11/12/13)의 내비게이션 토픽을 메인 PC(도메인 25)로 전달하는 역할을 합니다.

### Domain Bridge 상태 확인

```bash
# 메인 PC에서 실행
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

# 브리지 실행 여부 확인
ps aux | grep domain_bridge | grep -v grep

# 실행되지 않는 경우 시작:
ros2 run domain_bridge domain_bridge \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml &
```

### 토픽 브리징 확인

```bash
# 메인 PC에서 Pinky1 토픽 확인
ros2 topic list | grep pinky1

# 예상 토픽:
# /pinky1/amcl_pose
# /pinky1/scan
# /pinky1/odom
# /pinky1/initialpose
# /pinky1/navigate_to_pose/_action/feedback
# /pinky1/navigate_to_pose/_action/status
```

토픽이 없는 경우 Domain Bridge가 제대로 동작하지 않는 것입니다. 설정을 확인하세요:

```bash
# Domain Bridge 설정 확인
cat /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml | grep -A5 "pinky1"
```

---

## 3단계: AMCL 위치 추정 초기화

Nav2가 실행되고 Domain Bridge가 동작하면, AMCL 위치 추정을 위한 초기 자세를 설정해야 합니다.

### 초기 자세 결정

`fms/config/fms_config.yaml`에서 초기 자세 값:

```yaml
initial_poses:
  pinky1:
    x: 0.585
    y: 0.085
    theta: 0.0
  pinky2:
    x: 0.585
    y: 0.255
    theta: 0.0
```

### ROS 토픽을 통한 초기 자세 설정

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# Pinky1용
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {
    frame_id: "map"
  },
  pose: {
    pose: {
      position: {x: 0.585, y: 0.085, z: 0.0},
      orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
    },
    covariance: [
      0.25, 0, 0, 0, 0, 0,
      0, 0.25, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0.06853892326654787
    ]
  }
}' --once

# Pinky2용
ros2 topic pub /pinky2/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {
    frame_id: "map"
  },
  pose: {
    pose: {
      position: {x: 0.585, y: 0.255, z: 0.0},
      orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
    },
    covariance: [
      0.25, 0, 0, 0, 0, 0,
      0, 0.25, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0, 0, 0.06853892326654787
    ]
  }
}' --once
```

### AMCL 활성 상태 확인

```bash
# 자세 추정값 확인
timeout 5 ros2 topic echo /pinky1/amcl_pose --once

# 예상 출력: 위치와 공분산이 포함된 PoseWithCovarianceStamped
```

---

## 4단계: 내비게이션 목표 테스트

### 간단한 내비게이션 목표 전송

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# table1 (1.785, 0.35)로 목표 전송
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{
  pose: {
    header: {frame_id: "map"},
    pose: {
      position: {x: 1.785, y: 0.35, z: 0.0},
      orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
    }
  }
}'
```

### 내비게이션 진행 상황 모니터링

다른 터미널에서:

```bash
# AMCL 자세 업데이트 확인 (현재 위치 표시)
ros2 topic echo /pinky1/amcl_pose

# 내비게이션 피드백 확인 (진행 상황 표시)
ros2 topic echo /pinky1/navigate_to_pose/_action/feedback

# 코스트맵 확인 (장애물 표시)
ros2 topic echo /pinky1/local_costmap/costmap
```

---

## 5단계: FMS 자동 초기화 활성화

FMS는 시작 시 자동으로 초기 자세를 설정할 수 있습니다. 설정을 확인하세요:

```bash
grep -A5 "auto_set_initial_pose" \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml

# 다음과 같이 표시되어야 합니다:
# auto_set_initial_pose: true
```

활성화된 경우, FMS는:
1. `/pinky1/initialpose`, `/pinky2/initialpose`에 초기 자세를 발행
2. AMCL 위치 추정을 자동으로 초기화
3. 위치 추정이 수렴될 때까지 내비게이션 작업 수락을 대기

---

## 문제 해결

### 문제 1: Nav2 노드가 나타나지 않음

**증상**:
- `ros2 node list`에 `/bt_navigator`, `/amcl`, `/planner_server`가 없음
- 오류: "Nav2 package not found"

**해결 방법**:

A. 패키지 빌드:
```bash
ssh pinky@192.168.1.7
cd /home/pinky/pinky_pro
colcon build --packages-select pinky_navigation pinky_bringup
source install/setup.bash
```

B. 패키지 경로 확인:
```bash
ros2 pkg list | grep pinky
# pinky_navigation, pinky_bringup이 표시되어야 합니다

# 없는 경우 package_xml.xml 또는 setup.py가 잘못된 것입니다
```

C. 런치 파일 확인:
```bash
# 직접 실행해 봅니다
ros2 launch pinky_navigation bringup_launch.xml robot_name:=pinky_b4bc

# 출력에서 오류 확인
```

### 문제 2: Domain Bridge가 토픽을 전달하지 않음

**증상**:
- 도메인 25에서 `/pinky1/amcl_pose`를 사용할 수 없음
- 토픽이 도메인 11에는 있지만 25에는 없음

**해결 방법**:

A. Domain Bridge 실행 확인:
```bash
ps aux | grep domain_bridge
# 다음이 표시되어야 합니다: ros2 run domain_bridge domain_bridge ...
```

B. Domain Bridge 재시작:
```bash
pkill -f domain_bridge
sleep 1

ros2 run domain_bridge domain_bridge \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml &
```

C. 브리지 설정 확인:
```bash
# pinky1 토픽이 설정되어 있는지 확인
grep -A20 "from_domain: 11" \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml

# pinky1/* 토픽이 표시되어야 합니다
```

### 문제 3: AMCL이 자세를 발행하지 않음

**증상**:
- `/pinky1/amcl_pose` 토픽은 존재하지만 메시지가 없음
- FMS 플릿 상태에서 로봇 위치가 (0,0,0)으로 표시됨

**해결 방법**:

A. map_server 실행 확인:
```bash
export ROS_DOMAIN_ID=11
ros2 node info /map_server
# 오류가 발생하면 맵이 로드되지 않은 것입니다
```

B. 초기 자세 설정:
```bash
export ROS_DOMAIN_ID=25

ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {
    pose: {position: {x: 0.585, y: 0.085}, orientation: {w: 1.0}},
    covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]
  }
}' --once
```

C. AMCL 파라미터 확인:
```bash
ros2 param get /amcl max_particles
ros2 param get /amcl min_particles
# nav2_params.yaml과 비교
```

### 문제 4: 내비게이션 목표 시간 초과

**증상**:
- 목표를 전송했지만 액션 상태가 "TIMEOUT"으로 표시됨
- 로봇이 목표를 향해 이동하지 않음

**해결 방법**:

A. 코스트맵 초기화 확인:
```bash
timeout 2 ros2 topic echo /pinky1/local_costmap/costmap --once
# 유효한 코스트맵 데이터가 표시되어야 합니다
```

B. 경로 플래너 동작 확인:
```bash
# 플래너 피드백 모니터링
ros2 topic echo /pinky1/plan &

# 목표 전송
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{...}'

# /pinky1/plan에 경로가 발행되어야 합니다
```

C. 로봇 이동 가능 여부 확인:
```bash
# 속도 명령을 직접 전송 (로봇이 지원하는 경우)
# 하드웨어 동작 여부를 확인합니다
```

### 문제 5: Pinky2에 접속 불가

**증상**:
- 192.168.1.6에 SSH 시간 초과
- ping이 동작하지 않음

**해결 방법**:

A. 네트워크 연결 확인:
```bash
ping 192.168.1.6
# 실패하면 네트워크 문제

# 라우터/WiFi 확인
ping 192.168.1.1  # 라우터
```

B. 로봇 전원 확인:
- Pinky2 전원이 켜져 있는가?
- 배터리 표시등 확인

C. 로봇 상태 확인:
```bash
# 온라인 상태인 다른 Pinky에서 확인
ssh pinky@192.168.1.7
ping 192.168.1.6  # 네트워크 내부에서 시도
```

D. 수동 복구:
```bash
# 여전히 실패하면 Pinky2에 물리적으로 접근하여:
# 1. 전원이 켜져 있는지 확인
# 2. 이더넷 연결 확인
# 3. 로봇 재시작
# 4. SSH 재시도
```

---

## 성능 튜닝

내비게이션이 동작한 후 다음 파라미터로 성능을 조정할 수 있습니다:

### 더 빠른 내비게이션
```yaml
# nav2_params.yaml에서

controller_server:
  FollowPath:
    desired_linear_vel: 0.20        # 0.15에서 증가
    max_angular_vel: 1.0             # 0.8에서 증가

planner_server:
  GridBased:
    tolerance: 0.04                  # 0.02에서 증가
```

### 더 정밀한 내비게이션
```yaml
# nav2_params.yaml에서

controller_server:
  general_goal_checker:
    xy_goal_tolerance: 0.02          # 0.05에서 감소
    yaw_goal_tolerance: 0.05         # 0.1에서 감소
```

### 더 나은 위치 추정
```yaml
# nav2_params.yaml에서

amcl:
  max_particles: 4000                # 3000에서 증가
  min_particles: 1000                # 500에서 증가
```

---

## 성공 기준

내비게이션 시스템이 올바르게 동작하는 경우:

1. `ros2 node list`에 Nav2 노드가 표시됨
2. `/pinky1/amcl_pose`가 도메인 25에서 발행됨 (Domain Bridge를 통해)
3. `/pinky1/navigate_to_pose` 액션을 사용할 수 있음
4. FMS 플릿 상태에서 실제 로봇 위치가 표시됨
5. 내비게이션 목표가 성공적으로 완료됨
6. FMS 충돌 회피로 경로 충돌이 해결됨
7. Pinky1과 Pinky2가 동시에 내비게이션 가능

---

## 다음 단계

1. **1단계**의 시작 스크립트 변경 사항 적용
2. **2단계**의 Domain Bridge 확인
3. **3단계**의 AMCL 초기화
4. **4단계**의 목표 테스트
5. 진단 스크립트를 실행하여 전체 시스템 확인

```bash
bash /home/gw/kitchmatics/roscamp-repo-1/fms/scripts/diagnose_navigation.sh
```

---

## 참고 자료

- 내비게이션 검증 보고서: `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_VALIDATION_REPORT.md`
- 설정 파일: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/`
- ROS2 Nav2 문서: https://nav2.org/
