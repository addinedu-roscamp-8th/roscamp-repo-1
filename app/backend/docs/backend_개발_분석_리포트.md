# app/backend 개발 내용 분석 리포트

작성일: 2025-02-23  
대상: `/home/addinedu/Documents/roscamp-repo-1/app/backend` (Kitchmatics Main Server)

---

## 1. 개요

backend 디렉터리는 **Kitchmatics FMS(Fleet Management System)의 Main Server**를 구현한 ROS 2 Python 패키지입니다.  
Kiosk/Admin GUI(TCP), FMS·로봇팔(ROS 2), PostgreSQL(DB) 사이의 **중앙 통신 허브** 역할을 합니다.

| 항목 | 내용 |
|------|------|
| 패키지명 | `main_server` (package.xml, setup.py) |
| ROS 2 | Jazzy, ament_python 빌드 |
| 의존성 | rclpy, fleet_interfaces, SQLAlchemy, psycopg2 |
| 실행 | `ros2 run main_server main_server` (진입점: main_server_node.main) |

---

## 2. 디렉터리 구조

```
app/backend/
├── main_server/                    # 소스
│   ├── __init__.py
│   ├── main_server_node.py         # 메인 노드(통합·핸들러)
│   ├── ros_bridge.py               # ROS 2 퍼블리셔/서브스크라이버
│   ├── tcp_server.py               # TCP 서버(포트 9999)
│   └── database_manager.py         # PostgreSQL ORM
├── config/
│   ├── database.env.example        # DB 설정 예제
│   └── database.env               # 실제 설정 (gitignore)
├── tests/
│   ├── README.md
│   └── tcp_test_client.py         # TCP 테스트 클라이언트
├── launch/
│   └── main_server_launch.py
├── setup.py
├── package.xml
└── 문서 (루트 + docs/)
    ├── README_BACKEND.md           # 문서 인덱스·퀵스타트
    ├── BACKEND_SUMMARY.md          # 요약·등급·즉시 수정 항목
    ├── BACKEND_VALIDATION_REPORT.md
    ├── CRITICAL_FIXES.md           # 수정 가이드(코드 포함)
    ├── ARCHITECTURE_DIAGRAM.md     # 아키텍처·메시지 흐름
    ├── TESTING_CHECKLIST.md
    ├── IMPLEMENTATION_SUMMARY.md
    └── docs/backend_개발_분석_리포트.md  # 본 문서
```

---

## 3. 아키텍처

### 3.1 3-Tier 구조

- **TCP Server** (0.0.0.0:9999): Kiosk·Admin GUI와 JSON 메시지 교환 (주문 요청, 상태 조회, 배달 완료 등).
- **ROS Bridge** (rclpy Node): FMS·로봇팔과 ROS 2 토픽으로 통신 (OrderRequest, CookingOrder, PickupArrival, LoadingComplete, PrecisionParked, DeliveryComplete 등).
- **Database Manager** (SQLAlchemy): PostgreSQL(kitchmatic DB)에 주문·로봇·메뉴·재고 등 영속화.

Main Server Node가 위 세 컴포넌트를 초기화하고, TCP/ROS 메시지 타입별 **핸들러**를 등록해 라우팅·상태 관리·에러 처리를 담당합니다.

### 3.2 메시지 흐름 (주문 처리)

1. **Kiosk** → TCP `order_request` → Main Server → DB에 주문 생성(CONFIRMED) → ROS `OrderRequest` → **FMS**
2. **FMS** → ROS `PickupArrival` → Main Server → DB `AT_POINT13` → ROS `CookingOrder` → **로봇팔**  
   (Skip mode 시 2초 후 mock `PrecisionParked` → FMS)
3. **로봇팔** → ROS `LoadingComplete` → Main Server → DB `READY` → TCP broadcast
4. FMS가 테이블까지 배달 후 **Kiosk** → TCP `delivery_complete` → Main Server → DB `COMPLETED` → ROS `DeliveryComplete` 등

### 3.3 Skip Mode

외부 팀(정밀 주차·로봇팔) 없이 테스트하기 위한 모드.

- `PickupArrival` 수신 시: DB·CookingOrder 처리 후, 2초 뒤 mock `PrecisionParked` 자동 퍼블리시.
- 문서 상으로는 3초 뒤 `LoadingComplete` 자동 전송도 설계되어 있으나, **현재 구현 누락**으로 CRITICAL 이슈로 기록됨.

---

## 4. 주요 구현 내용

### 4.1 main_server_node.py

- `MainServer(skip_mode=False)`: DB 설정 로드(`_load_db_config`: env → config/database.env → 기본값), DatabaseManager·TCPServer·ROSBridge 초기화, ROS는 별도 스레드에서 spin.
- TCP 핸들러: `handle_order_request`, `handle_order_status_query`, `handle_fleet_status_query`, `handle_delivery_complete` 등.
- ROS 핸들러: `handle_pickup_arrival`(AT_POINT13 갱신, CookingOrder 발행), `handle_loading_complete`(READY 갱신), `handle_fleet_status_update` 등.
- **이슈**: `skip_mode`를 ROS 파라미터로 받아 전달하는 로직이 main()에 없음(CRITICAL로 문서화됨).

### 4.2 ros_bridge.py

- **Publishers**: `/fms/order_request`, `/robot_arm/cooking_order`, `/fms/delivery_complete`, `/fms/precision_parked`.
- **Subscribers**: `/robot_arm/loading_complete`, `/fms/fleet_status`, `/fms/pickup_arrival`, `/fms/table_arrival`.
- PickupArrival 콜백에서 `on_pickup_arrival` 호출, skip_mode 시 2초 후 `_send_mock_precision_parked` 호출.
- **이슈**: `_send_mock_loading_complete` 미구현(LoadingComplete 자동 전송 없음).

### 4.3 tcp_server.py

- JSON 기반 요청/응답, 메시지 타입별 `register_handler` 등록, 다중 클라이언트 스레드 처리, broadcast 지원.
- **이슈**: 메시지 구분자(버퍼링) 불일치 가능성 — 서버는 단일 recv(), 클라이언트는 개행 구분 등(MEDIUM).

### 4.4 database_manager.py

- schema.sql과 동일한 테이블 구조의 ORM: Menu, Ingredient, Recipe, RecipeStep, Inventory, InventoryTransaction, Robot, Order, QualityCheckResult 등.
- `create_order`, `update_order_status`, `get_order`, `get_menu`, 로봇 상태 갱신 등 제공.
- **이슈**: 주문 상태 CheckConstraint에 `AT_POINT13`이 없어, 해당 상태로 UPDATE 시 DB 에러 발생(CRITICAL).

---

## 5. 설정·테스트

- **DB 설정**: `config/database.env.example` 복사 → `database.env` 작성(DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD). `database.env`는 gitignore.
- **실행**: `ros2 run main_server main_server` (필요 시 `--ros-args -p skip_mode:=true`).
- **테스트**: `tests/tcp_test_client.py`로 order/status/fleet/complete 등 TCP API 호출 가능. 통합 테스트는 TESTING_CHECKLIST.md 및 integration_test.sh 참고.

---

## 6. 문서에서 정리한 현재 상태

- **등급**: B- (75/100). 아키텍처는 명확, 구현은 CRITICAL 버그 3건·ROS_DOMAIN_ID 미구현 등으로 인해 감점.
- **CRITICAL**  
  1. DB CheckConstraint에 `AT_POINT13` 추가 필요.  
  2. Skip mode에서 LoadingComplete 자동 전송 구현 필요.  
  3. main()에서 skip_mode ROS 파라미터 읽어 MainServer/ROSBridge에 전달 필요.
- **ROS_DOMAIN_ID**: 단일 도메인(0)만 사용. multi-domain(pinky1=11 등)은 미구현. 권장안은 FMS에서 도메인별 브릿지 처리.
- **로컬 테스트**: TCP·DB·단일 도메인 ROS·Skip mode로 대부분 가능. Multi-domain·실제 로봇 제어는 제한적.

---

## 7. 정리

| 구분 | 내용 |
|------|------|
| 목적 | Kitchmatics FMS의 중앙 Main Server (TCP + ROS 2 + DB) |
| 강점 | 3-tier 분리, 핸들러 패턴, Skip mode, 문서화·아키텍처 다이어그램 |
| 약점 | AT_POINT13 DB 제약 누락, Skip mode LoadingComplete 미구현, skip_mode 파라미터 미전달, ROS_DOMAIN_ID 미지원 |
| 다음 단계 | CRITICAL_FIXES.md 순서대로 수정 후, TESTING_CHECKLIST.md로 검증 |

상세 수정 방법·코드 스니펫·검증 절차는 **CRITICAL_FIXES.md**, **BACKEND_VALIDATION_REPORT.md**, **README_BACKEND.md**를 참고하면 됩니다.
