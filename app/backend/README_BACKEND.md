# Kitchmatics Main Server - Backend Documentation
**Backend/Main Server Lead**
**최종 업데이트**: 2026-02-25

---

## 문서 인덱스

본 디렉토리는 Kitchmatics FMS의 **Main Server (Backend)** 구현 및 검증 문서를 포함합니다.

### 핵심 문서

1. **[BACKEND_SUMMARY.md](BACKEND_SUMMARY.md)** - 시작하기 (3분 읽기)
   - TL;DR 요약
   - 현재 상태 및 등급
   - 즉시 수정 필요한 문제
   - 로컬 테스트 가능 여부

2. **[BACKEND_VALIDATION_REPORT.md](BACKEND_VALIDATION_REPORT.md)** - 상세 검증 보고서 (20분 읽기)
   - Main Server 통신 검증 (ROS, TCP, DB)
   - ROS_DOMAIN_ID 통합 검증
   - 메시지 프로토콜 검증
   - PostgreSQL 연동 검증
   - 문제점 종합 리스트 (CRITICAL/HIGH/MEDIUM/LOW)
   - 로컬 테스트 환경 구축 방법

3. **[CRITICAL_FIXES.md](CRITICAL_FIXES.md)** - 수정 구현 가이드 (코드 포함)
   - Fix #1: DB 제약조건 불일치 (AT_POINT13 상태)
   - Fix #2: Skip Mode - LoadingComplete 자동 전송
   - Fix #3: skip_mode 파라미터 전달
   - Fix #4: TCP 메시지 구분자 (버퍼링)
   - Fix #5: Robot 상태 제약조건 추가
   - 통합 테스트 스크립트
   - 적용 순서 및 검증 체크리스트

4. **[ARCHITECTURE_DIAGRAM.md](ARCHITECTURE_DIAGRAM.md)** - 아키텍처 다이어그램
   - 전체 시스템 아키텍처
   - Main Server 내부 구조
   - 메시지 흐름 (주문 처리)
   - Skip Mode 흐름
   - TCP 프로토콜
   - Database 스키마
   - Thread 모델
   - 에러 처리 흐름
   - 배포 뷰

5. **[TESTING_CHECKLIST.md](TESTING_CHECKLIST.md)** - 테스트 체크리스트
   - Pre-Testing Setup (DB, ROS, Tools)
   - Test Phase 1: Standalone Components
   - Test Phase 2: Integrated System
   - Test Phase 3: Integration Testing
   - Test Phase 4: Bug Verification
   - Test Phase 5: Performance & Stress
   - Post-Testing Cleanup
   - Test Result Summary

### 추가 문서

6. **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - 구현 요약
   - 전체 구현 내역
   - 제공 기능
   - 아키텍처 개요

7. **[tests/README.md](tests/README.md)** - TCP 테스트 도구 사용법
   - tcp_test_client.py 사용법
   - 메시지 타입별 예제
   - 통합 테스트 흐름

---

## 빠른 시작 (Quick Start)

### 1. 문서 읽는 순서

처음 사용하시는 분:
```
1. BACKEND_SUMMARY.md (3분) - 전체 상황 파악
2. ARCHITECTURE_DIAGRAM.md (10분) - 아키텍처 이해
3. TESTING_CHECKLIST.md (30분) - 로컬 테스트 실행
```

버그 수정하려는 분:
```
1. BACKEND_SUMMARY.md → "문제점 종합" 섹션
2. CRITICAL_FIXES.md - 수정 가이드 및 코드
3. TESTING_CHECKLIST.md → "Bug Verification" 섹션
```

상세 검증이 필요한 분:
```
1. BACKEND_VALIDATION_REPORT.md - 17페이지 전체 읽기
```

### 2. 로컬 테스트 시작

**방법 A – 리포지토리 루트 워크스페이스 (권장)**  
루트에서 빌드·실행 스크립트 사용. `build/`, `install/`, `log/`는 `.gitignore`에 있어 git에는 올라가지 않음.

```bash
# 리포지토리 루트에서 (최초 1회 빌드 후 실행)
./run_backend_from_workspace.sh
```

수동으로 빌드만 하려면 (패키지명은 **fleet_interfaces**. `fleet_ointerfaces` 오타 주의):

```bash
cd /path/to/roscamp-repo-1
source /opt/ros/jazzy/setup.bash   # 또는 humble
# --paths: robot_arm/venv 등 다른 setup.py 경로 스캔 방지
colcon build --paths fleet_interfaces --paths app/backend --packages-select fleet_interfaces main_server
source install/setup.bash
python3 app/backend/run_main_server.py
```

**방법 B – 기존 절차 (동일 머신 경로 기준)**

```bash
# 1. Database 설정
cd /path/to/roscamp-repo-1/database
./setup_database.sh

# 2. 빌드 (루트에서)
cd /path/to/roscamp-repo-1
colcon build --packages-select fleet_interfaces main_server
source install/setup.bash

# 3. Main Server 실행 (skip mode)
ros2 run main_server main_server --ros-args -p skip_mode:=true

# 4. 테스트 (별도 터미널)
cd app/backend/tests
./tcp_test_client.py order --table T01 --menu M001
./integration_test.sh
```

### 3. 버그 수정 시작

현재 3개의 CRITICAL 버그가 있습니다:

```bash
# 1. DB 제약조건 수정 (30분)
# CRITICAL_FIXES.md → Fix #1 참조
vim app/backend/main_server/database_manager.py
# Line 165 수정

# 2. Skip mode 완성 (1시간)
# CRITICAL_FIXES.md → Fix #2 참조
vim app/backend/main_server/ros_bridge.py
# _send_mock_loading_complete 메서드 추가

# 3. skip_mode 파라미터 (30분)
# CRITICAL_FIXES.md → Fix #3 참조
vim app/backend/main_server/main_server_node.py
# main() 함수 수정
```

전체 수정 가이드는 **CRITICAL_FIXES.md** 참조.

---

## 프로젝트 구조

```
app/backend/
├── main_server/                    # Main Server 소스 코드
│   ├── __init__.py
│   ├── main_server_node.py         # 메인 서버 노드 (통합)
│   ├── ros_bridge.py               # ROS 2 통신 브릿지
│   ├── tcp_server.py               # TCP 서버
│   └── database_manager.py         # PostgreSQL ORM
│
├── config/                          # 설정 파일
│   ├── database.env                 # DB 연결 정보 (실제 파일)
│   └── database.env.example         # DB 연결 정보 (예제)
│
├── tests/                           # 테스트 도구 및 스크립트
│   ├── README.md                    # 테스트 도구 사용법
│   ├── tcp_test_client.py           # TCP 테스트 클라이언트
│   └── integration_test.sh          # 통합 테스트 스크립트 (신규)
│
├── launch/                          # ROS 2 launch 파일
│   └── main_server_launch.py
│
├── setup.py                         # Python package setup
├── package.xml                      # ROS 2 package manifest
│
└── 문서 (본 디렉토리)
    ├── README_BACKEND.md            # 본 파일 (문서 인덱스)
    ├── BACKEND_SUMMARY.md           # 요약 보고서
    ├── BACKEND_VALIDATION_REPORT.md # 상세 검증 보고서
    ├── CRITICAL_FIXES.md            # 수정 가이드
    ├── ARCHITECTURE_DIAGRAM.md      # 아키텍처 다이어그램
    ├── TESTING_CHECKLIST.md         # 테스트 체크리스트
    └── IMPLEMENTATION_SUMMARY.md    # 구현 요약
```

---

## Main Server 개요

### 역할
Main Server는 **Kitchmatics FMS의 중앙 통신 허브**입니다:

1. **Kiosk/Admin GUI ↔ Main Server** (TCP)
   - Order request, status query, delivery complete

2. **Main Server ↔ FMS** (ROS 2)
   - Order assignment, fleet status

3. **Main Server ↔ Robot Arm** (ROS 2)
   - Cooking order, loading complete

4. **Main Server ↔ PostgreSQL** (SQLAlchemy)
   - Order/Robot/Menu/Inventory data

### 아키텍처

```
┌─────────────────────────────────────────┐
│         Main Server Process             │
│                                         │
│  ┌────────────┐  ┌──────────────┐      │
│  │ TCP Server │  │  ROS Bridge  │      │
│  │ (Port 9999)│  │  (ROS 2 Node)│      │
│  └─────┬──────┘  └──────┬───────┘      │
│        │                │              │
│        └────────┬───────┘              │
│                 │                      │
│        ┌────────▼────────┐             │
│        │  Main Server    │             │
│        │  Coordinator    │             │
│        └────────┬────────┘             │
│                 │                      │
│        ┌────────▼────────┐             │
│        │  Database Mgr   │             │
│        │  (SQLAlchemy)   │             │
│        └────────┬────────┘             │
└─────────────────┼──────────────────────┘
                  │
         ┌────────▼────────┐
         │  PostgreSQL DB  │
         │  (kitchmatic)   │
         └─────────────────┘
```

### 주요 기능

1. **Order Management**
   - Create, query, update order status
   - State: PENDING → CONFIRMED → AT_POINT13 → COOKING → READY → DELIVERING → COMPLETED

2. **Communication Routing**
   - TCP JSON messages ↔ ROS 2 messages
   - Broadcast status updates to all connected clients

3. **Skip Mode** (테스트용)
   - Precision parking 자동 완료 (2초)
   - Food loading 자동 완료 (3초) - 현재 버그, 수정 필요

4. **Database Integration**
   - Orders, Robots, Menu, Inventory management
   - Transaction-safe operations
   - Index-optimized queries

---

## 현재 상태

### 등급: B- (75/100)

**강점**:
- ✅ 깔끔한 3-tier 아키텍처 (DB, TCP, ROS)
- ✅ 확장성 있는 Handler 패턴
- ✅ Skip mode 지원 (외부 팀 없이 테스트)
- ✅ 일관된 에러 처리
- ✅ 상세한 문서화

**약점**:
- ❌ ROS_DOMAIN_ID 미구현 (multi-domain 통신 불가)
- ❌ DB 제약조건 불일치 (AT_POINT13 상태 누락)
- ❌ Skip mode 불완전 (LoadingComplete 자동 전송 누락)
- ❌ skip_mode 파라미터 전달 안 됨

### 로컬 테스트 가능 여부

**80% 가능**:
- ✅ TCP 통신 테스트
- ✅ Database 연동 테스트
- ✅ 단일 도메인 ROS 통신 테스트
- ✅ Skip mode로 전체 흐름 테스트

**20% 불가**:
- ❌ Multi-domain ROS 통신 (실제 네트워크 필요)
- ❌ 실제 로봇 제어 (Navigation, AMCL, 배터리)

---

## CRITICAL 문제 및 해결 방안

### 1. DB 제약조건 불일치

**문제**: 코드에서 `AT_POINT13` 상태 사용하지만 DB CheckConstraint에 없음

**영향**: DB 에러 발생, 주문 처리 실패

**해결**: `database_manager.py` Line 165 수정 + migration 실행

**예상 시간**: 30분

**상세**: CRITICAL_FIXES.md → Fix #1

### 2. Skip Mode - LoadingComplete 누락

**문제**: PrecisionParked는 자동 전송되지만 LoadingComplete는 수동

**영향**: Skip mode에서 완전한 테스트 불가

**해결**: `ros_bridge.py`에 `_send_mock_loading_complete` 메서드 추가

**예상 시간**: 1시간

**상세**: CRITICAL_FIXES.md → Fix #2

### 3. skip_mode 파라미터 미전달

**문제**: `main()` 함수에서 skip_mode 파라미터 전달 안 됨

**영향**: Skip mode 사용 불가 (하드코딩 필요)

**해결**: `main_server_node.py` main() 함수 수정 (ROS parameter 읽기)

**예상 시간**: 30분

**상세**: CRITICAL_FIXES.md → Fix #3

---

## ROS_DOMAIN_ID 이슈

### 현재 문제

Main Server는 **단일 ROS_DOMAIN_ID(기본값 0)**에서만 작동합니다.

CLAUDE.md 요구사항:
- pinky1: Domain 11
- pinky2: Domain 12
- pinky3: Domain 13
- cobot1: Domain 14
- cobot2: Domain 15

**결과**: Main Server가 여러 도메인의 로봇과 통신 불가능

### 해결 방안

**권장 (FMS에서 처리)**:
```
Master PC:
  - Main Server (Domain 0)
  - FMS (Domain 0)

FMS가 각 로봇 도메인으로 명령 전달
```

이 경우 Main Server 수정 불필요, FMS에서 multi-domain 처리.

**대안 (복잡도 높음)**:
- Main Server에서 각 도메인별 ROS 브릿지 프로세스 생성
- subprocess로 domain별 브릿지 실행
- 메시지 라우팅 로직 추가

**결정**: FMS 팀과 협의 필요

**상세**: BACKEND_VALIDATION_REPORT.md → Section 2

---

## 다음 단계

### 즉시 (이번 주)
1. CRITICAL 버그 수정 (DB, skip mode, 파라미터)
2. 통합 테스트 실행 및 검증
3. 문서 업데이트

### 단기 (다음 주)
4. TCP 버퍼링 추가 (MEDIUM 버그)
5. Robot 상태 제약조건 추가
6. FMS 팀과 ROS_DOMAIN_ID 아키텍처 협의

### 중기 (2주)
7. 주문 상태 전환 완성 (COOKING, DELIVERING, DELIVERED)
8. 에러 핸들링 강화
9. 단위 테스트 추가

### 장기 (1개월)
10. Multi-domain 통신 구현 (FMS 협의 후)
11. Health check 엔드포인트
12. 성능 모니터링 및 최적화

---

## 참고 자료

### 프로젝트 문서
- `/home/gw/kitchmatics/roscamp-repo-1/CLAUDE.md` - 프로젝트 전체 가이드
- `/home/gw/kitchmatics/roscamp-repo-1/README.md` - 사용자 문서
- `/home/gw/kitchmatics/roscamp-repo-1/database/README.md` - DB 설정 가이드
- `/home/gw/kitchmatics/roscamp-repo-1/fms/README.md` - FMS 문서

### 외부 문서
- [ROS 2 Jazzy Documentation](https://docs.ros.org/en/jazzy/index.html)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### ROS 2 메시지 정의
- `/home/gw/kitchmatics/roscamp-repo-1/fleet_interfaces/msg/`
  - OrderRequest.msg
  - CookingOrder.msg
  - LoadingComplete.msg
  - PickupArrival.msg
  - PrecisionParked.msg
  - DeliveryComplete.msg
  - FleetStatus.msg
  - RobotStatus.msg

---

## 연락처 및 지원

**Backend/Main Server Lead**: Backend 팀
**FMS 팀**: FMS 개발 팀과 ROS_DOMAIN_ID 이슈 협의 필요
**Database 팀**: Database 스키마 및 migration 관련

**이슈 보고**: 문제 발견 시 TESTING_CHECKLIST.md의 "Test Result Summary" 작성 후 공유

---

**최종 업데이트**: 2026-02-25
**문서 버전**: 1.0
**검증자**: Backend/Main Server Lead
