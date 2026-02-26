# Customer GUI 코드 수정 가이드

## 우선순위별 수정 코드

### 1. 우선순위 1: 소스 정보 FMS로 전송 (문제점 1)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/fms_client.py`

**현재 코드** (라인 219-226):
```python
'items': [
    {
        'menu_id': item.menu_item.menu_id,
        'name': item.menu_item.name,
        'quantity': item.quantity,
        'price': item.menu_item.price
    }
    for item in order.items
]
```

**수정된 코드**:
```python
'items': [
    {
        'menu_id': item.menu_item.menu_id,
        'name': item.menu_item.name,
        'quantity': item.quantity,
        'price': item.menu_item.price,
        'sauce': item.sauce  # ← 추가: 소스 정보 전송
    }
    for item in order.items
]
```

**Edit 명령어**:
```
old_string:
'items': [
    {
        'menu_id': item.menu_item.menu_id,
        'name': item.menu_item.name,
        'quantity': item.quantity,
        'price': item.menu_item.price
    }
    for item in order.items
]

new_string:
'items': [
    {
        'menu_id': item.menu_item.menu_id,
        'name': item.menu_item.name,
        'quantity': item.quantity,
        'price': item.menu_item.price,
        'sauce': item.sauce
    }
    for item in order.items
]
```

---

### 2. 우선순위 2: 메시지 포맷 통일 (문제점 2)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/fms_client.py`

**현재 코드** (라인 194-232):
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
```

**수정된 코드** (형식 통일):
```python
def submit_order(self, order: Order) -> Optional[str]:
    """
    주문 전송 (FMS로 직접)

    메시지 형식:
    {
        'type': 'new_order',
        'table_number': 1,
        'data': {
            'order_id': 'ORD-XXX',
            'items': [...],
            'table_number': 1,
            'total_price': 10000
        }
    }
    """
    # order_id 생성 (타임스탬프 + 랜덤 조합)
    import uuid
    order_id = f'ORD-{int(time.time())}-{str(uuid.uuid4())[:8]}'
    order.order_id = order_id

    # FMS 주문 메시지 생성 (포맷 통일)
    message = {
        'type': 'new_order',  # ← 'command' → 'type'로 변경
        'table_number': order.table_number,
        'data': {  # ← 'order' → 'data'로 변경
            'order_id': order_id,
            'items': [
                {
                    'menu_id': item.menu_item.menu_id,
                    'name': item.menu_item.name,
                    'quantity': item.quantity,
                    'price': item.menu_item.price,
                    'sauce': item.sauce  # ← 소스 정보 추가
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

**주의사항**: FMS 서버 코드가 'command' 또는 'type' 중 어느 것을 사용하는지 확인 필요. FMS 코드 확인 후 적절히 선택.

---

### 3. 우선순위 3: 테이블 동적 선택 (문제점 3)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/ui_main_window.py`

**현재 코드**:
```python
class MainWindow(QMainWindow):
    """주문 시작 화면"""

    # 시그널 정의
    start_order_signal = pyqtSignal()  # 주문 시작 버튼 클릭 시그널

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.connect_signals()

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

    def connect_signals(self):
        """시그널 연결"""
        self.btn_start_order.clicked.connect(self.on_start_order)

    def on_start_order(self):
        """주문 시작 버튼 클릭"""
        print(f'[MainWindow] 주문 시작 - 테이블 {Config.TABLE_NUMBER}')
        self.start_order_signal.emit()
```

**수정된 코드**:
```python
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QPushButton, QSpinBox, QLabel, QWidget
from PyQt5.QtCore import pyqtSignal, Qt

class MainWindow(QMainWindow):
    """주문 시작 화면"""

    # 시그널 정의
    start_order_signal = pyqtSignal()  # 주문 시작 버튼 클릭 시그널
    table_selected_signal = pyqtSignal(int)  # 테이블 번호 선택 시그널 추가

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """UI 설정"""
        # .ui 파일 로드 (있을 경우)
        ui_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'ui',
            'main_window.ui'
        )

        try:
            loadUi(ui_path, self)
        except:
            # .ui 파일이 없는 경우, 프로그래매틱하게 생성
            self._create_ui_programmatically()

        # 윈도우 설정
        self.setWindowTitle('주문 시작')
        if Config.FULLSCREEN:
            self.showFullScreen()
        else:
            self.resize(Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)

        # 테이블 번호 선택 UI 추가/수정
        self._setup_table_selection()

    def _create_ui_programmatically(self):
        """UI를 프로그래매틱하게 생성"""
        central_widget = QWidget()
        layout = QVBoxLayout()

        # 제목
        title = QLabel('<h1>주문 키오스크</h1>')
        layout.addWidget(title)

        # 테이블 번호 표시
        self.label_table = QLabel(f'테이블 번호: {Config.TABLE_NUMBER}')
        self.label_table.setStyleSheet('font-size: 20px; padding: 10px;')
        layout.addWidget(self.label_table)

        # 주문 시작 버튼
        self.btn_start_order = QPushButton('주문 시작')
        self.btn_start_order.setMinimumHeight(80)
        self.btn_start_order.setStyleSheet('font-size: 24px; font-weight: bold;')
        layout.addWidget(self.btn_start_order)

        layout.addStretch()

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def _setup_table_selection(self):
        """테이블 번호 선택 UI 설정"""
        # 기존 UI에서 테이블 관련 위젯 찾기
        if hasattr(self, 'spin_table'):
            # 이미 존재하는 경우 스킵
            return

        # 없으면 생성
        layout = self.layout() or QVBoxLayout(self.centralWidget())

        # 스페이서 추가 (간격)
        from PyQt5.QtWidgets import QSpacerItem, QSizePolicy
        spacer = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.insertSpacing(layout.count() - 1, 20) if layout.count() > 0 else None

        # 테이블 번호 스핀박스
        table_label = QLabel('테이블 번호:')
        table_label.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.insertWidget(layout.count() - 1, table_label)

        self.spin_table = QSpinBox()
        self.spin_table.setMinimum(1)
        self.spin_table.setMaximum(20)  # 최대 20개 테이블
        self.spin_table.setValue(Config.TABLE_NUMBER)
        self.spin_table.setStyleSheet('font-size: 20px; padding: 10px; min-height: 50px;')
        layout.insertWidget(layout.count() - 1, self.spin_table)

        # 테이블 번호 설정 버튼
        self.btn_set_table = QPushButton('테이블 번호 설정')
        self.btn_set_table.setMinimumHeight(60)
        self.btn_set_table.setStyleSheet('font-size: 18px;')
        layout.insertWidget(layout.count() - 1, self.btn_set_table)

    def connect_signals(self):
        """시그널 연결"""
        self.btn_start_order.clicked.connect(self.on_start_order)

        # 테이블 번호 설정 버튼
        if hasattr(self, 'btn_set_table'):
            self.btn_set_table.clicked.connect(self.on_table_set)

        # 스핀박스 엔터 키
        if hasattr(self, 'spin_table'):
            self.spin_table.returnPressed.connect(self.on_table_set)

    def on_start_order(self):
        """주문 시작 버튼 클릭"""
        print(f'[MainWindow] 주문 시작 - 테이블 {Config.TABLE_NUMBER}')
        self.start_order_signal.emit()

    def on_table_set(self):
        """테이블 번호 설정"""
        if hasattr(self, 'spin_table'):
            table_num = self.spin_table.value()
            Config.TABLE_NUMBER = table_num
            self.label_table.setText(f'테이블 번호: {table_num}')
            self.table_selected_signal.emit(table_num)
            print(f'[MainWindow] 테이블 번호 변경: {table_num}')
```

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main_fms_direct.py`

**현재 코드** (라인 126-129):
```python
def connect_signals(self):
    """시그널 연결 (이벤트 구독)"""
    # 메인 윈도우
    self.main_window.start_order_signal.connect(self.on_start_order)
```

**수정된 코드**:
```python
def connect_signals(self):
    """시그널 연결 (이벤트 구독)"""
    # 메인 윈도우
    self.main_window.start_order_signal.connect(self.on_start_order)
    self.main_window.table_selected_signal.connect(self.on_table_selected)  # ← 추가

    # ... 나머지 연결 ...

def on_table_selected(self, table_num: int):
    """테이블 번호 선택 처리"""
    print(f'[App] 테이블 번호 변경: {table_num}')
    Config.TABLE_NUMBER = table_num
    self.current_order = None
    self.pending_order = None
    # UI는 자동으로 Config.TABLE_NUMBER를 사용하므로 추가 처리 불필요
```

---

### 4. 우선순위 4: 메시지 재시도 로직 (문제점 4)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/fms_client.py`

**현재 코드** (라인 73-95):
```python
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
```

**수정된 코드**:
```python
def __init__(self, host: str, port: int, max_retries: int = 3, retry_delay: float = 1.0):
    self.host = host
    self.port = port
    self.socket: Optional[socket.socket] = None
    self.is_connected = False
    self.listener_thread: Optional[threading.Thread] = None
    self.running = False
    self.on_message_received: Optional[Callable] = None
    self.max_retries = max_retries  # ← 추가
    self.retry_delay = retry_delay  # ← 추가

def send_message(self, message: dict, retry_count: int = 0) -> bool:
    """메시지 전송 (4-byte length header + JSON, 재시도 로직 포함)"""
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
            time.sleep(self.retry_delay)
            print(f'[FMSClient] {self.retry_delay}초 후 재시도...')
            return self.send_message(message, retry_count + 1)

        self.is_connected = False
        return False
```

---

### 5. 우선순위 5: 배달 알림 검증 개선 (문제점 5)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/main_fms_direct.py`

**현재 코드** (라인 218-259):
```python
def on_delivery_notification_received(self, notification: dict):
    """
    배달 알림 수신 (FMS로부터 푸시)

    메시지 형식:
    {
        'type': 'delivery_notification',
        'data': {
            'order_id': 'ORD-XXX',
            'table_number': '1',
            'robot_id': 'pinky1'
        }
    }
    """
    print(f'[App] 배달 알림 수신: {notification}')

    try:
        order_data = notification.get('data', {})
        order_id = order_data.get('order_id', '')
        table_number = order_data.get('table_number', '')
        robot_id = order_data.get('robot_id', '')

        if not order_id:
            print('[App] 오류: 배달 알림에서 order_id를 찾을 수 없음')
            return

        # 테이블 번호 확인 - 이 GUI의 테이블과 일치하는지 확인
        notification_table = int(table_number) if table_number else 0
        if notification_table != Config.TABLE_NUMBER:
            print(f'[App] 다른 테이블({notification_table})의 알림, 이 테이블({Config.TABLE_NUMBER})과 무관')
            return

        # 현재 주문 또는 대기 중인 주문이 있으면 배달 알림 표시
        active_order = self.current_order or self.pending_order
        if active_order:
            print(f'[App] 배달 알림 - 테이블 {table_number}, 로봇 {robot_id}')
            self.show_delivery_notification(active_order)
        else:
            print(f'[App] 현재 주문이 없음, 배달 알림 무시: {order_id}')

    except Exception as e:
        print(f'[App] 배달 알림 처리 오류: {e}')
```

**수정된 코드**:
```python
def on_delivery_notification_received(self, notification: dict):
    """
    배달 알림 수신 (FMS로부터 푸시)

    메시지 형식:
    {
        'type': 'delivery_notification',
        'data': {
            'order_id': 'ORD-XXX',
            'table_number': '1',
            'robot_id': 'pinky1'
        }
    }
    """
    print(f'[App] 배달 알림 수신: {notification}')

    try:
        order_data = notification.get('data', {})
        order_id = order_data.get('order_id', '')
        table_number = order_data.get('table_number', '')
        robot_id = order_data.get('robot_id', '')

        if not order_id:
            print('[App] 오류: 배달 알림에서 order_id를 찾을 수 없음')
            return

        # 현재 진행 중인 주문 확인
        active_order = self.current_order or self.pending_order
        if not active_order:
            print(f'[App] 현재 진행 중인 주문이 없음, 배달 알림 무시: {order_id}')
            return

        # 주문 ID로 일치 검증 (가장 정확한 방법)
        if active_order.order_id != order_id:
            print(f'[App] 다른 주문({order_id})의 알림, 현재 주문({active_order.order_id})과 무관')
            return

        # 테이블 번호도 검증 (추가 검증)
        try:
            notification_table = int(table_number) if table_number else 0
            if notification_table != active_order.table_number:
                print(f'[App] 테이블 번호 불일치: 알림({notification_table}) vs 주문({active_order.table_number})')
                return
        except ValueError:
            print(f'[App] 테이블 번호 형식 오류: {table_number}')
            return

        # 검증 성공 - 배달 알림 표시
        print(f'[App] 배달 알림 - 테이블 {table_number}, 로봇 {robot_id}, 주문 {order_id}')
        self.show_delivery_notification(active_order)

    except Exception as e:
        print(f'[App] 배달 알림 처리 오류: {e}')
```

---

### 6. 우선순위 6: 음성 피드백 추가 (문제점 6)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/ui_delivery_notification.py`

**추가 import**:
```python
import os
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl
```

**수정된 코드** (on_confirm_delivery 메서드):
```python
def on_confirm_delivery(self):
    """수령 완료 버튼 클릭 - SR-16: 음식 수령 확인"""
    if not self.order:
        return

    print(f'[DeliveryNotification] 수령 완료 - 주문 {self.order.order_id}')

    # 깜빡임 중지
    self.stop_blink_animation()

    # 음성 피드백 재생
    self.play_completion_sound()

    # 수령 완료 시그널 발생
    self.delivery_confirmed_signal.emit({
        'order_id': self.order.order_id or '',
        'table_number': str(self.order.table_number) if hasattr(self.order, 'table_number') else ''
    })

def play_completion_sound(self):
    """수령 완료 음성 피드백"""
    try:
        # 방법 1: playsound 라이브러리 사용
        try:
            import playsound
            sound_file = os.path.join(
                os.path.dirname(__file__),
                '..',
                'sounds',
                'completion.mp3'
            )
            if os.path.exists(sound_file):
                playsound.playsound(sound_file)
                return
        except ImportError:
            pass

        # 방법 2: PyQt5 QMediaPlayer 사용
        try:
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            from PyQt5.QtCore import QUrl

            sound_file = os.path.join(
                os.path.dirname(__file__),
                '..',
                'sounds',
                'completion.mp3'
            )
            if os.path.exists(sound_file):
                player = QMediaPlayer()
                player.setMedia(QMediaContent(QUrl.fromLocalFile(sound_file)))
                player.play()
                return
        except ImportError:
            pass

        # 방법 3: 시스템 비프 음 출력
        print('\a')  # 벨 음

    except Exception as e:
        print(f'[DeliveryNotification] 음성 피드백 실패: {e}')
```

---

### 7. 우선순위 7: Order ID 생성 개선 (문제점 7)

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src/fms_client.py`

**현재 코드** (라인 209-210):
```python
# order_id 생성 (타임스탬프 기반)
order_id = f'ORD-{int(time.time())}'
```

**수정된 코드**:
```python
# order_id 생성 (타임스탐프 + UUID 조합)
import uuid
order_id = f'ORD-{int(time.time())}-{str(uuid.uuid4())[:8]}'.upper()
# 또는 더 간단하게:
order_id = f'ORD-{uuid.uuid4().hex[:12]}'.upper()
```

**전체 수정 예시**:
```python
def submit_order(self, order: Order) -> Optional[str]:
    """
    주문 전송 (FMS로 직접)

    메시지 형식:
    {
        'type': 'new_order',
        'table_number': 1,
        'data': {
            'order_id': 'ORD-XXX',
            'items': [...],
            'table_number': 1,
            'total_price': 10000
        }
    }
    """
    import uuid

    # order_id 생성 (UUID 기반 - 충돌 위험 제거)
    order_id = f'ORD-{uuid.uuid4().hex[:12]}'.upper()
    order.order_id = order_id

    # FMS 주문 메시지 생성
    message = {
        'type': 'new_order',
        'table_number': order.table_number,
        'data': {
            'order_id': order_id,
            'items': [
                {
                    'menu_id': item.menu_item.menu_id,
                    'name': item.menu_item.name,
                    'quantity': item.quantity,
                    'price': item.menu_item.price,
                    'sauce': item.sauce
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

---

## 통합 수정 스크립트

모든 수정을 한 번에 적용하려면 다음 순서로 진행하세요:

1. **fms_client.py** 수정 (우선순위 1, 2, 4, 7)
2. **main_fms_direct.py** 수정 (우선순위 3, 5)
3. **ui_main_window.py** 수정 (우선순위 3)
4. **ui_delivery_notification.py** 수정 (우선순위 6)

---

## 테스트 체크리스트

- [ ] 소스 정보가 FMS로 전송되는지 확인 (콘솔 로그)
- [ ] 메시지 포맷이 통일되었는지 확인 (콘솔 로그)
- [ ] 테이블 번호를 동적으로 선택할 수 있는지 확인
- [ ] 네트워크 오류 시 재시도가 작동하는지 확인
- [ ] 배달 알림이 올바른 주문에만 표시되는지 확인
- [ ] 수령 완료 시 음성 피드백이 재생되는지 확인
- [ ] Order ID가 고유한지 확인 (같은 초에 여러 주문)

---

## 주의사항

1. **FMS 호환성**: 메시지 포맷 변경 전에 FMS 서버의 기대 포맷 확인 필요
2. **음성 파일**: 음성 피드백을 사용하려면 `sounds/completion.mp3` 파일이 필요
3. **재시도 설정**: 재시도 횟수와 지연 시간은 필요에 따라 조정 가능
4. **테이블 수**: 테이블 선택 UI에서 최대 테이블 수(20)를 실제 운영 환경에 맞게 조정 필요
