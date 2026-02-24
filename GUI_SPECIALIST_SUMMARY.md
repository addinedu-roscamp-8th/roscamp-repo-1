# GUI Specialist 검증 종합 요약

**검증 일시**: 2026-02-25 14:30
**검증자**: GUI Specialist (Haiku)
**상태**: 완료

---

## 핵심 결론

Kitchmatics FMS GUI 시스템은 **구조적으로 우수**하며 **실물 로봇 없이 완전히 테스트 가능**합니다. 다만 **즉시 수정이 필요한 3가지 Critical 문제**가 있습니다.

---

## 1. 시스템 평가

### 1.1 강점 (Strengths)

| 영역 | 평가 | 설명 |
|------|------|------|
| **UI 구조** | 9/10 | 모듈화되고 확장 가능한 설계 |
| **Mock 모드** | 9/10 | 서버 없이 완전한 기능 테스트 가능 |
| **사용자 경험** | 8/10 | 한글화 완벽, 자연스러운 흐름 |
| **코드 품질** | 8/10 | PEP8 준수, 타입 힌트 사용 |
| **신호/슬롯** | 8/10 | PyQt5 기반 느슨한 결합 |
| **테스트 용이성** | 9/10 | Mock 클라이언트로 실물 없이 테스트 |

### 1.2 약점 (Weaknesses)

| 영역 | 심각도 | 문제 |
|------|--------|------|
| **TCP 프로토콜** | 🔴 Critical | Customer/Admin 클라이언트 형식 불일치 |
| **자동 재연결** | 🔴 Critical | 네트워크 끊김 시 수동 재시작 필요 |
| **배달 알림** | 🟠 Major | 5초 타이머로만 시뮬레이션 |
| **에러 복구** | 🟠 Major | 에러 발생 후 복구 메커니즘 부재 |
| **Domain ID 표시** | 🟡 Minor | UI에 표시되지 않음 |

---

## 2. 파일 구조 및 역할

```
/home/gw/kitchmatics/roscamp-repo-1/
├── app/gui/
│   ├── customer_gui/src/
│   │   ├── main.py                 # 290줄 - Customer GUI 메인
│   │   ├── tcp_client.py           # 291줄 - TCP 통신 (Mock 포함)
│   │   └── ui_*.py                 # UI 위젯들
│   │
│   ├── admin_gui/src/
│   │   ├── main.py                 # Admin GUI 메인
│   │   ├── fleet_client.py         # 288줄 - FMS TCP 클라이언트 (Mock 포함)
│   │   ├── tcp_client.py           # 621줄 - 주문/재고 MS 클라이언트
│   │   └── ui_fleet_monitor.py     # 566줄 - Fleet 모니터링 UI
│   │
│   └── common/
│       ├── config.py               # 122줄 - 네트워크 설정 관리
│       └── models.py               # 332줄 - 데이터 모델
│
└── fms/config/
    └── network_config.yaml         # 로봇/서버 설정 (domain_id 포함)
```

### 2.1 Customer GUI 아키텍처

```
CustomerGUIApp (QStackedWidget)
├── MockOrderServiceClient (TCP 통신)
│   ├── connect() → MockOrderServiceClient 사용
│   ├── fetch_menus() → 3개 메뉴 반환
│   ├── submit_order() → order_id 생성
│   └── confirm_delivery() → True 반환
│
└── 화면 전환
    ├── MainWindow (초기)
    ├── MenuSelectionWidget
    ├── OrderConfirmationWidget
    └── DeliveryNotificationWidget
```

### 2.2 Admin GUI 아키텍처

```
AdminGUIApp (QMainWindow)
└── 5개 탭
    ├── DashboardWidget (주문 관제)
    ├── CookingMonitorWidget (조리 모니터)
    ├── RecipeManagementWidget (레시피)
    ├── StockManagementWidget (재고)
    └── FleetMonitorWidget (로봇 상태)
        ├── MockFleetClient (TCP 통신)
        │   ├── connect() → Mock 연결
        │   ├── 2초마다 Mock 데이터 전송
        │   └── 배터리 소모 시뮬레이션
        │
        └── 로봇 상태 테이블
            ├── Mobile Robots (pinky1~3)
            └── Cobot Arms (cobot1~2)
```

---

## 3. TCP 통신 프로토콜 분석

### 3.1 현재 상황 (불일치)

**Customer GUI** (tcp_client.py 라인 70-71):
```
[4바이트 길이 (big-endian)] [JSON 메시지]
```

**Admin GUI** (fleet_client.py 라인 93-94):
```
[JSON 메시지만]
```

### 3.2 메시지 예시

**고객 주문** (Customer):
```
길이: 00000047 (71바이트)
JSON: {"command": "submit_order", "order": {...}}
```

**Fleet 상태** (Admin):
```json
{"type": "fleet_status_update", "data": {"robots": [...]}}
```

### 3.3 Main Server의 문제

```
✗ 문제: 두 가지 형식을 모두 처리해야 함
✓ 해결: 모든 클라이언트를 [길이][JSON] 형식으로 통일
```

---

## 4. ROS_DOMAIN_ID 로봇 구분

### 4.1 network_config.yaml의 설정

```yaml
mobile_robots:
  pinky_b4bc:     robot_id: pinky1    domain_id: 11
  pinky_e2a8:     robot_id: pinky2    domain_id: 12
  pinky_d29d:     robot_id: pinky3    domain_id: 13

cobot_arms:
  jetcobot_aa1f:  robot_id: cobot1    domain_id: 14
  jetcobot_aa85:  robot_id: cobot2    domain_id: 15
```

### 4.2 Admin GUI에서의 표시

| 항목 | 현재 | 평가 |
|------|------|------|
| Robot ID | ✓ pinky1, 2, 3 | 명확함 |
| IP 주소 | ✓ 192.168.x.x | 명확함 |
| Domain ID | ✗ 표시 안 됨 | 개선 필요 |
| 상태 색상 | ✓ 상태별 색상 | 우수 |

---

## 5. 테스트 가능성 (Critical)

### 5.1 실물 로봇 없이 가능한 항목

| 기능 | Customer GUI | Admin GUI | 테스트 시간 |
|------|-------------|----------|----------|
| 메뉴 조회 | ✓ Mock | - | 1분 |
| 주문 전송 | ✓ Mock | - | 1분 |
| 수령 확인 | ✓ Mock | - | 1분 |
| 로봇 모니터링 | - | ✓ Mock | 3분 |
| 배터리 상태 | - | ✓ Mock | 1분 |
| Fleet 상태 | - | ✓ Mock | 2분 |
| 배달 알림 | ⚠️ 시뮬레이션만 | - | 2분 |

### 5.2 테스트 명령어

```bash
# Customer GUI (Mock 자동)
python3 /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main.py

# Admin GUI (Mock 자동)
USE_MOCK=true python3 /home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/main.py

# 전체 테스트 소요 시간: 30분
```

---

## 6. Critical 문제 3가지

### 🔴 Issue #1: TCP 프로토콜 불일치

**파일**:
- Customer: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/tcp_client.py` 라인 60-81
- Admin: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/fleet_client.py` 라인 73-99

**영향**: Main Server가 모든 메시지 형식을 처리해야 함 (불가능)

**해결시간**: 2시간

**우선순위**: 🔴🔴🔴 즉시 필요

---

### 🔴 Issue #2: 메시지 파싱 버퍼 오버플로우

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/fleet_client.py` 라인 115-132

**문제**: 불완전한 JSON 메시지가 버퍼에 누적됨

**영향**: 메모리 누적, 메시지 손실 가능

**해결**: Issue #1 해결 시 자동 해결됨

**우선순위**: 🔴🔴🔴 즉시 필요

---

### 🔴 Issue #3: 자동 재연결 기능 부재

**파일**:
- Customer: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/tcp_client.py`
- Admin: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/fleet_client.py`

**문제**: 네트워크 끊김 시 자동 재연결 안 함

**영향**: WiFi 불안정한 Restaurant 환경에서 배달 중단

**해결**: 지수 백오프 재시도 구현 (1, 2, 4, 8, 16, 32초)

**해결시간**: 2.5시간

**우선순위**: 🔴🔴🔴 즉시 필요

---

## 7. Major 문제 2가지

### 🟠 Issue #4: 배달 알림 시뮬레이션

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main.py` 라인 187-189

**현재**: 고정 5초 타이머로 배달 알림 표시

**필요**: FMS로부터 실제 배달 알림 수신

**해결시간**: 2.5시간

**우선순위**: 🟠🟠 1주일 내

---

### 🟠 Issue #5: 에러 복구 메커니즘 부재

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main.py` 라인 233-241

**현재**: 에러 메시지만 표시, 자동 재연결 없음

**필요**: 자동 재연결 + 사용자 안내

**해결시간**: 1시간 (Issue #3 완료 후)

**우선순위**: 🟠🟠 1주일 내

---

## 8. Minor 문제

### 🟡 Issue #6: ROS_DOMAIN_ID UI 표시 부재

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/ui_fleet_monitor.py` 라인 222-225

**현재**: Robot ID와 IP 주소만 표시

**필요**: Domain ID도 함께 표시 (디버깅 편의)

**해결시간**: 30분

**우선순위**: 🟡 2주일 내

---

## 9. 구현 일정

```
Week 1: Critical 이슈 해결
├─ 월: TCP 프로토콜 통일 (2시간)
├─ 화: 프로토콜 테스트 (1.5시간)
├─ 수: 자동 재연결 구현 (2.5시간)
└─ 목: 재연결 테스트 및 배포 (1.5시간)

Week 2: Major 이슈 해결
├─ 월: 배달 알림 구현 (2.5시간)
├─ 화: 배달 알림 테스트 (1.5시간)
├─ 수: 에러 복구 구현 (1시간)
└─ 목: 종합 테스트 및 배포 (1시간)

Week 3: Minor 이슈 해결
├─ 월: Domain ID UI 추가 (30분)
└─ 화: 최종 테스트 및 배포 (15분)
```

---

## 10. 코드 스니펫 (수정 예시)

### 10.1 TCP 프로토콜 통일 (Admin GUI)

**Before**:
```python
def send_request(self, message_type: str, data: dict) -> bool:
    json_data = json.dumps(message, ensure_ascii=False)
    self.socket.sendall(json_data.encode('utf-8'))  # 길이 헤더 없음
```

**After**:
```python
def send_request(self, message_type: str, data: dict) -> bool:
    json_data = json.dumps(message, ensure_ascii=False)
    message_bytes = json_data.encode('utf-8')

    # 길이 헤더 추가 (Customer GUI와 동일)
    length_header = len(message_bytes).to_bytes(4, byteorder='big')
    self.socket.sendall(length_header + message_bytes)
```

### 10.2 자동 재연결 (지수 백오프)

```python
RECONNECT_DELAYS = [1, 2, 4, 8, 16, 32]  # 초
MAX_RECONNECT_ATTEMPTS = 10

for attempt in range(MAX_RECONNECT_ATTEMPTS):
    delay = RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS)-1)]
    print(f"재연결 시도 {attempt+1}/{MAX_RECONNECT_ATTEMPTS}, {delay}초 대기")

    time.sleep(delay)

    if self._try_connect():
        print("재연결 성공!")
        return True

print("재연결 실패 (최대 시도 횟수 초과)")
```

### 10.3 ROS_DOMAIN_ID UI 표시

**Before**:
```python
table.setHorizontalHeaderLabels([
    '로봇명', 'Robot ID', 'IP 주소', '상태', ...
])
```

**After**:
```python
table.setHorizontalHeaderLabels([
    '로봇명', 'Robot ID', 'Domain ID', 'IP 주소', '상태', ...
])
# Domain ID를 config에서 읽어서 표시
domain_id = cfg.get('domain_id', '-')
table.setItem(row, 2, QTableWidgetItem(str(domain_id)))
```

---

## 11. 최종 체크리스트

### 검증 완료 항목
- [x] Customer GUI 코드 리뷰 (290줄)
- [x] Admin GUI 코드 리뷰 (전체 UI 파일)
- [x] TCP 클라이언트 프로토콜 분석
- [x] Mock 모드 테스트 가능성 확인
- [x] ROS_DOMAIN_ID 사용 확인
- [x] 네트워크 설정 로드 검증
- [x] 에러 핸들링 분석
- [x] 문제점 종합 분석

### 배포 전 필수 체크
- [ ] TCP 프로토콜 통일 완료
- [ ] 자동 재연결 구현 완료
- [ ] 배달 알림 메커니즘 완료
- [ ] 통합 테스트 통과
- [ ] 실제 FMS와의 통신 테스트
- [ ] 배포 전 QA 검수

---

## 12. 참고 문서

생성된 상세 문서:

| 문서 | 목적 | 크기 |
|------|------|------|
| `GUI_VALIDATION_REPORT.md` | 상세 검증 보고서 | ~200줄 |
| `GUI_ISSUES_AND_FIXES.md` | 문제점 및 수정방안 | ~400줄 |
| `GUI_TEST_GUIDE.md` | 실물 없이 테스트하기 | ~300줄 |

---

## 13. 권장사항 (Executive Summary)

### 🎯 즉시 조치 (1주일)

1. **TCP 프로토콜 통일**: 모든 클라이언트를 `[길이][JSON]` 형식으로 수정
   - 담당: Backend Lead
   - 시간: 2시간
   - 위험도: 낮음 (기존 코드와 동일 로직)

2. **자동 재연결**: 지수 백오프로 최대 10회 재시도
   - 담당: GUI Specialist
   - 시간: 2.5시간
   - 위험도: 낮음 (추가 기능)

### 📋 추가 조치 (2주일)

3. **배달 알림**: FMS로부터 실제 알림 수신
   - 담당: Backend Lead + GUI
   - 시간: 2.5시간
   - 위험도: 중간 (FMS 연동)

4. **에러 복구**: 자동 재연결 연동 및 사용자 안내
   - 담당: GUI Specialist
   - 시간: 1시간
   - 위험도: 낮음 (UI 개선)

### ✨ 개선 (3주일)

5. **Domain ID 표시**: Admin GUI에 Domain ID 컬럼 추가
   - 담당: GUI Specialist
   - 시간: 30분
   - 위험도: 없음 (UI 추가)

---

## 14. 결론

**Kitchmatics FMS GUI는 구조적으로 우수하고 실물 로봇 없이 완전히 테스트 가능합니다.**

- ✅ Mock 모드로 실물 없이 전체 기능 테스트 가능
- ✅ 모듈화된 구조로 유지보수 용이
- ✅ 완전한 한글화로 사용자 경험 우수
- ✅ PyQt5 기반 안정적인 UI 구현

다만, **3가지 Critical 문제를 즉시 해결해야** 프로덕션 환경에서 안정적으로 운영할 수 있습니다. **1주일이면 모든 Critical 이슈 해결 가능**합니다.

---

**작성일**: 2026-02-25
**검증자**: GUI Specialist (Haiku)
**승인 대기**: Team Lead

다음 단계: TCP 프로토콜 통일 작업 착수
