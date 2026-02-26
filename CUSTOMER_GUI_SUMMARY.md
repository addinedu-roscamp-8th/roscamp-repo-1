# Customer GUI 분석 최종 요약

## 빠른 참조 (Quick Reference)

### 파일 위치
```
/home/gw/kitchmatics/roscamp-repo-1/app/gui/
├── customer_gui/src/
│   ├── main_fms_direct.py           ← 메인 애플리케이션 (화면 전환 관리)
│   ├── fms_client.py                ← FMS 통신 (TCP 소켓)
│   ├── ui_main_window.py            ← 메인 화면 (주문 시작)
│   ├── ui_menu_selection.py         ← 메뉴 선택 화면
│   ├── ui_order_confirmation.py     ← 주문 확인 화면
│   └── ui_delivery_notification.py  ← 배달 알림/수령 확인 화면
└── common/
    ├── config.py                     ← 설정 (FMS 주소, 테이블 번호 등)
    └── models.py                     ← 데이터 모델 (Order, MenuItem 등)
```

### 핵심 클래스
```
CustomerGUIApp (main_fms_direct.py)
  ├─ MainWindow (메인 화면)
  ├─ MenuSelectionWidget (메뉴 선택)
  ├─ OrderConfirmationWidget (주문 확인)
  ├─ DeliveryNotificationWidget (배달 알림)
  └─ FMSOrderServiceClient (FMS 통신)
       └─ FMSTCPClient (TCP 소켓)
```

---

## 아키텍처 다이어그램

### 시스템 전체 구조
```
┌─────────────────────────────────────────────────────────────┐
│                     Customer GUI (PyQt5)                      │
├─────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Main Screen │→ │ Menu Select  │→ │ Order Confirm│        │
│  │ (시작 화면)   │  │ (메뉴 선택)   │  │ (주문 확인)   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│         ↑                                    ↓                  │
│  ┌──────────────────────────────────────────────────┐         │
│  │    Delivery Notification (배달 알림)             │         │
│  │    ┌─────────────────────────────────┐          │         │
│  │    │ [깜빡이는 애니메이션]             │          │         │
│  │    │ 주문 번호 표시                    │          │         │
│  │    │ [수령 완료] 버튼                  │          │         │
│  │    └─────────────────────────────────┘          │         │
│  └──────────────────────────────────────────────────┘         │
│         ↑                                                       │
├─────────────────────────────────────────────────────────────┤
│ Application Layer                                              │
│ ┌────────────────────────────────────────────────────────┐   │
│ │      FMSOrderServiceClient (PyQt Signal 기반)          │   │
│ │  - submit_order(Order) → order_id                      │   │
│ │  - confirm_delivery(order_id, table) → bool            │   │
│ │  - 메시지 수신: delivery_notification_signal 발행      │   │
│ └────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ Infrastructure Layer                                           │
│ ┌────────────────────────────────────────────────────────┐   │
│ │         FMSTCPClient (TCP 소켓 통신)                    │   │
│ │  - connect() / disconnect()                            │   │
│ │  - send_message(dict) → bool                          │   │
│ │  - 백그라운드 스레드에서 메시지 수신                    │   │
│ └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
            ↕ TCP Socket (4-byte header + JSON)
┌─────────────────────────────────────────────────────────────┐
│              FMS (Fleet Management System)                    │
│         (192.168.1.3:9000)                                    │
└─────────────────────────────────────────────────────────────┘
```

### 메시지 흐름

#### 1. 주문 생성 및 전송
```
MainWindow
   ↓ [주문 시작 클릭]
MenuSelectionWidget
   ├─ 메뉴 더블클릭 → MenuItemDialog (소스 선택)
   ├─ [장바구니에 추가] → Order.items 추가
   ├─ 반복...
   └─ [주문 확인] → order_confirmed_signal 발행
     ↓
OrderConfirmationWidget
   ├─ Order 내용 표시 (영수증 형태)
   └─ [주문하기] → order_submitted_signal 발행
     ↓
FMSOrderServiceClient.submit_order(Order)
   ├─ Order ID 생성 (UUID)
   ├─ TCP 메시지 생성:
   │  {
   │      'type': 'new_order',
   │      'table_number': 1,
   │      'data': {
   │          'order_id': 'ORD-...',
   │          'items': [
   │              {
   │                  'menu_id': 'M001',
   │                  'name': '햄치즈샌드위치',
   │                  'quantity': 2,
   │                  'price': 5000,
   │                  'sauce': '마요네즈'
   │              }
   │          ],
   │          'table_number': 1,
   │          'total_price': 10000
   │      }
   │  }
   ├─ FMSTCPClient.send_message(message)
   └─ 성공 → pending_order 저장, 메인 화면으로 복귀
```

#### 2. 배달 알림 수신 및 수령 확인
```
FMS 포트 9000 ←→ TCP 리스너 스레드
   ↓ [배달 알림 메시지 수신]
   {
       'type': 'delivery_notification',
       'data': {
           'order_id': 'ORD-...',
           'table_number': '1',
           'robot_id': 'pinky1'
       }
   }
   ↓
FMSOrderServiceClient._handle_message()
   ├─ 메시지 타입 확인
   └─ delivery_notification_signal 발행
     ↓
CustomerGUIApp.on_delivery_notification_received()
   ├─ Order ID 검증 (현재 주문과 비교)
   ├─ 테이블 번호 검증
   └─ 일치 → show_delivery_notification()
     ↓
DeliveryNotificationWidget
   ├─ [깜빡이는 애니메이션 시작]
   ├─ 주문 정보 표시
   └─ [수령 완료] 버튼 클릭 → delivery_confirmed_signal 발행
     ↓
CustomerGUIApp.on_delivery_confirmed()
   ├─ FMSOrderServiceClient.confirm_delivery(order_id, table_number)
   └─ TCP 메시지 전송:
      {
          'type': 'delivery_complete',
          'data': {
              'order_id': 'ORD-...',
              'table_number': '1'
          }
      }
   ├─ 성공 메시지 표시
   └─ 메인 화면으로 복귀
```

---

## TCP 통신 프로토콜

### 메시지 구조
```
[4-byte Length Header (Big-Endian)] + [JSON Body (UTF-8)]

예시:
┌───────────────────────────────────────┐
│ 00 00 01 2A (길이: 298 bytes)         │ ← Header
├───────────────────────────────────────┤
│ {                                     │
│   "type": "new_order",               │
│   "table_number": 1,                 │
│   "data": {                          │
│     "order_id": "ORD-1234567890ABC", │
│     "items": [...],                  │
│     ...                              │
│   }                                  │
│ }                                     │ ← JSON Body
└───────────────────────────────────────┘
```

### 메시지 타입

| 방향 | 타입 | 포맷 |
|------|------|------|
| GUI → FMS | `new_order` | `{'type': 'new_order', 'table_number': int, 'data': {...}}` |
| GUI → FMS | `delivery_complete` | `{'type': 'delivery_complete', 'data': {...}}` |
| FMS → GUI | `delivery_notification` | `{'type': 'delivery_notification', 'data': {...}}` |

---

## 데이터 모델

### Order (주문)
```python
@dataclass
class Order:
    table_number: int           # 테이블 번호
    items: List[OrderItem]      # 주문 항목 리스트
    order_id: Optional[str]     # 주문 ID (ORD-...)
    status: OrderStatus         # 상태 (pending, confirmed, ...)
    created_at: Optional[datetime]  # 생성 시간
    total_price: int            # 총 금액

    def calculate_total() → int  # 합계 계산
    def add_item(MenuItem, quantity) → None
    def update_quantity(menu_id, quantity) → None
```

### OrderItem (장바구니 항목)
```python
@dataclass
class OrderItem:
    menu_item: MenuItem         # 메뉴
    quantity: int = 1           # 수량
    sauce: str = ""             # 소스 선택

    def get_subtotal() → int    # 항목별 소계
```

### MenuItem (메뉴)
```python
@dataclass
class MenuItem:
    menu_id: str                # M001, M002, ...
    name: str                   # 메뉴 이름
    price: int                  # 가격 (원)
    description: str            # 설명
    image_url: str              # 이미지 URL
    available: bool             # 제공 가능 여부
    category: str               # 카테고리
```

---

## 설정 (Config)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/common/config.py`

### 주요 설정값

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `FMS_HOST` | `192.168.1.3` | FMS 서버 주소 |
| `FMS_PORT` | `9000` | FMS 서버 포트 |
| `TABLE_NUMBER` | `1` | 테이블 번호 (CLI: `--table`) |
| `SCREEN_WIDTH` | `1024` | 화면 너비 |
| `SCREEN_HEIGHT` | `768` | 화면 높이 |
| `FULLSCREEN` | `true` | 전체화면 모드 |

### 환경 변수 설정
```bash
# .env 파일 또는 환경 변수
FMS_HOST=192.168.1.3
FMS_PORT=9000
TABLE_NUMBER=1
FULLSCREEN=true
```

### 명령줄 인자
```bash
python main_fms_direct.py --table 2 --mock
```

---

## PyQt Signal-Slot 연결

### 시그널 정의 및 연결
```python
class MainWindow(QMainWindow):
    start_order_signal = pyqtSignal()
    table_selected_signal = pyqtSignal(int)

class MenuSelectionWidget(QWidget):
    order_confirmed_signal = pyqtSignal(Order)
    cancel_signal = pyqtSignal()

class OrderConfirmationWidget(QWidget):
    order_submitted_signal = pyqtSignal(Order)
    back_signal = pyqtSignal()

class DeliveryNotificationWidget(QWidget):
    delivery_confirmed_signal = pyqtSignal(dict)

class FMSOrderServiceClient(QObject):
    error_signal = pyqtSignal(str)
    delivery_notification_signal = pyqtSignal(dict)

# main_fms_direct.py에서 연결
window.main_window.start_order_signal.connect(window.on_start_order)
window.menu_selection.order_confirmed_signal.connect(window.on_order_confirmed)
window.fms_client.delivery_notification_signal.connect(window.on_delivery_notification_received)
```

---

## 문제점 요약표

| # | 문제점 | 영향 | 심각도 | 상태 |
|---|--------|------|--------|------|
| 1 | 소스 정보 미전송 | 조리 품질 저하 | 높음 | 🔴 미수정 |
| 2 | 메시지 포맷 불일치 | FMS 호환성 | 중간 | 🔴 미수정 |
| 3 | 테이블 동적 선택 불가 | 사용성 저하 | 중간 | 🔴 미수정 |
| 4 | 재시도 로직 없음 | 네트워크 안정성 | 중간 | 🔴 미수정 |
| 5 | 배달 알림 검증 불완전 | 잘못된 주문 표시 | 낮음 | 🔴 미수정 |
| 6 | 피드백 부족 | UX 저하 | 낮음 | 🔴 미수정 |
| 7 | Order ID 생성 취약 | 주문 ID 충돌 | 낮음 | 🔴 미수정 |

---

## 실행 방법

### 기본 실행
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src
python main_fms_direct.py
```

### 테이블 번호 지정
```bash
python main_fms_direct.py --table 2
```

### Mock 모드 (FMS 없이 로컬 테스트)
```bash
python main_fms_direct.py --mock
```

### 옵션 조합
```bash
python main_fms_direct.py --table 3 --mock
```

---

## 의존성

### 필수 라이브러리
```
PyQt5
PyYAML
python-dotenv (선택사항)
```

### 설치
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui
pip install -r requirements.txt
```

---

## 디버깅 팁

### 1. 로그 출력 확인
모든 주요 이벤트는 콘솔에 출력됨:
```
[App] 주문 시작
[MenuSelection] 메뉴 추가: 햄치즈 샌드위치 x 2, 소스: 마요네즈
[OrderConfirmation] 주문 전송 - 테이블 1, 총액 10000원
[FMSOrderService] 주문 전송 - 테이블 1, 주문 ORD-...
[FMSClient] 메시지 전송 성공: {...}...
```

### 2. Mock 모드 사용
FMS가 없을 때는 `--mock` 옵션 사용:
```bash
python main_fms_direct.py --mock
```

### 3. 주요 파일 경로
- 메인 로직: `main_fms_direct.py` (라인 ~360)
- FMS 통신: `fms_client.py` (라인 ~400)
- 배달 알림 처리: `main_fms_direct.py` on_delivery_notification_received() (라인 218)
- 수령 확인: `ui_delivery_notification.py` on_confirm_delivery() (라인 110)

### 4. 네트워크 문제 확인
```bash
# FMS 연결 테스트
nc -zv 192.168.1.3 9000

# 포트 열려있는지 확인
netstat -an | grep 9000
```

---

## FMS 연동 체크리스트

- [ ] FMS 서버가 192.168.1.3:9000에서 실행 중
- [ ] 주문 메시지 포맷이 FMS와 일치
- [ ] 배달 알림 메시지 포맷이 FMS와 일치
- [ ] 소스 정보가 FMS에서 처리 가능
- [ ] 로봇이 배달 알림 메시지 발송 중
- [ ] TCP 통신이 안정적 (보안/방화벽 확인)

---

## 다음 단계

### 즉시 (우선순위 1-2)
1. 소스 정보 FMS 전송 수정 (CUSTOMER_GUI_FIXES.md 참고)
2. 메시지 포맷 통일 확인 (FMS 코드 확인 필요)

### 단기 (우선순위 3-4)
3. 테이블 번호 동적 선택 UI 추가
4. 메시지 재시도 로직 추가

### 장기 (우선순위 5-7)
5. 배달 알림 검증 개선
6. 음성 피드백 추가
7. Order ID 생성 방식 개선

---

## 문서 위치

- **분석 보고서**: `/home/gw/kitchmatics/roscamp-repo-1/CUSTOMER_GUI_ANALYSIS.md`
- **수정 가이드**: `/home/gw/kitchmatics/roscamp-repo-1/CUSTOMER_GUI_FIXES.md`
- **이 문서**: `/home/gw/kitchmatics/roscamp-repo-1/CUSTOMER_GUI_SUMMARY.md`

---

## 연락처 및 참고

- **프로젝트**: Kitchmatics (주문 키오스크 시스템)
- **기술 스택**: PyQt5, Python, ROS2, FMS
- **배포 위치**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/`
