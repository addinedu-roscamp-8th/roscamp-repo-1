# Customer GUI 아키텍처 상세 분석

## 계층 구조 (Layered Architecture)

```
┌─────────────────────────────────────────────────────────────────┐
│ Presentation Layer (사용자 인터페이스)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ ui_main_window │  │ui_menu_select  │  │ui_order_config │   │
│  │  (메인 화면)    │  │  (메뉴 선택)    │  │  (주문 확인)     │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │        ui_delivery_notification (배달 알림)              │  │
│  │  ┌──────────────────────────────────────────────┐       │  │
│  │  │ [깜빡이는 애니메이션]  [주문 번호 표시]       │       │  │
│  │  │ [수령 완료] [뒤로가기] [취소]                 │       │  │
│  │  └──────────────────────────────────────────────┘       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  [PyQt5 Signal/Slot 기반 이벤트 처리]                            │
│  - order_confirmed_signal(Order)                                │
│  - order_submitted_signal(Order)                                │
│  - delivery_confirmed_signal(dict)                              │
│  - delivery_notification_signal(dict)                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (이벤트 구독)
┌─────────────────────────────────────────────────────────────────┐
│ Application Layer (비즈니스 로직)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  CustomerGUIApp (main_fms_direct.py - StackedWidget)            │
│  ├─ 화면 전환 관리 (setCurrentWidget)                            │
│  ├─ 주문 플로우 오케스트레이션                                    │
│  └─ 이벤트 핸들러들:                                              │
│      ├─ on_start_order() - 주문 시작                            │
│      ├─ on_order_confirmed() - 주문 확인                        │
│      ├─ on_order_submitted() - 주문 전송                        │
│      ├─ on_delivery_notification_received() - 배달 알림 수신    │
│      ├─ on_delivery_confirmed() - 수령 확인                     │
│      └─ on_table_selected() - 테이블 변경                       │
│                                                                   │
│  FMSOrderServiceClient (fms_client.py - QObject)                │
│  ├─ submit_order(Order) → order_id                              │
│  │   ├─ Order ID 생성                                            │
│  │   ├─ 메시지 생성                                              │
│  │   └─ FMSTCPClient.send_message()                             │
│  │                                                               │
│  ├─ confirm_delivery(order_id, table) → bool                   │
│  │   ├─ 수령 확인 메시지 생성                                    │
│  │   └─ FMSTCPClient.send_message()                             │
│  │                                                               │
│  ├─ _handle_message(dict)                                       │
│  │   ├─ 메시지 타입 확인                                         │
│  │   └─ 해당 시그널 발행                                         │
│  │                                                               │
│  └─ Signals:                                                    │
│      ├─ connected_signal                                        │
│      ├─ disconnected_signal                                     │
│      ├─ error_signal(str)                                       │
│      ├─ order_response_signal(dict)                             │
│      └─ delivery_notification_signal(dict)                      │
│                                                                   │
│  MockFMSOrderServiceClient (테스트용)                            │
│  ├─ FMSOrderServiceClient와 동일한 인터페이스                    │
│  └─ 실제 TCP 통신 없이 로컬에서 시뮬레이션                       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (메시지 송수신)
┌─────────────────────────────────────────────────────────────────┐
│ Infrastructure Layer (통신)                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  FMSTCPClient (fms_client.py)                                    │
│  ├─ connect(host, port) → bool                                  │
│  │   ├─ 소켓 생성                                                │
│  │   ├─ FMS 서버에 연결                                          │
│  │   └─ 메시지 리스너 스레드 시작                                │
│  │                                                               │
│  ├─ disconnect()                                                │
│  │   ├─ 리스너 스레드 종료                                       │
│  │   └─ 소켓 종료                                                │
│  │                                                               │
│  ├─ send_message(dict, retry_count=0) → bool                   │
│  │   ├─ JSON 직렬화                                              │
│  │   ├─ 4-byte length header 추가                               │
│  │   ├─ socket.sendall() 전송                                    │
│  │   └─ 실패 시 재시도 (최대 3회)                                │
│  │                                                               │
│  ├─ _listen_messages() [백그라운드 스레드]                       │
│  │   ├─ 무한 루프에서 메시지 수신 대기                           │
│  │   ├─ _receive_message() 호출                                  │
│  │   └─ on_message_received 콜백 실행                           │
│  │                                                               │
│  ├─ _receive_message() → dict                                    │
│  │   ├─ 4-byte length header 수신                               │
│  │   ├─ 메시지 본문 청크 단위로 수신                             │
│  │   └─ JSON 파싱                                                │
│  │                                                               │
│  └─ Properties:                                                 │
│      ├─ host, port                                              │
│      ├─ socket                                                  │
│      ├─ is_connected                                            │
│      ├─ listener_thread                                         │
│      ├─ running                                                 │
│      ├─ max_retries (기본값: 3)                                  │
│      ├─ retry_delay (기본값: 1.0초)                              │
│      └─ on_message_received (콜백)                              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (TCP Socket)
┌─────────────────────────────────────────────────────────────────┐
│ Network Layer (네트워크)                                          │
├─────────────────────────────────────────────────────────────────┤
│  TCP Socket (IPv4, SOCK_STREAM)                                  │
│  192.168.1.3:9000                                                │
│  - 4-byte Big-Endian Length + JSON Body 프로토콜                 │
│  - 동기식 송신 / 비동기식 수신 (스레드 기반)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ FMS Server (외부 시스템)                                          │
├─────────────────────────────────────────────────────────────────┤
│  - 주문 수신 및 조리 실행                                         │
│  - 배달 알림 발송                                                 │
│  - 수령 확인 처리                                                 │
│  - 로봇 조종                                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 클래스 상세 정보

### 1. CustomerGUIApp (메인 애플리케이션)

**파일**: `main_fms_direct.py`
**부모 클래스**: `QStackedWidget`

```python
class CustomerGUIApp(QStackedWidget):
    """주문 화면 관리 및 FMS 통신 오케스트레이션"""

    # 상태
    current_order: Order            # 현재 진행 중인 주문
    pending_order: Order            # 배달 대기 중인 주문
    use_mock: bool                  # Mock 모드 사용 여부
    fms_client: FMSOrderServiceClient

    # UI 참조
    main_window: MainWindow
    menu_selection: MenuSelectionWidget
    order_confirmation: OrderConfirmationWidget
    delivery_notification: DeliveryNotificationWidget
    voice_feedback: VoiceFeedbackWidget

    # 메서드
    def setup_ui(self) → None                           # UI 초기화
    def setup_client(self) → None                       # FMS 클라이언트 초기화
    def connect_signals(self) → None                    # 시그널 연결

    def on_start_order(self) → None                     # 주문 시작
    def on_order_confirmed(self, order: Order) → None  # 주문 확인 (메뉴 선택 완료)
    def on_order_submitted(self, order: Order) → None  # 주문 전송
    def on_back_to_menu_selection(self) → None         # 메뉴 선택으로 돌아가기
    def on_cancel_order(self) → None                    # 주문 취소
    def on_delivery_notification_received(...) → None  # 배달 알림 수신
    def on_delivery_confirmed(self, delivery_data) → None  # 수령 확인
    def on_table_selected(self, table_num: int) → None # 테이블 선택
    def on_client_error(self, error_msg: str) → None   # 클라이언트 오류
    def show_delivery_notification(self, order) → None # 배달 알림 화면 표시
    def go_to_main(self) → None                        # 메인 화면으로 복귀

    # 이벤트
    def keyPressEvent(self, event) → None              # ESC로 전체화면 종료
    def closeEvent(self, event) → None                 # 종료 시 정리
```

---

### 2. FMSOrderServiceClient (FMS 비즈니스 로직)

**파일**: `fms_client.py`
**부모 클래스**: `QObject`

```python
class FMSOrderServiceClient(QObject):
    """FMS와의 주문 통신 (Application Layer)"""

    # 시그널
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    order_response_signal = pyqtSignal(dict)
    delivery_notification_signal = pyqtSignal(dict)

    # 상태
    client: FMSTCPClient                    # 저수준 TCP 클라이언트

    # 메서드
    def __init__(self) → None               # FMS 주소를 Config에서 로드

    def connect(self) → bool                # FMS에 연결
    def disconnect(self) → None             # 연결 종료

    def submit_order(self, order: Order) → Optional[str]
        """
        주문 전송
        - Order ID 생성
        - 메시지 형식:
          {'type': 'new_order', 'table_number': 1, 'data': {...}}
        - 반환: order_id 또는 None (실패)
        """

    def confirm_delivery(self, order_id: str, table_number: int) → bool
        """
        수령 확인 전송
        - 메시지 형식:
          {'type': 'delivery_complete', 'data': {...}}
        """

    def _handle_message(self, message: dict) → None
        """
        FMS로부터 수신한 메시지 처리
        - 메시지 타입에 따라 해당 시그널 발행
        """
```

---

### 3. FMSTCPClient (TCP 통신)

**파일**: `fms_client.py`
**부모 클래스**: `object`

```python
class FMSTCPClient:
    """FMS와의 저수준 TCP 통신 (Infrastructure Layer)"""

    # 상태
    host: str                                   # FMS 호스트
    port: int                                   # FMS 포트
    socket: Optional[socket.socket]             # 소켓 객체
    is_connected: bool                          # 연결 상태
    listener_thread: Optional[threading.Thread] # 메시지 리스너 스레드
    running: bool                               # 리스너 실행 중 여부
    on_message_received: Optional[Callable]    # 메시지 수신 콜백
    max_retries: int = 3                       # 재시도 최대 횟수
    retry_delay: float = 1.0                   # 재시도 간격 (초)

    # 메서드
    def __init__(self, host: str, port: int, max_retries: int = 3, ...)

    def connect(self) → bool
        """
        FMS 서버에 연결
        1. 소켓 생성
        2. 서버에 연결
        3. 메시지 리스너 스레드 시작
        """

    def disconnect(self) → None
        """
        연결 종료
        1. 리스너 스레드 중지
        2. 소켓 종료
        """

    def send_message(self, message: dict, retry_count: int = 0) → bool
        """
        메시지 전송 (재시도 로직 포함)
        1. JSON 직렬화
        2. 4-byte length header 추가
        3. socket.sendall()로 전송
        4. 실패 시 재시도 (최대 max_retries회)
        """

    def _start_listener(self) → None
        """백그라운드 스레드에서 메시지 리스너 시작"""

    def _listen_messages(self) → None
        """
        메시지 수신 루프 (백그라운드 스레드)
        - 무한 루프에서 _receive_message() 호출
        - 수신한 메시지를 on_message_received 콜백에 전달
        """

    def _receive_message(self) → Optional[dict]
        """
        메시지 수신
        1. 4-byte length header 수신
        2. 메시지 길이만큼 청크 단위로 수신
        3. JSON 파싱 후 반환
        """
```

---

### 4. 프레젠테이션 계층 UI 위젯들

#### MainWindow (메인 화면)
```python
class MainWindow(QMainWindow):
    start_order_signal = pyqtSignal()
    table_selected_signal = pyqtSignal(int)

    # UI
    label_table: QLabel              # 테이블 번호 표시
    spin_table: QSpinBox             # 테이블 번호 선택 (추가 필요)
    btn_start_order: QPushButton     # 주문 시작 버튼
    btn_set_table: QPushButton       # 테이블 설정 버튼 (추가 필요)

    # 메서드
    def setup_ui(self) → None
    def on_start_order(self) → None
    def on_table_set(self) → None    # 추가 필요
```

#### MenuSelectionWidget (메뉴 선택)
```python
class MenuSelectionWidget(QWidget):
    order_confirmed_signal = pyqtSignal(Order)
    cancel_signal = pyqtSignal()

    # UI
    list_menu: QListWidget           # 메뉴 리스트
    list_cart: QListWidget           # 장바구니
    label_total: QLabel              # 합계 표시
    btn_confirm_order: QPushButton   # 주문 확인 버튼
    btn_cancel: QPushButton          # 취소 버튼

    # 상태
    order: Order                     # 현재 주문
    menu_items: List[MenuItem]       # 메뉴 리스트

    # 메서드
    def set_menu_items(self, items: List[MenuItem]) → None
    def update_menu_list(self) → None
    def update_cart_list(self) → None
    def on_menu_item_clicked(self, item) → None
    def on_cart_item_clicked(self, item) → None
    def on_confirm_order(self) → None
    def on_cancel(self) → None
```

#### OrderConfirmationWidget (주문 확인)
```python
class OrderConfirmationWidget(QWidget):
    order_submitted_signal = pyqtSignal(Order)
    back_signal = pyqtSignal()

    # UI
    label_table: QLabel              # 테이블 번호
    label_datetime: QLabel           # 날짜/시간
    text_items: QPlainTextEdit       # 주문 항목 (영수증)
    label_total: QLabel              # 합계
    btn_submit: QPushButton          # 주문하기 버튼
    btn_back: QPushButton            # 뒤로가기 버튼

    # 상태
    order: Order

    # 메서드
    def set_order(self, order: Order) → None
    def update_receipt(self) → None
    def on_submit_order(self) → None
    def on_back(self) → None
```

#### DeliveryNotificationWidget (배달 알림)
```python
class DeliveryNotificationWidget(QWidget):
    delivery_confirmed_signal = pyqtSignal(dict)

    # UI
    label_notification: QLabel       # 알림 메시지 (깜빡임)
    label_order_info: QLabel         # 주문 정보
    text_order_items: QPlainTextEdit # 주문 항목 표시
    btn_confirm_delivery: QPushButton # 수령 확인 버튼

    # 상태
    order: Order
    blink_timer: QTimer              # 깜빡임 타이머
    blink_state: bool                # 깜빡임 상태

    # 메서드
    def set_order(self, order: Order) → None
    def update_notification(self) → None
    def start_blink_animation(self) → None
    def toggle_blink(self) → None
    def stop_blink_animation(self) → None
    def on_confirm_delivery(self) → None
    def play_completion_sound(self) → None  # 추가 필요
    def showEvent(self, event) → None
    def hideEvent(self, event) → None
```

---

## 데이터 흐름 (Data Flow)

### 주문 생성 흐름
```
MainWindow
    ↓ [start_order_signal]
on_start_order()
    ├─ MOCK_MENUS 로드
    ├─ menu_selection.set_menu_items(menus)
    └─ setCurrentWidget(menu_selection)
        ↓
MenuSelectionWidget
    ├─ [메뉴 더블클릭]
    │   └─ MenuItemDialog (소스/수량 선택)
    │       └─ [장바구니에 추가]
    │           └─ order.items 추가
    │
    ├─ [주문 확인]
    │   └─ [order_confirmed_signal]
    │       ↓
    │   on_order_confirmed(order)
    │       ├─ current_order = order
    │       ├─ order_confirmation.set_order(order)
    │       └─ setCurrentWidget(order_confirmation)
    │           ↓
    │       OrderConfirmationWidget
    │           ├─ update_receipt() [영수증 표시]
    │           └─ [주문하기]
    │               └─ [order_submitted_signal]
    │                   ↓
    │               on_order_submitted(order)
    │                   ├─ order_id = fms_client.submit_order(order)
    │                   ├─ pending_order = current_order
    │                   ├─ current_order = None
    │                   └─ go_to_main()
    │                       └─ setCurrentWidget(main_window)
    │                           ↓
    │                       FMSOrderServiceClient.submit_order(order)
    │                           ├─ order_id = f'ORD-{uuid...}'
    │                           ├─ message = {
    │                           │   'type': 'new_order',
    │                           │   'table_number': 1,
    │                           │   'data': {
    │                           │       'order_id': 'ORD-...',
    │                           │       'items': [...],
    │                           │       'sauce': '마요네즈',
    │                           │       'table_number': 1,
    │                           │       'total_price': 10000
    │                           │   }
    │                           │ }
    │                           ├─ FMSTCPClient.send_message(message)
    │                           │   ├─ length_header = len(json_data).to_bytes(4)
    │                           │   └─ socket.sendall(header + json_data)
    │                           │       ↓
    │                           │       FMS Server
    │                           │           ├─ 주문 수신
    │                           │           ├─ 조리 실행
    │                           │           └─ 배달 준비
    │                           │
    │                           └─ return order_id
```

### 배달 알림 흐름
```
FMS Server
    ├─ 음식 준비 완료
    ├─ 배달 알림 메시지 생성:
    │   {
    │       'type': 'delivery_notification',
    │       'data': {
    │           'order_id': 'ORD-...',
    │           'table_number': '1',
    │           'robot_id': 'pinky1'
    │       }
    │   }
    └─ TCP 전송
        ↓
FMSTCPClient._listen_messages() [백그라운드 스레드]
    └─ _receive_message()
        ├─ length_header 수신
        ├─ json_data 수신
        ├─ message = json.loads(json_data)
        └─ on_message_received(message)
            ↓
FMSOrderServiceClient._handle_message(message)
    └─ message['type'] == 'delivery_notification'
        └─ delivery_notification_signal.emit(message)
            ↓
on_delivery_notification_received(notification)
    ├─ order_id 추출
    ├─ active_order 확인 (current_order or pending_order)
    ├─ order_id 일치 검증
    ├─ table_number 일치 검증
    └─ show_delivery_notification(active_order)
        └─ setCurrentWidget(delivery_notification)
            ↓
DeliveryNotificationWidget
    ├─ set_order(order)
    ├─ start_blink_animation()
    │   ├─ label_notification 깜빡임 시작
    │   └─ blink_timer 500ms마다 토글
    │
    └─ [수령 완료] 클릭
        └─ [delivery_confirmed_signal]
            ↓
        on_delivery_confirmed(delivery_data)
            ├─ fms_client.confirm_delivery(order_id, table_number)
            │   ├─ message = {
            │   │   'type': 'delivery_complete',
            │   │   'data': {
            │   │       'order_id': 'ORD-...',
            │   │       'table_number': '1'
            │   │   }
            │   │ }
            │   ├─ FMSTCPClient.send_message(message)
            │   │   └─ FMS Server
            │   │       └─ 수령 확인 처리
            │   └─ return True
            │
            ├─ pending_order = None
            └─ go_to_main()
                └─ setCurrentWidget(main_window)
```

---

## 상태 머신 (State Machine)

```
                        ┌─────────────────┐
                        │   Main Screen   │
                        │   (시작 화면)     │
                        └────────┬────────┘
                                 │
                                 │ [주문 시작]
                                 ↓
                        ┌─────────────────┐
                        │ Menu Selection  │
                        │   (메뉴 선택)     │
                        └────────┬────────┘
                                 │
                                 │ [주문 확인]
                                 ↓
                        ┌─────────────────┐
                        │Order Confirma.  │
                        │   (주문 확인)     │
                        └────────┬────────┘
                                 │
                                 │ [주문하기]
                                 ↓
                    ┌────────────────────────┐
                    │ Waiting for Delivery   │
                    │   (배달 대기)           │
                    │ [current_order=None]   │
                    │ [pending_order=Order]  │
                    └────────┬───────────────┘
                             │
        [배달 알림 수신]       │
        [주문 ID 검증]        │
                             │
                             ↓
                    ┌─────────────────┐
                    │ Delivery Notif. │
                    │   (배달 알림)     │
                    │ [깜빡임 애니]     │
                    └────────┬────────┘
                             │
                             │ [수령 완료]
                             ↓
                    ┌─────────────────┐
                    │ Main Screen     │
                    │ (시작으로 돌아감)  │
                    └─────────────────┘

취소 경로:
┌─────────────────┐
│ Menu Selection  │ → [취소] → Main Screen
└─────────────────┘

│ Menu Selection  │ → [뒤로가기] → Main Screen
└─────────────────┘
```

---

## 에러 처리 흐름

```
┌─ FMS 연결 실패
│  └─ setup_client()
│      └─ QMessageBox.warning()
│           "FMS 서버에 연결할 수 없습니다..."
│
├─ 주문 전송 실패
│  ├─ send_message() 실패
│  │  ├─ 재시도 (최대 3회)
│  │  └─ 3회 이상 실패
│  │      └─ error_signal.emit('주문 전송 실패')
│  │
│  └─ on_order_submitted()
│      └─ QMessageBox.critical()
│           "FMS로 주문 전송에 실패했습니다..."
│
├─ 배달 알림 검증 실패
│  ├─ order_id 누락 → 로그 출력 (무시)
│  ├─ order_id 불일치 → 로그 출력 (무시)
│  ├─ table_number 불일치 → 로그 출력 (무시)
│  └─ 검증 오류 → 로그 출력 (무시)
│
└─ 수령 확인 전송 실패
   └─ confirm_delivery()
       └─ QMessageBox.warning()
            "수령 확인 처리 중 오류가 발생했습니다."
```

---

## 성능 고려사항

### 1. 네트워크 I/O
- **블로킹 vs 비블로킹**:
  - 송신: 동기식 (blocking)
  - 수신: 비동기식 (background thread)

- **타임아웃**: 5초 (TCP 연결 타임아웃)

- **재시도**: 최대 3회, 1초 간격

### 2. UI 응답성
- **GUI 블로킹 방지**:
  - 모든 네트워크 I/O는 스레드에서 실행
  - GUI 업데이트는 main thread에서만 (PyQt Signal 이용)

- **애니메이션**: QTimer로 500ms 간격 깜빡임

### 3. 메모리 관리
- **메시지 크기**: JSON 200자 이상은 로그에서 축약
- **백그라운드 스레드**: daemon=True (앱 종료 시 자동 정리)
- **리스너 스레드**: 명시적으로 join(timeout=2.0)

---

## 보안 고려사항

### 1. 입력 검증
- Order ID: UUID 기반 생성 (충돌 불가)
- 테이블 번호: int 형변환, 범위 검증 (1-20)
- 메시지: JSON 직렬화/파싱 (문법 오류 처리)

### 2. 네트워크 보안
- TCP only (암호화 없음) - Closed network 환경
- 길이 기반 메시지 경계 명확 (injection 방지)

### 3. 접근 제어
- 로컬 소켓만 사용 (GUI와 FMS가 같은 네트워크)
- 방화벽 설정 필요

---

## 테스트 전략

### Unit Test
```python
# fms_client.py
def test_submit_order_creates_valid_message():
    # Order 생성 → submit_order() → 메시지 검증

# models.py
def test_order_total_calculation():
    # Order.calculate_total() 검증

def test_order_item_sauce():
    # OrderItem.sauce 필드 검증
```

### Integration Test
```python
# Mock 모드 테스트
python main_fms_direct.py --mock

# 다양한 주문 시나리오
- 단일 메뉴 주문
- 다중 메뉴 주문
- 소스 선택 포함
- 수량 변경
- 취소
```

### System Test
```python
# 실제 FMS 연결 테스트
python main_fms_direct.py --table 1

# 네트워크 문제 시뮬레이션
- FMS 서버 다운
- 네트워크 지연
- 메시지 손실
```

---

## 배포 체크리스트

- [ ] FMS 서버가 192.168.1.3:9000에서 실행 중
- [ ] Config.FMS_HOST, FMS_PORT 설정 확인
- [ ] 메뉴 데이터 로드 (MOCK_MENUS 또는 별도 API)
- [ ] 테이블 번호 설정 (--table 또는 Config)
- [ ] 음성 파일 배치 (선택사항)
- [ ] 의존성 설치 (pip install -r requirements.txt)
- [ ] 권한 설정 (실행 가능)
- [ ] 로그 경로 확인
- [ ] 에러 핸들링 테스트
- [ ] 재시도 로직 테스트
