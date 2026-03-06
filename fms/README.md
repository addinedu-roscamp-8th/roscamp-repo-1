# FMS (Fleet Management System)

Kitchmatics 서빙 로봇 함대 관리 시스템. 3대의 서빙 로봇(pinky1, pinky2, pinky3)을 중앙에서 관리하며, 주문 접수부터 음식 배달, 복귀까지의 전체 워크플로우를 자동으로 처리한다.

---

## 목차

1. [시스템 개요](#1-시스템-개요)
2. [아키텍처](#2-아키텍처)
3. [모듈 상세 설명](#3-모듈-상세-설명)
4. [설정 파일](#4-설정-파일)
5. [ROS2 토픽/서비스 인터페이스](#5-ros2-토픽서비스-인터페이스)
6. [Domain Bridge 구조](#6-domain-bridge-구조)
7. [주문 처리 워크플로우](#7-주문-처리-워크플로우)
8. [실행 방법](#8-실행-방법)
9. [테스트 방법](#9-테스트-방법)
10. [트러블슈팅](#10-트러블슈팅)

---

## 1. 시스템 개요

### 목적

FMS는 레스토랑 환경에서 다수의 서빙 로봇을 조율하여 음식 배달을 자동화하는 중앙 관제 시스템이다. 고객이 키오스크(GUI)에서 주문하면 로봇팔이 음식을 준비하고, 서빙 로봇이 해당 테이블까지 자율 배달한다.

### 핵심 기능

- **다중 로봇 관제**: 3대의 서빙 로봇(pinky1/2/3)의 상태 추적, 태스크 할당, 네비게이션 제어
- **주문 처리 파이프라인**: GUI 주문 접수 -> 로봇팔 조리 명령 -> 서빙 로봇 배달 -> 복귀
- **충돌 회피**: 다중 로봇 경로 충돌 감지 및 회피, Zone 기반 접근 제어
- **Pickup Slot 관리**: 한 번에 한 대만 pickup_spot 접근 가능, FIFO 대기열 관리
- **경로 계획**: Navigation Graph 기반 Dijkstra 최단경로 탐색 및 Waypoint 기반 네비게이션
- **에러 감지 및 복구**: 통신 손실, 배터리 부족, 네비게이션 실패 감지와 운영자 명령 기반 복구
- **GUI 통신**: TCP 소켓 서버(Port 9000)를 통한 주문 수신 및 배달 알림 푸시

### 기술 스택

| 항목 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| 프레임워크 | ROS2 Humble/Jazzy |
| 네비게이션 | Nav2 (FollowWaypoints, NavigateToPose) |
| 위치 추정 | AMCL |
| GUI 통신 | TCP Socket (4-byte header + JSON) |
| 크로스 도메인 | Domain Bridge |
| 아키텍처 | Clean Architecture + SOLID |

### 네트워크 토폴로지

```
kitchmatics WiFi (192.168.1.x)

  Master PC (192.168.1.3)
  FMS Node (Domain 25) + Sandwich Coordinator (Domain 25)
       |
       +--- Domain Bridge ---+--- pinky1 (192.168.1.7,  Domain 11)
       |                      +--- pinky2 (192.168.1.6,  Domain 12)
       |                      +--- pinky3 (192.168.1.11, Domain 13)
       |
       +--- Domain Bridge ---+--- Arm A: Sandwich Arm (192.168.1.4,  Domain 20)
                              +--- Arm B: Sauce Arm    (192.168.1.10, Domain 21)

  Customer GUI (Tablet) --- TCP:9000 --- FMS Node
```

---

## 2. 아키텍처

### 2.1 레이어 구조 (Clean Architecture)

```
+-----------------------------------------------------------+
|  Presentation Layer (fms_node.py)                         |
|  - ROS2 노드 초기화, 콜백 등록, 컴포넌트 조정            |
+--------------------+--------------------------------------+
                     |
+--------------------v-----------------+  +-----------------+
|  Application Layer                   |  | Infrastructure  |
|  (order_handler.py)                  |  | Layer           |
|  - 주문 워크플로우 오케스트레이션     |  | (gui_tcp_server)|
|  - 비즈니스 로직 (상태 머신)          |  | - TCP 서버      |
|  - Dependency Inversion (callbacks)  |  | - 메시지 라우팅  |
+--------------------+-----------------+  +-----------------+
                     |
+--------------------v--------------------------------------+
|  Domain Layer                                             |
|  - TaskManager, FleetController, ZoneManager              |
|  - TaskScheduler, PathPlanner, CollisionAvoidance         |
|  - ErrorDetector, ErrorRecoveryHandler                    |
+-----------------------------------------------------------+
```

### 2.2 핵심 컴포넌트 관계

```
                    FMSNode (fms_node.py)
                         |
         +-------+-------+-------+-------+-------+
         |       |       |       |       |       |
   TaskManager  Fleet  Zone   Task   Path   Collision
              Controller Manager Scheduler Planner Avoidance
                                  |
                           PickupSlotManager

   + ErrorDetector + ErrorRecoveryHandler
   + OrderHandler + GUITCPServer
```

### 2.3 데이터 흐름

```
Customer GUI --TCP:9000--> GUITCPServer --> OrderHandler --> FMSNode
                                                              |
                  +-------------------------------------------+
                  |                    |                       |
            /cooking/command     Navigation Action      Fleet Status
            /cooking/order       (FollowWaypoints)      Publishing
                  |                    |                       |
            Robot Arm            Serving Robots          /fms/fleet_status
            (Domain 20/21)       (Domain 11/12/13)
```

---

## 3. 모듈 상세 설명

### 3.1 fms_node.py -- 메인 FMS 노드

FMS의 진입점이자 전체 시스템을 조율하는 ROS2 노드. 모든 컴포넌트를 초기화하고, ROS2 토픽/액션 구독/발행, 타이머 기반 주기적 처리를 수행한다.

**주요 기능:**
- 핵심 컴포넌트 초기화 (TaskManager, FleetController, ZoneManager, TaskScheduler, PathPlanner, CollisionAvoidance, ErrorDetector, ErrorRecoveryHandler, OrderHandler, GUITCPServer)
- 로봇별 NavigateToPose, FollowWaypoints 액션 클라이언트 생성
- 로봇별 amcl_pose, battery 토픽 구독 (Domain Bridge 경유)
- 주기적 타이머: Fleet Status 발행(1Hz), Task 할당(2Hz), Pickup Queue 처리(10Hz), 예약 정리(1Hz), 에러 모니터링(2Hz), 충돌 검사(5Hz)
- Initial Pose 자동 설정 (AMCL 위치 추정 초기화)
- skip_robot_arm 모드 (로봇팔 없이 테스트용)

**ROS2 파라미터:**
- `skip_robot_arm` (bool, 기본값: false): 로봇팔 스킵 모드. true이면 pickup_spot 도착 후 자동으로 테이블 이동
- `auto_set_initial_pose` (bool, 기본값: true): 시작 시 모든 로봇의 AMCL 초기 위치 자동 설정

### 3.2 fleet_controller.py -- 플릿 컨트롤러

3대의 서빙 로봇 함대 상태를 관리한다.

**RobotState 클래스:**
- 상태: `IDLE`, `MOVING_TO_PICKUP`, `LOADED`, `MOVING_TO_TABLE`, `DELIVERING`, `RETURNING`, `ERROR`
- 속성: robot_id, domain_id, current_pose, battery_voltage, battery_present, current_task_id, target_location
- 가용성 판단: IDLE 상태 + 태스크 미할당 + 10초 이내 POSE 수신 + 배터리 정상

**FleetController 클래스:**
- 로봇 상태 추적 및 업데이트 (pose, battery, status)
- 최적 로봇 선택 (현재 FIFO 기반, 향후 거리 기반 선택 확장 가능)
- 상태 전환 관리: assign -> reached_pickup -> start_delivery -> reached_table -> complete_delivery -> returned_home

### 3.3 task_manager.py -- 태스크 매니저

주문 기반 배달 태스크의 생성, 할당, 상태 추적을 담당한다.

**Task 클래스:**
- 속성: task_id(UUID), order_id, menu_id, table_number, quantity, sauce_type, voice_order
- 상태: `PENDING` -> `ASSIGNED` -> `IN_PROGRESS` -> `COMPLETED` / `FAILED`
- 실패 시 대기열 앞으로 재투입 (자동 재시도)

**TaskManager 클래스:**
- pending_tasks (deque): FIFO 대기열
- assigned_tasks (dict): 진행 중 태스크
- completed_tasks (list): 완료 이력
- task_lookup (dict): order_id -> task_id 빠른 검색

### 3.4 task_scheduler.py -- 태스크 스케줄러

다중 로봇 환경에서의 태스크 할당 및 Pickup Spot 접근 제어를 담당한다.

**TaskState (Enum):**
```
PENDING -> ASSIGNED -> MOVING_TO_PICKUP -> WAITING_FOR_PICKUP -> AT_PICKUP -> LOADED -> MOVING_TO_TABLE -> AT_TABLE -> COMPLETED
```

**PickupSlotManager:**
- pickup_spot에 한 번에 1대의 로봇만 접근 가능
- FIFO 대기열로 접근 순서 관리
- 대기 위치: 1번째 대기 로봇은 point13, 이후 로봇은 point2/point3 또는 parking spot
- 타임아웃(60초) 초과 시 강제 해제
- 위치 변경 콜백으로 대기 로봇 자동 이동

**TaskScheduler:**
- 태스크 대기열 관리 및 로봇 할당
- Pickup Slot 접근 요청/해제
- 로봇 에러 발생 시 자동 정리 (슬롯 해제, 큐 제거, 태스크 재투입)

### 3.5 order_handler.py -- 주문 핸들러

Application Layer. GUI로부터의 주문을 받아 전체 배달 워크플로우를 오케스트레이션한다.

**OrderWorkflow 상태 머신:**
```
RECEIVED -> COOKING -> LOADING -> LOADED -> DELIVERING -> ARRIVED -> COMPLETED
                                                                        |
QUEUED (가용 로봇 없을 때)                                    FAILED (에러 발생)
```

**핵심 기능:**
- 주문 대기열 관리: 가용 로봇이 없으면 FIFO 큐에 대기
- 자동 디스패치: 배달 완료 후 대기 주문이 있으면 home 복귀 없이 바로 다음 주문 처리
- GUI 알림: 테이블 도착 시 push notification, 큐 위치 변경 시 알림
- Dependency Inversion: 콜백 기반으로 인프라 레이어와 분리

### 3.6 path_planner.py -- 경로 플래너

navigation_graph.yaml 기반의 waypoint 경로 계획을 수행한다.

**NavigationGraph:**
- YAML에서 waypoint(vertex)와 lane(edge) 로드
- Dijkstra 알고리즘으로 최단 경로 탐색
- blocked_nodes를 회피하는 대체 경로 탐색 지원
- 가장 가까운 waypoint 검색

**PathPlanner:**
- 로봇별 경로 관리 (계획, 진행 추적, 완료 확인)
- 충돌 회피를 위한 blocked nodes 기반 대체 경로 계획
- 다른 로봇들이 점유한 노드 조회 기능

### 3.7 collision_avoidance.py -- 충돌 회피 컨트롤러

다중 로봇 환경에서 경로 충돌을 감지하고 회피하는 시스템.

**충돌 유형 (ConflictType):**
- `NODE_OCCUPIED`: 노드가 다른 로봇에 의해 점유됨
- `NODE_RESERVED`: 노드가 다른 로봇에 의해 예약됨
- `PATH_CROSSING`: 경로 교차 발생
- `PATH_BLOCKED`: 경로가 완전히 차단됨
- `PICKUP_SLOT_OCCUPIED`: 픽업 슬롯 점유됨

**핵심 기능:**
- 경로 계획 시 다른 로봇의 현재 위치/경로와 비교하여 충돌 감지
- Dijkstra 기반 대체 경로 탐색
- 대기 위치 결정 및 Pickup 대기열 연동
- 로봇 위치 업데이트 시 통과한 노드 실시간 해제
- 대기 중인 로봇의 재계획 트리거

### 3.8 zone_manager.py -- 구역 관리

Zone 기반 충돌 회피 및 공간 조정 시스템.

**Zone 상태:**
```
AVAILABLE -> RESERVED -> OCCUPIED -> AVAILABLE
                |
           EXPIRED (타임아웃)
```

**Zone 목록 (총 25개):**
- zone_pickup: 음식 적재 구역
- zone_table1 ~ zone_table8: 테이블 구역 (8개)
- zone_parking1 ~ zone_parking3: 주차 구역 (3개)
- zone_point1 ~ zone_point13: 웨이포인트 구역 (13개)

**핵심 기능:**
- 사전 예약 시스템: 로봇이 진입 전 zone을 미리 예약
- 자동 점유/해제: 로봇 pose 업데이트로 zone 진출입 자동 관리
- 경로 충돌 검사: 계획된 경로의 zone 충돌 사전 검증
- 예약 만료 자동 정리 (기본 30초 타임아웃)

### 3.9 error_detector.py -- 에러 감지

로봇 서빙 중 발생하는 다양한 에러를 감지하고 추적한다.

**에러 유형 (ErrorType):**
| 유형 | 설명 | 감지 조건 |
|------|------|----------|
| NAV_FAILED | 네비게이션 실패 | Action 상태 ABORTED/CANCELED |
| COMM_LOST | 통신 손실 | Heartbeat 타임아웃 (1시간) |
| LOW_BATTERY | 배터리 부족 | 전압 threshold 미만 |
| TIMEOUT | 태스크 타임아웃 | Pickup 60초, Delivery 120초 |
| OBSTACLE | 장애물 | 지속적 경로 차단 |

**핵심 기능:**
- Heartbeat 기반 통신 상태 모니터링 (AMCL pose 수신 기반)
- 에러 등록/해제 및 이력 관리
- COMM_LOST 자동 복구 (heartbeat 복원 시 에러 자동 클리어)

### 3.10 error_recovery.py -- 에러 복구

운영자 명령을 처리하고 복구 작업을 실행한다.

**운영자 명령 (OperatorCommand):**
| 명령 | 동작 |
|------|------|
| RETRY | 실패한 네비게이션 태스크 재시도 |
| RETURN_HOME | 로봇을 parking spot으로 강제 복귀 |
| EMERGENCY_STOP | 로봇 즉시 정지 |
| CLEAR_ERROR | 에러 상태 수동 클리어 |

- 콜백 기반 작업 실행 (명령별 핸들러 등록)
- 작업 이력 추적 및 통계

### 3.11 gui_tcp_server.py -- GUI TCP 서버

Customer GUI(키오스크/태블릿)와의 TCP 통신을 담당하는 인프라 레이어.

**프로토콜:** 4-byte big-endian 길이 헤더 + UTF-8 JSON 페이로드

**지원 메시지:**

| 방향 | 타입 | 설명 |
|------|------|------|
| GUI -> FMS | `new_order` | 새 주문 접수 |
| GUI -> FMS | `delivery_complete` | 수령 확인 |
| FMS -> GUI | `delivery_notification` | 테이블 도착 알림 (Push) |
| FMS -> GUI | `order_queued` | 주문 대기열 추가 알림 |
| FMS -> GUI | `order_processing` | 대기 주문 처리 시작 알림 |
| FMS -> GUI | `queue_position_updated` | 대기 순서 변경 알림 |

**기능:**
- 멀티스레드 클라이언트 처리 (1 thread per client)
- 요청-응답 패턴 및 브로드캐스트 푸시 알림
- 메시지 핸들러 등록 시스템 (확장 용이)

---

## 4. 설정 파일

### 4.1 fms_config.yaml

FMS 전체 설정 파일. 위치: `fms/config/fms_config.yaml`

```yaml
# 로봇 함대 설정
robots:
  - robot_id: "pinky1"
    domain_id: 11
    ip_address: "192.168.1.7"
    parking_spot: "pinky1_spot"
    enabled: true

# 맵 위치 (미터 단위)
positions:
  pickup_spot: {x: 0.47, y: 0.63, theta: 0.0}
  table1: {x: 1.785, y: 0.35, theta: 0.0}
  # ... table2~table8, pinky1~3_spot, point1~13

# Zone 설정 (충돌 회피)
zones:
  - id: "zone_pickup"
    center_x: 0.47
    center_y: 0.63
    radius: 0.10
  # ... 총 25개 zone

# 운영 파라미터
parameters:
  assignment_frequency: 2.0       # 태스크 할당 빈도 (Hz)
  goal_reached_threshold: 0.1     # 도착 판정 거리 (m)
  zone_reservation_timeout: 30.0  # Zone 예약 타임아웃 (초)
  auto_set_initial_pose: true     # 시작 시 AMCL 초기 위치 설정

# AMCL 초기 위치
initial_poses:
  pinky1: {x: 0.585, y: 0.085, theta: 0.0}
  pinky2: {x: 0.585, y: 0.255, theta: 0.0}
  pinky3: {x: 0.585, y: 0.915, theta: 0.0}
```

### 4.2 navigation_graph.yaml

Waypoint 기반 경로 계획을 위한 네비게이션 그래프. 위치: `fms/config/navigation_graph.yaml`

**구조:**
- `vertices`: 모든 waypoint 좌표 (pickup_spot, table1~8, point1~13, pinky1~3_spot)
- `lanes`: 양방향 경로 연결 (Grid 형태의 3x4 + 테이블/주차 연결)

**맵 레이아웃 (2m x 1m):**
```
y=0.85  point4 -------- point8 -------- point12
         |                |                |
y=0.65  point3 - table8  table7 - point7 - table4  table3 - point11
         |       |                |                  |        |
         |      point13           |                  |        |
y=0.63  pickup_spot               |                  |        |
         |                        |                  |        |
y=0.35  point2 - table6  table5 - point6 - table2  table1 - point10
         |                |                |                |
y=0.15  point1 -------- point5 -------- point9
         |
      pinky2_spot (y=0.255)
      pinky1_spot (y=0.085)
                                            pinky3_spot (y=0.915)

        x=0.585  x=0.78   x=0.865  x=1.235  x=1.325  x=1.415  x=1.785  x=1.85
```

### 4.3 Domain Bridge 설정 파일

각 로봇 및 로봇팔과의 크로스 도메인 통신을 위한 bridge 설정. 위치: `fms/config/bridge_*.yaml`

**파일 목록:**
- `bridge_pinky1.yaml` / `bridge_pinky1_reverse.yaml`: pinky1 (Domain 11 <-> Domain 25)
- `bridge_pinky2.yaml` / `bridge_pinky2_reverse.yaml`: pinky2 (Domain 12 <-> Domain 25)
- `bridge_pinky3.yaml` / `bridge_pinky3_reverse.yaml`: pinky3 (Domain 13 <-> Domain 25)
- `bridge_arm_a.yaml` / `bridge_arm_a_cmd.yaml`: Robot Arm A (Domain 20 <-> Domain 25)
- `bridge_arm_b.yaml` / `bridge_arm_b_cmd.yaml`: Robot Arm B (Domain 21 <-> Domain 25)

**브릿지 동작 (예: pinky1):**
- 로봇 -> FMS: `/amcl_pose` (Domain 11) -> `/pinky1/amcl_pose` (Domain 25)
- 로봇 -> FMS: `/battery/voltage` -> `/pinky1/battery/voltage`
- FMS -> 로봇: `/pinky1/navigate_to_pose` -> `/navigate_to_pose`
- FMS -> 로봇: `/pinky1/follow_waypoints` -> `/follow_waypoints`
- FMS -> 로봇: `/pinky1/initialpose` -> `/initialpose`

---

## 5. ROS2 토픽/서비스 인터페이스

### 5.1 FMS가 구독하는 토픽

| 토픽 | 메시지 타입 | 소스 | 설명 |
|------|------------|------|------|
| `/fms/order_request` | `OrderRequest` | Main Server | 주문 요청 (레거시) |
| `/fms/delivery_complete` | `DeliveryComplete` | Main Server | 배달 완료/복귀 명령 |
| `/fms/precision_parked` | `PrecisionParked` | Precision Control | 정밀 주차 완료 |
| `/cooking/loading_complete` | `LoadingComplete` | Robot Arm | 음식 적재 완료 |
| `/cooking/status` | `String` | Robot Arm | 조리 상태 |
| `/fms/operator_command` | `OperatorCommand` | Admin GUI | 운영자 복구 명령 |
| `/{robot_id}/amcl_pose` | `PoseWithCovarianceStamped` | Domain Bridge | 로봇 위치 |
| `/{robot_id}/battery/voltage` | `Float32` | Domain Bridge | 배터리 전압 |
| `/{robot_id}/battery/present` | `Bool` | Domain Bridge | 배터리 존재 |

### 5.2 FMS가 발행하는 토픽

| 토픽 | 메시지 타입 | 수신자 | 설명 |
|------|------------|--------|------|
| `/fms/fleet_status` | `FleetStatus` | 모니터링 | 함대 상태 (1Hz) |
| `/fms/pickup_arrival` | `PickupArrival` | Precision Control | Pickup 도착 알림 |
| `/fms/table_arrival` | `TableArrival` | Main Server | 테이블 도착 알림 |
| `/cooking/order` | `CookingOrder` | Robot Arm | 조리 주문 |
| `/cooking/command` | `String` (JSON) | Robot Arm | 조리 명령 |
| `/fms/error_alert` | `ErrorAlert` | Admin GUI | 에러 알림 |
| `/inventory/reset_all` | `Empty` | Robot Arm | 인벤토리 초기화 |
| `/{robot_id}/initialpose` | `PoseWithCovarianceStamped` | Domain Bridge | AMCL 초기 위치 |

### 5.3 FMS가 사용하는 액션

| 액션 | 메시지 타입 | 대상 | 설명 |
|------|------------|------|------|
| `/{robot_id}/navigate_to_pose` | `NavigateToPose` | Nav2 | 단일 목표점 네비게이션 |
| `/{robot_id}/follow_waypoints` | `FollowWaypoints` | Nav2 | 다중 waypoint 순차 네비게이션 (주 사용) |

### 5.4 커스텀 메시지 (fleet_interfaces)

| 메시지 | 필드 |
|--------|------|
| `OrderRequest` | order_id, menu_id, table_number, quantity, sauce_type, voice_order |
| `RobotStatus` | robot_id, status, current_pose, battery_voltage, battery_present, timestamp |
| `FleetStatus` | robots[], pending_orders, active_orders, timestamp |
| `DeliveryComplete` | order_id, table_number |
| `PickupArrival` | robot_id, order_id, current_pose, arrived_at |
| `TableArrival` | robot_id, order_id, table_number, current_pose, arrived_at |
| `PrecisionParked` | robot_id, order_id, success, message |
| `CookingOrder` | order_id, menu_id, quantity, sauce_type, assigned_robot_id |
| `LoadingComplete` | order_id, robot_id, success, message |
| `ErrorAlert` | (에러 정보) |
| `OperatorCommand` | (복구 명령) |

---

## 6. Domain Bridge 구조

### 6.1 개요

FMS(Domain 25)와 각 로봇(Domain 11/12/13), 로봇팔(Domain 20/21)이 서로 다른 ROS_DOMAIN_ID에서 동작하므로, Domain Bridge가 토픽/액션을 중계한다.

### 6.2 브릿지 방향

**Forward (로봇 -> FMS):**
- 로봇의 토픽을 FMS 도메인에서 로봇별 네임스페이스로 리맵
- 예: pinky1의 `/amcl_pose` (Domain 11) -> `/pinky1/amcl_pose` (Domain 25)

**Reverse (FMS -> 로봇):**
- FMS의 로봇별 네임스페이스 토픽/액션을 로봇 도메인의 글로벌 토픽으로 전달
- 예: `/pinky1/follow_waypoints` (Domain 25) -> `/follow_waypoints` (Domain 11)

### 6.3 Fallback 메커니즘

Domain Bridge 액션 서버가 응답하지 않을 경우 SSH를 통한 직접 명령 전송으로 폴백:
```
FMS -> SSH -> pinky@{robot_ip} -> ros2 action send_goal /follow_waypoints ...
```

---

## 7. 주문 처리 워크플로우

### 7.1 전체 흐름

```
1. [주문 접수] Customer GUI --TCP:9000--> FMS
       |
2. [로봇 배정] FleetController에서 IDLE 로봇 선택
       |          (가용 로봇 없으면 대기열에 추가)
       |
3. [조리 명령] FMS --/cooking/command--> Robot Arm
       |
4. [Pickup 이동] FMS --FollowWaypoints--> 서빙 로봇 -> pickup_spot
       |          (Pickup Slot 점유 불가 시 대기 zone으로 이동)
       |
5. [정밀 주차] Precision Control 팀에 의한 정밀 위치 조정
       |          (skip_robot_arm 모드 시 자동 스킵)
       |
6. [음식 적재] Robot Arm이 음식 적재 후 LoadingComplete 발행
       |
7. [테이블 이동] FMS --FollowWaypoints--> 서빙 로봇 -> tableN
       |
8. [도착 알림] FMS --TCP Push--> Customer GUI (delivery_notification)
       |
9. [수령 확인] Customer GUI --TCP--> FMS (delivery_complete)
       |
10. [복귀/재배정] 대기 주문 있으면 바로 다음 주문 처리,
                   없으면 parking spot으로 복귀
```

### 7.2 다중 로봇 시나리오 (3 Orders 동시)

| 시점 | 이벤트 | 상태 |
|------|--------|------|
| T0 | 3개 주문 도착 | Queue: [order1, order2, order3] |
| T1 | pinky1/2/3 각각 배정 | Active: 3, Pending: 0 |
| T2 | pinky1 pickup 도착 | pinky1 슬롯 점유 |
| T3 | pinky2 pickup 도착 | pinky2 대기 (point13) |
| T4 | pinky3 pickup 도착 | pinky3 대기 (point3) |
| T5 | pinky1 적재 완료, 출발 | pinky2 슬롯 획득 |
| T6 | pinky2 적재 완료, 출발 | pinky3 슬롯 획득 |
| T7 | 모든 로봇 배달 중 | - |
| T8+ | 배달 완료, 복귀 | IDLE 상태 |

---

## 8. 실행 방법

### 8.1 사전 요구사항

- ROS2 Humble 또는 Jazzy
- Python 3.10+
- `fleet_interfaces` 패키지 빌드 완료
- Nav2 패키지 설치
- kitchmatics WiFi 네트워크 연결 (192.168.1.x)

### 8.2 빌드

```bash
cd ~/kitchmatics/roscamp-repo-1
colcon build --packages-select fms
source install/setup.bash
```

### 8.3 FMS 노드 실행

**Production 모드 (로봇팔 연동):**
```bash
export ROS_DOMAIN_ID=25
ros2 run fms fms_node
```

**테스트 모드 (로봇팔 스킵):**
```bash
export ROS_DOMAIN_ID=25
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
```

**Launch 파일 사용:**
```bash
export ROS_DOMAIN_ID=25
ros2 launch fms fms_launch.py
```

### 8.4 Sandwich Coordinator 실행

FMS와 함께 로봇팔 조율을 위한 Sandwich Coordinator를 반드시 실행해야 한다. Coordinator는 Arm A(Domain 20, Sandwich Arm)와 Arm B(Domain 21, Sauce Arm) 간의 조리 워크플로우를 관리한다.

**방법 1: 실행 스크립트 사용 (권장)**
```bash
cd fms/coordinator_Ws
./run_coordinator.sh
# ROS_DOMAIN_ID=25로 자동 설정, fleet_interfaces + coordinator 환경 자동 소싱
```

**방법 2: Launch 파일로 직접 실행**
```bash
export ROS_DOMAIN_ID=25

# Production 모드 (FMS 연동) - Domain Bridge(bridge_a, bridge_b) 자동 포함
ros2 launch sandwich_coordinator coordinator_all.launch.py test_mode:=false

# 테스트 모드 (로봇팔 단독 테스트)
ros2 launch sandwich_coordinator coordinator_all.launch.py \
  test_mode:=true test_recipe:=ham_cheese test_sauce:=mustard
```

> Launch 파일은 내부적으로 `bridge_a.yaml`(Domain 25 <-> 20)과 `bridge_b.yaml`(Domain 25 <-> 21)의 Domain Bridge 노드를 함께 실행한다.

### 8.5 Domain Bridge 실행

각 로봇과의 크로스 도메인 통신을 위해 별도 터미널에서 bridge를 실행한다:

```bash
# Pinky1 Bridge (Forward: 11->25)
ros2 run domain_bridge domain_bridge --ros-args \
  -p config_file:=fms/config/bridge_pinky1.yaml

# Pinky1 Bridge (Reverse: 25->11)
ros2 run domain_bridge domain_bridge --ros-args \
  -p config_file:=fms/config/bridge_pinky1_reverse.yaml

# 나머지 로봇도 동일하게 실행 (pinky2, pinky3, arm_a, arm_b)
```

### 8.6 모니터링

```bash
# Fleet 상태 확인
export ROS_DOMAIN_ID=25
ros2 topic echo /fms/fleet_status

# 조리 주문 확인
ros2 topic echo /cooking/order

# 특정 로봇 위치 확인
ros2 topic echo /pinky1/amcl_pose
```

---

## 9. 테스트 방법

### 9.1 빌드 테스트

```bash
cd ~/kitchmatics/roscamp-repo-1
colcon build --packages-select fms
# 결과: Success
```

### 9.2 구문 검사

```bash
python3 -m py_compile fms/fms/order_handler.py
python3 -m py_compile fms/fms/gui_tcp_server.py
python3 -m py_compile fms/fms/collision_avoidance.py
# 에러 없으면 통과
```

### 9.3 GUI 통합 테스트

```bash
# Terminal 1: FMS 실행
export ROS_DOMAIN_ID=25
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true

# Terminal 2: 테스트 주문 전송
python3 fms/scripts/test_gui_order.py new_order
```

### 9.4 단위 테스트

```bash
cd ~/kitchmatics/roscamp-repo-1/fms
pytest tests/ -v

# Zone Manager 테스트
python3 -m pytest fms/tests/test_zone_manager_reservation.py -v
```

### 9.5 TCP 메시지 직접 테스트

**새 주문 전송:**
```json
{
    "command": "new_order",
    "table_number": 1,
    "order": {
        "items": [
            {"menu_id": "M001", "quantity": 1, "sauce": "ketchup"}
        ]
    }
}
```

**수령 확인:**
```json
{
    "command": "delivery_complete",
    "order_id": "ORD-20260225123456-0001",
    "table_number": 1
}
```

---

## 10. 트러블슈팅

### 10.1 연결 관련

**문제: TCP 연결 거부 (Connection Refused)**
```
ERROR: Could not connect to FMS at 192.168.1.3:9000
```
- FMS 노드 실행 확인: `ps aux | grep fms_node`
- 포트 확인: `netstat -tulpn | grep 9000`
- 방화벽 확인: `sudo ufw status`

**문제: Domain Bridge 통신 실패**
- Bridge 프로세스 실행 확인
- ROS_DOMAIN_ID 환경변수 확인
- 네트워크 연결 확인: `ping 192.168.1.7`
- Fallback으로 SSH 네비게이션 자동 전환됨

### 10.2 네비게이션 관련

**문제: 로봇이 목적지에 도달하지 못함**
- 맵 위치 확인: `fms/config/fms_config.yaml`의 positions 섹션
- goal_reached_threshold 값 확인 (기본 0.1m)
- Nav2 스택 실행 확인: 로봇 측에서 `ros2 topic list | grep navigate`

**문제: FollowWaypoints 액션 서버 미응답**
- Domain Bridge 정상 동작 확인
- 자동으로 SSH Fallback 시도됨 (로그에서 `[SSH-NAV]` 확인)
- 로봇 IP 연결 확인

**문제: 로봇이 pickup_spot에서 멈춤**
- Pickup Slot 타임아웃 확인: 기본 60초 후 강제 해제
- 스케줄러 상태 확인 (로그에서 Scheduler Status 검색)
- skip_robot_arm 모드에서는 3초 후 자동 진행

### 10.3 로봇 상태 관련

**문제: 로봇이 IDLE로 돌아오지 않음**
- Fleet Controller 상태 확인: `/fms/fleet_status` 토픽 모니터링
- RETURNING 상태에서 parking spot 도달 여부 확인
- 수동 복구: `/fms/operator_command`로 CLEAR_ERROR 또는 RETURN_HOME 명령

**문제: 가용 로봇 없음 (No available robot)**
- 모든 로봇의 상태 확인 (IDLE이 아닌 경우 태스크 진행 중)
- POSE 데이터 수신 확인 (10초 이내 미수신 시 offline 판정)
- `clear_robot()` 호출로 zombie 상태 정리

### 10.4 주문 관련

**문제: 배달 알림이 GUI에 도달하지 않음**
- TCP 클라이언트 연결 확인 (FMS 로그에서 connected/disconnected 확인)
- 로봇이 실제로 테이블에 도착했는지 확인
- 주문 상태 확인: OrderHandler의 active_orders

**문제: 로봇팔이 조리 명령을 받지 못함**
- `/cooking/command` 토픽 모니터링: `ros2 topic echo /cooking/command`
- Domain Bridge (Robot Arm) 실행 확인
- ROS_DOMAIN_ID 25에서 토픽 발행 확인

### 10.5 로그 확인

```bash
# ROS2 로그 확인
~/.ros/log/

# FMS 로그에서 특정 키워드 검색
grep "ERROR" ~/.ros/log/latest_run/*.log
grep "WORKFLOW" ~/.ros/log/latest_run/*.log
grep "COLLISION_AVOIDANCE" ~/.ros/log/latest_run/*.log
grep "PICKUP" ~/.ros/log/latest_run/*.log
```

---

## 디렉토리 구조

```
fms/
+-- fms/                          # 핵심 Python 모듈
|   +-- __init__.py
|   +-- fms_node.py               # 메인 FMS 노드 (Presentation Layer)
|   +-- fleet_controller.py       # 로봇 함대 상태 관리
|   +-- task_manager.py           # 태스크 대기열 및 할당
|   +-- task_scheduler.py         # 다중 로봇 스케줄링 + Pickup Slot 관리
|   +-- order_handler.py          # 주문 워크플로우 (Application Layer)
|   +-- path_planner.py           # Navigation Graph 기반 경로 계획
|   +-- collision_avoidance.py    # 다중 로봇 충돌 회피
|   +-- zone_manager.py           # Zone 기반 공간 조정
|   +-- error_detector.py         # 에러 감지 및 모니터링
|   +-- error_recovery.py         # 에러 복구 핸들러
|   +-- gui_tcp_server.py         # GUI TCP 서버 (Infrastructure Layer)
+-- config/                       # 설정 파일
|   +-- fms_config.yaml           # FMS 전체 설정
|   +-- navigation_graph.yaml     # 네비게이션 그래프
|   +-- bridge_pinky*.yaml        # Domain Bridge 설정 (로봇)
|   +-- bridge_arm_*.yaml         # Domain Bridge 설정 (로봇팔)
+-- launch/                       # ROS2 Launch 파일
|   +-- fms_launch.py
+-- maps/                         # 맵 파일
+-- docs/                         # 문서
|   +-- ARCHITECTURE_DIAGRAM.md
|   +-- QUICKSTART.md
+-- scripts/                      # 테스트 스크립트
+-- tests/                        # 단위 테스트
+-- package.xml                   # ROS2 패키지 매니페스트
+-- setup.py                      # Python 패키지 설정
+-- README.md                     # 이 문서
```
