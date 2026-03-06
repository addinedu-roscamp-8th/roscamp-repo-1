# ROS2 DDS 디스커버리 트러블슈팅 가이드

## 문제 설명

**증상**: 메인 PC에서 SSH는 정상 동작하지만 로봇의 ROS2 토픽을 볼 수 없음.

**근본 원인**: WiFi 네트워크에서 멀티캐스트 UDP 패킷을 차단하는 경우가 많으며, ROS2는 기본적으로 노드 디스커버리에 멀티캐스트를 사용함.

**해결책**: CycloneDDS를 사용한 **유니캐스트 피어 디스커버리** 적용.

---

## 빠른 수정 (단계별)

### 1단계: 로봇에 DDS 설정 배포

```bash
# 메인 PC에서 실행
cd /home/gw/kitchmatics/roscamp-repo-1/fms/scripts
./deploy_dds_config.sh
```

이 스크립트는 다음을 수행합니다:
- 각 로봇에 CycloneDDS XML 설정 파일 복사
- 각 로봇에 `~/setup_dds.sh` 생성
- 유니캐스트 피어 디스커버리 설정

### 2단계: 로봇 .bashrc 업데이트

**pinky1** (192.168.1.7):
```bash
ssh pinky@192.168.1.7
echo 'source ~/setup_dds.sh' >> ~/.bashrc
source ~/.bashrc
# Nav2 또는 실행 중인 ROS2 노드 재시작
```

**pinky2** (192.168.1.6):
```bash
ssh pinky@192.168.1.6
echo 'source ~/setup_dds.sh' >> ~/.bashrc
source ~/.bashrc
# Nav2 또는 실행 중인 ROS2 노드 재시작
```

### 3단계: 메인 PC에서 연결 테스트

**pinky1 테스트 (도메인 11)**:
```bash
# 터미널 1 - 메인 PC에서
source /home/gw/kitchmatics/roscamp-repo-1/fms/config/setup_dds_domain11.sh
ros2 topic list

# 다음과 같은 토픽이 표시되어야 합니다:
# /amcl_pose
# /cmd_vel
# /odom
# /scan
# /tf
# /tf_static
```

**pinky2 테스트 (도메인 12)**:
```bash
# 터미널 2 - 메인 PC에서
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
export ROS_DOMAIN_ID=12
ros2 topic list
```

### 4단계: Domain Bridge 실행

디스커버리가 정상 동작하면 Domain Bridge를 시작합니다:

```bash
# 메인 PC에서 (도메인 25)
source /home/gw/kitchmatics/roscamp-repo-1/fms/config/setup_dds_main.sh
ros2 run domain_bridge domain_bridge /home/gw/kitchmatics/roscamp-repo-1/fms/config/domain_bridge_complete.yaml
```

---

## 기술 상세

### 변경 사항

**변경 전** (멀티캐스트 디스커버리):
- ROS2가 멀티캐스트 UDP (239.255.0.1)를 사용하여 노드 탐색
- WiFi 라우터가 멀티캐스트 패킷을 드롭하는 경우가 많음
- 결과: 노드 간 디스커버리 불가

**변경 후** (유니캐스트 디스커버리):
- 각 노드가 피어 IP 주소를 명시적으로 인식
- 유니캐스트 UDP (직접 IP-to-IP) 사용
- WiFi 환경에서 안정적으로 동작

### 설정 파일

**메인 PC**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml`
```xml
<Peers>
  <Peer address="192.168.1.7"/>  <!-- pinky1 -->
  <Peer address="192.168.1.6"/>  <!-- pinky2 -->
</Peers>
```

**로봇 (pinky1)**: `~/cyclonedds.xml`
```xml
<Peers>
  <Peer address="192.168.1.3"/>  <!-- 메인 PC -->
</Peers>
```

### 환경 변수

**메인 PC**:
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
export ROS_DOMAIN_ID=25  # 또는 로봇 도메인용 11, 12, 13
```

**로봇 (pinky1)**:
```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/pinky/cyclonedds.xml
export ROS_DOMAIN_ID=11
```

---

## 검증 명령어

### CycloneDDS 로드 확인
```bash
ros2 doctor --report | grep rmw
# rmw_cyclonedds_cpp가 표시되어야 합니다
```

### DDS 트래픽 모니터링
```bash
# 메인 PC에서
source setup_dds_domain11.sh
ros2 topic hz /odom  # 메시지 수신 빈도가 표시되어야 합니다
```

### 네트워크 연결 확인
```bash
# 기본 UDP 연결 테스트
nc -u -v 192.168.1.7 7400  # DDS 기본 포트 범위는 7400부터 시작
```

---

## 자주 발생하는 문제

### 문제 1: "rmw_cyclonedds_cpp not found"

**해결**: CycloneDDS 설치
```bash
sudo apt update
sudo apt install ros-humble-rmw-cyclonedds-cpp
```

### 문제 2: 여전히 토픽이 보이지 않음

**확인 사항**:
1. 로봇의 ROS2 노드가 실제로 실행 중인가?
   ```bash
   ssh pinky@192.168.1.7
   ros2 node list
   ```

2. 환경 변수가 올바르게 설정되었는가?
   ```bash
   echo $RMW_IMPLEMENTATION
   echo $CYCLONEDDS_URI
   echo $ROS_DOMAIN_ID
   ```

3. XML 파일을 읽을 수 있는가?
   ```bash
   cat $CYCLONEDDS_URI
   ```

### 문제 3: 토픽이 나타났다가 사라짐

**원인**: 방화벽이 UDP 포트를 차단

**해결**: DDS 포트 허용 (7400-7999)
```bash
sudo ufw allow 7400:7999/udp
```

---

## 영구 설정

메인 PC의 `~/.bashrc`에 추가:
```bash
# WiFi용 ROS2 DDS 설정
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///home/gw/kitchmatics/roscamp-repo-1/fms/config/cyclonedds_main.xml
export ROS_DOMAIN_ID=25  # FMS 도메인 기본값
```

각 로봇의 `~/.bashrc`에 추가:
```bash
source ~/setup_dds.sh
```

---

## 네트워크 다이어그램

```
메인 PC (192.168.1.3, 도메인 25)
  │
  ├─ CycloneDDS 피어: [192.168.1.7, 192.168.1.6, 192.168.1.11]
  │
  ├─ pinky1 (192.168.1.7, 도메인 11)
  │   └─ CycloneDDS 피어: [192.168.1.3]
  │
  ├─ pinky2 (192.168.1.6, 도메인 12)
  │   └─ CycloneDDS 피어: [192.168.1.3]
  │
  └─ pinky3 (192.168.1.11, 도메인 13)
      └─ CycloneDDS 피어: [192.168.1.3]
```

---

## 참고 자료

- [CycloneDDS 설정 가이드](https://github.com/eclipse-cyclonedds/cyclonedds)
- [ROS2 DDS 튜닝](https://docs.ros.org/en/humble/How-To-Guides/DDS-tuning.html)
- [WiFi 모범 사례](https://docs.ros.org/en/humble/How-To-Guides/Installation-Troubleshooting.html#enable-multicast)
