# Customer GUI - FMS Direct Communication

Backend 없이 FMS로 직접 주문을 전달하는 기능 구현

## Architecture (Clean Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│ Presentation Layer                                          │
│  - main_fms_direct.py (UI 화면 전환, 이벤트 처리)            │
│  - ui_*.py (각 화면 위젯)                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ depends on
┌──────────────────────▼──────────────────────────────────────┐
│ Application Layer                                           │
│  - FMSOrderServiceClient (FMS 주문 서비스)                  │
│  - MockFMSOrderServiceClient (테스트용 Mock)                │
└──────────────────────┬──────────────────────────────────────┘
                       │ depends on
┌──────────────────────▼──────────────────────────────────────┐
│ Infrastructure Layer                                        │
│  - FMSTCPClient (TCP 소켓 통신)                             │
└──────────────────────┬──────────────────────────────────────┘
                       │ uses
┌──────────────────────▼──────────────────────────────────────┐
│ Domain Layer                                                │
│  - Order, MenuItem, OrderItem (common/models.py)            │
└─────────────────────────────────────────────────────────────┘
```

### SOLID Principles

1. **Single Responsibility**
   - `FMSTCPClient`: TCP 통신 전담
   - `FMSOrderServiceClient`: FMS 비즈니스 로직 (주문/배달)
   - `CustomerGUIApp`: UI 화면 전환 오케스트레이션

2. **Open/Closed**
   - 새로운 클라이언트 타입 추가 가능 (FMS, Mock, Future: REST API)
   - 메시지 타입 확장 가능

3. **Liskov Substitution**
   - `FMSOrderServiceClient`와 `MockFMSOrderServiceClient`는 교체 가능
   - 동일한 시그널 인터페이스 제공

4. **Interface Segregation**
   - PyQt Signal로 이벤트 기반 느슨한 결합
   - 각 계층은 필요한 인터페이스만 의존

5. **Dependency Inversion**
   - 상위 계층은 추상화(시그널)에 의존
   - 구체적인 TCP 구현은 하위 계층에서 처리

## 파일 구조

```
app/gui/customer_gui/
├── src/
│   ├── fms_client.py              # FMS TCP 클라이언트 (새로 추가)
│   ├── main_fms_direct.py         # FMS 직접 통신 메인 (새로 추가)
│   ├── tcp_client.py              # 기존 (Backend 통신용)
│   ├── main.py                    # 기존 (Backend 통신용)
│   └── ui_*.py                    # UI 화면 위젯들
├── test_gui_to_fms.py             # FMS 통신 테스트 스크립트 (새로 추가)
└── README_FMS_DIRECT.md           # 이 문서
```

## 주요 파일 설명

### 1. `src/fms_client.py` (새로 추가)

**FMSTCPClient** (Infrastructure Layer)
- TCP 소켓 연결/해제
- 메시지 송수신 (4-byte length header + JSON)
- 백그라운드 메시지 리스너 스레드

**FMSOrderServiceClient** (Application Layer)
- FMS로 주문 전송
- FMS로 수령 확인 전송
- 배달 알림 수신 처리
- PyQt Signal로 이벤트 발행

**MockFMSOrderServiceClient** (테스트용)
- 실제 FMS 없이 로컬 테스트
- 동일한 인터페이스 제공 (Strategy Pattern)

### 2. `src/main_fms_direct.py` (새로 추가)

- Backend 없이 FMS로 직접 통신하는 GUI
- Mock 메뉴 데이터 사용 (테스트용)
- 주문 플로우: 메뉴 선택 → 주문 확인 → FMS 전송 → 배달 알림 → 수령 확인

### 3. `test_gui_to_fms.py` (새로 추가)

- GUI 없이 FMS 통신만 테스트
- 메시지 형식 검증
- 주문 플로우 전체 테스트

## FMS 통신 프로토콜

### 메시지 형식

모든 메시지는 다음 형식을 따릅니다:
```
[4-byte length header] + [JSON message]
```

### 1. 주문 전송 (GUI → FMS)

```json
{
  "command": "new_order",
  "table_number": 1,
  "order": {
    "order_id": "ORD-1234567890",
    "items": [
      {
        "menu_id": "M001",
        "name": "햄버거",
        "quantity": 2,
        "price": 8000
      }
    ],
    "table_number": 1,
    "total_price": 16000
  }
}
```

### 2. 배달 알림 (FMS → GUI, Push)

```json
{
  "type": "delivery_notification",
  "data": {
    "order_id": "ORD-1234567890",
    "table_number": "1",
    "robot_id": "pinky1",
    "status": "delivered"
  }
}
```

### 3. 수령 확인 (GUI → FMS)

```json
{
  "type": "delivery_complete",
  "data": {
    "order_id": "ORD-1234567890",
    "table_number": "1"
  }
}
```

## 사용 방법

### 1. FMS 서버 실행 (먼저)

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms
source venv/bin/activate
python -m fms.fms_node
```

FMS가 `192.168.1.3:9000`에서 실행됩니다.

### 2. GUI 실행 (실제 FMS 연결)

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui
source pyqt/bin/activate
python src/main_fms_direct.py
```

### 3. GUI 실행 (Mock 모드)

FMS 없이 테스트하려면:

```bash
python src/main_fms_direct.py --mock
```

### 4. CLI 테스트 (GUI 없이)

```bash
# 실제 FMS로 테스트
python test_gui_to_fms.py

# Mock 모드로 테스트
python test_gui_to_fms.py --mock

# 메시지 형식만 확인
python test_gui_to_fms.py --format
```

## 테스트 시나리오

### 시나리오 1: 전체 주문 플로우

1. GUI 시작
2. "주문 시작" 클릭
3. 메뉴 선택 (햄버거 2개, 피자 1개)
4. "주문 확인" 클릭
5. FMS로 주문 전송
6. 주문 접수 완료 메시지 표시
7. 메인 화면으로 돌아감
8. (FMS에서) 배달 알림 푸시 수신
9. 배달 알림 화면 표시
10. "수령 완료" 클릭
11. FMS로 수령 확인 전송
12. 감사 메시지 표시
13. 메인 화면으로 돌아감

### 시나리오 2: CLI 테스트

```bash
$ python test_gui_to_fms.py
============================================================
FMS 주문 플로우 테스트
============================================================
[Test] 실제 FMS 클라이언트 사용: 192.168.1.3:9000

[Step 1] FMS 연결 중...
[FMSClient] FMS 연결 성공: 192.168.1.3:9000
[Success] FMS 연결 성공

[Step 2] 테스트 주문 생성
테이블 번호: 1
주문 항목:
  - 햄버거 x 2 (8000원)
  - 피자 x 1 (15000원)
총 금액: 31000원

[Step 3] FMS로 주문 전송 중...
[FMSOrderService] 주문 전송 - 테이블 1, 주문 ORD-1234567890
[Success] 주문 전송 성공
주문 번호: ORD-1234567890

[Step 4] 배달 알림 대기 중... (시뮬레이션)
테스트를 위해 5초 대기...

[Step 5] 수령 확인 전송 중...
[FMSOrderService] 수령 확인 전송 - 주문 ORD-1234567890
[Success] 수령 확인 전송 성공

[Step 6] FMS 연결 종료
[Success] 연결 종료 완료

============================================================
테스트 완료
============================================================
```

## Mock 메뉴 데이터

테스트용으로 다음 메뉴를 제공합니다:

| menu_id | 이름      | 가격   | 설명                |
|---------|-----------|--------|---------------------|
| M001    | 햄버거    | 8,000원 | 신선한 소고기 패티  |
| M002    | 치즈버거  | 9,000원 | 더블 치즈 햄버거    |
| M003    | 피자      | 15,000원 | 마르게리타 피자     |
| M004    | 샌드위치  | 6,000원 | 클럽 샌드위치       |

## 설정

### FMS 주소 변경

`/home/gw/kitchmatics/roscamp-repo-1/fms/config/network_config.yaml`:

```yaml
master:
  host: "192.168.1.3"
  tcp_port: 9000
```

또는 환경 변수:

```bash
export FMS_HOST=192.168.1.3
export FMS_PORT=9000
```

### 테이블 번호 변경

```bash
export TABLE_NUMBER=2
```

## 트러블슈팅

### 1. FMS 연결 실패

**증상:**
```
[FMSClient] FMS 연결 실패: [Errno 111] Connection refused
```

**해결:**
1. FMS 서버가 실행 중인지 확인
   ```bash
   ps aux | grep fms_node
   ```
2. FMS 주소/포트 확인
   ```bash
   netstat -tlnp | grep 9000
   ```
3. 네트워크 연결 확인
   ```bash
   ping 192.168.1.3
   ```

### 2. Mock 모드로 전환

FMS 서버 없이 테스트하려면:

```bash
python src/main_fms_direct.py --mock
```

### 3. 배달 알림 수신 안 됨

**원인:** FMS가 배달 알림을 푸시하지 않음

**해결:**
1. FMS 로그 확인
2. 주문 번호와 테이블 번호 일치 여부 확인
3. TCP 연결이 유지되는지 확인

## 성능 및 확장성 고려사항

### Scalability
1. **Connection Pooling**: 여러 GUI가 동시 연결 시 FMS TCP 서버 부하 관리
2. **Message Queue**: 주문 폭주 시 큐잉 메커니즘 추가 가능
3. **Async I/O**: 필요 시 asyncio로 전환 가능 (현재는 threading)

### Error Handling
1. **Retry Logic**: 네트워크 실패 시 자동 재연결
2. **Circuit Breaker**: FMS 장애 시 Mock 모드로 자동 전환
3. **Logging**: 모든 통신 로그 기록 (디버깅 및 모니터링)

### Testing
1. **Unit Test**: 각 계층별 독립 테스트
2. **Integration Test**: FMS와의 통합 테스트
3. **Mock Test**: 실제 FMS 없이 전체 플로우 테스트

## 향후 개선 사항

1. **WebSocket 지원**: TCP 대신 WebSocket으로 전환 (양방향 통신)
2. **REST API**: HTTP API 추가 지원 (Fallback)
3. **인증/암호화**: TLS/SSL 암호화 통신
4. **배치 주문**: 여러 주문 동시 전송
5. **주문 취소**: 주문 취소 기능 추가
6. **실시간 상태**: 주문 상태 실시간 업데이트

## 관련 파일

- `/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml` - FMS 설정
- `/home/gw/kitchmatics/roscamp-repo-1/fms/config/network_config.yaml` - 네트워크 설정
- `/home/gw/kitchmatics/roscamp-repo-1/app/gui/common/config.py` - GUI 설정
- `/home/gw/kitchmatics/roscamp-repo-1/app/gui/common/models.py` - Domain 모델

## 문의

- 아키텍처 관련: Clean Architecture 원칙 참조
- FMS 프로토콜: FMS 팀 문의
- GUI 버그: Issue 등록
