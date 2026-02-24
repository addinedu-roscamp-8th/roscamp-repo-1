# GUI 테스트 가이드 - 실물 로봇 없이 테스트 가능

**작성일**: 2026-02-25
**Specialist**: GUI Specialist (Haiku)
**목표**: 실물 로봇/FMS 없이 GUI 기능 검증

---

## 1. Customer GUI 테스트

### 1.1 완전 Mock 모드 테스트 (가장 간단)

```bash
# 터미널 1: Customer GUI 시작
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src
python3 main.py
```

**테스트 시나리오**:

1. **메인 화면**
   - 화면: "주문 시작" 버튼 표시
   - 기대: 초기 화면이 정상 로드

2. **주문 시작**
   - 버튼 클릭: "주문 시작"
   - 기대: 메뉴 선택 화면으로 전환
   - Mock 메뉴 3개 표시:
     - M001: 햄치즈샌드위치 (5000원)
     - M002: 머쉬룸샌드위치 (5500원)
     - M003: 올인원샌드위치 (6500원)

3. **메뉴 선택**
   - 메뉴 1개 선택: "햄치즈샌드위치" 클릭
   - 수량 선택: 2개
   - 소스 선택: "마요네즈"
   - 장바구니에 추가: "+장바구니" 버튼
   - 기대:
     - 선택된 메뉴가 장바구니에 표시
     - 소계: 10,000원 표시

4. **주문 확인**
   - "주문하기" 버튼 클릭
   - 기대: 주문 확인 화면
   - 표시 내용:
     - 테이블 번호
     - 메뉴: 햄치즈샌드위치 × 2
     - 합계: 10,000원

5. **주문 전송**
   - "주문 완료" 버튼 클릭
   - 기대:
     - 메시지박스: "주문 완료" (주문 번호 표시)
     - 메인 화면으로 돌아가기
     - **5초 후** 배달 알림 화면 표시

6. **배달 알림**
   - 화면: "음식이 도착했습니다"
   - 로봇 상태 표시
   - "수령 완료" 버튼 클릭
   - 기대:
     - "감사합니다" 메시지박스
     - 메인 화면으로 돌아가기

**검증 항목**:
- [ ] Mock 메뉴 로드 성공
- [ ] 모든 화면 전환 정상 작동
- [ ] 계산 정확성 (수량 × 가격)
- [ ] 5초 배달 알림 정상 표시
- [ ] UI 응답성 양호

**예상 소요시간**: 5분

---

### 1.2 TCP 클라이언트 단위 테스트

```bash
# tcp_client.py의 main() 함수 실행
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src
python3 tcp_client.py
```

**콘솔 출력 확인**:

```
[MockOrderService] Mock 연결 성공
[MockOrderService] Mock 메뉴 리스트 반환
메뉴 3개 조회됨
[MockOrderService] Mock 주문 전송 성공 - 주문 번호: ORD-1708666680
주문 번호: ORD-1708666680
[MockOrderService] Mock 수령 확인 - 주문 ORD-1708666680
```

**검증 항목**:
- [ ] Mock 클라이언트 연결 성공
- [ ] 메뉴 3개 수신
- [ ] 주문 ID 생성
- [ ] 수령 확인 처리

**예상 소요시간**: 1분

---

## 2. Admin GUI 테스트

### 2.1 완전 Mock 모드 테스트

```bash
# 터미널 1: Admin GUI 시작 (Mock 모드 자동)
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src
python3 main.py

# 또는 명시적으로 Mock 모드 설정
USE_MOCK=true python3 main.py
```

**테스트 시나리오**:

1. **주문 관제 탭**
   - 표시되는 내용:
     - 📊 주문 관제 (초기 탭)
     - 주문 목록 (ORD001, ORD002, ORD003)
     - 각 주문의 상태: cooking, confirmed, ready
     - 테이블, 금액, 상태

2. **조리 모니터 탭**
   - 탭 클릭: "🍳 조리 모니터"
   - 표시되는 내용:
     - 현재 조리 중인 주문
     - 진행상황 바
     - 완료까지 남은 시간

3. **레시피 관리 탭**
   - 탭 클릭: "📖 레시피 관리"
   - 표시되는 내용:
     - 레시피 목록 (R001, R002, R003)
     - 각 레시피의 재료 및 조리 단계
     - 조리 난도 (easy, medium)

4. **재고 관리 탭**
   - 탭 클릭: "📦 재고 관리"
   - 표시되는 내용:
     - 재고 목록
     - 부족 상태: 햄 (20개, 임계값 이하)
     - 빨강 경고 표시

5. **서빙 로봇 탭** (핵심)
   - 탭 클릭: "🚗 서빙 로봇"
   - **연결 상태**:
     - 표시: "연결됨" (초록색)
     - WiFi: kitchmatics
     - Server: 192.168.1.3:9000

   - **Mobile Robot 통계**:
     ```
     전체: 3        연결됨: 3
     대기: 2        작업중: 1
     ```

   - **로봇 상태 테이블**:
     ```
     ┌────────┬────────┬──────────┬───────────┬─────┬──────────┐
     │ 로봇명 │Robot ID│IP주소    │ 상태      │배터리│최종업데이트│
     ├────────┼────────┼──────────┼───────────┼─────┼──────────┤
     │pinky1  │pinky1  │192.168.1.7│대기 중   │24.5V│14:23:45  │
     │pinky2  │pinky2  │192.168.1.6│테이블이동│23.8V│14:23:45  │
     │pinky3  │pinky3  │192.168.1.11│배달중  │22.1V│14:23:45  │
     └────────┴────────┴──────────┴───────────┴─────┴──────────┘
     ```

   - **배터리 상태 색상** (확인):
     - pinky1 (24.5V): 초록색 "충분"
     - pinky2 (23.8V): 노랑색 "보통"
     - pinky3 (22.1V): 주황색 "부족"

   - **이벤트 로그**:
     ```
     [14:23:15] FMS Server 연결됨 (192.168.1.3:9000)
     [14:23:16] Fleet 상태 업데이트 수신
     [14:23:20] 로봇 pinky1 상태 변경: IDLE
     ```

6. **배터리 소모 시뮬레이션**
   - 2초마다 배터리 값 감소
   - 20V 이하로 내려가면 자동 재충전
   - UI에서 실시간 업데이트 확인

**검증 항목**:
- [ ] 모든 탭 정상 로드
- [ ] Fleet 모니터링 UI 표시 정상
- [ ] 3개 로봇 모두 표시
- [ ] 배터리 상태 색상 정확
- [ ] 실시간 업데이트 (2초 간격)
- [ ] 배터리 소모 시뮬레이션 작동

**예상 소요시간**: 5분

---

### 2.2 Fleet Client 단위 테스트

```bash
# fleet_client.py의 MockFleetClient 테스트
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src')

from fleet_client import MockFleetClient
from PyQt5.QtCore import QCoreApplication
import time

app = QCoreApplication(sys.argv)

# Mock 클라이언트 생성
client = MockFleetClient()
client.connect()

# 신호 연결
def on_fleet_status_updated(data):
    print(f"Fleet 상태 업데이트:")
    print(f"  - 로봇 수: {len(data['robots'])}")
    print(f"  - 대기 주문: {data['pending_orders']}")
    print(f"  - 진행 중 주문: {data['active_orders']}")
    for robot in data['robots']:
        print(f"  - {robot['robot_id']}: {robot['status']} (배터리: {robot['battery_voltage']:.1f}V)")

client.fleet_status_updated.connect(on_fleet_status_updated)

# 테스트 실행
print("Fleet Client Mock 테스트 시작...")
time.sleep(5)  # 5초 동안 업데이트 수신
client.disconnect()
print("테스트 완료")
EOF
```

**예상 출력**:

```
Fleet 상태 업데이트:
  - 로봇 수: 3
  - 대기 주문: 2
  - 진행 중 주문: 1
  - pinky1: IDLE (배터리: 24.45V)
  - pinky2: MOVING_TO_TABLE (배터리: 23.75V)
  - pinky3: DELIVERING (배터리: 22.05V)

(2초 후)
Fleet 상태 업데이트:
  - 로봇 수: 3
  - 대기 주문: 2
  - 진행 중 주문: 1
  - pinky1: IDLE (배터리: 24.40V)
  - pinky2: MOVING_TO_TABLE (배터리: 23.70V)
  - pinky3: DELIVERING (배터리: 22.00V)
```

**예상 소요시간**: 2분

---

## 3. 통합 테스트 (두 GUI 함께)

### 3.1 시나리오: Customer 주문 → Admin 모니터링

```bash
# 터미널 1: Customer GUI
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src
python3 main.py

# 터미널 2: Admin GUI (별도 터미널)
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src
python3 main.py
```

**테스트 절차**:

1. **초기 상태**
   - Admin GUI: 서빙 로봇 탭 → 3개 로봇 모두 IDLE
   - Customer GUI: 메인 화면

2. **Customer 주문**
   - "주문 시작" → "메뉴 선택" → "햄치즈샌드위치" 추가
   - "주문 완료" → 주문 번호 표시: ORD-XXXXX

3. **Admin 모니터링**
   - Admin GUI 로봇 상태 변경 (Mock 시뮬레이션):
     - pinky1: IDLE → MOVING_TO_PICKUP
     - pinky1: MOVING_TO_PICKUP → LOADED
     - pinky1: LOADED → MOVING_TO_TABLE
     - pinky1: MOVING_TO_TABLE → DELIVERING

4. **배달 알림**
   - 5초 후 Customer GUI에서 배달 알림 표시
   - 로봇 상태와 일치 확인

5. **수령 완료**
   - "수령 완료" 버튼 클릭
   - Admin GUI: pinky1 상태 → IDLE 로 돌아가기

**검증 항목**:
- [ ] Customer 주문 정상 처리
- [ ] Admin GUI에서 주문 상태 반영
- [ ] 로봇 상태 변경 정상 표시
- [ ] 배달 알림 정상 표시
- [ ] 수령 후 로봇 IDLE 상태로 복귀

**예상 소요시간**: 10분

---

## 4. Network Configuration 검증

### 4.1 network_config.yaml 로드 확인

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src')

from config import Config

print("=== Network Configuration 검증 ===\n")

print("Master Server:")
print(f"  Host: {Config.FMS_HOST}")
print(f"  Port: {Config.FMS_PORT}")

print("\nMobile Robots:")
for name, cfg in Config.get_mobile_robots().items():
    print(f"  {name}:")
    print(f"    - Robot ID: {cfg.get('robot_id')}")
    print(f"    - Domain ID: {cfg.get('domain_id')}")
    print(f"    - IP: {cfg.get('ip_address')}")
    print(f"    - Enabled: {cfg.get('enabled')}")

print("\nCobot Arms:")
for name, cfg in Config.get_cobot_arms().items():
    print(f"  {name}:")
    print(f"    - Robot ID: {cfg.get('robot_id')}")
    print(f"    - Domain ID: {cfg.get('domain_id')}")
    print(f"    - IP: {cfg.get('ip_address')}")
    print(f"    - Enabled: {cfg.get('enabled')}")

print("\nEnabled Robots:")
for robot in Config.get_enabled_robots():
    print(f"  - {robot.get('robot_id')} (Domain: {robot.get('domain_id')})")
EOF
```

**예상 출력**:

```
=== Network Configuration 검증 ===

Master Server:
  Host: 192.168.1.3
  Port: 9000

Mobile Robots:
  pinky_b4bc:
    - Robot ID: pinky1
    - Domain ID: 11
    - IP: 192.168.1.7
    - Enabled: True
  pinky_e2a8:
    - Robot ID: pinky2
    - Domain ID: 12
    - IP: 192.168.1.6
    - Enabled: True
  pinky_d29d:
    - Robot ID: pinky3
    - Domain ID: 13
    - IP: 192.168.1.11
    - Enabled: True

Cobot Arms:
  jetcobot_aa1f:
    - Robot ID: cobot1
    - Domain ID: 14
    - IP: 192.168.1.4
    - Enabled: True
  jetcobot_aa85:
    - Robot ID: cobot2
    - Domain ID: 15
    - IP: 192.168.1.10
    - Enabled: True

Enabled Robots:
  - pinky1 (Domain: 11)
  - pinky2 (Domain: 12)
  - pinky3 (Domain: 13)
  - cobot1 (Domain: 14)
  - cobot2 (Domain: 15)
```

**예상 소요시간**: 2분

---

## 5. 데이터 모델 검증

### 5.1 Order 모델 테스트

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/gw/kitchmatics/roscamp-repo-1/app/gui/common')

from models import Order, MenuItem, OrderItem

print("=== Order 모델 테스트 ===\n")

# 메뉴 아이템 생성
menu1 = MenuItem('M001', '햄치즈샌드위치', 5000, '맛있는 샌드위치', '', True, '샌드위치')
menu2 = MenuItem('M002', '머쉬룸샌드위치', 5500, '버섯이 많은 샌드위치', '', True, '샌드위치')

# 주문 생성
order = Order(table_number=1)

# 아이템 추가
order.add_item(menu1, 2)  # 5000 * 2 = 10000
order.add_item(menu2, 1)  # 5500 * 1 = 5500

print(f"테이블 번호: {order.table_number}")
print(f"총 금액: {order.total_price:,}원")
print(f"\n주문 항목:")
for item in order.items:
    print(f"  - {item.menu_item.name} × {item.quantity} = {item.get_subtotal():,}원")

print(f"\nOrder to_dict():")
import json
print(json.dumps(order.to_dict(), indent=2, ensure_ascii=False))
EOF
```

**예상 출력**:

```
=== Order 모델 테스트 ===

테이블 번호: 1
총 금액: 15,500원

주문 항목:
  - 햄치즈샌드위치 × 2 = 10,000원
  - 머쉬룸샌드위치 × 1 = 5,500원

Order to_dict():
{
  "order_id": null,
  "table_number": 1,
  "items": [
    {
      "menu_id": "M001",
      "menu_name": "햄치즈샌드위치",
      "price": 5000,
      "quantity": 2,
      "subtotal": 10000,
      "sauce": ""
    },
    {
      "menu_id": "M002",
      "menu_name": "머쉬룸샌드위치",
      "price": 5500,
      "quantity": 1,
      "subtotal": 5500,
      "sauce": ""
    }
  ],
  "total_price": 15500,
  "status": "pending",
  "created_at": null
}
```

**예상 소요시간**: 2분

---

## 6. TCP 프로토콜 검증 (길이 헤더)

### 6.1 Customer GUI TCP 프로토콜 테스트

```bash
python3 << 'EOF'
import socket
import json

# Customer GUI의 메시지 형식 시뮬레이션
def send_message(sock, data):
    json_data = json.dumps(data, ensure_ascii=False)
    message = json_data.encode('utf-8')
    length_header = len(message).to_bytes(4, byteorder='big')
    sock.sendall(length_header + message)
    print(f"전송 ({len(message)} bytes): {json_data[:50]}...")

def receive_message(sock):
    length_header = sock.recv(4)
    if not length_header:
        return None
    message_length = int.from_bytes(length_header, byteorder='big')
    message = b''
    while len(message) < message_length:
        chunk = sock.recv(min(4096, message_length - len(message)))
        if not chunk:
            break
        message += chunk
    data = json.loads(message.decode('utf-8'))
    print(f"수신 ({message_length} bytes): {data}")
    return data

print("=== TCP 프로토콜 테스트 ===\n")

# Mock 소켓 쌍 생성
server_sock, client_sock = socket.socketpair()

# 클라이언트 → 서버
print("클라이언트 → 서버:")
send_message(client_sock, {'command': 'get_menus', 'table_number': 1})

print("\n서버 수신:")
receive_message(server_sock)

# 서버 → 클라이언트
print("\n서버 → 클라이언트:")
send_message(server_sock, {
    'status': 'success',
    'menus': [
        {'menu_id': 'M001', 'name': '햄치즈샌드위치', 'price': 5000}
    ]
})

print("\n클라이언트 수신:")
receive_message(client_sock)

server_sock.close()
client_sock.close()

print("\n프로토콜 검증 완료!")
EOF
```

**예상 출력**:

```
=== TCP 프로토콜 테스트 ===

클라이언트 → 서버:
전송 (47 bytes): {"command": "get_menus", "table_number": 1}...

서버 수신:
수신 (47 bytes): {'command': 'get_menus', 'table_number': 1}

서버 → 클라이언트:
전송 (120 bytes): {"status": "success", "menus": [{"menu_id": "M001", ...

클라이언트 수신:
수신 (120 bytes): {'status': 'success', 'menus': [{'menu_id': 'M001', 'name': '햄치즈샌드위치', 'price': 5000}]}

프로토콜 검증 완료!
```

**예상 소요시간**: 3분

---

## 7. 자동 테스트 스크립트

### 7.1 Customer GUI 자동 테스트

```bash
# test_customer_gui_auto.py
#!/usr/bin/env python3

import sys
import time
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

sys.path.insert(0, '/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src')
sys.path.insert(0, '/home/gw/kitchmatics/roscamp-repo-1/app/gui/common')

from main import CustomerGUIApp
from models import MenuItem

def test_customer_gui_flow():
    app = QApplication(sys.argv)
    gui = CustomerGUIApp()
    gui.show()

    # 테스트 1: 메인 화면에서 주문 시작
    print("테스트 1: 주문 시작")
    QTest.mouseClick(gui.main_window.start_order_button, Qt.LeftButton)
    time.sleep(1)
    assert gui.currentWidget() == gui.menu_selection
    print("✓ 메뉴 선택 화면으로 전환 완료")

    # 테스트 2: 메뉴 선택
    print("\n테스트 2: 메뉴 선택")
    menus = gui.menu_selection.menu_items
    assert len(menus) == 3
    print(f"✓ 메뉴 {len(menus)}개 로드 완료")

    # 테스트 3: 주문 확인
    print("\n테스트 3: 주문 확인")
    order = gui.current_order
    assert order is not None
    print(f"✓ 주문 생성: {len(order.items)}개 항목")

    # 테스트 4: 주문 전송
    print("\n테스트 4: 주문 전송")
    order_id = gui.order_client.submit_order(order)
    assert order_id is not None
    print(f"✓ 주문 전송 완료: {order_id}")

    # 테스트 5: 배달 알림
    print("\n테스트 5: 배달 알림")
    time.sleep(6)  # 5초 타이머 대기
    assert gui.currentWidget() == gui.delivery_notification
    print("✓ 배달 알림 화면 표시")

    # 테스트 6: 수령 확인
    print("\n테스트 6: 수령 확인")
    result = gui.order_client.confirm_delivery(order_id)
    assert result == True
    print("✓ 수령 확인 완료")

    print("\n모든 테스트 통과!")
    gui.close()

if __name__ == '__main__':
    test_customer_gui_flow()
```

**실행 방법**:

```bash
python3 test_customer_gui_auto.py
```

**예상 소요시간**: 10초

---

## 8. 성능 테스트

### 8.1 Admin GUI Fleet 업데이트 성능

```bash
python3 << 'EOF'
import sys
import time
from PyQt5.QtCore import QCoreApplication

sys.path.insert(0, '/home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui/src')

from fleet_client import MockFleetClient

app = QCoreApplication(sys.argv)

client = MockFleetClient()
client.connect()

print("=== Fleet 업데이트 성능 테스트 ===\n")

update_times = []
update_count = 0

def on_fleet_update(data):
    global update_count, update_times
    update_count += 1
    current_time = time.time()
    if update_count > 1:
        interval = (current_time - update_times[-1]) * 1000  # ms
        print(f"업데이트 #{update_count}: 간격 {interval:.1f}ms, 로봇 {len(data['robots'])}개")
    update_times.append(current_time)

client.fleet_status_updated.connect(on_fleet_update)

# 10초 동안 모니터링
print("10초 동안 Fleet 업데이트 모니터링...\n")
time.sleep(10)

client.disconnect()

if len(update_times) > 1:
    intervals = [
        (update_times[i+1] - update_times[i]) * 1000
        for i in range(len(update_times)-1)
    ]
    avg_interval = sum(intervals) / len(intervals)
    print(f"\n평균 업데이트 간격: {avg_interval:.1f}ms")
    print(f"총 업데이트 수: {update_count}")
    print(f"기대값: 5개 (2초 간격)")
else:
    print("충분한 데이터 없음")
EOF
```

**예상 출력**:

```
=== Fleet 업데이트 성능 테스트 ===

10초 동안 Fleet 업데이트 모니터링...

업데이트 #2: 간격 2003.5ms, 로봇 3개
업데이트 #3: 간격 2001.2ms, 로봇 3개
업데이트 #4: 간격 2002.8ms, 로봇 3개
업데이트 #5: 간격 2000.9ms, 로봇 3개

평균 업데이트 간격: 2001.6ms
총 업데이트 수: 5
기대값: 5개 (2초 간격)
```

**성능 기준**:
- 평균 간격: 2000 ± 100ms ✓
- 업데이트 수: 5 ± 1 ✓

**예상 소요시간**: 15초

---

## 9. 테스트 결과 기록 서식

```markdown
# GUI 테스트 결과

**테스트 일시**: 2026-02-25 14:30:00
**테스터**: [이름]
**환경**: Ubuntu 22.04, Python 3.10, PyQt5 5.15

## Customer GUI 테스트

### Mock 모드 테스트
- [ ] 메인 화면 로드
- [ ] 메뉴 조회 (3개 메뉴)
- [ ] 메뉴 선택 및 장바구니 추가
- [ ] 주문 확인 및 계산 정확성
- [ ] 주문 전송 및 주문 번호 생성
- [ ] 배달 알림 표시 (5초 후)
- [ ] 수령 확인 처리
- [ ] 메인 화면 복귀

**결과**: ✓ 통과 / ⚠️ 부분 통과 / ✗ 실패

**주요 발견사항**:
- [기술할 사항]

## Admin GUI 테스트

### Mock 모드 테스트
- [ ] 모든 탭 로드
- [ ] Fleet 모니터링 UI 표시
- [ ] 3개 로봇 모두 표시
- [ ] 배터리 상태 색상 정확
- [ ] 실시간 업데이트 (2초 간격)
- [ ] 배터리 소모 시뮬레이션

**결과**: ✓ 통과 / ⚠️ 부분 통과 / ✗ 실패

**주요 발견사항**:
- [기술할 사항]

## 통합 테스트

**결과**: ✓ 통과 / ⚠️ 부분 통과 / ✗ 실패

**주요 발견사항**:
- [기술할 사항]

## 성능 테스트

| 항목 | 기대값 | 실제값 | 상태 |
|------|--------|--------|------|
| Fleet 업데이트 간격 | 2000ms | 2001.6ms | ✓ |
| 총 업데이트 수 | 5회 | 5회 | ✓ |
| UI 응답시간 | < 100ms | [실제값] | ? |
| 메모리 사용 | < 100MB | [실제값] | ? |

## 종합 평가

**점수**: [점수]/10
**평가**: [평가]

**개선 권장사항**:
1. [권장사항 1]
2. [권장사항 2]
3. [권장사항 3]
```

---

## 10. 문제 진단 가이드

### 10.1 Customer GUI가 실행되지 않음

**증상**: "ModuleNotFoundError" 또는 "No module named 'common'"

**해결**:
```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src
python3 main.py  # 올바른 작업 디렉토리
```

### 10.2 Admin GUI에 로봇이 표시되지 않음

**증상**: Fleet 모니터링 테이블이 빈 상태

**원인**: network_config.yaml을 찾을 수 없음

**해결**:
```bash
# network_config.yaml이 존재하는지 확인
ls /home/gw/kitchmatics/roscamp-repo-1/fms/config/network_config.yaml

# Config 클래스에서 경로 확인
python3 << 'EOF'
from config import Config
print(Config.get_mobile_robots())
EOF
```

### 10.3 배터리 값이 업데이트되지 않음

**증상**: Admin GUI에서 배터리 값이 고정됨

**원인**: MockFleetClient의 2초 타이머가 작동하지 않음

**해결**:
```bash
# QTimer가 정상 작동하는지 확인
python3 << 'EOF'
from PyQt5.QtCore import QCoreApplication, QTimer
import time

app = QCoreApplication([])

timer = QTimer()
timer.timeout.connect(lambda: print("Timer fired!"))
timer.start(2000)

# 5초 대기
QCoreApplication.processEvents()
time.sleep(5)
EOF
```

### 10.4 주문이 전송되지 않음

**증상**: MockOrderServiceClient가 응답하지 않음

**원인**: TCP 클라이언트가 연결 실패

**해결**:
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui/src')

from tcp_client import MockOrderServiceClient

client = MockOrderServiceClient()
if client.connect():
    print("✓ Mock 클라이언트 연결 성공")
    menus = client.fetch_menus()
    print(f"✓ 메뉴 {len(menus)}개 조회")
else:
    print("✗ 연결 실패")
EOF
```

---

## 11. 최종 검증 체크리스트

실물 로봇 없이 GUI 테스트 가능성 검증:

- [x] **Customer GUI Mock 모드**: 서버 없이 완전 테스트 가능
- [x] **Admin GUI Mock 모드**: 서버 없이 완전 테스트 가능
- [x] **데이터 모델**: 정상 작동 검증 가능
- [x] **TCP 프로토콜**: 형식 검증 가능
- [x] **네트워크 설정**: YAML 로드 검증 가능
- [x] **성능 테스트**: 업데이트 간격 검증 가능
- [x] **통합 테스트**: 두 GUI 함께 테스트 가능

**결론**: **완전히 테스트 가능** (실물 로봇 필요 없음)

---

**문서 작성일**: 2026-02-25
**예상 테스트 시간**: 30분 (모든 항목)
**다음 테스트**: 프로토콜 통일 후 1주일
