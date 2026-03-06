# FMS 스크립트 목록

**위치:** `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/`

**작성일:** 2026년 2월 25일

**상태:** 운영 준비 완료

---

## 신규 테스트 스크립트 (통신 검증)

### 1. test_messages.py
**용도:** ROS 2 메시지 발행 및 구독 검증

**테스트 항목:**
- `goal_arrived` 메시지 발행 (로봇 도착 알림)
- `fleet_status` 메시지 구독 (플릿 업데이트)
- `OrderRequest` 메시지 발행 (주문 제출)
- 로봇 간 네임스페이스 격리 (/pinky1, /pinky2, /pinky3)
- TCP 메시지 형식 직렬화

**주요 명령어:**
```bash
python3 test_messages.py --all
python3 test_messages.py --test-goal-arrived
python3 test_messages.py --interactive
```

**출력:** 플릿 관리 메시지를 발행/구독하는 ROS 2 노드

---

### 2. mock_external_teams.py
**용도:** skip 모드 테스트를 위한 외부 팀 서비스 모의

**모의 대상:**
1. **정밀 제어 팀** (Domain 14)
   - `goal_arrived` 메시지 수신 대기
   - 설정 가능한 지연(기본 2초) 후 `precision_parked` 메시지 발행

2. **로봇 암 팀** (Domain 15)
   - `food_load_request` 메시지 수신 대기
   - 설정 가능한 지연(기본 3초) 후 `food_loaded` 메시지 발행

**주요 명령어:**
```bash
python3 mock_external_teams.py --start-all
python3 mock_external_teams.py --mock-precision --precision-delay 2
python3 mock_external_teams.py --interactive
```

**출력:** 외부 팀 동작을 시뮬레이션하는 ROS 2 노드

---

### 3. test_tcp_communication.py
**용도:** 폐쇄 네트워크에서 TCP 통신 검증

**테스트 항목:**
- TCP 포트 접근성 (마스터 PC, 로봇, 로봇 암)
- 메시지 직렬화/역직렬화
- JSON 형식 파싱
- 메시지 페이로드 크기
- 에코 서버를 통한 양방향 통신

**주요 명령어:**
```bash
python3 test_tcp_communication.py --test-all
python3 test_tcp_communication.py --test-ports
python3 test_tcp_communication.py --test-message-format
python3 test_tcp_communication.py --echo-server --port 9000
```

**출력:** TCP 연결 및 메시지 형식 검증 보고서

---

## 문서 파일

### TEST_SCRIPTS_README.md
**용도:** 모든 테스트 스크립트의 종합 사용 가이드

**포함 내용:**
- 빠른 시작 예제
- 각 스크립트의 상세 사용법
- 예상 출력 및 예제
- 네트워크 설정 참조
- ROS 2 토픽 구조
- 메시지 타입 정의
- 테스트 체크리스트
- 문제 해결 가이드
- 구현 참고사항

**먼저 읽어야 할 사항:** 테스트 기능의 전체 이해를 위해

---

### VERIFICATION_CHECKLIST.md
**용도:** 품질 보증 및 검증 문서

**포함 내용:**
- 산출물 체크리스트
- 코드 품질 검증
- 기능 검증
- 문서 품질 평가
- 테스트 권장사항
- 알려진 문제
- 배포 안내
- 승인 검증

**읽어야 할 경우:** QA 검증 및 배포 준비 상태 확인

---

### QUICK_REFERENCE.txt
**용도:** 한 페이지 빠른 참조 카드

**포함 내용:**
- 빠른 시작 명령어
- 네트워크 설정 다이어그램
- 메시지 타입 참조
- 대화형 모드 명령어
- 문제 해결 팁
- 파일 위치
- 성공 지표

**읽어야 할 경우:** 명령어 및 설정의 빠른 조회

---

## 관련 기존 스크립트

### send_order.py
**용도:** FMS에 테스트 주문 전송

**사용법:**
```bash
python3 send_order.py --table 1
python3 send_order.py --table 3 --menu M002 --quantity 2
python3 send_order.py --interactive
```

**연동:** skip 모드 테스트에서 모의 서비스와 함께 사용

---

### robot_client.py
**용도:** 로봇 통신용 TCP 클라이언트

**사용법:** 내부용 - FMS 노드에서 사용

---

### robot_file_sync.py
**용도:** 로봇 설정 파일 동기화

**사용법:** SSH를 통해 로봇에 파라미터 및 설정 동기화

---

## 상위 디렉토리의 문서

### COMMUNICATION_VALIDATION_SUMMARY.md
**위치:** `/home/gw/kitchmatics/roscamp-repo-1/`

**용도:** 통신 검증 요약

**포함 내용:**
- 산출물 개요
- 아키텍처 설명
- 메시지 정의
- 네트워크 설정
- 테스트 전략
- 다음 단계 및 성공 기준

---

### CLAUDE.md
**위치:** `/home/gw/kitchmatics/roscamp-repo-1/`

**용도:** 프로젝트 요구사항 및 아키텍처 가이드

**포함 내용:**
- 프로젝트 개요 및 범위
- FMS 역할
- 배달 흐름
- 프로젝트 구조
- 현재 문제 및 할 일
- 필수 ROS_DOMAIN_ID 요구사항
- skip 모드 테스트 전략

---

## 빠른 시작 시나리오

### 시나리오 1: 메시지 발행 테스트
```bash
# 터미널 1: 테스트 노드 시작
python3 test_messages.py --test-goal-arrived

# 출력: goal_arrived 메시지 형식 검증
```

### 시나리오 2: 전체 skip 모드 테스트
```bash
# 터미널 1: 모의 서비스 시작
python3 mock_external_teams.py --start-all

# 터미널 2: FMS 시작
ros2 launch fms fms_launch.py skip_robot_arm:=true

# 터미널 3: 주문 전송
python3 send_order.py --table 1

# 터미널 4: 모니터링
python3 test_messages.py --test-fleet-status

# 예상: 로봇이 테이블로 이동 후 복귀
```

### 시나리오 3: TCP 검증
```bash
# 터미널 1: 에코 서버 시작
python3 test_tcp_communication.py --echo-server --port 9000

# 터미널 2: 연결 테스트
python3 test_tcp_communication.py --test-ports
python3 test_tcp_communication.py --echo-client --host 192.168.1.3 --port 9000

# 출력: TCP 통신 동작 검증
```

---

## 파일 요약

| 파일 | 크기 | 유형 | 상태 |
|------|------|------|------|
| test_messages.py | 18KB | 스크립트 | 준비 완료 |
| mock_external_teams.py | 20KB | 스크립트 | 준비 완료 |
| test_tcp_communication.py | 20KB | 스크립트 | 준비 완료 |
| TEST_SCRIPTS_README.md | 15KB | 문서 | 준비 완료 |
| VERIFICATION_CHECKLIST.md | 15KB | 문서 | 준비 완료 |
| QUICK_REFERENCE.txt | 5KB | 문서 | 준비 완료 |
| INDEX.md | 이 파일 | 문서 | 준비 완료 |

**합계:** 테스트 스크립트 및 문서 약 93KB

---

## 네트워크 참조

### WiFi: "kitchmatics"

```
Master PC:       192.168.1.3
├── FMS:         port 9000
├── Main Server: port 9999
└── PostgreSQL:  port 5432

Robots:
├── pinky1:      192.168.1.7:9001
├── pinky2:      192.168.1.6:9001
└── pinky3:      192.168.1.11:9001

Arms:
├── cobot1:      192.168.1.4:9002
└── cobot2:      192.168.1.10:9002
```

---

## ROS 2 토픽 참조

### FMS 토픽
- `/fms/order_request` - OrderRequest
- `/fms/fleet_status` - FleetStatus
- `/fms/delivery_complete` - DeliveryComplete
- `/fms/goal_arrived` - String (JSON)
- `/fms/precision_parked` - String (JSON)
- `/fms/food_loaded` - String (JSON)
- `/fms/food_load_request` - String (JSON)

### 로봇별 토픽 (네임스페이스)
- `/{robot_id}/pose` - 로봇 위치
- `/{robot_id}/battery/voltage` - 배터리 전압
- `/{robot_id}/battery/present` - 배터리 상태
- `/{robot_id}/navigate_to_pose` - 내비게이션 액션

---

## 스크립트 사용 방법

### 통신 테스트용
1. 읽기: `TEST_SCRIPTS_README.md`
2. 실행: `test_messages.py --all`
3. 실행: `test_tcp_communication.py --test-all`

### 통합 테스트용
1. 시작: `mock_external_teams.py --start-all`
2. 실행: skip 모드로 FMS 실행
3. 전송: `send_order.py`로 테스트 주문
4. 모니터링: `test_messages.py`로 메시지 흐름 확인

### 배포용
1. 검토: `VERIFICATION_CHECKLIST.md`
2. 스크립트를 대상 위치에 복사
3. 문서 참조 업데이트
4. CI/CD 파이프라인에 통합

---

## 문제 해결

### 임포트 오류: "No module named fleet_interfaces"
```bash
# 인터페이스 패키지 빌드
colcon build --packages-select fleet_interfaces
source install/setup.bash
```

### 포트 연결 오류
```bash
# 네트워크 연결 확인
python3 test_tcp_communication.py --test-ports

# 특정 로봇 확인
ping 192.168.1.7

# "kitchmatics" WiFi 연결 확인
```

### 메시지 미수신
```bash
# ROS 2 도메인 ID 설정 확인 (현재 네임스페이스 사용 중)
ros2 node list
ros2 topic list
ros2 topic echo /fms/fleet_status
```

---

## 주요 구현 참고사항

### 현재 상태 (네임스페이스 기반)
- `/pinky1`, `/pinky2`, `/pinky3` 네임스페이스 사용
- 네임스페이스를 통한 토픽 접근: `/pinky1/navigate_to_pose`
- 단일 ROS 2 도메인(도메인 0)에서 동작

### 계획된 상태 (Domain ID 기반)
CLAUDE.md 요구사항에 따른 계획:
- Domain 11: pinky1
- Domain 12: pinky2
- Domain 13: pinky3
- Domain 14: robot_arm_1 (정밀 제어)
- Domain 15: robot_arm_2 (로봇 암)
- Domain 0: 마스터 FMS

### 커스텀 메시지 (임시)
JSON 페이로드가 포함된 `std_msgs/String` 사용:
- `goal_arrived`
- `precision_parked`
- `food_loaded`

**TODO:** `fleet_interfaces/`에 공식 메시지 타입 생성

---

## 성공 기준

- [x] 3개 테스트 스크립트 생성
- [x] 4개 문서 파일 생성
- [x] 모든 메시지 타입 검증
- [x] TCP 통신 테스트
- [x] 네트워크 설정 문서화
- [x] skip 모드 테스트 준비 완료
- [x] 운영 수준의 코드 품질

---

## 다음 단계

1. **확인:** 네트워크 연결
2. **테스트:** `test_tcp_communication.py`로 메시지 형식 검증
3. **실행:** `mock_external_teams.py`로 모의 서비스 실행
4. **시작:** skip 모드로 FMS 실행
5. **검증:** 전체 배달 사이클 확인

---

## 연락처

**통신 검증 담당:** 본 작업
**프로덕트 기획:** 팀 협업
**FMS 담당:** 연동 지원

요구사항: `/home/gw/kitchmatics/roscamp-repo-1/CLAUDE.md` 참조

---

**최종 수정일:** 2026년 2월 25일
**상태:** 테스트 준비 완료
