# Kitchmatics

**ROS 2 기반 자율주행 서빙로봇 + 로봇팔 협업 스마트 키친 시스템**

Kitchmatics는 다수의 자율주행 서빙로봇(Pinky Pro 기반)과 로봇팔(Jetcobot)이 협업하여 샌드위치 주문 접수부터 조리, 품질 검사, 서빙까지 전 과정을 자동화하는 Fleet Management System입니다.

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Main PC (Domain 25)                         │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ FMS Node │  │  Sandwich    │  │   Domain     │  │  Database   │  │
│  │ (Fleet   │  │  Coordinator │  │   Bridge     │  │ (PostgreSQL)│  │
│  │ Manager) │  │              │  │  (8 bridges) │  │             │  │
│  └────┬─────┘  └──────┬───────┘  └──────┬───────┘  └─────────────┘  │
│       │               │                 │                           │
│  ┌────┴────┐   ┌──────┴───────┐   ┌─────┴──────┐                   │
│  │GUI TCP  │   │ AI Servers   │   │  Nav2      │                   │
│  │Server   │   │ (YOLO/Voice) │   │  Actions   │                   │
│  └─────────┘   └──────────────┘   └─────┬──────┘                   │
└─────────────────────────────────────────┼───────────────────────────┘
                                          │ Domain Bridge
          ┌───────────────────────────────┼───────────────────────┐
          │                               │                       │
  ┌───────┴────────┐  ┌─────────┴────────┐  ┌───────┴────────┐
  │  Pinky1        │  │  Pinky2          │  │  Pinky3        │
  │  (Domain 11)   │  │  (Domain 12)     │  │  (Domain 13)   │
  │  192.168.1.7   │  │  192.168.1.6     │  │  192.168.1.11  │
  └────────────────┘  └──────────────────┘  └────────────────┘

  ┌────────────────┐  ┌──────────────────┐
  │  Arm A         │  │  Arm B           │
  │  (샌드위치 제조)│  │  (소스 도포)      │
  │  192.168.1.4   │  │  192.168.1.10    │
  └────────────────┘  └──────────────────┘
```

---

## 프로젝트 구조

```
roscamp-repo-1/
├── fms/                          # Fleet Management System (핵심)
│   ├── fms/
│   │   ├── fms_node.py           # 메인 FMS 노드
│   │   ├── task_manager.py       # 주문 큐 및 태스크 관리
│   │   ├── fleet_controller.py   # 로봇 플릿 상태/제어
│   │   ├── zone_manager.py       # 충돌 회피 및 구역 조정
│   │   ├── task_scheduler.py     # 태스크 스케줄링, 픽업 슬롯 관리
│   │   ├── path_planner.py       # 경로 계획 (Navigation Graph)
│   │   ├── collision_avoidance.py# 다중 로봇 충돌 회피
│   │   ├── error_detector.py     # 에러 감지
│   │   ├── error_recovery.py     # 에러 복구 핸들러
│   │   ├── order_handler.py      # 주문 처리
│   │   └── gui_tcp_server.py     # GUI 연동 TCP 서버
│   ├── config/
│   │   ├── fms_config.yaml       # 로봇/포지션/존 설정
│   │   ├── navigation_graph.yaml # 경로 그래프 정의
│   │   ├── bridge_*.yaml         # Domain Bridge 설정 (8개)
│   │   └── network_config.yaml   # 네트워크 설정
│   └── launch/
│       ├── fms_launch.py         # FMS 런치 파일
│       └── domain_bridges.launch.py
│
├── fleet_interfaces/             # ROS 2 커스텀 메시지 패키지
│   └── msg/
│       ├── OrderRequest.msg      # 주문 요청
│       ├── CookingOrder.msg      # 조리 명령
│       ├── RobotStatus.msg       # 로봇 상태
│       ├── FleetStatus.msg       # 플릿 전체 상태
│       ├── PickupArrival.msg     # 픽업 지점 도착
│       ├── LoadingComplete.msg   # 적재 완료
│       ├── TableArrival.msg      # 테이블 도착
│       ├── DeliveryComplete.msg  # 배달 완료
│       ├── PrecisionParked.msg   # 정밀 주차 완료
│       ├── ErrorAlert.msg        # 에러 알림
│       └── OperatorCommand.msg   # 운영자 명령
│
├── robot_arm/                    # 로봇팔 제어
│   ├── sandwich_arm_ws/          # Arm A: 샌드위치 조립 (Jetcobot)
│   │   └── src/mycobot_kitchen_nodes/
│   │       ├── arm_driver_node.py
│   │       ├── recipe_executor_node.py
│   │       ├── inventory_manager_node.py
│   │       ├── refill_executor_node.py
│   │       ├── cooking_interface_node.py
│   │       ├── fms_command_interface_node.py
│   │       └── bias_provider_node.py
│   ├── sauce_arm_ws/             # Arm B: 소스 도포
│   │   └── src/mycobot_sauce/
│   │       ├── arm_driver_node.py
│   │       ├── pour_sauce_node.py
│   │       ├── trash_or_delivery_node.py
│   │       └── bias_provider_node.py
│   └── image_streaming_server/   # 로봇팔 카메라 스트리밍
│
├── ai_server/                    # AI 처리 서버
│   ├── image_processing_server/  # YOLO 기반 품질 검사 (Flask)
│   │   └── app.py                # 이미지 분석 API
│   └── voice_processing_server/  # 음성 주문 처리 (FastAPI)
│       └── app/main.py           # STT/TTS/Agent API
│
├── database/                     # PostgreSQL 데이터베이스
│   ├── schema.sql                # 스키마 정의
│   ├── setup_database.sh         # 자동 설치 스크립트
│   ├── migrations/               # 마이그레이션 파일
│   └── db_server/                # REST API 서버
│
├── scripts/                      # 운영 스크립트
│   ├── start_fms.sh              # 전체 시스템 시작
│   ├── stop_fms.sh               # 전체 시스템 종료
│   ├── restart_fms.sh            # 시스템 재시작
│   ├── monitor_topics.sh         # 토픽 실시간 모니터링
│   ├── verify_system.sh          # 시스템 검증
│   └── setup_ssh_keys.sh         # SSH 키 설정
│
├── tests/                        # 테스트 스위트 (~155개 테스트)
│   ├── test_fms_unit.py          # 단위 테스트
│   ├── test_multi_robot.py       # 다중 로봇 통합 테스트
│   └── test_e2e_skip_mode.py     # E2E 테스트
│
└── presentation/                 # 발표 자료
```

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| **로봇 미들웨어** | ROS 2 Jazzy |
| **자율주행** | Nav2 (NavigateToPose, FollowWaypoints, AMCL) |
| **다중 도메인 통신** | Domain Bridge (ROS_DOMAIN_ID 격리) |
| **로봇팔** | Jetcobot (Jetcobot SDK) |
| **AI - 비전** | YOLOv8 (품질 검사, 식재료 인식) |
| **AI - 음성** | OpenAI API (STT/TTS/Function Calling/Agent) |
| **백엔드** | Flask (이미지 서버), FastAPI (음성 서버) |
| **데이터베이스** | PostgreSQL |
| **언어** | Python 3.10+ |
| **빌드** | colcon, ament_python, ament_cmake |
| **테스트** | pytest, pytest-cov |
| **모바일 로봇** | Pinky Pro 기반 PinkyPro |

---

## 주문-배달 흐름

```
1. 주문 접수 (GUI/음성)
      │
2. FMS: 주문 큐에 등록 (TaskManager)
      │
3. FMS: 가용 로봇 선택 (FleetController)
      │
4. FMS: 로봇팔에 조리 명령 (/cooking/order)
      │
5. Arm A: 샌드위치 조립 → Arm B: 소스 도포
      │
6. AI 서버: YOLO 품질 검사
      │
7. 서빙로봇: pickup_spot으로 이동 (Nav2)
      │
8. 로봇팔: 음식 적재 → LoadingComplete 발행
      │
9. 서빙로봇: 테이블로 이동 (경로 계획 + 충돌 회피)
      │
10. 고객 수령 → DeliveryComplete
      │
11. 서빙로봇: 주차 위치로 복귀
```

---

## ROS 2 통신 구조

### Domain ID 구성

| Domain ID | 장치 | 설명 |
|-----------|------|------|
| 11 | Pinky1 | 서빙로봇 1 (192.168.1.7) |
| 12 | Pinky2 | 서빙로봇 2 (192.168.1.6) |
| 13 | Pinky3 | 서빙로봇 3 (192.168.1.11) |
| 20 | Arm A | Sandwich Arm (192.168.1.4) |
| 21 | Arm B | Sauce Arm (192.168.1.10) |
| 25 | Main PC | FMS, Coordinator, Domain Bridge |

### 주요 토픽

| 토픽 | 메시지 타입 | 방향 | 설명 |
|------|------------|------|------|
| `/fms/order_request` | `OrderRequest` | GUI -> FMS | 신규 주문 요청 |
| `/fms/fleet_status` | `FleetStatus` | FMS -> 전체 | 플릿 상태 브로드캐스트 |
| `/fms/pickup_arrival` | `PickupArrival` | FMS -> Arm | 로봇 픽업 지점 도착 알림 |
| `/fms/delivery_complete` | `DeliveryComplete` | Kiosk -> FMS | 배달 완료 확인 |
| `/cooking/order` | `CookingOrder` | FMS -> Arm | 조리 명령 |
| `/cooking/loading_complete` | `LoadingComplete` | Arm -> FMS | 음식 적재 완료 |
| `/arm_a/cmd`, `/arm_b/cmd` | `String` | FMS -> Arm | 로봇팔 직접 제어 |
| `/arm_a/status`, `/arm_b/status` | `String` | Arm -> FMS | 로봇팔 상태 보고 |
| `/pinkyN/amcl_pose` | `PoseWithCovarianceStamped` | Robot -> FMS | 로봇 위치 (AMCL) |
| `/pinkyN/odom` | `Odometry` | Robot -> FMS | 로봇 오도메트리 |
| `/pinkyN/cmd_vel` | `Twist` | FMS -> Robot | 속도 명령 |

### 커스텀 메시지 (fleet_interfaces)

```
OrderRequest    : order_id, menu_id, table_number, quantity, sauce_type, voice_order
CookingOrder    : order_id, menu_id, quantity, sauce_type, assigned_robot_id
RobotStatus     : robot_id, status, current_pose, battery_voltage
FleetStatus     : robots[], pending_orders, active_orders
PickupArrival   : (로봇이 픽업 지점 도착 시)
LoadingComplete : order_id, success, robot_id, message
DeliveryComplete: order_id, table_number
PrecisionParked : (정밀 주차 완료 시)
TableArrival    : (테이블 도착 시)
ErrorAlert      : (에러 발생 시)
OperatorCommand : (운영자 수동 명령)
```

---

## 설치 및 실행

### 사전 요구사항

- Ubuntu 24.04
- ROS 2 Jazzy
- Python 3.10+
- PostgreSQL 15+
- Nav2
- domain_bridge 패키지

### 1. 빌드

```bash
cd ~/kitchmatics/roscamp-repo-1

# ROS 2 환경 설정
source /opt/ros/jazzy/setup.bash

# 빌드
colcon build --symlink-install
source install/setup.bash
```

### 2. 데이터베이스 설정

```bash
cd database
./setup_database.sh
```

### 3. AI 서버 실행

```bash
# 이미지 처리 서버 (YOLO)
cd ai_server/image_processing_server
pip install -r requirements.txt
python app.py

# 음성 처리 서버
cd ai_server/voice_processing_server
pip install -r requirements.txt
python run.py
```

### 4. FMS 시스템 시작

```bash
# 전체 시스템 한 번에 시작 (Domain Bridge + FMS + Coordinator)
./scripts/start_fms.sh

# 또는 개별 실행
export ROS_DOMAIN_ID=25
ros2 launch fms fms_launch.py
```

### 5. Sandwich Coordinator 실행

FMS와 별도로 로봇팔 조율을 위한 Sandwich Coordinator를 실행해야 합니다.

```bash
# 방법 1: 실행 스크립트 사용 (환경 자동 설정)
cd fms/coordinator_Ws
./run_coordinator.sh

# 방법 2: Launch 파일로 직접 실행 (Domain Bridge 포함)
export ROS_DOMAIN_ID=25
ros2 launch sandwich_coordinator coordinator_all.launch.py test_mode:=false

# 테스트 모드 (하드코딩 주문으로 로봇팔 단독 테스트)
ros2 launch sandwich_coordinator coordinator_all.launch.py test_mode:=true test_recipe:=ham_cheese test_sauce:=mustard
```

> Coordinator는 Domain 25에서 동작하며, 내부적으로 Arm A(Domain 20)와 Arm B(Domain 21)로의 Domain Bridge를 자동으로 실행합니다.

### 6. 시스템 종료

```bash
./scripts/stop_fms.sh
```

### 7. 시스템 검증

```bash
# 모든 로봇/노드 연결 상태 확인
./scripts/verify_system.sh

# 실시간 토픽 모니터링
./scripts/monitor_topics.sh
```

---

## 테스트

```bash
# 전체 테스트 실행 (~155개)
pytest tests/ -v

# 단위 테스트
pytest tests/test_fms_unit.py -v

# 다중 로봇 통합 테스트
pytest tests/test_multi_robot.py -v

# E2E 테스트 (skip mode)
pytest tests/test_e2e_skip_mode.py -v

# 커버리지 리포트
pytest tests/ --cov=fms --cov-report=html -v
```

### Skip Mode (로봇팔 없이 테스트)

로봇팔 연결 없이 서빙로봇 동작만 테스트할 수 있습니다:

```bash
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
```

---

## 데이터베이스 스키마

| 테이블 | 설명 |
|--------|------|
| `menus` | 메뉴 정보 (샌드위치 종류) |
| `ingredients` | 식재료 마스터 |
| `recipes` / `recipe_steps` | 레시피 및 조리 단계 |
| `inventory` | 재고 현황 (창고/조리대) |
| `robots` | 로봇 목록 (서빙봇 3대 + 로봇팔 2대) |
| `orders` | 주문 내역 및 상태 관리 |
| `quality_check_results` | YOLO 품질 검사 결과 |
| `inventory_transactions` | 재고 변동 이력 |
| `fms_navigation_states` | 로봇 내비게이션 상태 추적 |
| `fms_event_log` | 이벤트 감사 로그 |

### 주문 상태 흐름

```
PENDING -> ORDERED -> AT_POINT13 -> PRECISION_PARKING -> LOADING -> LOADED -> DELIVERING -> DELIVERED -> COMPLETED -> RETURNED
```

---

## 네트워크 구성

```
192.168.1.4   - Arm A (샌드위치 제조)
192.168.1.6   - Pinky2 (서빙로봇)
192.168.1.7   - Pinky1 (서빙로봇)
192.168.1.10  - Arm B (소스 도포)
192.168.1.11  - Pinky3 (서빙로봇)
Main PC       - FMS, Domain Bridge, Coordinator
```

---

## 맵 구성

- 맵 크기: 410x210px (0.005m/pixel)
- 8개 테이블 (table1~table8)
- 1개 픽업 지점 (pickup_spot)
- 3개 로봇 주차/충전 위치
- 13개 내비게이션 웨이포인트 (그리드 기반 경로 계획)
- 충돌 회피 존 설정 (테이블, 주차, 웨이포인트별)

---

## 라이선스

MIT License

---

## 팀

Kitchmatic Team (team@kitchmatic.com)
