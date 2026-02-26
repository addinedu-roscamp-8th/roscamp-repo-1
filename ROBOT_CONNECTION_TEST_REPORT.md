# 로봇 연결 상태 테스트 보고서

테스트 일시: 2026-02-26 19:45 KST
테스트자: Connection Tester Agent
FMS Domain: 25 (Main PC)

---

## 1. 네트워크 연결 테스트 (Ping)

| 로봇 | IP 주소 | 상태 | 평균 응답시간 | 패킷 손실 |
|------|---------|------|-------------|---------|
| pinky1 | 192.168.1.7 | PASS | 19.93ms | 0% |
| pinky2 | 192.168.1.6 | PASS | 64.18ms | 0% |
| armA | 192.168.1.4 | PASS | 7.78ms | 0% |
| armB | 192.168.1.10 | PASS | 68.04ms | 0% |

모든 로봇이 네트워크상에서 정상적으로 응답합니다.

---

## 2. ROS2 토픽 가용성 테스트

### 2.1 pinky1 (Domain 11)
**상태**: PASS
**발견된 토픽 수**: 60+

주요 토픽:
- /amcl_pose (Pose 발행)
- /battery/voltage (배터리 전압)
- /odom (Odometry)
- /scan (LiDAR)
- /cmd_vel, /cmd_vel_nav, /cmd_vel_teleop (속도 명령)
- Navigation 관련: /plan, /received_global_plan, /global_costmap/*, /local_costmap/*

### 2.2 pinky2 (Domain 12)
**상태**: PASS
**발견된 토픽 수**: 60+

주요 토픽: pinky1과 동일한 구조
- /amcl_pose (Pose 발행 - 데이터 수신 확인됨)
- /battery/voltage (배터리 전압)
- /odom, /scan, /cmd_vel 등

### 2.3 armA (Domain 20)
**상태**: PASS
**발견된 토픽 수**: 5

주요 토픽:
- /arm_a/cmd (명령 수신 대기 중)
- /arm_a/status (상태 발행)
- /parameter_events
- /rosout

### 2.4 armB (Domain 21)
**상태**: PASS
**발견된 토픽 수**: 6

주요 토픽:
- /arm_b/cmd (명령 수신 대기 중)
- /arm_b/status (상태 발행)
- /verify/cmd, /verify/status
- /parameter_events, /rosout

---

## 3. 토픽 데이터 발행 테스트

### 3.1 pinky1 데이터 발행 상태
| 토픽 | 상태 | 설명 |
|-----|------|------|
| /amcl_pose | TIMEOUT | 로봇이 실행 중이지 않거나 초기화 대기 중 |
| /battery/voltage | TIMEOUT | 데이터 발행 없음 |

### 3.2 pinky2 데이터 발행 상태
| 토픽 | 상태 | 설명 |
|-----|------|------|
| /amcl_pose | PASS | 데이터 수신 성공 (위치: 0,0,0) |
| /battery/voltage | PASS | 데이터 수신 성공 (7.74V) |

### 3.3 armA, armB 데이터 발행 상태
| 토픽 | 상태 | 설명 |
|-----|------|------|
| /arm_a/cmd | TIMEOUT | 명령 수신 대기 중 |
| /arm_b/status | TIMEOUT | 상태 발행 없음 |
| /verify/status | TIMEOUT | 상태 발행 없음 |

---

## 4. Domain Bridge 연결 테스트 (FMS Domain 25에서)

**상태**: PASS
**Domain Bridge 프로세스**: 실행 중
- PID: 185161
- 설정 파일: /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_v3.yaml

### 4.1 FMS에서 보이는 브리지된 토픽

| 토픽 | 출처 Domain | 상태 |
|------|------------|------|
| /pinky1/amcl_pose | 11 | 브리지됨 |
| /pinky1/battery/voltage | 11 | 브리지됨 |
| /pinky1/battery/present | 11 | 브리지됨 |
| /pinky1/odom | 11 | 브리지됨 |
| /pinky1/scan | 11 | 브리지됨 |
| /pinky2/amcl_pose | 12 | 브리지됨 |
| /pinky2/battery/voltage | 12 | 브리지됨 |
| /pinky2/battery/present | 12 | 브리지됨 |
| /pinky2/odom | 12 | 브리지됨 |
| /arm_a/status | 20 | 브리지됨 |
| /arm_a/cmd | 25 -> 20 | 브리지됨 (양방향) |
| /arm_b/status | 21 | 브리지됨 |
| /arm_b/cmd | 25 -> 21 | 브리지됨 (양방향) |

---

## 5. 종합 분석

### 5.1 정상 작동하는 항목
1. **네트워크 연결**: 모든 로봇 정상 (모두 0% 패킷손실)
2. **ROS2 데몬**: 모든 Domain에서 실행 중
3. **Domain Bridge**: 정상 작동 중 (PID 185161)
4. **Topic 브리징**: 명명법 변환이 정상적으로 동작
5. **pinky2**: /amcl_pose와 /battery/voltage에서 데이터 수신 확인
6. **로봇 토픽 발행**: pinky1, pinky2 모두 예상되는 모든 토픽이 목록에 표시됨

### 5.2 주의 사항
1. **pinky1**: /amcl_pose와 /battery/voltage에서 데이터 수신 실패
   - 원인: 로봇이 아직 초기화되지 않았거나 센서 데이터를 아직 발행하지 않음
   - 현재 상태: 토픽 구조는 존재하나 데이터 발행 없음

2. **armA, armB**: 상태 토픽에서 데이터 수신 실패
   - 원인: 로봇팔 프로세스가 아직 시작되지 않았거나 대기 중
   - 현재 상태: /cmd 토픽은 명령 수신 대기 중, /status는 데이터 발행 없음

3. **topicinfo 분석** (pinky1):
   - /amcl_pose: Publisher count = 1, Subscription count = 2
   - /amcl_pose: Publisher count = 1, Subscription count = 0 (pinky2)
   - pinky1은 구독자가 있으나 pinky2는 없음

---

## 6. 권장사항

### 즉시 조치
1. pinky1 로봇 시작 확인
   ```bash
   ssh pinky@192.168.1.7 "source /opt/ros/jazzy/setup.bash && source ~/pinky_pro/install/local_setup.bash && export ROS_DOMAIN_ID=11 && ros2 launch pinky_bringup bringup_robot.launch.xml"
   ```

2. armA, armB 로봇팔 프로세스 시작
   ```bash
   ssh jetcobot@192.168.1.4 "source /opt/ros/jazzy/setup.bash && <적절한 론치 커맨드>"
   ssh jetcobot@192.168.1.10 "source /opt/ros/jazzy/setup.bash && <적절한 론치 커맨드>"
   ```

### 모니터링 항목
- pinky1이 시작되면 /amcl_pose와 /battery/voltage 데이터 발행 확인
- armA, armB의 /status 토픽 데이터 발행 확인
- Domain Bridge 로그에서 에러 메시지 확인

---

## 7. 테스트 결론

**전체 상태: PARTIALLY OPERATIONAL**

- Domain Bridge 인프라: 정상 작동
- 네트워크 연결: 모든 로봇 도달 가능
- ROS2 Topic 구조: 정상 설정
- 데이터 흐름: pinky2는 정상, pinky1과 로봇팔들은 아직 시작 필요

다음 단계: 각 로봇의 비루시 소프트웨어가 정상적으로 시작될 때까지 대기

