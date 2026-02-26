# Customer GUI 코드 분석 보고서

## 목차
1. [아키텍처 개요](#아키텍처-개요)
2. [코드 분석](#코드-분석)
3. [주요 흐름](#주요-흐름)
4. [FMS 통신 방식](#fms-통신-방식)
5. [문제점 및 개선 방안](#문제점-및-개선-방안)

---

## 아키텍처 개요

### 디렉토리 구조
```
/home/gw/kitchmatics/roscamp-repo-1/app/gui/
├── common/                          # 공통 모듈
│   ├── __init__.py
│   ├── config.py                   # 설정 관리
│   └── models.py                   # 데이터 모델 (Order, MenuItem 등)
└── customer_gui/                    # Customer GUI
    └── src/
        ├── main_fms_direct.py      # 메인 애플리케이션 (FMS 직접 통신)
        ├── fms_client.py            # FMS TCP 클라이언트
        ├── ui_main_window.py        # 메인 화면 (주문 시작)
        ├── ui_menu_selection.py     # 메뉴 선택 화면
        ├── ui_order_confirmation.py # 주문 확인 화면 (영수증)
        ├── ui_delivery_notification.py  # 배달 알림 및 수령 확인 화면
        └── voice_feedback_widget.py # 음성 피드백 위젯
```

### 아키텍처 계층
```
Presentation Layer (PyQt5 UI)
    ├── MainWindow (메인 화면)
    ├── MenuSelectionWidget (메뉴 선택)
    ├── OrderConfirmationWidget (주문 확인)
    └── DeliveryNotificationWidget (수령 확인)
            ↓
Application Layer (Business Logic)
    └── FMSOrderServiceClient (주문/배달 관리)
            ↓
Infrastructure Layer (TCP Communication)
    └── FMSTCPClient (저수준 TCP 통신)
            ↓
Domain Layer (Data Models)
    ├── Order (주문)
    ├── OrderItem (주문 항목)
    └── MenuItem (메뉴)
```

---

## 코드 분석

### 1. 주문 생성 및 FMS로 전송하는 로직

#### 파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/fms_client.py`

**FMSOrderServiceClient.submit_order() 메서드 (라인 194-240)**

```python
def submit_order(self, order: Order) -> Optional[str]:
    """
    주문 전송 (FMS로 직접)

    메시지 형식:
    {
        'command': 'new_order',
        'table_number': 1,
        'order': {
            'order_id': 'ORD-XXX',
            'items': [...],
            'table_number': 1
        }
    }
    """
    # order_id 생성 (타임스탬프 기반)
    order_id = f'ORD-{int(time.time())}'
    order.order_id = order_id

    # FMS 주문 메시지 생성
    message = {
        'command': 'new_order',
        'table_number': order.table_number,
        'order': {
            'order_id': order_id,
            'items': [
                {
                    'menu_id': item.menu_item.menu_id,
                    'name': item.menu_item.name,
                    'quantity': item.quantity,
                    'price': item.menu_item.price
                }
                for item in order.items
            ],
            'table_number': order.table_number,
            'total_price': order.calculate_total()
        }
    }

    print(f'[FMSOrderService] 주문 전송 - 테이블 {order.table_number}, 주문 {order_id}')

    # 전송
    if self.client.send_message(message):
        return order_id
    else:
        self.error_signal.emit('주문 전송 실패')
        return None
```

**분석:**
- 주문 ID는 Unix 타임스탬프 기반으로 생성됨
- FMS로 전송되는 메시지 포맷: `{'command': 'new_order', ...}`
- 메뉴 아이템의 소스(sauce) 정보가 **전송되지 않음** ❌

---

### 2. 테이블 번호 선택 로직

#### 파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main_fms_direct.py`

**main() 함수 (라인 328-362)**

```python
def main():
    """메인 함수"""
    import argparse

    # 명령줄 인자 파서
    parser = argparse.ArgumentParser(description='고객용 GUI (FMS Direct)')
    parser.add_argument('--table', type=int, default=1, help='테이블 번호 (기본값: 1)')
    parser.add_argument('--mock', action='store_true', help='Mock 모드 사용')

    # PyQt의 sys.argv 처리를 위해 알려진 인자만 파싱
    args, unknown = parser.parse_known_args()

    # 테이블 번호 설정
    Config.TABLE_NUMBER = args.table

    # QApplication 생성
    app = QApplication(sys.argv)

    # 애플리케이션 설정
    app.setApplicationName(f'주문 키오스크 (테이블 {args.table})')
    app.setOrganizationName('Kitchmatics')

    # 메인 윈도우 생성 및 표시
    window = CustomerGUIApp(use_mock=args.mock)
    window.show()
```

**분석:**
- 테이블 번호는 **명령줄 인자(`--table`)**로 설정됨
- Config.TABLE_NUMBER에 저장되고 모든 화면에서 사용됨
- UI 내에서 테이블 번호 선택 화면이 없음 (명령줄 기반 설정만 가능) ❌

#### 파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/ui_main_window.py`

**MainWindow.setup_ui() (라인 27-46)**

```python
def setup_ui(self):
    """UI 설정"""
    # .ui 파일 로드
    ui_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'ui',
        'main_window.ui'
    )
    loadUi(ui_path, self)

    # 윈도우 설정
    self.setWindowTitle('주문 시작')
    if Config.FULLSCREEN:
        self.showFullScreen()
    else:
        self.resize(Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)

    # 테이블 번호 표시
    self.label_table.setText(f'테이블 번호: {Config.TABLE_NUMBER}')
```

**분석:**
- 메인 화면에서 테이블 번호는 **읽기 전용으로 표시**됨 (label_table)
- 테이블 변경이 불가능함

---

### 3. 수령완료 버튼 및 기능

#### 파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/ui_delivery_notification.py`

**DeliveryNotificationWidget 클래스 분석**

```python
class DeliveryNotificationWidget(QWidget):
    """음식 도착 알림 위젯"""

    # 시그널 정의
    delivery_confirmed_signal = pyqtSignal(dict)  # 수령 완료 시그널

    def on_confirm_delivery(self):
        """수령 완료 버튼 클릭 - SR-16: 음식 수령 확인"""
        if not self.order:
            return

        print(f'[DeliveryNotification] 수령 완료 - 주문 {self.order.order_id}')

        # 깜빡임 중지
        self.stop_blink_animation()

        # 수령 완료 시그널 발생 (order_id와 table_number 포함)
        self.delivery_confirmed_signal.emit({
            'order_id': self.order.order_id or '',
            'table_number': str(self.order.table_number) if hasattr(self.order, 'table_number') else ''
        })
```

**흐름:**

1. 수령 완료 버튼 클릭 → `delivery_confirmed_signal` 발생
2. `main_fms_direct.py`의 `on_delivery_confirmed()` 핸들러 호출 (라인 261-285)

```python
def on_delivery_confirmed(self, delivery_data: dict):
    """수령 확인 (FMS로 전송)"""
    order_id = delivery_data.get('order_id', '')
    table_number = int(delivery_data.get('table_number', Config.TABLE_NUMBER))
    print(f'[App] 수령 확인 - 주문 {order_id}, 테이블 {table_number}')

    # FMS로 수령 확인 전송
    if self.fms_client.confirm_delivery(order_id, table_number):
        QMessageBox.information(
            self,
            '감사합니다',
            '맛있게 드세요!',
            QMessageBox.Ok
        )
    else:
        QMessageBox.warning(
            self,
            '오류',
            '수령 확인 처리 중 오류가 발생했습니다.',
            QMessageBox.Ok
        )

    # pending_order 초기화 후 메인 화면으로
    self.pending_order = None
    self.go_to_main()
```

3. `FMSOrderServiceClient.confirm_delivery()` 호출 (라인 242-269)

```python
def confirm_delivery(self, order_id: str, table_number: int) -> bool:
    """
    수령 확인 전송 (FMS로)

    메시지 형식:
    {
        'type': 'delivery_complete',
        'data': {
            'order_id': 'ORD-XXX',
            'table_number': '1'
        }
    }
    """
    message = {
        'type': 'delivery_complete',
        'data': {
            'order_id': order_id,
            'table_number': str(table_number)
        }
    }

    print(f'[FMSOrderService] 수령 확인 전송 - 주문 {order_id}')

    if self.client.send_message(message):
        return True
    else:
        self.error_signal.emit('수령 확인 전송 실패')
        return False
```

**분석:**
- 수령 확인 메시지 포맷: `{'type': 'delivery_complete', 'data': {...}}`
- 주문 생성 메시지와 포맷 불일치 (command vs type) ❌
- 사용자 피드백: 메시지박스만 제공 (음성/진동 미지원)

---

### 4. FMS와의 통신 방식

#### 파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/fms_client.py`

**통신 프로토콜: TCP 소켓**

**저수준 TCP 통신 (FMSTCPClient 클래스)**

```python
class FMSTCPClient:
    """
    FMS TCP 클라이언트 (저수준 TCP 통신)
    Responsibility: FMS 서버와의 TCP 연결 및 메시지 송수신
    """

    def send_message(self, message: dict) -> bool:
        """메시지 전송 (4-byte length header + JSON)"""
        if not self.is_connected or not self.socket:
            print('[FMSClient] 오류: FMS 연결되지 않음')
            return False

        try:
            # JSON 직렬화
            json_data = json.dumps(message, ensure_ascii=False)
            message_bytes = json_data.encode('utf-8')

            # 4-byte length header
            length_header = len(message_bytes).to_bytes(4, byteorder='big')

            # 전송
            self.socket.sendall(length_header + message_bytes)
            print(f'[FMSClient] 메시지 전송: {json_data[:200]}...')
            return True

        except Exception as e:
            print(f'[FMSClient] 메시지 전송 실패: {e}')
            self.is_connected = False
            return False

    def _receive_message(self) -> Optional[dict]:
        """메시지 수신 (4-byte length header + JSON)"""
        # 4-byte length header 수신
        length_header = self.socket.recv(4)
        if not length_header or len(length_header) < 4:
            return None

        message_length = int.from_bytes(length_header, byteorder='big')

        # 메시지 본문 수신 (청크 단위로)
        message_bytes = b''
        while len(message_bytes) < message_length:
            chunk = self.socket.recv(min(4096, message_length - len(message_bytes)))
            if not chunk:
                break
            message_bytes += chunk

        # JSON 파싱
        json_data = message_bytes.decode('utf-8')
        message = json.loads(json_data)
        return message
```

**메시지 포맷:**

| 용도 | 메시지 구조 | 예시 |
|------|-----------|------|
| 주문 생성 | `{'command': 'new_order', 'table_number': 1, 'order': {...}}` | - |
| 수령 확인 | `{'type': 'delivery_complete', 'data': {...}}` | - |
| 배달 알림 수신 | `{'type': 'delivery_notification', 'data': {...}}` | - |

**특징:**
- 4-byte 빅엔디안 length header + JSON 바디
- 비동기 메시지 수신 (백그라운드 스레드에서 리스너 실행)
- PyQt Signal으로 메시지 처리

---

## 주요 흐름

### 주문 생성 플로우
```
메인 화면
  ↓
메뉴 선택 화면 (set_menu_items)
  ├─ 메뉴 더블클릭 → MenuItemDialog (수량/소스 선택)
  ├─ 장바구니에 추가 → Order.items에 OrderItem 추가
  ├─ 장바구니 더블클릭 → 수량 변경 또는 삭제
  └─ "주문 확인" 클릭 → order_confirmed_signal 발행
    ↓
주문 확인 화면 (영수증 형태)
  ├─ Order 정보 표시 (테이블, 시간, 항목, 합계)
  └─ "주문하기" 클릭 → order_submitted_signal 발행
    ↓
FMS로 주문 전송
  ├─ submit_order(order) 호출
  ├─ Order ID 생성 (타임스탐프 기반)
  ├─ TCP 메시지 생성 및 전송
  ├─ 메시지 수신 대기
  └─ pending_order에 저장 후 메인 화면으로 복귀
```

### 배달 알림 수신 플로우
```
FMS → GUI (TCP 메시지 수신)
  ↓
_handle_message() → delivery_notification_signal 발행
  ↓
on_delivery_notification_received() 호출
  ├─ 테이블 번호 검증 (현재 테이블과 비교)
  ├─ order_id 확인
  └─ 일치하면 배달 알림 화면 표시
    ↓
배달 알림 화면 (깜빡이는 애니메이션)
  └─ "수령 확인" 클릭 → delivery_confirmed_signal 발행
    ↓
수령 확인 FMS 전송
  ├─ confirm_delivery(order_id, table_number) 호출
  ├─ TCP 메시지 전송
  └─ 메시지박스 표시 후 메인 화면으로 복귀
```

---

## FMS 통신 방식

### 사용 기술
- **프로토콜**: TCP 소켓 (직접 연결)
- **메시지 형식**: JSON (UTF-8 인코딩)
- **포트**: Config.FMS_PORT (기본값: 9000)
- **호스트**: Config.FMS_HOST (기본값: 192.168.1.3)
- **메시지 구조**: 4-byte length header (빅엔디안) + JSON 바디

### 토픽/서비스/액션 사용 여부
- **ROS2 토픽 미사용** ❌
- **ROS2 서비스 미사용** ❌
- **ROS2 액션 미사용** ❌
- **기본 TCP 소켓만 사용** ✓

### FMS 연동 메시지
```python
# 1. 주문 생성 메시지
{
    'command': 'new_order',
    'table_number': 1,
    'order': {
        'order_id': 'ORD-1234567890',
        'items': [
            {
                'menu_id': 'M001',
                'name': '햄치즈 샌드위치',
                'quantity': 2,
                'price': 5000
            }
        ],
        'table_number': 1,
        'total_price': 10000
    }
}

# 2. 수령 확인 메시지
{
    'type': 'delivery_complete',
    'data': {
        'order_id': 'ORD-1234567890',
        'table_number': '1'
    }
}

# 3. 배달 알림 메시지 (FMS → GUI)
{
    'type': 'delivery_notification',
    'data': {
        'order_id': 'ORD-XXX',
        'table_number': '1',
        'robot_id': 'pinky1'
    }
}
```

---

## 문제점 및 개선 방안

### 문제점 1: 메뉴 아이템의 소스 정보가 FMS로 전송되지 않음 ❌

**위치**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/fms_client.py`, 라인 219-226

**현재 코드:**
```python
'items': [
    {
        'menu_id': item.menu_item.menu_id,
        'name': item.menu_item.name,
        'quantity': item.quantity,
        'price': item.menu_item.price  # ← sauce 정보 누락!
    }
    for item in order.items
]
```

**문제점:**
- OrderItem에 sauce 필드가 있지만 FMS 메시지에 포함되지 않음
- 조리 시 소스 정보가 없어 잘못된 제품이 나올 수 있음

**개선 방안:**
```python
'items': [
    {
        'menu_id': item.menu_item.menu_id,
        'name': item.menu_item.name,
        'quantity': item.quantity,
        'price': item.menu_item.price,
        'sauce': item.sauce  # ← 추가
    }
    for item in order.items
]
```

---

### 문제점 2: 주문 생성과 수령 확인 메시지 포맷 불일치 ❌

**주문 생성 메시지:**
```python
{
    'command': 'new_order',  # ← 'command' 필드 사용
    'table_number': 1,
    'order': {...}
}
```

**수령 확인 메시지:**
```python
{
    'type': 'delivery_complete',  # ← 'type' 필드 사용
    'data': {...}
}
```

**문제점:**
- 메시지 포맷 일관성이 없음
- FMS 파서가 혼동할 수 있음

**개선 방안:**
모든 메시지를 통일된 포맷으로 변경:

**방안 A (현재 포맷 유지):**
```python
# FMS 수신 메시지 확인 필요
# 현재 FMS 구현에 맞게 통일
```

**방안 B (통일된 포맷):**
```python
def submit_order(self, order: Order) -> Optional[str]:
    message = {
        'type': 'new_order',  # ← 'type' 사용
        'table_number': order.table_number,
        'data': {
            'order_id': order_id,
            'items': [...],
            'table_number': order.table_number,
            'total_price': order.calculate_total()
        }
    }
    # ...

def confirm_delivery(self, order_id: str, table_number: int) -> bool:
    message = {
        'type': 'delivery_complete',
        'data': {
            'order_id': order_id,
            'table_number': str(table_number)
        }
    }
    # ...
```

---

### 문제점 3: 테이블 번호 동적 선택 불가능 ❌

**현재 상황:**
- 테이블 번호는 명령줄 인자(`--table`)로만 설정 가능
- 런타임 중 변경 불가능
- 여러 테이블을 서빙하는 키오스크 환경에서 부적절

**개선 방안:**

**방안 A: 메인 화면에 테이블 선택 추가**

파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/ui_main_window.py`

```python
class MainWindow(QMainWindow):
    """주문 시작 화면"""

    start_order_signal = pyqtSignal()
    table_selected_signal = pyqtSignal(int)  # 테이블 선택 시그널 추가

    def setup_ui(self):
        """UI 설정"""
        # ... 기존 코드 ...

        # 테이블 번호 선택 스핀박스 추가
        self.spin_table = QSpinBox()
        self.spin_table.setMinimum(1)
        self.spin_table.setMaximum(20)  # 최대 20개 테이블
        self.spin_table.setValue(Config.TABLE_NUMBER)
        self.spin_table.setStyleSheet('font-size: 24px; padding: 10px;')
        layout.addWidget(self.spin_table)

        # 테이블 변경 버튼
        btn_set_table = QPushButton('테이블 번호 설정')
        btn_set_table.setMinimumHeight(60)
        btn_set_table.clicked.connect(self.on_table_selected)
        layout.addWidget(btn_set_table)

    def on_table_selected(self):
        """테이블 번호 설정"""
        table_num = self.spin_table.value()
        Config.TABLE_NUMBER = table_num
        self.table_selected_signal.emit(table_num)
        print(f'[MainWindow] 테이블 번호 변경: {table_num}')
```

**방안 B: 애플리케이션 메인에서 신호 처리**

파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main_fms_direct.py`

```python
def connect_signals(self):
    """시그널 연결 (이벤트 구독)"""
    # 메인 윈도우
    self.main_window.start_order_signal.connect(self.on_start_order)
    self.main_window.table_selected_signal.connect(self.on_table_selected)  # 추가

    # ... 나머지 연결 ...

def on_table_selected(self, table_num: int):
    """테이블 번호 선택"""
    print(f'[App] 테이블 번호 변경: {table_num}')
    Config.TABLE_NUMBER = table_num
```

---

### 문제점 4: 메시지 전송 실패 시 재시도 로직 없음 ❌

**문제점:**
- TCP 전송 실패 시 재시도 없이 바로 실패 처리
- 네트워크 일시적 오류 시 주문 손실 가능

**개선 방안:**

파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/fms_client.py`

```python
class FMSTCPClient:
    def __init__(self, host: str, port: int, max_retries: int = 3):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.is_connected = False
        self.listener_thread: Optional[threading.Thread] = None
        self.running = False
        self.on_message_received: Optional[Callable] = None
        self.max_retries = max_retries

    def send_message(self, message: dict, retry_count: int = 0) -> bool:
        """메시지 전송 (재시도 로직 포함)"""
        if not self.is_connected or not self.socket:
            print('[FMSClient] 오류: FMS 연결되지 않음')
            return False

        try:
            # JSON 직렬화
            json_data = json.dumps(message, ensure_ascii=False)
            message_bytes = json_data.encode('utf-8')

            # 4-byte length header
            length_header = len(message_bytes).to_bytes(4, byteorder='big')

            # 전송
            self.socket.sendall(length_header + message_bytes)
            print(f'[FMSClient] 메시지 전송 성공: {json_data[:200]}...')
            return True

        except Exception as e:
            print(f'[FMSClient] 메시지 전송 실패 (시도 {retry_count + 1}/{self.max_retries + 1}): {e}')

            # 재시도 로직
            if retry_count < self.max_retries:
                time.sleep(1)  # 1초 대기 후 재시도
                return self.send_message(message, retry_count + 1)

            self.is_connected = False
            return False
```

---

### 문제점 5: 배달 알림 테이블 검증 로직이 불완전 ❌

**현재 코드** (라인 244-248):

```python
# 테이블 번호 확인 - 이 GUI의 테이블과 일치하는지 확인
notification_table = int(table_number) if table_number else 0
if notification_table != Config.TABLE_NUMBER:
    print(f'[App] 다른 테이블({notification_table})의 알림, 이 테이블({Config.TABLE_NUMBER})과 무관')
    return
```

**문제점:**
- 순환참조 위험: `Config.TABLE_NUMBER` 변경 후 배달 알림이 와도 검증 실패
- 주문 ID로 현재 주문과의 연결 관계를 확인하지 않음

**개선 방안:**

```python
def on_delivery_notification_received(self, notification: dict):
    """
    배달 알림 수신 (FMS로부터 푸시)
    """
    try:
        order_data = notification.get('data', {})
        order_id = order_data.get('order_id', '')
        table_number = order_data.get('table_number', '')
        robot_id = order_data.get('robot_id', '')

        if not order_id:
            print('[App] 오류: 배달 알림에서 order_id를 찾을 수 없음')
            return

        # 현재 진행 중인 주문과 일치하는지 확인
        active_order = self.current_order or self.pending_order
        if not active_order:
            print(f'[App] 현재 진행 중인 주문이 없음, 배달 알림 무시: {order_id}')
            return

        # order_id로 주문 확인 (테이블 번호 확인보다 정확)
        if active_order.order_id != order_id:
            print(f'[App] 다른 주문({order_id})의 알림, 현재 주문({active_order.order_id})과 무관')
            return

        # 테이블 번호도 검증 (추가 검증)
        notification_table = int(table_number) if table_number else 0
        if notification_table != active_order.table_number:
            print(f'[App] 테이블 번호 불일치: 알림({notification_table}) vs 주문({active_order.table_number})')
            return

        print(f'[App] 배달 알림 - 테이블 {table_number}, 로봇 {robot_id}')
        self.show_delivery_notification(active_order)

    except Exception as e:
        print(f'[App] 배달 알림 처리 오류: {e}')
```

---

### 문제점 6: 수령 완료 후 피드백 부족 ❌

**현재 코드:**
- 메시지박스만 표시 (텍스트 기반)
- 음성 피드백 미사용
- 진동 피드백 없음

**개선 방안:**

파일: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/ui_delivery_notification.py`

```python
def on_confirm_delivery(self):
    """수령 완료 버튼 클릭"""
    if not self.order:
        return

    print(f'[DeliveryNotification] 수령 완료 - 주문 {self.order.order_id}')

    # 깜빡임 중지
    self.stop_blink_animation()

    # 음성 피드백 추가
    self.play_completion_sound()  # 긍정적인 소리

    # 수령 완료 시그널 발생
    self.delivery_confirmed_signal.emit({
        'order_id': self.order.order_id or '',
        'table_number': str(self.order.table_number) if hasattr(self.order, 'table_number') else ''
    })

def play_completion_sound(self):
    """수령 완료 음성 피드백"""
    try:
        import playsound
        # /path/to/sound/completion.mp3 재생
        playsound.playsound('sounds/completion.mp3')
    except Exception as e:
        print(f'[DeliveryNotification] 음성 피드백 실패: {e}')
```

---

### 문제점 7: Order ID 생성 방식이 취약함 ❌

**현재 코드:**
```python
order_id = f'ORD-{int(time.time())}'
```

**문제점:**
- 같은 초에 두 주문이 생기면 ID 충돌 가능
- 주문 조회/추적 시 ID 형식이 일관성 없을 수 있음

**개선 방안:**

```python
def submit_order(self, order: Order) -> Optional[str]:
    """주문 전송 (FMS로 직접)"""
    # UUID 또는 타임스탐프 + 랜덤 조합
    import uuid

    order_id = f'ORD-{int(time.time())}-{str(uuid.uuid4())[:8]}'
    # 또는
    order_id = f'ORD-{uuid.uuid4().hex[:16]}'.upper()

    order.order_id = order_id
    # ...
```

---

## 요약 테이블

| 번호 | 문제점 | 심각도 | 권장사항 |
|------|--------|--------|---------|
| 1 | 소스 정보 미전송 | 높음 | 조리 품질 저하 위험 - 즉시 수정 필요 |
| 2 | 메시지 포맷 불일치 | 중간 | FMS 호환성 확인 후 통일 |
| 3 | 테이블 동적 선택 불가 | 중간 | UI 개선으로 사용성 향상 |
| 4 | 재시도 로직 없음 | 중간 | 네트워크 안정성 개선 |
| 5 | 배달 알림 검증 불완전 | 낮음 | 주문 ID 기반 검증 추가 |
| 6 | 피드백 부족 | 낮음 | 음성/진동 피드백 추가 |
| 7 | Order ID 생성 취약 | 낮음 | UUID 기반 생성으로 개선 |

---

## 실행 방법

```bash
# 1. 테이블 1번으로 실행 (기본값)
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src
python main_fms_direct.py

# 2. 테이블 2번으로 실행
python main_fms_direct.py --table 2

# 3. Mock 모드로 실행 (FMS 연결 없이 테스트)
python main_fms_direct.py --mock

# 4. Mock 모드 + 테이블 3번
python main_fms_direct.py --table 3 --mock
```

---

## 다음 단계

1. **소스 정보 전송 수정** (문제점 1) - 우선순위: 1
2. **메시지 포맷 통일** (문제점 2) - 우선순위: 2
3. **테이블 동적 선택 구현** (문제점 3) - 우선순위: 3
4. **재시도 로직 추가** (문제점 4) - 우선순위: 4
5. **배달 알림 검증 개선** (문제점 5) - 우선순위: 5
6. **음성/진동 피드백 추가** (문제점 6) - 우선순위: 6
7. **Order ID 생성 개선** (문제점 7) - 우선순위: 7
