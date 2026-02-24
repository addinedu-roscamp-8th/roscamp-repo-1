# Kitchmatic Fleet Management System

Kitchmatic 프로젝트의 Fleet Management System (FMS) 및 Main Server 구현입니다.

## 빠른 시작 (Quick Start)

### 옵션 A: 주문 → Pinky 로봇 이동 테스트 (로봇팔 스킵 모드)

**터미널 1: FMS 실행**
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
```

**터미널 2: 테스트 주문 전송**
```bash
cd /home/gw/kitchmatics/roscamp-repo-1

# 테이블 1번으로 주문
python3 fms/scripts/send_order.py --table 1

# 인터랙티브 모드
python3 fms/scripts/send_order.py --interactive
```

> **로봇팔 스킵 모드**: Pinky가 pickup_spot 도착 후 3초 뒤 자동으로 테이블로 이동

---

### 옵션 B: Customer GUI → 전체 시스템

**터미널 1: FMS 실행**
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
```

**터미널 2: Main Server 실행**
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run main_server main_server
```

**터미널 3: Customer GUI 실행**
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui
python3 src/main.py
```

---

### 옵션 C: Closed Network TCP 서버 (로봇 직접 통신)

**1단계: FMS 서버 시작 (PC: 192.168.1.3)**
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
./fms/scripts/start_fms_server.sh
```

**2단계: 관리자 GUI 실행**
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui
python3 src/main.py
```

**3단계: 로봇 파라미터 동기화 (필요시)**
```bash
# 모든 로봇에 nav2_params.yaml 동기화
python3 fms/scripts/robot_file_sync.py --all --sync
```

---

## Closed Network 구성 (WiFi: kitchmatics)

| 장치 | IP 주소 | 포트 | 상태 |
|------|---------|------|------|
| **Master PC** | 192.168.1.3 | 9000 | FMS Server |
| pinky_b4bc | 192.168.1.7 | 9001 | Mobile Robot |
| pinky_e2a8 | 192.168.1.6 | 9001 | Mobile Robot |
| pinky_d29d | - | - | 보류중 |
| jetcobot_aa1f | 192.168.1.4 | 9002 | Cobot Arm |
| jetcobot_aa85 | 192.168.0.59 | 9002 | Cobot Arm |

---

## 시스템 아키텍처

```
                          ┌─────────────────────────────────────────┐
                          │         WiFi: kitchmatics               │
                          └─────────────────────────────────────────┘
                                            │
        ┌───────────────────────────────────┼───────────────────────────────────┐
        │                                   │                                   │
        ▼                                   ▼                                   ▼
┌───────────────┐                  ┌───────────────┐                   ┌───────────────┐
│  Mobile Robot │                  │   Master PC   │                   │  Cobot Arm    │
│  (PinkyPro)   │◄────TCP 9001────►│  192.168.1.3  │◄────TCP 9002─────►│  (JetCobot)   │
│  192.168.1.7  │                  │   Port 9000   │                   │  192.168.1.4  │
│  192.168.1.6  │                  │               │                   │ 192.168.0.59  │
└───────────────┘                  └───────┬───────┘                   └───────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
           ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
           │  Admin GUI   │       │  PostgreSQL  │       │    Kiosks    │
           │ Fleet Monitor│       │   Database   │       │  (8 tables)  │
           └──────────────┘       └──────────────┘       └──────────────┘
```

### 주요 컴포넌트

1. **Main Server** (`app/backend/main_server/`)
   - ROS 2 Node + TCP Server + PostgreSQL 통합
   - 키오스크/Admin GUI와 TCP 통신
   - FMS 및 로봇팔과 ROS 2 Topics 통신
   - 데이터베이스 관리 (주문, 재고, 로봇 상태 등)

2. **Fleet Management System (FMS)** (`fms/`)
   - 3대의 서빙 로봇 관리 (pinky1, pinky2, pinky3)
   - 주문 큐 및 작업 할당
   - 충돌 방지 (Zone-based collision avoidance)
   - Nav2 기반 경로 계획 및 네비게이션

3. **Fleet Interfaces** (`fleet_interfaces/`)
   - 커스텀 ROS 2 메시지 타입 정의
   - OrderRequest, CookingOrder, LoadingComplete, RobotStatus, FleetStatus, DeliveryComplete

4. **Database** (`database/`)
   - PostgreSQL 스키마 정의
   - 메뉴, 재고, 주문, 로봇, 품질검사 테이블

## 빌드 및 설치

### 1. 사전 요구사항

```bash
# ROS 2 Jazzy 설치 필요
# Python 3.10+
# PostgreSQL 14+

# Python 패키지 설치
sudo apt install python3-sqlalchemy python3-psycopg2
```

### 2. 데이터베이스 설정

```bash
cd database
# README.md의 지침에 따라 PostgreSQL 설정
cat README.md
```

**중요**: `database/README.md`의 TODO 항목을 채워주세요:
- 데이터베이스 비밀번호 설정
- DB 서버 IP 주소 설정

### 3. ROS 2 패키지 빌드

```bash
cd ~/roscamp-repo-1/

# fleet_interfaces 빌드
cd fleet_interfaces
colcon build
source install/setup.bash

# Main Server 빌드
cd ../app/backend
colcon build
source install/setup.bash

# FMS 빌드
cd ../../fms
colcon build
source install/setup.bash
```

## 실행 방법

### 방법 1: Closed Network FMS (권장)

#### 터미널 1: FMS TCP 서버 시작 (PC: 192.168.1.3)

```bash
cd /home/gw/kitchmatics/roscamp-repo-1

# 네트워크 연결 확인 및 서버 시작
./fms/scripts/start_fms_server.sh
```

**출력 예시:**
```
==========================================================
     Kitchmatics FMS - Closed Network Server
==========================================================

Checking network connectivity...
✓ Connected to WiFi: kitchmatics
✓ Local IP: 192.168.1.3

Mobile Robots (PinkyPro):
  ✓ 192.168.1.7 - Reachable
  ✓ 192.168.1.6 - Reachable

Cobot Arms (JetCobot):
  ✓ 192.168.0.56 - Reachable
  ✓ 192.168.0.59 - Reachable

Starting server on port 9000...
```

#### 터미널 2: 관리자 GUI (Fleet Monitor)

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui
python3 src/main.py
```

GUI 기능:
- Mobile Robots 탭: PinkyPro 로봇 상태 모니터링
- Cobot Arms 탭: JetCobot 로봇팔 상태 모니터링
- 전체 통계 탭: Fleet 통계 및 이벤트 로그

#### 터미널 3: 로봇에서 Navigation 실행 (SSH로 로봇 접속 후)

```bash
# PinkyPro 로봇에서 (예: pinky_b4bc - 192.168.1.7)
ssh pinky@192.168.1.7  # 비밀번호: 1

# 터미널 1: 로봇 하드웨어 (라이다, 모터 등)
ros2 launch pinky_bringup bringup_robot.launch.xml namespace:=pinky1

# 터미널 2: 네비게이션 (roscamp-repo-1의 launch 파일 사용)
ros2 launch ~/roscamp-repo-1/mobile_robot/launch/bringup_launch.py namespace:=pinky1 map:=~/real.yaml
```

> **참고**: `bringup_launch.py`는 RewrittenYaml을 사용하여 namespace에 따라 자동으로 파라미터를 설정합니다.
> pinky1, pinky2, pinky3 모두 동일한 방법으로 실행하면 됩니다.

#### 터미널 4: 로봇 TCP 클라이언트 실행 (선택사항)

```bash
# PinkyPro 로봇에서 FMS와 TCP 통신
cd ~/roscamp-repo-1/fms/scripts
python3 robot_client.py --robot-id pinky1 --server 192.168.1.3

# JetCobot에서 (예: jetcobot_aa1f)
ssh jetson@192.168.1.4
cd ~/roscamp-repo-1/fms/scripts
python3 robot_client.py --robot-id cobot1 --server 192.168.1.3 --type JETCOBOT
```

---

### 방법 2: 기존 ROS 2 방식

#### 터미널 1: Main Server 실행

```bash
cd ~/roscamp-repo-1/app/backend
source install/setup.bash

# Main Server 시작
ros2 run main_server main_server
```

**실행 전 확인사항**:
- PostgreSQL이 실행 중인지 확인
- `main_server/database_manager.py`의 TODO 주석에서 DB 연결 정보 설정
- TCP 포트 9999가 사용 가능한지 확인

#### 터미널 2: FMS 실행

```bash
cd ~/roscamp-repo-1/fms
source install/setup.bash

# FMS 노드 시작
ros2 launch fms fms_launch.py
```

**실행 전 확인사항**:
- 3대의 서빙 로봇이 각각의 네임스페이스로 실행 중인지 확인
  - `/pinky1`, `/pinky2`, `/pinky3`
- Nav2가 각 로봇에서 실행 중인지 확인
- AMCL 초기 위치가 설정되어 있는지 확인

#### 터미널 3: 로봇 네임스페이스 확인

```bash
# 실행 중인 로봇 Topics 확인
ros2 topic list | grep pinky

# 예상 출력:
# /pinky1/pose
# /pinky1/battery/voltage
# /pinky1/battery/present
# /pinky1/navigate_to_pose/_action/...
# (pinky2, pinky3도 동일)
```

## 로봇 파라미터 동기화 (File Override)

로봇 내부의 nav2_params.yaml, mapper_params.yaml 파일을 프로젝트에서 관리하고 동기화합니다.

### 사용법

```bash
cd /home/gw/kitchmatics/roscamp-repo-1

# 설정된 로봇 목록 확인
python3 fms/scripts/robot_file_sync.py --list

# 특정 로봇에 파일 동기화
python3 fms/scripts/robot_file_sync.py --robot pinky_b4bc --sync

# 모든 활성화된 로봇에 동기화
python3 fms/scripts/robot_file_sync.py --all --sync

# 동기화 전 미리보기 (dry-run)
python3 fms/scripts/robot_file_sync.py --robot pinky_b4bc --sync --dry-run

# SSH 연결 테스트
python3 fms/scripts/robot_file_sync.py --robot pinky_b4bc --check

# 파일 비교 (로컬 vs 원격)
python3 fms/scripts/robot_file_sync.py --robot pinky_b4bc --compare

# 원격 파일 백업 후 동기화
python3 fms/scripts/robot_file_sync.py --robot pinky_b4bc --sync --backup
```

### 동기화 경로

| 로컬 (PC) | 원격 (PinkyPro 로봇) |
|-----------|---------------------|
| `mobile_robot/params/nav2_params.yaml` | `~/pinky_pro/src/pinky_pro/pinky_navigation/params/nav2_params.yaml` |
| `mobile_robot/params/mapper_params.yaml` | `~/pinky_pro/src/pinky_pro/pinky_navigation/params/mapper_params.yaml` |

---

## 설정 파일

### 네트워크 설정 (`fms/config/network_config.yaml`)

Closed Network 환경의 로봇 IP 주소 및 연결 설정:

```yaml
# Master PC
master:
  host: "192.168.1.3"
  tcp_port: 9000

# Mobile Robots
mobile_robots:
  pinky_b4bc:
    ip_address: "192.168.1.7"
    enabled: true
  pinky_e2a8:
    ip_address: "192.168.1.6"
    enabled: true
  # pinky_d29d: 보류중

# Cobot Arms
cobot_arms:
  jetcobot_aa1f:
    ip_address: "192.168.1.4"
  jetcobot_aa85:
    ip_address: "192.168.0.59"
```

### FMS 설정 (`fms/config/fms_config.yaml`)

- **로봇 설정**: 로봇 ID, 네임스페이스, 주차 위치
- **맵 위치**: pickup_spot, table1-8, parking spots 좌표
- **존 설정**: 충돌 방지를 위한 zone 정의
- **파라미터**: 배터리 임계값, 목표 도달 거리 등

**TODO**: 실제 맵 측량 후 좌표 값을 보정해야 합니다.

### Main Server 설정

`app/backend/main_server/main_server_node.py`에서 다음 항목 설정:

```python
db_config = {
    'db_host': 'localhost',  # TODO: DB 서버 IP
    'db_port': 5432,
    'db_name': 'kitchmatic',
    'db_user': 'kitchmatic_user',
    'db_password': 'your_password_here'  # TODO: 비밀번호
}

tcp_config = {
    'host': '0.0.0.0',
    'port': 9999  # TODO: 필요시 포트 변경
}
```

## 메시지 흐름

### 1. 주문 생성 (Kiosk → Main Server → FMS)

```
Kiosk (TCP)
  └─► Main Server: order_request
        └─► Database: CREATE order
        └─► FMS (ROS): /fms/order_request
              └─► TaskManager: create_task()
              └─► FleetController: assign_robot()
              └─► Robot: navigate_to_pose(pickup_spot)
```

### 2. 조리 및 로딩 (Main Server → Robot Arm)

```
Main Server (ROS)
  └─► Robot Arm: /robot_arm/cooking_order
        └─► Cooking process...
        └─► Main Server: /robot_arm/loading_complete
              └─► Database: UPDATE order status to READY
```

### 3. 배달 (FMS → Robot → Kiosk)

```
FMS
  └─► Robot: navigate_to_pose(table_X)
        └─► Robot arrives at table
        └─► Customer receives food
        └─► Kiosk (TCP): delivery_complete
              └─► Main Server: UPDATE order status to COMPLETED
              └─► FMS (ROS): /fms/delivery_complete
                    └─► Robot: navigate_to_pose(parking_spot)
```

## ROS 2 Topics

### Main Server가 발행하는 Topics

- `/fms/order_request` (OrderRequest): FMS에 새 주문 전달
- `/robot_arm/cooking_order` (CookingOrder): 로봇팔에 조리 요청
- `/fms/delivery_complete` (DeliveryComplete): FMS에 배달 완료 알림

### Main Server가 구독하는 Topics

- `/robot_arm/loading_complete` (LoadingComplete): 로봇팔에서 조리 완료 신호
- `/fms/fleet_status` (FleetStatus): FMS에서 Fleet 상태 업데이트

### FMS가 발행하는 Topics

- `/fms/fleet_status` (FleetStatus): Fleet 전체 상태 (1Hz)

### FMS가 구독하는 Topics

- `/fms/order_request` (OrderRequest): Main Server에서 주문 수신
- `/fms/delivery_complete` (DeliveryComplete): Main Server에서 배달 완료 수신
- `/{namespace}/pose` (Pose): 각 로봇의 현재 위치
- `/{namespace}/battery/voltage` (Float32): 배터리 전압
- `/{namespace}/battery/present` (Bool): 배터리 연결 상태

### FMS가 사용하는 Action

- `/{namespace}/navigate_to_pose` (NavigateToPose): 로봇 경로 계획 및 이동

## TCP 메시지 프로토콜

### 키오스크 → Main Server

```json
{
  "type": "order_request",
  "data": {
    "table_number": "T01",
    "menu_id": "M001",
    "quantity": 1,
    "sauce_type": "mayo",
    "voice_order": false
  }
}
```

### Main Server → 키오스크/Admin GUI

```json
{
  "type": "order_status_update",
  "data": {
    "order_id": "uuid-string",
    "status": "COOKING",
    "table_number": "T01",
    "timestamp": "2026-02-23T12:00:00"
  }
}
```

자세한 TCP 메시지 타입은 `app/backend/main_server/tcp_server.py` 참조

## 트러블슈팅

### 1. WiFi kitchmatics에 연결되지 않음

```bash
# 현재 WiFi 확인
iwgetid -r

# 사용 가능한 네트워크 확인
nmcli device wifi list

# kitchmatics에 연결
nmcli device wifi connect kitchmatics password "YOUR_PASSWORD"
```

### 2. 로봇에 SSH 연결 실패

```bash
# 로봇 IP에 ping 테스트
ping 192.168.1.7

# SSH 연결 테스트
ssh -v pinky@192.168.1.7

# SSH 키 설정 (비밀번호 없이 접속)
ssh-keygen -t rsa
ssh-copy-id pinky@192.168.1.7
```

### 3. FMS TCP 서버 연결 실패

```bash
# 포트 9000이 사용 중인지 확인
sudo lsof -i :9000

# 방화벽 확인
sudo ufw status

# 포트 열기
sudo ufw allow 9000/tcp
```

### 4. Main Server가 데이터베이스에 연결 실패

```bash
# PostgreSQL 상태 확인
sudo systemctl status postgresql

# 데이터베이스 연결 테스트
psql -U kitchmatic_user -d kitchmatic -c "SELECT 1;"
```

### 5. FMS가 로봇 Topics을 찾지 못함

```bash
# 로봇 네임스페이스 확인
ros2 node list | grep pinky

# Topics 확인
ros2 topic list | grep "/pinky"

# Nav2가 실행 중인지 확인
ros2 action list | grep navigate_to_pose
```

### 6. 로봇이 목표 지점에 도달하지 못함

- `fms/config/fms_config.yaml`에서 위치 좌표 확인
- Nav2 설정 확인 (`inflation_radius`, `goal_tolerance` 등)
- AMCL 초기화가 제대로 되었는지 확인

### 7. 파일 동기화 실패

```bash
# rsync 설치 확인
which rsync

# SSH 연결 확인
python3 fms/scripts/robot_file_sync.py --robot pinky_b4bc --check

# 파일 권한 확인
ls -la mobile_robot/params/
```

## 개발 팁

### 로그 레벨 조정

```python
# main_server_node.py 또는 fms_node.py에서
logging.basicConfig(level=logging.DEBUG)  # 상세 로그
logging.basicConfig(level=logging.INFO)   # 일반 로그
```

### 데이터베이스 직접 쿼리

```bash
psql -U kitchmatic_user -d kitchmatic

# 주문 조회
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;

# 로봇 상태 조회
SELECT name, type, status, last_heartbeat FROM robots;
```

### ROS 2 메시지 모니터링

```bash
# Fleet 상태 모니터링
ros2 topic echo /fms/fleet_status

# 주문 요청 모니터링
ros2 topic echo /fms/order_request
```

## 프로젝트 구조

```
roscamp-repo-1/
├── fms/                              # Fleet Management System
│   ├── config/
│   │   ├── fms_config.yaml           # 로봇 위치, 존 설정
│   │   └── network_config.yaml       # Closed Network IP 설정
│   ├── fms/
│   │   ├── fms_node.py               # FMS ROS 2 노드
│   │   ├── fms_tcp_node.py           # FMS TCP 통합 노드
│   │   ├── tcp_communication.py      # TCP Server/Client 모듈
│   │   ├── fleet_controller.py       # Fleet 상태 관리
│   │   ├── task_manager.py           # 작업 큐 관리
│   │   └── zone_manager.py           # 충돌 방지
│   ├── scripts/
│   │   ├── start_fms_server.sh       # FMS 서버 시작 스크립트
│   │   ├── robot_client.py           # 로봇용 TCP 클라이언트
│   │   └── robot_file_sync.py        # 파일 동기화 스크립트
│   └── launch/
│       └── fms_closed_network.launch.py
│
├── mobile_robot/                     # Mobile Robot 설정
│   ├── launch/
│   │   └── bringup_launch.py         # 다중 로봇 네비게이션 launch (RewrittenYaml)
│   ├── params/
│   │   └── nav2_params.yaml          # Navigation2 파라미터
│   ├── maps/
│   │   ├── real.yaml                 # 실제 맵 설정
│   │   └── real.png                  # 실제 맵 이미지
│   └── config/
│       ├── pinky_b4bc.yaml           # 로봇별 설정 (192.168.1.7)
│       ├── pinky_e2a8.yaml           # 로봇별 설정 (192.168.1.6)
│       └── pinky_d29d.yaml           # 로봇별 설정 (192.168.1.11)
│
├── app/
│   ├── backend/                      # Main Server
│   │   └── main_server/
│   └── gui/
│       ├── admin_gui/                # 관리자 GUI
│       │   └── src/
│       │       ├── ui_fleet_monitor.py  # Fleet 모니터링 화면
│       │       └── fleet_client.py      # TCP 클라이언트
│       └── common/
│           └── config.py             # 네트워크 설정 로더
│
├── fleet_interfaces/                 # ROS 2 메시지 정의
├── database/                         # PostgreSQL 스키마
└── README.md
```

## 라이선스

MIT License

## 작성자

Kitchmatic Team
