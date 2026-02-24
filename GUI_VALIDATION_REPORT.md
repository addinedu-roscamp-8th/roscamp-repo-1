# GUI Specialist 검증 보고서
**작성일**: 2026-02-25
**검증자**: GUI Specialist (Haiku)
**상태**: 상세 검증 완료

---

## 1. Customer GUI 검증

### 1.1 구조 및 아키텍처 ✓

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main.py`

| 항목 | 상태 | 설명 |
|------|------|------|
| 화면 전환 구조 | ✓ 양호 | QStackedWidget 사용으로 메인→메뉴→주문→배달 순서 제어 |
| TCP 클라이언트 통합 | ✓ 양호 | MockOrderServiceClient로 서버 없이 테스트 가능 |
| 시그널/슬롯 연결 | ✓ 양호 | PyQt5 시그널 기반 통신, 느슨한 결합 구현 |
| Mock 모드 | ✓ 우수 | 실제 서버 없이 Mock 데이터로 전체 흐름 테스트 가능 |

**주요 기능**:
- 메인 화면 → 메뉴 선택 → 주문 확인 → 배달 대기 화면 전환
- TCP 기반 주문 전송 및 수령 확인
- 메시지박스를 통한 사용자 피드백
- 타이머 기반 시뮬레이션 (배달 알림 5초 후 표시)

### 1.2 TCP 클라이언트 통신 ✓

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/tcp_client.py`

#### TCPClient 클래스
```python
메시지 형식: JSON 텍스트 + 4바이트 길이 헤더
┌─────────┬──────────────────────────────────┐
│ 4 bytes │ Variable-length JSON message     │
│ (big)   │ {command, table_number, data}    │
└─────────┴──────────────────────────────────┘
```

**통신 흐름**:

| 메서드 | 기능 | 요청 형식 | 응답 형식 |
|--------|------|---------|---------|
| fetch_menus() | 메뉴 조회 | `{command: get_menus, table_number}` | `{status, menus[]}` |
| submit_order() | 주문 전송 | `{command: submit_order, order}` | `{status, order_id}` |
| confirm_delivery() | 수령 확인 | `{command: confirm_delivery, order_id}` | `{status}` |

**검증 결과**:
- ✓ 타임아웃 처리: 5초 설정
- ✓ 메시지 길이 헤더: 4바이트 big-endian
- ✓ JSON 인코딩: utf-8 사용
- ✓ 시그널 통합: QObject를 상속받아 PyQt5 시스템과 통합

#### MockOrderServiceClient 클래스
```python
실제 서버 없이 작동하는 Mock 구현:
- connect(): 항상 True 반환
- fetch_menus(): 3개의 Mock 메뉴 반환
- submit_order(): 타임스탬프 기반 order_id 생성
- confirm_delivery(): 항상 True 반환
```

**테스트 가능성**: 매우 우수 (실제 서버 필요 없음)

### 1.3 사용자 경험 및 UI ✓

**메인 창**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main.py`

```
InitializationEvent
├── setup_ui()
│   ├── MainWindow (초기 화면)
│   ├── MenuSelectionWidget
│   ├── OrderConfirmationWidget
│   ├── DeliveryNotificationWidget
│   └── VoiceFeedbackWidget (오버레이)
│
├── setup_client()
│   └── MockOrderServiceClient.connect()
│
└── connect_signals()
    ├── start_order_signal → on_start_order()
    ├── order_confirmed_signal → on_order_confirmed()
    ├── order_submitted_signal → on_order_submitted()
    ├── delivery_confirmed_signal → on_on_delivery_confirmed()
    └── error_signal → on_client_error()
```

**화면 크기 설정**:
- 기본: 1024x768
- 전체화면: 활성화 (FULLSCREEN=true)
- 환경 변수로 커스터마이징 가능

**언어**: 완전한 한글 지원

---

## 2. Admin GUI 검증

### 2.1 구조 및 아키텍처 ✓

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/main.py`

**탭 기반 인터페이스**:
| 탭 | 역할 | 파일 |
|----|------|------|
| 📊 주문 관제 | 주문 상태 모니터링 | `ui_dashboard.py` |
| 🍳 조리 모니터 | 조리 진행상황 | `ui_cooking_monitor.py` |
| 📖 레시피 관리 | 레시피 CRUD | `ui_recipe_management.py` |
| 📦 재고 관리 | 재고 모니터링 | `ui_stock_management.py` |
| 🚗 서빙 로봇 | 로봇 상태 모니터링 | `ui_fleet_monitor.py` |

**검증 결과**: ✓ 모듈화되고 확장 가능한 구조

### 2.2 Fleet 모니터링 (로봇 상태 표시) ✓

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/ui_fleet_monitor.py`

#### Mobile Robots 탭
```
상태 표시 (PinkyPro):
┌─────────────────────────────────────────┐
│ Fleet 모니터링 - Closed Network         │
│ WiFi: kitchmatics | Server: 192.168.1.3 │
└─────────────────────────────────────────┘

Mobile Robot 통계:
┌──────────┬──────────┬──────────┬──────────┐
│ 전체: 3  │ 연결: 3  │ 대기: 2  │ 작업: 1  │
└──────────┴──────────┴──────────┴──────────┘

로봇 상태 테이블:
┌────────┬─────────┬──────────┬────────┬───────┬──────────┐
│ 로봇명 │ Robot ID│ IP주소   │ 상태   │ 연결  │ 배터리   │
├────────┼─────────┼──────────┼────────┼───────┼──────────┤
│pinky1  │pinky1   │192.168.1.7│대기중 │연결  │24.5V (충분)│
│pinky2  │pinky2   │192.168.1.6│테이블 │연결  │23.8V (보통)│
│pinky3  │pinky3   │192.168.1.11│배달중│연결  │22.1V (부족)│
└────────┴─────────┴──────────┴────────┴───────┴──────────┘
```

**상태 맵핑**:
- `IDLE`: 연한 초록 배경 (대기 중)
- `MOVING_TO_PICKUP`: 연한 노랑 (픽업 이동 중)
- `LOADED`: 연한 파랑 (음식 적재됨)
- `MOVING_TO_TABLE`: 연한 주황 (테이블 이동 중)
- `DELIVERING`: 연한 빨강 (배달 중)
- `RETURNING`: 연한 회색 (복귀 중)
- `ERROR`: 진한 빨강 (에러)

**배터리 상태**:
```python
def get_battery_status(voltage, present):
    if not present: return "미연결" (회색)
    elif voltage >= 24.0: return "충분" (초록)
    elif voltage >= 22.0: return "보통" (노랑)
    elif voltage >= 20.0: return "부족" (주황)
    else: return "위험" (빨강)
```

**네트워크 설정 로드**:
```python
network_config = Config._network_config  # network_config.yaml에서 로드
mobile_robots = network_config.get('mobile_robots', {})
# robot_id, enabled, ip_address 등 설정값 사용
```

#### Cobot Arms 탭
- JetCobot 로봇 상태 모니터링
- 온도 정보 표시
- 조리 중/대기 상태 색상 표시

#### 전체 통계 탭
```
┌──────────────────────┬──────────────────┐
│ 전체 로봇: 3        │ 대기 로봇: 2     │
│ 작업 중: 1          │ 대기 주문: 2     │
│ 진행 중 주문: 1     │                  │
└──────────────────────┴──────────────────┘

이벤트 로그:
[14:23:15] FMS Server 연결됨 (192.168.1.3:9000)
[14:23:16] Fleet 상태 업데이트 수신
[14:23:20] 로봇 pinky1 상태 변경: IDLE
```

### 2.3 TCP 클라이언트 통신

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/fleet_client.py`

#### FleetClient (실제 구현)

**메시지 형식**:
```json
요청: {"type": "fleet_status_query", "data": {}}
응답: {
  "type": "fleet_status_update",
  "data": {
    "robots": [
      {"robot_id": "pinky1", "status": "IDLE", "battery_voltage": 24.5, "battery_present": true},
      {"robot_id": "pinky2", "status": "MOVING_TO_TABLE", "battery_voltage": 23.8, "battery_present": true},
      {"robot_id": "pinky3", "status": "DELIVERING", "battery_voltage": 22.1, "battery_present": true}
    ],
    "pending_orders": 2,
    "active_orders": 1
  }
}
```

**연결 정보**:
- 기본 호스트: `127.0.0.1` (localhost)
- 기본 포트: `9999` (Main Server)
- 타임아웃: 5.0초
- 재연결: 별도 스레드에서 주기적 수신

**API 메서드**:
| 메서드 | 목적 | 요청 타입 |
|--------|------|---------|
| query_fleet_status() | Fleet 전체 상태 조회 | fleet_status_query |
| query_order_status(order_id) | 주문 상태 조회 | order_status_query |
| send_delivery_complete(order_id, table) | 배달 완료 신호 | delivery_complete |

**수신 루프** (별도 스레드):
```python
def _receive_loop(self):
    while self.running:
        data = socket.recv(4096)  # 수신
        if not data: break         # 연결 끊김

        buffer += data
        # JSON 파싱 (불완전한 메시지는 버퍼링)
        message = json.loads(buffer)
        _handle_message(message)  # 처리 및 시그널 발신
```

**시그널**:
```python
connected_signal = pyqtSignal()        # 연결됨
disconnected_signal = pyqtSignal()     # 연결 끊김
error_signal = pyqtSignal(str)         # 에러 메시지
fleet_status_updated = pyqtSignal(dict) # Fleet 상태 업데이트
robot_status_updated = pyqtSignal(dict) # 개별 로봇 상태
order_status_updated = pyqtSignal(dict) # 주문 상태
```

**문제점**: ⚠️ JSON 메시지에 길이 헤더가 없음 (Customer GUI와 프로토콜 불일치)

#### MockFleetClient (테스트 용)

**특징**:
- 서버 없이 작동
- QTimer로 2초마다 Mock 데이터 전송
- 배터리 소모 시뮬레이션
- 충전 시뮬레이션 (< 20V일 때 자동 충전)

**테스트 가능성**: 매우 우수

---

## 3. TCP 프로토콜 검증

### 3.1 메시지 형식 비교

| 구성요소 | Customer GUI | Admin GUI | 상태 |
|---------|-------------|----------|------|
| 길이 헤더 | 4바이트 big-endian | 없음 | ⚠️ 불일치 |
| JSON 형식 | `{command, table_number, data}` | `{type, data}` | ⚠️ 구조 다름 |
| 인코딩 | UTF-8 | UTF-8 | ✓ 일치 |
| 타임아웃 | 5초 | 5초 | ✓ 일치 |

### 3.2 재연결 로직

#### Customer GUI (OrderServiceClient)
```python
- 단순 소켓 연결: socket.connect()
- 타임아웃: 5초
- 재연결 없음 (에러 반환)
```

**문제점**: ⚠️ 연결 끊김 시 자동 재연결 없음

#### Admin GUI (FleetClient)
```python
- 별도 스레드에서 수신 루프 진행
- 타임아웃: 5초
- 연결 끊김 시: disconnect() 호출
- 재연결 메커니즘: 없음 (외부에서 수동)
```

**문제점**: ⚠️ 자동 재연결 기능 부재

### 3.3 에러 핸들링

#### Customer GUI
```python
try:
    socket.sendall(data)
except Exception as e:
    error_signal.emit(str(e))
    return False
```
- ✓ 기본적인 예외 처리
- ⚠️ 세부 에러 타입 구분 없음

#### Admin GUI
```python
try:
    data = socket.recv(4096)
except socket.timeout:
    continue  # 타임아웃은 무시
except Exception as e:
    if self.running:
        print(f'수신 오류: {str(e)}')
    break
```
- ✓ 타임아웃 처리
- ⚠️ 부분 수신 메시지 처리 미흡

---

## 4. ROS_DOMAIN_ID 로봇 상태 표시

### 4.1 현재 구현 상태

**network_config.yaml 설정**:
```yaml
mobile_robots:
  pinky_b4bc:
    robot_id: "pinky1"
    domain_id: 11          # ROS_DOMAIN_ID
    ip_address: "192.168.1.7"
    enabled: true

  pinky_e2a8:
    robot_id: "pinky2"
    domain_id: 12          # ROS_DOMAIN_ID
    ip_address: "192.168.1.6"
    enabled: true

  pinky_d29d:
    robot_id: "pinky3"
    domain_id: 13          # ROS_DOMAIN_ID
    ip_address: "192.168.1.11"
    enabled: true
```

### 4.2 Admin GUI에서의 표시

**로봇 상태 테이블 초기화** (`ui_fleet_monitor.py` 라인 236-251):
```python
for row, (name, cfg) in enumerate(mobile_robots.items()):
    enabled = cfg.get('enabled', False)
    robot_id = cfg.get('robot_id', '-')    # pinky1, pinky2, pinky3
    ip_addr = cfg.get('ip_address', '-')   # 192.168.1.7 등

    table.setItem(row, 1, QTableWidgetItem(robot_id))
    table.setItem(row, 2, QTableWidgetItem(ip_addr))
```

**실시간 상태 업데이트** (`ui_fleet_monitor.py` 라인 454-490):
```python
def update_robot_table(self, robots: list):
    for row, robot in enumerate(robots):
        robot_id = robot.get('robot_id', '-')
        status = robot.get('status', '-')
        battery_voltage = robot.get('battery_voltage', 0.0)
        # ... 테이블 업데이트
```

### 4.3 ROS_DOMAIN_ID 표시 평가

| 항목 | 상태 | 설명 |
|------|------|------|
| Robot ID 표시 | ✓ 양호 | pinky1, pinky2, pinky3로 명확히 표시 |
| IP 주소 표시 | ✓ 양호 | 각 로봇의 IP 주소 표시 |
| Domain ID 표시 | ⚠️ 부족 | network_config.yaml에는 있지만 UI에 표시 안 됨 |
| 로봇 구분 | ✓ 양호 | Robot ID로 충분히 구분 가능 |
| 상태 색상 | ✓ 우수 | 상태별로 색상 구분 |

**개선 제안**: Domain ID도 UI에 표시하면 디버깅 편의성 증대

---

## 5. 문제점 종합 분석

### 5.1 심각한 문제 (Critical)

#### 1. TCP 프로토콜 불일치

**문제**:
- Customer GUI: `[4바이트 길이][JSON]` 형식
- Admin GUI: `[JSON만]` 형식

**영향**:
```
Main Server가 두 가지 형식을 모두 지원해야 함
또는 프로토콜 통일 필요
```

**수정 위치**:
- `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/fleet_client.py` 라인 73-99

#### 2. 자동 재연결 기능 부재

**문제**:
- 네트워크 끊김 시 서버에 자동 재연결 안 함
- 사용자가 수동으로 재시작해야 함

**영향**:
```
Restaurant 환경에서 WiFi 불안정 → 배달 중단
```

**수정 위치**:
- `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/tcp_client.py`
- `/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/fleet_client.py`

#### 3. 메시지 파싱 버퍼 오버플로우 위험

**문제** (fleet_client.py 라인 108-132):
```python
while buffer:
    try:
        message_str = buffer.decode('utf-8')
        message = json.loads(message_str)  # 전체 버퍼를 파싱
        buffer = b''  # 전체 버퍼 초기화
    except json.JSONDecodeError:
        break  # 불완전한 JSON은 다음 recv 대기
```

**문제점**:
- 큰 메시지가 여러 번에 걸쳐 수신되면 누적
- 다음 메시지와 함께 파싱되어 에러 가능성

**해결방안**: 메시지 길이 헤더 추가 필요

---

### 5.2 중대한 문제 (Major)

#### 1. MockOrderServiceClient와 실제 OrderServiceClient 메시지 형식 불일치

**Customer GUI tcp_client.py 라인 216-259**:
```python
class MockOrderServiceClient(OrderServiceClient):
    def fetch_menus(self):
        return mock_menus  # 실제 서버 통신 안 함

    def submit_order(self):
        return order_id  # 실제 전송 안 함
```

**문제**:
- Mock 모드에서 완벽하게 작동하지만
- 실제 서버 전환 시 프로토콜이 맞지 않을 수 있음

#### 2. 에러 메시지가 UI에 표시되지 않을 수 있음

**Customer GUI main.py 라인 233-241**:
```python
def on_client_error(self, error_msg: str):
    QMessageBox.warning(...)
```

**문제**:
- TCP 클라이언트 에러가 발생하면 사용자에게 알려짐
- 하지만 에러 복구 메커니즘 없음
- 사용자는 앱 재시작해야 함

#### 3. Admin GUI의 Fleet 상태 업데이트 빈도 부족

**ui_fleet_monitor.py 라인 62-65**:
```python
self.status_timer = QTimer()
self.status_timer.timeout.connect(self.refresh_fleet_status)
self.status_timer.start(1000)  # 1초마다
```

**문제**:
- 1초 간격이지만 실제로는 MockFleetClient만 2초 간격으로 데이터 보냄
- 실제 FMS와의 동기 필요

---

### 5.3 경미한 문제 (Minor)

#### 1. ROS_DOMAIN_ID를 UI에 표시하지 않음

**ui_fleet_monitor.py 라인 222-225**:
```python
table.setHorizontalHeaderLabels([
    '로봇명', 'Robot ID', 'IP 주소', '상태', '연결',
    '배터리 (V)', '현재 작업', '최종 업데이트'
])
```

**개선안**: Domain ID 컬럼 추가

```python
table.setHorizontalHeaderLabels([
    '로봇명', 'Robot ID', 'Domain ID', 'IP 주소', '상태', ...
])
```

#### 2. Customer GUI에서 배달 알림이 시뮬레이션됨

**main.py 라인 187-189**:
```python
# 시뮬레이션: 5초 후 배달 알림 (실제로는 TCP로 알림 수신)
from PyQt5.QtCore import QTimer
QTimer.singleShot(5000, lambda: self.show_delivery_notification(order))
```

**문제**:
- 실제 FMS로부터 배달 알림을 받는 메커니즘이 구현되지 않음
- 현재는 고정 타이머로 시뮬레이션

**해결방안**: 실제 TCP 수신으로 전환 필요

#### 3. 환경 변수 기본값이 localhost

**config.py 라인 38-43**:
```python
ORDER_MS_HOST = os.getenv('ORDER_MS_HOST', '127.0.0.1')  # localhost 기본
FMS_HOST = _network_config.get('master', {}).get('host', '192.168.1.3')
```

**문제**:
- Order MS는 localhost 기본값
- FMS는 network_config.yaml에서 읽음
- 불일치로 인한 혼동 가능

---

## 6. 실물 로봇 없이 GUI 테스트 가능성

### 6.1 현재 상태

| 시나리오 | Customer GUI | Admin GUI | 평가 |
|---------|-------------|----------|------|
| 메뉴 조회 | ✓ Mock 메뉴 | - | 우수 |
| 주문 전송 | ✓ Mock 전송 | - | 우수 |
| 배달 알림 | ⚠️ 고정 타이머 | ✓ Mock 배터리 | 부분 |
| 로봇 상태 | - | ✓ Mock 상태 | 우수 |
| 수령 확인 | ✓ Mock 확인 | - | 우수 |
| Fleet 모니터링 | - | ✓ Mock 데이터 | 우수 |

### 6.2 Mock 모드 사용 방법

#### Customer GUI 테스트
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src
python3 main.py
```
- 자동으로 `MockOrderServiceClient` 사용
- 메뉴 조회, 주문, 수령 전체 흐름 테스트 가능
- 실제 서버 필요 없음 ✓

#### Admin GUI 테스트
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src
USE_MOCK=true python3 main.py
```
- 환경 변수 `USE_MOCK=true` 설정 (기본값)
- `MockFleetClient` 자동 사용
- 로봇 상태 모니터링 테스트 가능 ✓

### 6.3 개선 필요사항

1. **배달 알림 메커니즘 구현**
   - 실제 FMS로부터 알림 받기
   - 또는 Main Server로부터 수신

2. **실제 서버와의 통신 프로토콜 확정**
   - 길이 헤더 사용 여부
   - 메시지 형식 통일

3. **자동 재연결 기능**
   - 지수 백오프 재시도
   - 최대 재시도 횟수 제한

---

## 7. 코드 품질 평가

| 지표 | 점수 | 설명 |
|------|------|------|
| 모듈화 | 8/10 | 잘 분리되어 있으나 프로토콜 불일치 |
| 테스트 가능성 | 9/10 | Mock 모드로 실물 없이 테스트 가능 |
| 한글화 | 10/10 | 완전한 한글 지원 |
| 에러 처리 | 6/10 | 기본적인 처리만 있고 복구 메커니즘 부족 |
| 문서화 | 7/10 | 코드 주석 있으나 프로토콜 문서 필요 |
| 보안 | 7/10 | 기본 보안이나 인증/암호화 없음 |
| 성능 | 8/10 | UI 반응성 양호, 네트워크 지연 처리 미흡 |

**종합 평가**: 7/10 (양호하나 프로토콜 통일 필요)

---

## 8. 권장 조치 순서

### Phase 1: 긴급 (즉시)
1. **TCP 프로토콜 통일**
   - 모든 클라이언트에 `[4바이트 길이][JSON]` 형식 적용
   - Main Server에서 올바른 파싱 확인

2. **메시지 파싱 버퍼 개선**
   - 길이 헤더로 메시지 경계 명확히
   - 부분 수신 메시지 정확히 처리

### Phase 2: 중요 (1주일 내)
1. **자동 재연결 기능**
   - 지수 백오프: 1초, 2초, 4초, 8초
   - 최대 10회 재시도

2. **배달 알림 메커니즘**
   - FMS로부터의 배달 알림 실제 수신
   - 또는 Main Server를 통한 알림

3. **에러 복구**
   - 사용자 친화적 에러 메시지
   - 자동 또는 수동 복구 옵션

### Phase 3: 개선 (2주일 내)
1. **ROS_DOMAIN_ID 표시**
   - Admin GUI에 Domain ID 컬럼 추가
   - 로봇 디버깅 편의성 향상

2. **성능 최적화**
   - 메시지 배칭
   - 네트워크 압축

3. **테스트 자동화**
   - 통합 테스트 스크립트
   - CI/CD 파이프라인

---

## 9. 파일 목록

### Customer GUI
```
/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/
├── main.py                      # 메인 애플리케이션 (290줄)
├── tcp_client.py                # TCP 클라이언트 (291줄)
├── ui_main_window.py            # 메인 화면 위젯
├── ui_menu_selection.py         # 메뉴 선택 화면
├── ui_order_confirmation.py     # 주문 확인 화면
├── ui_delivery_notification.py  # 배달 알림 화면
├── voice_feedback_widget.py     # 음성 피드백 위젯
└── __init__.py
```

### Admin GUI
```
/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src/
├── main.py                      # 메인 애플리케이션
├── tcp_client.py                # 주문/재고 MS 클라이언트 (621줄)
├── fleet_client.py              # FMS 클라이언트 (288줄)
├── ui_dashboard.py              # 주문 관제 화면
├── ui_cooking_monitor.py        # 조리 모니터 화면
├── ui_recipe_management.py      # 레시피 관리 화면
├── ui_stock_management.py       # 재고 관리 화면
└── ui_fleet_monitor.py          # Fleet 모니터링 (566줄)
```

### Common
```
/home/gw/kitchmatics/roscamp-repo-1/app/gui/common/
├── config.py                    # 설정 관리 (122줄)
├── models.py                    # 데이터 모델 (332줄)
└── __init__.py
```

### Network Configuration
```
/home/gw/kitchmatics/roscamp-repo-1/fms/config/
└── network_config.yaml          # 로봇/서버 설정
```

---

## 10. 결론

### 현황 요약
- ✓ **UI 구조**: 잘 설계되고 모듈화됨
- ✓ **Mock 모드**: 실물 로봇 없이 테스트 가능
- ⚠️ **TCP 프로토콜**: 클라이언트 간 형식 불일치
- ⚠️ **자동 재연결**: 기능 부재
- ⚠️ **배달 알림**: 시뮬레이션만 구현

### 즉시 필요한 조치
1. TCP 프로토콜 통일 (길이 헤더 추가)
2. 메시지 파싱 개선
3. 자동 재연결 기능 구현

### 권장 일정
- **Week 1**: 프로토콜 통일 및 기본 안정성
- **Week 2**: 자동 재연결 및 실제 배달 알림
- **Week 3**: 성능 최적화 및 테스트 자동화

**검증 완료 일시**: 2026-02-25 14:30
**다음 검증**: 프로토콜 통일 후 1주일

---

## 부록 A: Mock 데이터 스키마

### Customer GUI Mock 메뉴
```python
[
    {
        'menu_id': 'M001',
        'name': '햄치즈샌드위치',
        'price': 5000,
        'description': '재료: 빵, 양상추, 토마토, 치즈, 햄',
        'category': '샌드위치',
        'available': True
    },
    ...
]
```

### Admin GUI Mock Fleet 상태
```python
{
    'robots': [
        {
            'robot_id': 'pinky1',
            'status': 'IDLE',
            'battery_voltage': 24.5,
            'battery_present': True
        },
        ...
    ],
    'pending_orders': 2,
    'active_orders': 1
}
```

---

*이 보고서는 2026-02-25에 작성되었습니다.*
*최신 코드 상태: commit 6d87690 (fix(gui): resolve python-dotenv dependency)*
