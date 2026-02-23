# Kitchmatic Fleet Management System

Kitchmatic 프로젝트의 Fleet Management System (FMS) 및 Main Server 구현입니다.

## 시스템 아키텍처

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Kiosks    │◄──TCP──►│ Main Server  │◄──ROS──►│     FMS     │
│ (8 tables)  │         │  (Backend)   │         │   (Fleet)   │
└─────────────┘         └──────┬───────┘         └──────┬──────┘
                               │                        │
                               │                        │
                        ┌──────▼───────┐         ┌──────▼──────┐
                        │ PostgreSQL   │         │ 3x Serving  │
                        │   Database   │         │   Robots    │
                        └──────────────┘         └─────────────┘
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

### 터미널 1: Main Server 실행

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

### 터미널 2: FMS 실행

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

### 터미널 3: 로봇 네임스페이스 확인

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

## 설정 파일

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

### 1. Main Server가 데이터베이스에 연결 실패

```bash
# PostgreSQL 상태 확인
sudo systemctl status postgresql

# 데이터베이스 연결 테스트
psql -U kitchmatic_user -d kitchmatic -c "SELECT 1;"
```

### 2. FMS가 로봇 Topics을 찾지 못함

```bash
# 로봇 네임스페이스 확인
ros2 node list | grep pinky

# Topics 확인
ros2 topic list | grep "/pinky"

# Nav2가 실행 중인지 확인
ros2 action list | grep navigate_to_pose
```

### 3. 로봇이 목표 지점에 도달하지 못함

- `fms/config/fms_config.yaml`에서 위치 좌표 확인
- Nav2 설정 확인 (`inflation_radius`, `goal_tolerance` 등)
- AMCL 초기화가 제대로 되었는지 확인

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

## 라이선스

MIT License

## 작성자

Kitchmatic Team
