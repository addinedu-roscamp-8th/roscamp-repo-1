# GUI Order Integration - Implementation Summary

## Overview

FMS에서 GUI로부터 주문을 받아 로봇팔에 조리 명령 전달 및 pinky1 로봇 이동 제어 기능이 구현되었습니다.

## Architecture

Clean Architecture 원칙에 따라 레이어별로 구현:

```
Presentation Layer (FMS Node)
    ↓
Application Layer (OrderHandler)
    ↓
Infrastructure Layer (GUITCPServer, ROS2 Publishers)
    ↓
Domain Layer (OrderWorkflow)
```

### 1. Domain Layer: OrderWorkflow

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py`

**책임**: 주문 워크플로우 상태 관리

**상태 머신**:
```
RECEIVED -> COOKING -> LOADING -> LOADED -> DELIVERING -> ARRIVED -> COMPLETED
```

- `RECEIVED`: 주문 접수
- `COOKING`: 로봇팔 조리 중
- `LOADING`: pinky1이 point13으로 이동 중
- `LOADED`: 음식 적재 완료
- `DELIVERING`: 테이블로 이동 중
- `ARRIVED`: 테이블 도착 (GUI 알림 발송)
- `COMPLETED`: 수령 확인, 로봇 복귀

### 2. Application Layer: OrderHandler

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py`

**책임**: 주문 처리 유스케이스 오케스트레이션

**주요 메서드**:
- `handle_new_order()`: GUI로부터 주문 수신 처리
- `handle_cooking_complete()`: 로봇팔 조리 완료 처리
- `handle_robot_arrived_table()`: 테이블 도착 처리 및 GUI 알림
- `handle_delivery_confirmation()`: 수령 확인 및 로봇 복귀

**의존성 역전 (Dependency Inversion)**:
- 인프라스트럭처 레이어의 콜백을 등록받아 사용
- 순수 비즈니스 로직만 포함, 외부 의존성 없음

### 3. Infrastructure Layer: GUITCPServer

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/gui_tcp_server.py`

**책임**: TCP 통신 처리 (Port 9000)

**프로토콜**:
- 4-byte length header + JSON payload
- Request-Response 패턴
- Push notification 지원 (broadcast)

**지원 메시지**:

#### 1. new_order (GUI → FMS)
```json
{
    "command": "new_order",
    "table_number": 1,
    "order": {
        "items": [
            {"menu_id": "M001", "quantity": 1}
        ]
    }
}
```

**Response**:
```json
{
    "status": "success",
    "data": {
        "order_id": "ORD-20260225123456-0001",
        "message": "Order accepted"
    }
}
```

#### 2. delivery_complete (GUI → FMS)
```json
{
    "command": "delivery_complete",
    "order_id": "ORD-20260225123456-0001",
    "table_number": 1
}
```

**Response**:
```json
{
    "status": "success",
    "data": {
        "message": "Delivery confirmed, robot returning home"
    }
}
```

#### 3. delivery_notification (FMS → GUI) - Push Notification
```json
{
    "type": "delivery_notification",
    "data": {
        "order_id": "ORD-20260225123456-0001",
        "table_number": 1,
        "robot_id": "pinky1",
        "status": "arrived"
    }
}
```

### 4. Presentation Layer: FMSNode Integration

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py`

**통합 포인트**:

1. **TCP 서버 초기화**:
   ```python
   self.gui_tcp_server = GUITCPServer(host='0.0.0.0', port=9000)
   self.gui_tcp_server.start()
   ```

2. **OrderHandler 초기화 및 콜백 등록**:
   ```python
   self.order_handler = OrderHandler()
   self.order_handler.register_callbacks(
       send_cooking_command=self._send_cooking_command_to_arm,
       navigate_robot=self._navigate_robot_by_name,
       send_gui_notification=self._send_gui_notification,
       fleet_controller=self._fleet_controller_operation
   )
   ```

3. **TCP 메시지 핸들러 등록**:
   ```python
   self.gui_tcp_server.register_handler('new_order', self._handle_gui_new_order)
   self.gui_tcp_server.register_handler('delivery_complete', self._handle_gui_delivery_complete)
   ```

## Workflow Sequence

### 주문 접수 ~ 배달 완료 Flow

```
1. GUI → FMS: new_order
   ├─→ FMS: OrderHandler.handle_new_order()
   ├─→ FMS: Send CookingOrder to robot arm (/cooking/order)
   └─→ FMS: Navigate pinky1 to point13

2. Robot Arm: Cooking starts
   └─→ pinky1: Navigating to point13

3. pinky1 arrives at point13
   └─→ FMS: OrderHandler.handle_robot_arrived_point13()

4. Robot Arm → FMS: LoadingComplete
   └─→ FMS: OrderHandler.handle_cooking_complete()
       └─→ Skip precision control (3초 딜레이)
           └─→ Navigate pinky1 to table1

5. pinky1 arrives at table1
   └─→ FMS: OrderHandler.handle_robot_arrived_table()
       └─→ FMS → GUI: delivery_notification (Push)

6. GUI → FMS: delivery_complete
   └─→ FMS: OrderHandler.handle_delivery_confirmation()
       └─→ Navigate pinky1 to pinky1_spot (home)

7. pinky1 arrives at home
   └─→ FMS: Robot status = IDLE
```

## ROS2 Integration

### Published Topics

1. **/cooking/order** (`CookingOrder`)
   - 로봇팔에 조리 명령 전달
   - Fields: order_id, menu_id, quantity, sauce_type, assigned_robot_id

### Subscribed Topics

1. **/cooking/loading_complete** (`LoadingComplete`)
   - 로봇팔 조리 완료 알림
   - Triggers: `OrderHandler.handle_cooking_complete()`

### Action Clients

1. **/navigate_to_pose** (`NavigateToPose`)
   - pinky1 네비게이션 제어
   - Destinations: point13, table1~8, pinky1_spot

## Configuration

### Network Configuration

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/network_config.yaml`

```yaml
master:
  host: "192.168.1.3"
  tcp_port: 9000
  ros_domain_id: 25
```

### Map Positions

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml`

```yaml
positions:
  point13:
    x: 0.585
    y: 0.63
    theta: 0.0

  table1:
    x: 1.785
    y: 0.35
    theta: 0.0

  pinky1_spot:
    x: 0.585
    y: 0.085
    theta: 0.0
```

## Testing

### Test Script

**파일**: `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/test_gui_order.py`

**사용법**:

1. 새 주문 테스트:
   ```bash
   cd /home/gw/kitchmatics/roscamp-repo-1/fms/scripts
   python3 test_gui_order.py new_order
   ```

2. 수령 확인 테스트:
   ```bash
   python3 test_gui_order.py delivery_complete
   ```

**테스트 시나리오**:
- FMS TCP 서버 연결
- 주문 전송 및 응답 확인
- 배달 알림 수신 (Push notification)
- 수령 확인 전송
- 전체 워크플로우 검증

## Skip Mode Behavior

현재 구현은 Skip Mode를 지원합니다:

1. **Precision Control Skip**:
   - point13 도착 후 정밀제어 단계를 건너뜀
   - 음식 적재 완료 후 3초 딜레이 후 자동으로 테이블로 이동

2. **pickup_spot Skip**:
   - pickup_spot 대신 point13을 사용
   - 정밀제어 없이 바로 다음 단계로 진행

**설정**:
```python
# fms_node.py
self.declare_parameter('skip_robot_arm', True)
```

## Error Handling

### Application Layer

- 주문 처리 실패 시 `OrderWorkflow.STATE_FAILED`로 전환
- 예외 발생 시 적절한 에러 응답 반환
- 로깅을 통한 디버깅 지원

### Infrastructure Layer

- TCP 연결 에러 처리
- JSON 파싱 에러 처리
- 클라이언트 연결 끊김 처리
- 메시지 전송 실패 시 재시도 없음 (로그만 기록)

## Scalability Considerations

1. **Horizontal Scaling**:
   - OrderHandler는 stateless 설계 가능
   - 여러 FMS 인스턴스 실행 가능 (로봇 분산)

2. **Performance**:
   - TCP 서버는 멀티스레드로 클라이언트 처리
   - 각 주문은 독립적으로 처리
   - 블로킹 없는 비동기 네비게이션

3. **Extensibility**:
   - 새로운 메시지 타입 추가 용이 (register_handler)
   - 워크플로우 상태 확장 가능
   - 다른 로봇 추가 가능 (pinky2, pinky3)

## Future Improvements

1. **Persistence**:
   - 주문 상태를 데이터베이스에 저장
   - 시스템 재시작 시 복구 가능

2. **Monitoring**:
   - Prometheus metrics 추가
   - 주문 처리 시간 추적
   - 에러율 모니터링

3. **Reliability**:
   - TCP 재연결 로직 강화
   - 메시지 ACK 추가
   - 타임아웃 처리 개선

4. **Multiple Robots**:
   - 여러 서빙 로봇 동시 처리
   - 로봇 선택 알고리즘 개선
   - 부하 분산 전략

## Files Modified/Created

### Created Files
1. `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py` - Application Layer
2. `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/gui_tcp_server.py` - Infrastructure Layer
3. `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/test_gui_order.py` - Test Script
4. `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/GUI_ORDER_INTEGRATION.md` - Documentation

### Modified Files
1. `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py` - Integration points

## Summary

이 구현은 Clean Architecture 원칙을 따라:

1. **Separation of Concerns**: 각 레이어는 명확한 책임을 가짐
2. **Dependency Inversion**: Application Layer는 Infrastructure에 의존하지 않음
3. **Testability**: 각 레이어를 독립적으로 테스트 가능
4. **Scalability**: 수평 확장 가능한 설계
5. **Maintainability**: 명확한 구조와 문서화

GUI로부터 주문을 받아 로봇팔 조리 명령 및 pinky1 이동을 제어하는 전체 워크플로우가 구현되었습니다.
