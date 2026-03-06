# 내비게이션 시스템 - 빠른 시작 가이드

## 문제 요약

Kitchmatics FMS 내비게이션 시스템에 **치명적인 문제**가 있습니다:
- Pinky 로봇에서 Nav2 스택이 실행되지 않음
- AMCL 위치 추정이 활성화되지 않음
- Domain Bridge가 내비게이션 토픽을 전달하지 않음
- FMS가 내비게이션 목표를 전송할 수 없음

**수정 소요 시간**: 로봇당 약 30분

---

## 빠른 진단

```bash
# 시스템 상태 확인
bash /home/gw/kitchmatics/roscamp-repo-1/fms/scripts/diagnose_navigation.sh
```

---

## 빠른 수정 (30분)

### 1. Pinky1과 Pinky2에 내비게이션 설정

```bash
# 메인 PC에서 실행
cd /home/gw/kitchmatics/roscamp-repo-1
bash fms/scripts/setup_pinky_navigation.sh all

# 이 스크립트는 다음을 수행합니다:
# ✓ 두 로봇의 연결 상태 확인
# ✓ 맵 파일 복사
# ✓ 내비게이션 패키지 빌드
# ✓ 시작 스크립트 생성
```

### 2. 각 로봇에서 내비게이션 시작

```bash
# Pinky1에 SSH 접속
ssh pinky@192.168.1.7
/home/pinky/start_navigation.sh

# 다른 터미널에서 Pinky2에 SSH 접속
ssh pinky@192.168.1.6
/home/pinky/start_navigation.sh

# Nav2가 완전히 초기화될 때까지 5~10초 대기
```

### 3. 내비게이션 실행 확인

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash
source /home/gw/kitchmatics/roscamp-repo-1/install/setup.bash

# 노드가 나타나는지 확인
ros2 node list | grep -E "pinky|amcl|planner"

# 토픽이 나타나는지 확인
ros2 topic list | grep pinky1 | head -5

# 예상 출력:
# /pinky1/amcl_pose
# /pinky1/scan
# /pinky1/odom
# 등
```

### 4. 로봇 위치 추정 초기화

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# Pinky1 초기 자세 설정
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {
    pose: {position: {x: 0.585, y: 0.085}, orientation: {w: 1.0}},
    covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]
  }
}' --once

# Pinky2 초기 자세 설정
ros2 topic pub /pinky2/initialpose geometry_msgs/PoseWithCovarianceStamped '{
  header: {frame_id: "map"},
  pose: {
    pose: {position: {x: 0.585, y: 0.255}, orientation: {w: 1.0}},
    covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.06853892326654787]
  }
}' --once
```

### 5. 내비게이션 목표 테스트

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# table1로 내비게이션 목표 전송
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{
  pose: {
    header: {frame_id: "map"},
    pose: {position: {x: 1.785, y: 0.35}, orientation: {w: 1.0}}
  }
}'

# 로봇이 table1을 향해 이동해야 합니다
# 진행 상황 확인:
# ros2 topic echo /pinky1/amcl_pose
```

### 6. FMS에서 확인

```bash
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash

# FMS가 로봇 위치를 인식하는지 확인
ros2 topic echo /fms/fleet_status --once | head -20

# (0, 0, 0)이 아닌 실제 좌표가 표시되어야 합니다
```

---

## 성공 지표

빠른 수정 완료 후:

- [ ] `diagnose_navigation.sh`에서 모두 초록색(GREEN)으로 표시
- [ ] `/pinky1/amcl_pose`와 `/pinky2/amcl_pose`가 도메인 25에서 발행됨
- [ ] `/pinky1/navigate_to_pose` 액션 서버 사용 가능
- [ ] FMS 플릿 상태에서 실제 로봇 위치가 표시됨
- [ ] 내비게이션 목표를 전송하면 로봇이 이동함
- [ ] Pinky1과 Pinky2가 동시에 작동 가능

---

## 문제 해결

### Nav2가 시작되지 않는 경우

**시작 스크립트 확인**:
```bash
ssh pinky@192.168.1.7
cat /home/pinky/start_navigation.sh
# ros2 launch pinky_navigation ...이 표시되어야 합니다
```

**수동으로 실행 테스트**:
```bash
ssh pinky@192.168.1.7
export ROS_DOMAIN_ID=11
source /opt/ros/jazzy/setup.bash
cd /home/pinky/pinky_pro
source install/setup.bash
ros2 launch pinky_navigation bringup_launch.xml robot_name:=pinky_b4bc
# 오류 확인
```

### 도메인 25에 토픽이 나타나지 않는 경우

**Domain Bridge 확인**:
```bash
ps aux | grep domain_bridge
# 다음이 표시되어야 합니다: ros2 run domain_bridge domain_bridge ...
```

**브리지 재시작**:
```bash
pkill -f domain_bridge
sleep 2
ros2 run domain_bridge domain_bridge \
    /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml &
```

### Pinky2에 접속할 수 없는 경우

**네트워크 확인**:
```bash
ping 192.168.1.6
# 실패하면 다음을 확인:
# 1. Pinky2 전원이 켜져 있는가?
# 2. 이더넷 케이블이 연결되어 있는가?
# 3. IP 주소가 올바른가?
# 4. 라우터 문제인가?
```

### 로봇이 움직이지 않는 경우

**AMCL 자세 확인**:
```bash
ros2 topic echo /pinky1/amcl_pose --once
# 0이 아닌 위치 값이 표시되어야 합니다
```

**코스트맵 확인**:
```bash
ros2 topic echo /pinky1/local_costmap/costmap --once
# 유효한 코스트맵이 표시되어야 합니다
```

**로봇이 수동으로 움직이는지 확인**:
- 로봇을 물리적으로 밀어봄
- /pinky1/odom 값이 업데이트되는지 확인
- /tf 프레임 변환이 발행되는지 확인

---

## 참고 파일

```
설정 파일:
  /home/gw/kitchmatics/roscamp-repo-1/mobile_robot/params/nav2_params.yaml
  /home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml

진단 도구:
  /home/gw/kitchmatics/roscamp-repo-1/fms/scripts/diagnose_navigation.sh
  /home/gw/kitchmatics/roscamp-repo-1/fms/scripts/setup_pinky_navigation.sh

문서:
  /home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_VALIDATION_REPORT.md
  /home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_SETUP_GUIDE.md
  /home/gw/kitchmatics/roscamp-repo-1/fms/docs/NAVIGATION_QUICK_START.md
```

---

## 전체 타임라인

```
0:00   - 설정 스크립트 실행
5:00   - 두 로봇에서 내비게이션 시작
10:00  - Nav2 노드 실행 확인
15:00  - /initialpose를 통해 초기 자세 설정
20:00  - 단일 내비게이션 목표 테스트
25:00  - 다중 로봇 목표 테스트
30:00  - FMS 플릿 연동 확인
```

---

## 명령어 요약

```bash
# 진단
bash fms/scripts/diagnose_navigation.sh

# 설정
bash fms/scripts/setup_pinky_navigation.sh all

# 연결 확인
export ROS_DOMAIN_ID=25
source /opt/ros/jazzy/setup.bash
ros2 topic list | grep pinky

# 자세 설정
ros2 topic pub /pinky1/initialpose geometry_msgs/PoseWithCovarianceStamped '{...}' --once

# 목표 전송
ros2 action send_goal /pinky1/navigate_to_pose nav2_msgs/action/NavigateToPose '{...}'

# 모니터링
ros2 topic echo /pinky1/amcl_pose
ros2 topic echo /pinky1/navigate_to_pose/_action/feedback
ros2 topic echo /fms/fleet_status
```

---

## 다음 단계

1. **오늘**: 설정 스크립트를 실행하고 내비게이션 동작 확인
2. **내일**: 다중 로봇 연동 테스트
3. **추후**: 속도/정밀도 파라미터 최적화

자세한 내용은 `NAVIGATION_SETUP_GUIDE.md`를 참조하세요.
