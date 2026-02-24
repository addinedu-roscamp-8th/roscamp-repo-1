# Kitchmatics 프로젝트 - Claude 작업 가이드

## 프로젝트 정보

- **프로젝트 루트**: `/home/gw/kitchmatics/roscamp-repo-1`
- **현재 작업 티켓**: SC-357 (FMS 구동)
- **작업 브랜치**: `feature/SC-357-FMS`

---

## 필수 규칙

### 1. 코드 수정 규칙
- **로봇 내부 코드는 절대 수정하지 말 것**
- 로봇 코드 수정이 필요한 경우:
  1. 프로젝트 디렉토리(`roscamp-repo-1`)에서 수정
  2. PC에서 `git push`
  3. 로봇에서 `git clone` 또는 `git pull`
  4. 적용하고자 하는 코드를 오버라이딩

### 2. Git 커밋 규칙
- 커밋 메시지 앞에 `[SC-357]` 붙이기
- 간결하게 작성
- Claude가 작성했다는 티가 나지 않게

### 3. 브랜치 규칙
- SC-357 목표 달성 전까지 별도 브랜치에서 개발
- 브랜치명: `FMS 구동(SC-357)`

---

## SC-357 목표

### 최종 목표
pinky1, pinky2, pinky3이 FMS를 통해 제어되어야 함

### 목표 달성 기준 (플로우)
1. Customer GUI를 통해 주문 (table1)
2. 주문 확정에 따라 pinky가 pickup_spot으로 이동
3. 로봇팔 과정은 skip (추후 로봇팔 연결 예정)
4. table1로 pinky가 서빙 도착
5. pinky 도착과 연동하여 Customer GUI에서 음식 도착 화면 송출
6. Customer GUI에서 `수령 완료` 버튼 클릭
7. pinky가 다시 pinky_spot으로 이동

### 개발 순서
1. **pinky1**만 사용하여 먼저 코드 완성
2. 이후 pinky2, pinky3 적용

---

## 현재까지 완료된 작업 (2026-02-24)

### TCP 통신 버그 수정
- **파일**: `fms/fms/tcp_communication.py`
- **내용**: `socket` → `client_socket` 속성명 수정

### 다중 로봇 네비게이션 Launch 파일 생성
- **파일**: `mobile_robot/launch/bringup_launch.py`
- **기능**:
  - RewrittenYaml을 사용하여 namespace에 따라 파라미터 자동 설정
  - pinky1, pinky2, pinky3 모두 동일한 params 파일로 동작
  - 로봇 내부 코드 수정 없이 roscamp-repo-1에서 관리

### TF Frame Prefix 이슈 해결
- 로봇이 namespace prefix 없이 TF를 발행하는 문제 해결
- `bringup_launch.py`에서 frame 설정 수정

### Nav2 파라미터 튜닝
- **파일**: `mobile_robot/params/nav2_params.yaml`
- 소형 로봇(5.5cm 반경)에 맞게 파라미터 조정

---

## 네트워크 구성

| 장치 | IP 주소 | 역할 |
|------|---------|------|
| Master PC | 192.168.1.3 | FMS Server |
| pinky_b4bc (pinky1) | 192.168.1.7 | Mobile Robot |
| pinky_e2a8 (pinky2) | 192.168.1.6 | Mobile Robot |
| pinky_d29d (pinky3) | 192.168.1.11 | Mobile Robot |

---

## 로봇 실행 명령어

### PC에서 FMS 실행
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 launch fms fms_closed_network.launch.py
```

### 로봇에서 실행 (SSH 접속 후)
```bash
# 터미널 1: 로봇 하드웨어
ros2 launch pinky_bringup bringup_robot.launch.xml namespace:=pinky1

# 터미널 2: 네비게이션
ros2 launch ~/roscamp-repo-1/mobile_robot/launch/bringup_launch.py namespace:=pinky1 map:=~/real.yaml
```

---

## 진행 중인 작업

- [ ] FMS → 로봇 네비게이션 통합 테스트
- [ ] AMCL 초기 위치 설정 및 localization 확인
- [ ] Customer GUI → FMS → Robot 플로우 완성
- [ ] 음식 도착 화면 연동
- [ ] 수령 완료 후 pinky_spot 복귀 구현
