# GUI 문제점 및 해결방안

**작성일**: 2026-02-25
**Specialist**: GUI Specialist (Haiku)
**우선순위**: Critical, Major, Minor

---

## Issue #1: TCP 프로토콜 불일치 (CRITICAL)

### 현재 상황

**Customer GUI** (`tcp_client.py` 라인 60-81):
```python
def send_data(self, data: dict) -> bool:
    json_data = json.dumps(data, ensure_ascii=False)
    message = json_data.encode('utf-8')
    length_header = len(message).to_bytes(4, byteorder='big')  # 길이 헤더 사용

    self.socket.sendall(length_header + message)  # [4바이트][JSON]
```

**Admin GUI** (`fleet_client.py` 라인 73-99):
```python
def send_request(self, message_type: str, data: dict) -> bool:
    message = {
        'type': message_type,
        'data': data
    }
    json_data = json.dumps(message, ensure_ascii=False)
    self.socket.sendall(json_data.encode('utf-8'))  # 길이 헤더 없음
```

### 문제 분석

| 측면 | Customer GUI | Admin GUI |
|------|-------------|----------|
| 메시지 형식 | `[4B][JSON]` | `[JSON]` |
| 수신 방식 | 길이 헤더 읽기 | 스트림 읽기 + JSON 파싱 |
| 메시지 경계 | 명확함 | 불명확함 |

**결과**: Main Server가 두 가지 형식을 모두 처리해야 함 (불가능)

### 해결방안

#### 옵션 A: 모두 길이 헤더 형식으로 통일 (권장)

**Admin GUI 수정** (`fleet_client.py`):
```python
def send_request(self, message_type: str, data: dict) -> bool:
    if not self.is_connected:
        print('[FleetClient] 연결되지 않음')
        return False

    try:
        message = {
            'type': message_type,
            'data': data
        }
        json_data = json.dumps(message, ensure_ascii=False)
        message_bytes = json_data.encode('utf-8')

        # 길이 헤더 추가 (Customer GUI와 동일)
        length_header = len(message_bytes).to_bytes(4, byteorder='big')
        self.socket.sendall(length_header + message_bytes)

        return True
    except Exception as e:
        print(f'[FleetClient] 요청 전송 실패: {str(e)}')
        self.error_signal.emit(f'요청 전송 실패: {str(e)}')
        return False
```

**Admin GUI 수신** (`fleet_client.py` 라인 101-143):
```python
def _receive_loop(self):
    """메시지 수신 루프 (별도 스레드)"""
    buffer = b''

    while self.running:
        try:
            # 길이 헤더 수신 (4 bytes)
            length_header = self.socket.recv(4)
            if not length_header:
                print('[FleetClient] 서버 연결 끊김')
                break

            message_length = int.from_bytes(length_header, byteorder='big')

            # 메시지 수신
            message = b''
            while len(message) < message_length:
                chunk = self.socket.recv(
                    min(4096, message_length - len(message))
                )
                if not chunk:
                    break
                message += chunk

            # JSON 파싱
            json_data = message.decode('utf-8')
            message_dict = json.loads(json_data)

            # 메시지 처리
            self._handle_message(message_dict)

        except socket.timeout:
            continue
        except Exception as e:
            if self.running:
                print(f'[FleetClient] 수신 오류: {str(e)}')
            break

    # 연결 종료
    self.disconnect()
```

**Main Server 수신** (모두 동일 형식):
```python
def receive_message(socket):
    # 길이 헤더 읽기
    length_header = socket.recv(4)
    if not length_header:
        return None

    message_length = int.from_bytes(length_header, byteorder='big')

    # 메시지 읽기
    message = b''
    while len(message) < message_length:
        chunk = socket.recv(min(4096, message_length - len(message)))
        if not chunk:
            break
        message += chunk

    return json.loads(message.decode('utf-8'))
```

#### 옵션 B: 메시지 마지막에 구분자 추가

**문제**: 바이너리 데이터 포함 시 실패 가능

### 구현 체크리스트

- [ ] Admin GUI fleet_client.py 수정 (send_request)
- [ ] Admin GUI fleet_client.py 수정 (_receive_loop)
- [ ] Main Server TCP 서버 수정 (통일된 형식 수신)
- [ ] Customer GUI 호환성 확인
- [ ] 통합 테스트 실행
- [ ] 배포

### 예상 시간
- 구현: 30분
- 테스트: 1시간
- 배포: 15분

---

## Issue #2: 메시지 파싱 버퍼 오버플로우 위험 (CRITICAL)

### 현재 상황

**Admin GUI** (`fleet_client.py` 라인 115-132):
```python
while buffer:
    try:
        # 버퍼 전체를 UTF-8로 디코드하고 JSON 파싱
        message_str = buffer.decode('utf-8')
        message = json.loads(message_str)
        buffer = b''  # 성공하면 버퍼 비우기
    except json.JSONDecodeError:
        # 불완전한 JSON이면 더 받기
        break
    except Exception as e:
        print(f'[FleetClient] 메시지 처리 오류: {str(e)}')
        buffer = b''
        break
```

### 문제 분석

**시나리오 1: 큰 메시지가 여러 번 수신**
```
수신 1: {"type": "fleet_status_update", "data": {
수신 2: "robots": [{"robot_id": "pinky1"}...
수신 3: ]}}}

현재 로직:
1. 첫 수신: JSON 불완전 → JSONDecodeError → break
2. 두 번째 loop 진입: 첫 데이터 + 두 번째 데이터 조합
3. 여전히 불완전 → break
4. 세 번째 loop 진입: 모든 데이터 조합 → 성공
```

**문제**: 메모리 누적 및 불필요한 파싱 시도

**시나리오 2: 메시지 경계 오류**
```
메시지 1: {...}메시지 2: {...}

현재 로직이 메시지 1만 파싱하고 메시지 2는 버림
```

### 해결방안

**Issue #1을 먼저 해결하면 자동 해결됨**

길이 헤더를 사용하면:
```python
def _receive_loop(self):
    while self.running:
        try:
            # 정확한 길이 읽기
            length_header = self.socket.recv(4)
            if not length_header:
                break

            message_length = int.from_bytes(length_header, byteorder='big')

            # 정확한 길이만큼 읽기
            message = b''
            while len(message) < message_length:
                chunk = self.socket.recv(
                    min(4096, message_length - len(message))
                )
                if not chunk:
                    break
                message += chunk

            # 메시지 경계가 명확하므로 안전
            data = json.loads(message.decode('utf-8'))
            self._handle_message(data)

        except Exception as e:
            # 에러 처리
            break
```

### 예상 시간
Issue #1 수정 시 자동 해결 (추가 시간 0분)

---

## Issue #3: 자동 재연결 기능 부재 (MAJOR)

### 현재 상황

**Customer GUI** (`tcp_client.py` 라인 31-45):
```python
def connect(self) -> bool:
    try:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5.0)
        self.socket.connect((self.host, self.port))
        self.is_connected = True
        self.connected_signal.emit()
        print(f'[TCPClient] 연결 성공: {self.host}:{self.port}')
        return True
    except Exception as e:
        error_msg = f'연결 실패: {str(e)}'
        print(f'[TCPClient] {error_msg}')
        self.error_signal.emit(error_msg)
        return False  # 재연결 시도 안 함
```

**Admin GUI** (`fleet_client.py` 라인 37-57):
```python
def connect(self) -> bool:
    try:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5.0)
        self.socket.connect((self.host, self.port))
        self.is_connected = True
        self.running = True

        # 수신 스레드 시작
        self.receive_thread = threading.Thread(
            target=self._receive_loop, daemon=True
        )
        self.receive_thread.start()

        self.connected_signal.emit()
        print(f'[FleetClient] Main Server 연결 성공: {self.host}:{self.port}')
        return True
    except Exception as e:
        error_msg = f'Main Server 연결 실패: {str(e)}'
        print(f'[FleetClient] {error_msg}')
        self.error_signal.emit(error_msg)
        return False  # 재연결 시도 안 함
```

### 문제 분석

**Restaurant 환경의 WiFi 불안정성**:
```
시나리오:
1. 고객이 주문 진행 중
2. WiFi 신호 약해짐
3. TCP 연결 끊김
4. GUI에서 에러 메시지 표시
5. 사용자가 대기... (자동 재연결 없음)
6. 관리자가 앱 재시작 필요

결과: 주문 완료 불가능
```

### 해결방안

#### Customer GUI OrderServiceClient 수정

```python
class OrderServiceClient(QObject):
    # ... 기존 시그널 ...
    reconnecting_signal = pyqtSignal(int)  # 재연결 시도 횟수
    reconnected_signal = pyqtSignal()       # 재연결 성공

    RECONNECT_DELAYS = [1, 2, 4, 8, 16, 32]  # 초 단위
    MAX_RECONNECT_ATTEMPTS = 10

    def __init__(self):
        super().__init__()
        self.client = TCPClient(*Config.get_order_ms_address())
        self.client.error_signal.connect(self.on_tcp_error)
        self.reconnect_thread = None
        self.reconnect_attempt = 0

    def on_tcp_error(self, error_msg: str):
        """TCP 오류 발생 시 재연결 시작"""
        if not hasattr(self, '_reconnecting'):
            self._reconnecting = False

        if not self._reconnecting:
            self._reconnecting = True
            self.reconnect_attempt = 0
            self._start_reconnect()

        self.error_signal.emit(error_msg)

    def _start_reconnect(self):
        """재연결 스레드 시작"""
        self.reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            daemon=True
        )
        self.reconnect_thread.start()

    def _reconnect_loop(self):
        """재연결 루프"""
        while self.reconnect_attempt < self.MAX_RECONNECT_ATTEMPTS:
            # 지수 백오프 대기
            delay_idx = min(self.reconnect_attempt, len(self.RECONNECT_DELAYS) - 1)
            delay = self.RECONNECT_DELAYS[delay_idx]

            print(f'[OrderService] {delay}초 후 재연결 시도 ({self.reconnect_attempt + 1}/{self.MAX_RECONNECT_ATTEMPTS})')
            self.reconnecting_signal.emit(self.reconnect_attempt + 1)

            time.sleep(delay)

            # 재연결 시도
            if self.client.connect():
                print(f'[OrderService] 재연결 성공!')
                self.reconnected_signal.emit()
                self._reconnecting = False
                return

            self.reconnect_attempt += 1

        # 최대 재시도 횟수 초과
        print(f'[OrderService] 재연결 실패 (최대 시도 횟수 초과)')
        self._reconnecting = False
        self.error_signal.emit('서버 연결 불가 - 나중에 다시 시도해주세요')
```

#### Admin GUI FleetClient 수정

```python
class FleetClient(QObject):
    # ... 기존 시그널 ...
    reconnecting_signal = pyqtSignal(int)
    reconnected_signal = pyqtSignal()

    RECONNECT_DELAYS = [1, 2, 4, 8, 16, 32]
    MAX_RECONNECT_ATTEMPTS = 10

    def __init__(self, host: str = 'localhost', port: int = 9999):
        super().__init__()
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False
        self.receive_thread = None
        self.running = False
        self._reconnecting = False
        self.reconnect_attempt = 0
        self.reconnect_thread = None

    def _receive_loop(self):
        """메시지 수신 루프"""
        buffer = b''

        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    print('[FleetClient] 서버 연결 끊김')
                    self._reconnecting = False
                    break

                buffer += data
                # ... 기존 메시지 파싱 로직 ...

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f'[FleetClient] 수신 오류: {str(e)}')
                self._reconnecting = False
                break

        # 연결 종료
        self.disconnect()

        # 자동 재연결 시도
        if not self._reconnecting:
            self._start_reconnect()

    def _start_reconnect(self):
        """재연결 스레드 시작"""
        self._reconnecting = True
        self.reconnect_attempt = 0
        self.reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            daemon=True
        )
        self.reconnect_thread.start()

    def _reconnect_loop(self):
        """재연결 루프"""
        while self.reconnect_attempt < self.MAX_RECONNECT_ATTEMPTS:
            delay_idx = min(self.reconnect_attempt, len(self.RECONNECT_DELAYS) - 1)
            delay = self.RECONNECT_DELAYS[delay_idx]

            print(f'[FleetClient] {delay}초 후 재연결 시도 ({self.reconnect_attempt + 1}/{self.MAX_RECONNECT_ATTEMPTS})')
            self.reconnecting_signal.emit(self.reconnect_attempt + 1)

            time.sleep(delay)

            # 재연결 시도
            if self._try_connect():
                print(f'[FleetClient] 재연결 성공!')
                self.reconnected_signal.emit()
                self._reconnecting = False
                return

            self.reconnect_attempt += 1

        print(f'[FleetClient] 재연결 실패 (최대 시도 횟수 초과)')
        self._reconnecting = False
        self.error_signal.emit('FMS Server 연결 불가')

    def _try_connect(self) -> bool:
        """재연결 시도"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            self.running = True

            # 수신 스레드 시작
            self.receive_thread = threading.Thread(
                target=self._receive_loop,
                daemon=True
            )
            self.receive_thread.start()

            self.connected_signal.emit()
            return True
        except Exception as e:
            print(f'[FleetClient] 재연결 시도 실패: {str(e)}')
            return False
```

#### UI 업데이트

**Customer GUI** (`main.py`):
```python
def on_start_order(self):
    # 기존 코드
    self.order_client.reconnecting_signal.connect(self.on_reconnecting)
    self.order_client.reconnected_signal.connect(self.on_reconnected)

def on_reconnecting(self, attempt: int):
    print(f'[App] 서버 재연결 시도 ({attempt}회)')
    # 사용자 피드백 표시 가능

def on_reconnected(self):
    print(f'[App] 서버 재연결 성공')
    QMessageBox.information(self, '연결 복구', '서버 연결이 복구되었습니다.')
```

**Admin GUI** (`ui_fleet_monitor.py`):
```python
def __init__(self, use_mock=True, parent=None):
    # ...
    self.client.reconnecting_signal.connect(self.on_client_reconnecting)
    self.client.reconnected_signal.connect(self.on_client_reconnected)

def on_client_reconnecting(self, attempt: int):
    status = f'재연결 시도 중 ({attempt}/10)...'
    self.connection_status.setText(status)
    self.connection_status.setStyleSheet("color: orange; font-weight: bold;")
    self.log_event(status)

def on_client_reconnected(self):
    self.connection_status.setText('연결됨')
    self.connection_status.setStyleSheet("color: green; font-weight: bold;")
    self.log_event('FMS Server 재연결 성공')
```

### 예상 시간
- 구현: 1.5시간
- 테스트: 1시간
- 배포: 15분

---

## Issue #4: 배달 알림 시뮬레이션 (MAJOR)

### 현재 상황

**Customer GUI** (`main.py` 라인 156-189):
```python
def on_order_submitted(self, order: Order):
    # ...
    QMessageBox.information(...)
    self.go_to_main()

    # 시뮬레이션: 5초 후 배달 알림 (실제로는 TCP로 알림 수신)
    from PyQt5.QtCore import QTimer
    QTimer.singleShot(5000, lambda: self.show_delivery_notification(order))
```

### 문제 분석

- 실제 FMS로부터 배달 알림 수신 메커니즘 없음
- 고정 5초 타이머로 시뮬레이션
- Main Server로부터의 배달 알림도 받지 않음

### 해결방안

#### 방법 1: Main Server에서 배달 알림 수신

**Customer GUI에 배달 알림 수신 스레드 추가**:

```python
class CustomerGUIApp(QStackedWidget):
    # 배달 알림 시그널 추가
    delivery_notification_signal = pyqtSignal(dict)  # {'order_id', 'table_number', 'robot_id'}

    def setup_client(self):
        # ...
        # 배달 알림 수신 스레드 시작
        self.delivery_listener_thread = threading.Thread(
            target=self._listen_delivery_notifications,
            daemon=True
        )
        self.delivery_listener_thread.start()

    def _listen_delivery_notifications(self):
        """FMS로부터 배달 알림 수신"""
        # Main Server에 별도 연결 (배달 알림 수신용)
        notification_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        notification_socket.settimeout(5.0)

        try:
            # Main Server의 배달 알림 포트에 연결
            notification_socket.connect((
                Config.ORDER_MS_HOST,
                Config.ORDER_MS_PORT + 1  # 배달 알림 포트 (예: 5001)
            ))

            while True:
                # 배달 알림 수신
                length_header = notification_socket.recv(4)
                if not length_header:
                    break

                message_length = int.from_bytes(length_header, byteorder='big')
                message = b''
                while len(message) < message_length:
                    chunk = notification_socket.recv(
                        min(4096, message_length - len(message))
                    )
                    if not chunk:
                        break
                    message += chunk

                data = json.loads(message.decode('utf-8'))

                # order_id 확인
                if data.get('order_id') == self.current_order.order_id:
                    # 배달 알림 신호
                    self.delivery_notification_signal.emit(data)

        except Exception as e:
            print(f'[App] 배달 알림 수신 오류: {str(e)}')
        finally:
            notification_socket.close()

    def connect_signals(self):
        # ...
        self.delivery_notification_signal.connect(self.on_delivery_arrived)

    def on_delivery_arrived(self, notification_data: dict):
        """배달 알림 수신"""
        print(f'[App] 배달 알림: {notification_data}')
        order_id = notification_data.get('order_id')

        # 현재 주문과 비교
        if self.current_order and self.current_order.order_id == order_id:
            self.show_delivery_notification(self.current_order)
```

#### 방법 2: Main Server에서 배달 알림을 기존 TCP 연결로 전송

**더 간단한 방법 - 기존 TCP 연결 재사용**:

```python
class OrderServiceClient(QObject):
    delivery_arrived_signal = pyqtSignal(dict)  # {'order_id', 'table_number', 'robot_id'}

    def __init__(self):
        super().__init__()
        # ...
        # 배달 알림 수신 스레드
        self.listen_thread = threading.Thread(
            target=self._listen_delivery,
            daemon=True
        )
        self.listen_thread.start()

    def _listen_delivery(self):
        """배달 알림 수신 (별도 스레드)"""
        while self.client.is_connected:
            try:
                # Main Server로부터 배달 알림 수신
                # (수신은 이미 send_data 후에 자동으로 되어야 함)
                response = self.client.receive_data()

                if response and response.get('type') == 'delivery_arrived':
                    self.delivery_arrived_signal.emit(response.get('data', {}))

                time.sleep(0.1)
            except Exception as e:
                print(f'[OrderService] 배달 알림 수신 오류: {str(e)}')
                break
```

**Customer GUI 연결**:

```python
def __init__(self):
    # ...
    self.order_client.delivery_arrived_signal.connect(self.on_delivery_arrived)

def on_delivery_arrived(self, notification_data: dict):
    """배달 알림 수신"""
    order_id = notification_data.get('order_id')

    if self.current_order and self.current_order.order_id == order_id:
        print(f'[App] 배달 도착! 주문: {order_id}')
        # 배달 알림 화면 표시
        self.show_delivery_notification(self.current_order)
```

### 예상 시간
- 방법 1 구현: 2시간
- 방법 2 구현: 1시간
- 테스트: 1시간
- 배포: 15분

---

## Issue #5: ROS_DOMAIN_ID를 UI에 표시하지 않음 (MINOR)

### 현재 상황

**Admin GUI** (`ui_fleet_monitor.py` 라인 222-225):
```python
table.setHorizontalHeaderLabels([
    '로봇명', 'Robot ID', 'IP 주소', '상태', '연결',
    '배터리 (V)', '현재 작업', '최종 업데이트'
])
```

### 해결방안

**컬럼 추가**:

```python
def create_mobile_robot_table(self) -> QTableWidget:
    """Mobile Robot (PinkyPro) 테이블 생성"""
    table = QTableWidget()
    table.setColumnCount(9)  # 기존 8개에서 9개로 변경
    table.setHorizontalHeaderLabels([
        '로봇명', 'Robot ID', 'Domain ID', 'IP 주소', '상태', '연결',
        '배터리 (V)', '현재 작업', '최종 업데이트'
    ])

    # ... 기존 코드 ...

    for row, (name, cfg) in enumerate(mobile_robots.items()):
        enabled = cfg.get('enabled', False)
        robot_id = cfg.get('robot_id', '-')
        domain_id = cfg.get('domain_id', '-')  # Domain ID 추가
        ip_addr = cfg.get('ip_address', '-')

        table.setItem(row, 0, QTableWidgetItem(name))
        table.setItem(row, 1, QTableWidgetItem(robot_id))
        table.setItem(row, 2, QTableWidgetItem(str(domain_id)))  # Domain ID 표시
        table.setItem(row, 3, QTableWidgetItem(ip_addr))  # 기존 IP주소를 위치 조정
        # ... 나머지 컬럼 ...

def create_cobot_table(self) -> QTableWidget:
    """Cobot Arm (JetCobot) 테이블 생성"""
    table = QTableWidget()
    table.setColumnCount(9)
    table.setHorizontalHeaderLabels([
        '로봇명', 'Robot ID', 'Domain ID', 'IP 주소', '상태', '연결',
        '온도', '현재 작업', '최종 업데이트'
    ])

    # ... 동일하게 Domain ID 추가 ...
```

### 예상 시간
- 구현: 15분
- 테스트: 10분
- 배포: 5분

---

## Issue #6: 에러 메시지 표시 후 복구 메커니즘 부재 (MAJOR)

### 현재 상황

**Customer GUI** (`main.py` 라인 233-241):
```python
def on_client_error(self, error_msg: str):
    QMessageBox.warning(
        self,
        '통신 오류',
        f'서버 통신 중 오류가 발생했습니다:\n{error_msg}',
        QMessageBox.Ok
    )
    # 복구 메커니즘 없음 - 사용자는 앱 재시작해야 함
```

### 해결방안

**자동 재연결 + 사용자 옵션**:

```python
def on_client_error(self, error_msg: str):
    """TCP 클라이언트 오류"""
    print(f'[App] 클라이언트 오류: {error_msg}')

    # 에러 메시지 표시
    reply = QMessageBox.warning(
        self,
        '통신 오류',
        f'서버 통신 중 오류가 발생했습니다:\n{error_msg}\n\n'
        f'자동으로 재연결을 시도합니다.',
        QMessageBox.Ok | QMessageBox.Cancel
    )

    if reply == QMessageBox.Cancel:
        # 사용자가 취소하면 메인 화면으로
        self.go_to_main()
    else:
        # 자동 재연결 (이미 setup_client()에서 진행 중)
        pass
```

또는 더 나은 UX:

```python
def on_client_error(self, error_msg: str):
    """TCP 클라이언트 오류"""
    print(f'[App] 클라이언트 오류: {error_msg}')

    # 메뉴 화면 비활성화
    self.menu_selection.setEnabled(False)

    # 재연결 정보 표시
    QMessageBox.information(
        self,
        '서버 연결 끊김',
        '서버 연결이 끊어졌습니다.\n'
        '자동으로 재연결을 시도합니다...',
        QMessageBox.Ok
    )

def on_reconnecting(self, attempt: int):
    """재연결 중"""
    if attempt == 1:
        # 첫 재연결 시도 시 사용자 알림
        QMessageBox.information(
            self,
            '재연결 중',
            f'서버에 재연결을 시도하고 있습니다... ({attempt}회)'
        )

def on_reconnected(self):
    """재연결 성공"""
    self.menu_selection.setEnabled(True)
    QMessageBox.information(
        self,
        '연결 복구',
        '서버 연결이 복구되었습니다.\n'
        '계속 진행할 수 있습니다.'
    )
```

### 예상 시간
- Issue #3 (자동 재연결) 완료 후: 30분

---

## 구현 우선순위 및 일정

### 1주차 (Critical 이슈)
| 일 | Issue | 예상시간 | 담당자 |
|----|-------|--------|------|
| 월 | #1, #2: TCP 프로토콜 통일 | 2시간 | Backend Lead |
| 화 | #1, #2: 테스트 및 배포 | 1.5시간 | Communication Validator |
| 수 | #3: 자동 재연결 | 2.5시간 | GUI Specialist |
| 목 | #3: 테스트 및 배포 | 1.5시간 | QA Tester |

### 2주차 (Major 이슈)
| 일 | Issue | 예상시간 | 담당자 |
|----|-------|--------|------|
| 월 | #4: 배달 알림 메커니즘 | 2.5시간 | Backend Lead + GUI |
| 화 | #4: 테스트 및 배포 | 1.5시간 | QA Tester |
| 수 | #6: 에러 복구 개선 | 1시간 | GUI Specialist |
| 목 | #6: 테스트 및 배포 | 1시간 | QA Tester |

### 3주차 (Minor 이슈)
| 일 | Issue | 예상시간 | 담당자 |
|----|-------|--------|------|
| 월 | #5: ROS_DOMAIN_ID UI 표시 | 0.5시간 | GUI Specialist |
| 화 | #5: 테스트 및 배포 | 0.25시간 | QA Tester |

---

## 테스트 계획

### Issue #1 테스트

```python
# test_tcp_protocol.py
def test_customer_gui_message_format():
    """Customer GUI 메시지 형식 검증"""
    client = TCPClient('127.0.0.1', 5000)

    # 메시지 전송
    data = {'command': 'get_menus', 'table_number': 1}
    result = client.send_data(data)
    assert result == True

def test_admin_gui_message_format():
    """Admin GUI 메시지 형식 검증 (통일 후)"""
    client = FleetClient('127.0.0.1', 9999)

    # 메시지 전송
    result = client.send_request('fleet_status_query', {})
    assert result == True

def test_message_protocol_compatibility():
    """프로토콜 호환성 검증"""
    # 길이 헤더 + JSON 형식이 모든 클라이언트에서 일관됨
    pass
```

### Issue #3 테스트

```python
def test_auto_reconnect_on_disconnect():
    """연결 끊김 시 자동 재연결"""
    client = OrderServiceClient()

    # 서버 시뮬레이션 (정상 응답)
    mock_server.start()
    client.connect()
    assert client.is_connected == True

    # 서버 중단
    mock_server.stop()
    time.sleep(6)  # 타임아웃 대기

    # 자동 재연결 시도
    mock_server.restart()
    time.sleep(3)  # 재연결 대기

    assert client.is_connected == True

def test_reconnect_max_attempts():
    """최대 재시도 횟수 초과"""
    client = OrderServiceClient()

    # 서버 미가동 상태에서 연결 시도
    result = client.connect()
    assert result == False

    # 자동 재연결 시도 10회
    time.sleep(65)  # 최대 재시도 대기

    # 이후 재연결 중단
    assert client._reconnecting == False
```

### 통합 테스트

```bash
#!/bin/bash

echo "=== Customer GUI Mock 테스트 ==="
python3 app/gui/customer_gui/src/tcp_client.py

echo "=== Admin GUI Mock 테스트 ==="
USE_MOCK=true python3 app/gui/admin_gui/src/main.py

echo "=== 프로토콜 호환성 테스트 ==="
python3 tests/test_tcp_protocol.py

echo "=== 자동 재연결 테스트 ==="
python3 tests/test_auto_reconnect.py
```

---

## 체크리스트

### Phase 1: TCP 프로토콜 통일
- [ ] Admin GUI fleet_client.py send_request() 수정
- [ ] Admin GUI fleet_client.py _receive_loop() 수정
- [ ] Main Server TCP 수신 로직 검증
- [ ] Customer GUI 호환성 확인
- [ ] 프로토콜 문서 작성
- [ ] 통합 테스트 실행
- [ ] 배포

### Phase 2: 자동 재연결
- [ ] Customer GUI OrderServiceClient 수정
- [ ] Admin GUI FleetClient 수정
- [ ] UI 신호 처리 구현
- [ ] 단위 테스트 실행
- [ ] 네트워크 끊김 시뮬레이션 테스트
- [ ] 배포

### Phase 3: 배달 알림
- [ ] Main Server 배달 알림 메커니즘 설계
- [ ] Customer GUI 배달 알림 수신 구현
- [ ] 통합 테스트 (FMS와 함께)
- [ ] 배포

### Phase 4: 에러 복구
- [ ] 사용자 친화적 에러 메시지 작성
- [ ] UI 비활성화/활성화 로직
- [ ] 메시지박스 UX 개선
- [ ] 테스트
- [ ] 배포

### Phase 5: Minor 개선
- [ ] ROS_DOMAIN_ID UI 추가
- [ ] 테스트
- [ ] 배포

---

**문서 작성일**: 2026-02-25
**최종 검토**: 대기 중
**예상 완료일**: 2026-03-15
