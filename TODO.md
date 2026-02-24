# Kitchmatic Fleet Management System - TODO 목록

이 문서는 Kitchmatic FMS의 구현 완료 후 적용/수정이 필요한 사항들을 정리한 것입니다.

## 🟣 현재 진행 중

### 문서화 정렬 (DevOps - Documentation Priority)
- [x] CLAUDE.md 업데이트: ROS_DOMAIN_ID 제거, 네임스페이스 기반 아키텍처로 변경 ✅
- [x] 현재 구현과 문서 일관성 맞추기 ✅
- [x] README.md와 CLAUDE.md 동기화 ✅
- [x] TODO.md 완료 항목 업데이트 ✅
- [ ] 향후 작업: 빠른 시작 가이드 작성 (개발자용)
- [ ] 향후 작업: 배포 가이드 작성 (폐쇄 네트워크)
- [ ] 향후 작업: 트러블슈팅 가이드 작성

### 관련 파일
- `CLAUDE.md` - 프로젝트 가이드 (네임스페이스 아키텍처)
- `README.md` - 사용자 설명서 (이미 최신)
- `TODO.md` - 이 파일

---

---

## 📊 아키텍처 결정 확정

### ROS_DOMAIN_ID vs 네임스페이스 검증 결과

**최종 결정: ROS 2 네임스페이스 사용**

현재 구현 검증:
- [x] `network_config.yaml`: 모든 로봇이 namespace로 설정됨 ✅
- [x] `fms_config.yaml`: 로봇 설정이 namespace 기반 ✅
- [x] `fms_node.py`: FMS가 namespace 기반 topic/action 사용 ✅
- [x] `bringup_launch.py`: PushRosNamespace로 다중 로봇 지원 ✅
- [x] `mobile_robot/params/nav2_params.yaml`: RewrittenYaml로 namespace 주입 ✅

**이점:**
- 마스터 PC에서 중앙 제어 용이
- 같은 ROS domain에서 모든 로봇 통신
- 간단한 namespace 관리
- 다중 로봇 조정 및 충돌 방지 용이

**주의사항:**
- ROS_DOMAIN_ID는 모든 로봇/PC에서 동일하게 유지 필요
- 폐쇄 네트워크(kitchmatics WiFi) 환경에서만 권장
- 각 로봇은 namespace로 구분됨

---

## 🔴 필수 설정 (시스템 실행 전 반드시 완료)

### 1. 데이터베이스 설정

#### 1.1 PostgreSQL 초기 설정
- [ ] PostgreSQL 설치 및 초기화
  ```bash
  sudo apt update
  sudo apt install postgresql postgresql-contrib
  ```

- [ ] 데이터베이스 및 사용자 생성
  - 파일: `database/README.md` 참조
  - **비밀번호 설정 필요**: `CREATE USER kitchmatic_user WITH PASSWORD 'your_password_here';`
  - 강력한 비밀번호로 변경할 것

- [ ] 스키마 적용
  ```bash
  psql -U kitchmatic_user -d kitchmatic -f database/schema.sql
  ```

#### 1.2 Main Server DB 연결 설정
- [ ] **파일**: `app/backend/main_server/main_server_node.py`
- [ ] **Line 34-41**: DB 연결 정보 수정
  ```python
  db_config = {
      'db_host': 'localhost',  # TODO: DB 서버 IP 입력
      'db_port': 5432,
      'db_name': 'kitchmatic',
      'db_user': 'kitchmatic_user',
      'db_password': 'your_password_here'  # TODO: 실제 비밀번호 입력
  }
  ```

- [ ] **별도 DB 서버 사용 시**:
  - `/etc/postgresql/*/main/postgresql.conf`에서 `listen_addresses` 설정
  - `/etc/postgresql/*/main/pg_hba.conf`에서 네트워크 접근 권한 설정

### 2. 네트워크 및 IP 설정

#### 2.1 Main Server TCP 설정
- [ ] **파일**: `app/backend/main_server/main_server_node.py`
- [ ] **Line 44-47**: TCP 서버 설정
  ```python
  tcp_config = {
      'host': '0.0.0.0',  # 모든 인터페이스에서 수신
      'port': 9999  # TODO: 필요시 포트 변경
  }
  ```

#### 2.2 로봇 IP 주소 설정
- [ ] **파일**: `database/schema.sql`의 Line 132-137에서 로봇 IP 주소 확인/수정
  ```sql
  INSERT INTO robots (name, type, ip_address, port) VALUES
      ('로봇팔 1', 'ARM_1', '192.168.1.101', 5001),  -- TODO: 실제 IP
      ('로봇팔 2', 'ARM_2', '192.168.1.102', 5002),  -- TODO: 실제 IP
      ('서빙로봇 1', 'SERVING_BOT_1', '192.168.1.201', 5011),  -- TODO: 실제 IP
      ('서빙로봇 2', 'SERVING_BOT_2', '192.168.1.202', 5012),  -- TODO: 실제 IP
      ('서빙로봇 3', 'SERVING_BOT_3', '192.168.1.203', 5013);  -- TODO: 실제 IP
  ```

### 3. 로봇 네임스페이스 설정

#### 3.1 서빙 로봇 네임스페이스
- [x] 각 PinkyPro 로봇이 다음 네임스페이스로 실행되도록 설정: ✅
  - `/pinky1`
  - `/pinky2`
  - `/pinky3`

- [x] **실행 방법** (로봇에서): ✅
  ```bash
  # 터미널 1: 로봇 하드웨어
  ros2 launch pinky_bringup bringup_robot.launch.xml namespace:=pinky1

  # 터미널 2: 네비게이션 (roscamp-repo-1의 launch 파일)
  ros2 launch ~/roscamp-repo-1/mobile_robot/launch/bringup_launch.py namespace:=pinky1 map:=~/real.yaml
  ```

- [x] **bringup_launch.py 기능**: ✅ (완료)
  - RewrittenYaml을 사용하여 namespace에 따라 파라미터 자동 설정
  - pinky1, pinky2, pinky3 모두 동일한 params 파일로 동작
  - 로봇 내부 코드 수정 없이 roscamp-repo-1에서 관리

#### 3.2 FMS 설정 파일 확인
- [x] **파일**: `fms/config/fms_config.yaml` ✅ (완료)
- [x] **Line 4-17**: 로봇 설정이 실제 네임스페이스와 일치하는지 확인 ✅ (확인됨)

### 4. 맵 좌표 보정 (중요!)

#### 4.1 실제 맵 측량
- [ ] 맵 파일: `/home/gw/rmf_ws/src/rmf_demos/rmf_demos_maps/maps/kitchmatics/`
- [ ] 실제 로봇으로 각 위치의 정확한 좌표 측정 필요:
  - pickup_spot (음식 픽업 위치)
  - table1 ~ table8 (8개 테이블 위치)
  - pinky1_spot, pinky2_spot, pinky3_spot (주차 위치)

#### 4.2 FMS 설정 파일 업데이트
- [ ] **파일**: `fms/config/fms_config.yaml`
- [ ] **Line 19-71**: positions 섹션의 모든 좌표 보정
  ```yaml
  positions:
    pickup_spot:
      x: 1.0      # TODO: 실제 측정값으로 변경
      y: 0.3      # TODO: 실제 측정값으로 변경
      theta: 0.0  # TODO: 실제 측정값으로 변경
    # ... (모든 위치에 대해 동일하게 수정)
  ```

#### 4.3 Zone 좌표 보정
- [ ] **파일**: `fms/config/fms_config.yaml`
- [ ] **Line 75-132**: zones 섹션의 모든 좌표 보정
  - 각 zone의 center_x, center_y, radius를 실제 맵에 맞게 조정
  - 로봇 크기(직경 ~0.1m)를 고려하여 radius 설정

#### 4.4 FMS 코드 업데이트
- [ ] **파일**: `fms/fms/fms_node.py`
- [ ] **Line 138-164**: `_load_map_positions()` 메서드를 설정 파일에서 읽도록 수정
  - 현재는 하드코딩된 플레이스홀더 값 사용
  - YAML 파일에서 읽어오도록 변경 필요

## 🟡 기능 구현 (핵심 기능 완성)

### 5. Admin GUI 통합 ✅

#### 5.1 UI 파일 이동
- [x] `/home/gw/kitchmatics/ui_sample/` → `/home/gw/kitchmat0ics/roscamp-repo-1/kitchmatics/app/gui/` 복사 ✅

#### 5.2 서빙 로봇 모니터링 탭 추가
- [x] Admin GUI에 새로운 탭 생성 ✅
- [x] TCP 클라이언트 구현하여 Main Server에 연결 (포트 9999) ✅
  - **파일**: `app/gui/admin_gui/src/fleet_client.py`
- [x] Fleet 상태 표시: ✅
  - 각 로봇의 상태 (IDLE, BUSY, ERROR 등)
  - 배터리 잔량
  - 현재 위치 표시
  - 현재 작업 (주문 ID, 목적지)
  - **파일**: `app/gui/admin_gui/src/ui_fleet_monitor.py`

#### 5.3 메시지 타입 구현
- [x] `fleet_status_query` 요청 메시지 구현 ✅
- [x] `fleet_status_update` 수신 및 UI 업데이트 ✅
- [x] `robot_status_update` 수신 및 UI 업데이트 ✅
- [x] Mock 클라이언트 구현 (테스트용) ✅

**실행 방법**:
```bash
# Mock 모드 (서버 없이 테스트)
cd app/gui/admin_gui/src
python main.py

# 실제 서버 모드
USE_MOCK=false python main.py
```

### 6. 로봇팔 팀과의 인터페이스 연동

#### 6.1 로봇팔 → Main Server 통신
- [ ] 로봇팔 팀에서 `/robot_arm/loading_complete` Topic 발행 구현 확인
- [ ] LoadingComplete 메시지 형식 전달:
  ```
  string order_id
  bool success
  string robot_id         # pinky1, pinky2, pinky3
  string message
  builtin_interfaces/Time completed_at
  ```

#### 6.2 Main Server → 로봇팔 통신
- [ ] CookingOrder 메시지로 주문 정보 전달되는지 확인
- [ ] 로봇팔 팀에서 `/robot_arm/cooking_order` Topic 구독 구현 확인

#### 6.3 조리 완료 후 FMS 연동
- [ ] FMS의 `notify_food_loaded()` 메서드 호출 흐름 확인
- [ ] 로봇이 pickup_spot에서 음식 로딩 후 테이블로 이동하는지 테스트

### 7. 키오스크 통신 구현

#### 7.1 키오스크 TCP 클라이언트
- [ ] 키오스크에서 Main Server TCP 연결 (포트 9999)
- [ ] 주문 요청 메시지 구현:
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

#### 7.2 주문 상태 업데이트 수신
- [ ] `order_status_update` broadcast 메시지 수신
- [ ] UI에 주문 상태 표시 (PENDING → CONFIRMED → COOKING → READY → DELIVERING → DELIVERED → COMPLETED)

#### 7.3 배달 완료 신호
- [ ] "수령완료" 버튼 클릭 시 `delivery_complete` 메시지 전송
- [ ] Main Server에서 응답 수신 및 처리

## 🟢 최적화 및 개선 (선택 사항)

### 8. Navigation 튜닝

#### 8.1 Nav2 파라미터 조정
- [x] **파일**: `mobile_robot/params/nav2_params.yaml` (roscamp-repo-1에서 관리) ✅
- [x] 좁은 공간(2m x 1m)에 맞게 파라미터 조정 완료: ✅
  - `inflation_radius`: 0.01m (좁은 통로 통과용)
  - `xy_goal_tolerance`: 0.02m (2cm 정밀 도착)
  - `lookahead_dist`: 0.08m (소형 로봇용)
  - `robot_radius`: 0.055m (실제 로봇 크기)
  - `resolution`: 0.01m (1cm 해상도)

#### 8.2 Goal Reached Threshold 조정
- [ ] **파일**: `fms/config/fms_config.yaml`
- [ ] **Line 124**: `goal_reached_threshold: 0.1` → 실제 테스트 후 조정

### 9. 로봇 선택 알고리즘 개선

#### 9.1 거리 기반 선택 구현
- [ ] **파일**: `fms/fms/fleet_controller.py`
- [ ] **Line 182-198**: `get_available_robot()` 메서드 개선
- [ ] pickup_spot에 가장 가까운 로봇 선택하도록 수정
- [ ] `calculate_distance()` 메서드 활용

#### 9.2 배터리 잔량 고려
- [ ] 배터리 임계값 조정: `fms/config/fms_config.yaml` Line 127
- [ ] 배터리 부족 시 알림 메커니즘 추가

### 10. 에러 처리 강화

#### 10.1 Navigation 실패 처리
- [ ] Nav2 Action 결과 확인 로직 추가
- [ ] 경로 찾기 실패 시 재시도 로직
- [ ] 최대 재시도 횟수 초과 시 관리자 알림

#### 10.2 데이터베이스 연결 실패 처리
- [ ] Main Server에서 DB 연결 끊김 감지
- [ ] 자동 재연결 메커니즘
- [ ] 연결 실패 시 로그 및 알림

#### 10.3 로봇 통신 끊김 처리
- [ ] Heartbeat 메커니즘 구현
- [ ] 일정 시간 응답 없으면 ERROR 상태로 전환
- [ ] 관리자 알림 및 자동 복구 시도

### 11. 로깅 및 모니터링

#### 11.1 로그 레벨 설정
- [ ] 운영 환경: `logging.INFO`
- [ ] 디버그 환경: `logging.DEBUG`
- [ ] 로그 파일 저장 위치 설정

#### 11.2 성능 메트릭 수집
- [ ] 주문 처리 시간 측정 및 기록
- [ ] 로봇 이동 시간 측정
- [ ] 데이터베이스 쿼리 성능 모니터링

#### 11.3 이벤트 로그
- [ ] 주요 이벤트(주문 생성, 조리 완료, 배달 완료 등)를 DB에 기록
- [ ] 에러 발생 시 상세 정보 저장

### 12. 설정 파일화

#### 12.1 환경 변수 또는 설정 파일 사용
- [ ] Main Server의 하드코딩된 설정을 YAML 또는 .env 파일로 이동
- [ ] 설정 예시:
  ```yaml
  database:
    host: localhost
    port: 5432
    name: kitchmatic
    user: kitchmatic_user
    password: ${DB_PASSWORD}  # 환경 변수에서 읽기

  tcp_server:
    host: 0.0.0.0
    port: 9999
  ```

#### 12.2 FMS 설정 로딩
- [ ] `fms_node.py`에서 `fms_config.yaml` 파일 읽어오기 구현
- [ ] 현재는 하드코딩된 값 사용 중

## 🔵 테스트 및 검증

### 13. 단위 테스트

- [ ] TaskManager 테스트
  - 작업 생성, 할당, 완료 시나리오
  - 작업 실패 및 재할당 시나리오

- [ ] FleetController 테스트
  - 로봇 상태 업데이트
  - 로봇 선택 알고리즘
  - 배터리 모니터링

- [ ] ZoneManager 테스트
  - Zone 점유/해제
  - 충돌 감지
  - Zone 전환

### 14. 통합 테스트

#### 14.1 주문 → 배달 전체 플로우
- [ ] 키오스크에서 주문 생성
- [ ] Main Server가 주문 수신 및 DB 저장
- [ ] FMS가 로봇 할당
- [ ] 로봇이 pickup_spot으로 이동
- [ ] 로봇팔이 조리 및 로딩
- [ ] 로봇이 테이블로 배달
- [ ] 고객이 수령 완료
- [ ] 로봇이 주차 위치로 복귀

#### 14.2 동시 주문 처리
- [ ] 여러 테이블에서 동시 주문 시 로봇 할당 확인
- [ ] Queue 동작 확인
- [ ] 충돌 방지 동작 확인

#### 14.3 에러 시나리오
- [ ] 로봇 통신 끊김 시 동작
- [ ] Navigation 실패 시 동작
- [ ] 데이터베이스 연결 끊김 시 동작

### 15. 성능 테스트

- [ ] 최대 동시 주문 처리 개수 측정
- [ ] 평균 배달 시간 측정
- [ ] 시스템 부하 테스트

## 📋 문서화

### 16. 사용자 매뉴얼

- [ ] 시스템 시작/종료 절차
- [ ] 로봇 초기화 절차 (AMCL 초기 위치 설정)
- [ ] 에러 대응 가이드
- [ ] 일상 운영 체크리스트

### 17. 개발자 문서

- [ ] API 문서 (TCP 메시지 프로토콜)
- [ ] ROS 2 Topics/Messages 명세
- [ ] 데이터베이스 스키마 문서
- [ ] 아키텍처 다이어그램

### 18. 운영 문서

- [ ] 백업 및 복구 절차
- [ ] 모니터링 대시보드 설정
- [ ] 알림 설정 (에러 발생 시)
- [ ] 정기 점검 항목

## 🎯 우선순위 요약

### 즉시 처리 (시스템 실행 전 필수)
1. ✅ **데이터베이스 설정** (섹션 1)
2. ✅ **IP 주소 및 비밀번호 설정** (섹션 2)
3. ✅ **로봇 네임스페이스 설정** (섹션 3)
4. ✅ **맵 좌표 보정** (섹션 4)

### 1주일 내
5. ✅ **Admin GUI 통합** (섹션 5)
6. ✅ **로봇팔 인터페이스 연동** (섹션 6)
7. ✅ **키오스크 통신 구현** (섹션 7)

### 2주일 내
8. ✅ **기본 테스트** (섹션 14.1)
9. ✅ **에러 처리 강화** (섹션 10)

### 지속적 개선
10. ✅ **성능 최적화** (섹션 8, 9)
11. ✅ **모니터링 및 로깅** (섹션 11)
12. ✅ **문서화** (섹션 16, 17, 18)

## 📞 팀 간 협업 필요 사항

### 로봇팔 팀
- [ ] `/robot_arm/cooking_order` Topic 구독 구현 확인
- [ ] `/robot_arm/loading_complete` Topic 발행 구현 확인
- [ ] 서빙 로봇 ID 전달 및 음식 로딩 프로세스 협의

### 키오스크 팀
- [ ] TCP 클라이언트 구현
- [ ] 메시지 프로토콜 문서 공유
- [ ] 주문 상태 UI 연동

### Admin GUI 팀
- [ ] 서빙 로봇 모니터링 탭 UI 디자인
- [ ] TCP 클라이언트 통합
- [ ] Fleet 상태 시각화

### AI Server 팀
- [ ] 음성 주문 처리 후 키오스크로 TTS 전달 확인
- [ ] 키오스크에서 Main Server로 주문 전달 플로우 확인

---

## 📚 개발자 빠른 참조

### 현재 상태 요약

**구현됨:**
- ✅ ROS 2 네임스페이스 아키텍처 (모든 로봇이 /pinky1, /pinky2, /pinky3)
- ✅ 다중 로봇 네비게이션 (bringup_launch.py with RewrittenYaml)
- ✅ FMS 기본 구조 (task_manager, fleet_controller, zone_manager)
- ✅ Skip 모드 (로봇팔 연동 전 테스트용)
- ✅ TCP 통신 기본 구조
- ✅ Admin GUI 기본 (fleet_monitor)
- ✅ 문서화 (CLAUDE.md, README.md, CLAUDE.md 동기화)

**필요한 작업:**
- [ ] YAML 파일에서 동적 설정 로드 (현재 hardcoded)
- [ ] End-to-end 테스트 (skip 모드 포함)
- [ ] 다중 로봇 시나리오 테스트
- [ ] 실제 로봇 하드웨어 테스트
- [ ] 좌표 보정 (실제 맵 측량)

### 빠른 시작 명령어

```bash
# 빌드
cd /home/gw/kitchmatics/roscamp-repo-1
colcon build
source install/setup.bash

# FMS 실행 (skip 모드)
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true

# 테스트 주문 전송
python3 fms/scripts/send_order.py --table 1

# Fleet 상태 모니터링
ros2 topic echo /fms/fleet_status
```

### 주요 파일 위치

| 파일 | 설명 |
|------|------|
| `CLAUDE.md` | 프로젝트 가이드 (네임스페이스 아키텍처) |
| `README.md` | 사용자 설명서 |
| `TODO.md` | 이 파일 (진행 상황 추적) |
| `fms/config/network_config.yaml` | 로봇 IP & 네임스페이스 설정 |
| `fms/config/fms_config.yaml` | FMS 파라미터 & 맵 좌표 |
| `mobile_robot/launch/bringup_launch.py` | 다중 로봇 네비게이션 |
| `mobile_robot/params/nav2_params.yaml` | Nav2 튜닝 파라미터 |

### 문의 사항

- **아키텍처 질문**: CLAUDE.md의 "Current Architecture" 섹션 참조
- **설정 문제**: README.md의 "설정 파일" 섹션 참조
- **테스트 방법**: README.md의 "빠른 시작" 섹션 참조
- **로봇 연결**: README.md의 "Closed Network 구성" 섹션 참조

---

**최종 업데이트**: 2026-02-25 (Documentation Sync)
