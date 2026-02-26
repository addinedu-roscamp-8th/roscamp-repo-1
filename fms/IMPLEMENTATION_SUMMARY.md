# FMS GUI Order Integration - Implementation Summary

## Executive Summary

FMS에서 GUI로부터 주문을 받아 로봇팔에 조리 명령을 전달하고 pinky1 로봇의 이동을 제어하는 통합 시스템이 Clean Architecture 원칙에 따라 구현되었습니다.

**구현 날짜**: 2026-02-25

## Implemented Features

### 1. TCP Server for GUI Communication (Port 9000)

- 4-byte length header + JSON payload 프로토콜
- 멀티스레드 클라이언트 처리
- 요청-응답 패턴 및 푸시 알림 지원

**메시지 타입**:
- `new_order`: GUI로부터 주문 수신
- `delivery_complete`: GUI로부터 수령 확인
- `delivery_notification`: GUI로 배달 도착 알림 (Push)

### 2. Robot Arm Integration

- ROS2 토픽으로 조리 명령 전달 (`/cooking/order`)
- 조리 완료 알림 수신 (`/cooking/loading_complete`)
- 주문 정보 전달: menu_id, quantity, sauce_type

### 3. pinky1 Navigation Control

- point13으로 자동 네비게이션 (픽업 대기 지점)
- 조리 완료 후 테이블로 자동 이동
- 수령 확인 후 home으로 자동 복귀

### 4. Skip Mode Support

- 정밀제어 단계 스킵 (as per requirements)
- pickup_spot 대신 point13 사용
- 3초 딜레이 후 자동으로 다음 단계 진행

### 5. Workflow State Machine

주문 상태 관리:
- RECEIVED → COOKING → LOADING → LOADED → DELIVERING → ARRIVED → COMPLETED

## Architecture Design

### Clean Architecture Layers

```
┌─────────────────────────────────────────────────────┐
│  Presentation Layer (fms_node.py)                   │
│  - ROS2 integration                                 │
│  - Component coordination                           │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│  Application Layer (order_handler.py)               │
│  - Business logic                                   │
│  - Use case orchestration                           │
│  - Dependency inversion (callbacks)                 │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│  Infrastructure Layer                               │
│  - GUITCPServer (TCP communication)                 │
│  - ROS2 publishers/subscribers                      │
│  - Navigation action clients                        │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│  Domain Layer (OrderWorkflow)                       │
│  - Pure business entities                           │
│  - State machine logic                              │
└─────────────────────────────────────────────────────┘
```

### SOLID Principles Applied

1. **Single Responsibility**:
   - OrderHandler: 주문 워크플로우 관리
   - GUITCPServer: TCP 통신
   - OrderWorkflow: 상태 관리

2. **Open/Closed**:
   - 새로운 메시지 타입 추가 시 기존 코드 수정 불필요
   - Handler 등록 시스템으로 확장 가능

3. **Liskov Substitution**:
   - 콜백 인터페이스로 구현체 교체 가능

4. **Interface Segregation**:
   - 각 콜백은 특정 기능만 담당

5. **Dependency Inversion**:
   - Application Layer는 추상화에 의존 (callbacks)
   - Infrastructure 구현은 주입됨

## Files Created

### Core Implementation

1. **order_handler.py** (Application Layer)
   - Path: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py`
   - Lines: 353
   - Purpose: 주문 처리 비즈니스 로직

2. **gui_tcp_server.py** (Infrastructure Layer)
   - Path: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/gui_tcp_server.py`
   - Lines: 435
   - Purpose: TCP 서버 및 프로토콜 처리

### Testing

3. **test_gui_order.py** (Test Script)
   - Path: `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/test_gui_order.py`
   - Lines: 196
   - Purpose: 통합 테스트 스크립트

### Documentation

4. **GUI_ORDER_INTEGRATION.md**
   - Path: `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/GUI_ORDER_INTEGRATION.md`
   - Purpose: 상세 구현 문서

5. **QUICKSTART.md**
   - Path: `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/QUICKSTART.md`
   - Purpose: 빠른 시작 가이드

6. **ARCHITECTURE_DIAGRAM.md**
   - Path: `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/ARCHITECTURE_DIAGRAM.md`
   - Purpose: 아키텍처 다이어그램 및 데이터 플로우

## Files Modified

1. **fms_node.py**
   - Path: `/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py`
   - Changes:
     - Added OrderHandler and GUITCPServer imports
     - Initialized new components
     - Registered callbacks
     - Added integration methods
     - Enhanced navigation status checking

## Code Statistics

```
Total Lines Added:     ~1,200
Total Files Created:   6
Total Files Modified:  1
Build Status:          ✓ Success
Syntax Check:          ✓ Pass
```

## How It Works

### Order Processing Flow

```
1. GUI sends 'new_order' → TCP (Port 9000)
   ├─→ FMS receives and validates
   └─→ Response with order_id

2. FMS orchestrates parallel tasks:
   ├─→ Send cooking command to robot arm (/cooking/order)
   └─→ Navigate pinky1 to point13

3. Robot arm cooks food
   └─→ Publishes LoadingComplete

4. pinky1 arrives at point13
   └─→ Waits for cooking completion

5. Cooking complete + Robot at point13
   └─→ Skip precision control (3s delay)
       └─→ Navigate to table

6. pinky1 arrives at table
   └─→ FMS sends push notification to GUI

7. GUI sends 'delivery_complete'
   └─→ FMS navigates pinky1 to home
       └─→ Robot status → IDLE
```

### Key Integration Points

1. **GUI ↔ FMS**: TCP Socket (Port 9000)
2. **FMS → Robot Arm**: ROS2 Topic (`/cooking/order`)
3. **Robot Arm → FMS**: ROS2 Topic (`/cooking/loading_complete`)
4. **FMS → pinky1**: ROS2 Action (`/navigate_to_pose`)
5. **pinky1 → FMS**: ROS2 Topic (`/pose`)

## Configuration

### Network

- Master PC: 192.168.1.3
- TCP Port: 9000
- ROS_DOMAIN_ID: 25 (FMS), 11 (pinky1), 20 (Robot Arm)

### Map Positions (fms_config.yaml)

```yaml
positions:
  point13:      {x: 0.585, y: 0.63,  theta: 0.0}
  table1:       {x: 1.785, y: 0.35,  theta: 0.0}
  pinky1_spot:  {x: 0.585, y: 0.085, theta: 0.0}
```

## Testing

### Build Test

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms
colcon build --packages-select fms
# Result: ✓ Success (1.21s)
```

### Syntax Check

```bash
python3 -m py_compile fms/order_handler.py fms/gui_tcp_server.py
# Result: ✓ Pass (no errors)
```

### Integration Test

```bash
# Terminal 1: Start FMS
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true

# Terminal 2: Test order
python3 scripts/test_gui_order.py new_order
```

## Usage

### Start FMS

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms
source install/setup.bash
export ROS_DOMAIN_ID=11
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
```

### Send Test Order

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms/scripts
python3 test_gui_order.py new_order
```

### Monitor Topics

```bash
# Cooking orders
export ROS_DOMAIN_ID=25
ros2 topic echo /cooking/order

# Robot pose
export ROS_DOMAIN_ID=11
ros2 topic echo /pose
```

## Scalability & Performance

### Current Capacity

- Single robot (pinky1)
- Sequential order processing
- ~30-60 seconds per order (cooking + delivery)

### Scalability Features

1. **Horizontal Scaling**:
   - Add more robots (pinky2, pinky3)
   - Multiple FMS instances possible
   - Stateless order handler design

2. **Concurrent Processing**:
   - Multi-threaded TCP server
   - Parallel cooking and navigation
   - Non-blocking message handling

3. **Extensibility**:
   - Easy to add new message types
   - Pluggable workflow states
   - Modular architecture

## Error Handling

### Implemented

- TCP connection errors → Log and continue
- JSON parsing errors → Send error response
- Invalid orders → Return error status
- Navigation failures → (to be enhanced)

### To Be Implemented

- Order retry mechanism
- Timeout handling
- Robot failure recovery
- Database persistence

## Known Limitations

1. **Single Robot**: Currently only pinky1 is used
2. **No Persistence**: Orders not saved to database
3. **No Retry**: Failed orders are not automatically retried
4. **No Monitoring**: No Prometheus metrics yet

## Future Enhancements

### Phase 1: Reliability

- [ ] Add order persistence (SQLite/PostgreSQL)
- [ ] Implement retry mechanism
- [ ] Add timeout handling
- [ ] Improve error recovery

### Phase 2: Multi-Robot

- [ ] Support pinky2, pinky3
- [ ] Implement robot selection algorithm
- [ ] Add concurrent order processing
- [ ] Load balancing

### Phase 3: Monitoring

- [ ] Add Prometheus metrics
- [ ] Implement health checks
- [ ] Order processing time tracking
- [ ] Error rate monitoring

### Phase 4: Advanced Features

- [ ] Order priority queue
- [ ] Estimated delivery time
- [ ] Real-time order status updates
- [ ] Customer notification preferences

## Dependencies

### Python Packages

- rclpy (ROS2)
- geometry_msgs
- fleet_interfaces (custom)
- threading (stdlib)
- socket (stdlib)
- json (stdlib)

### ROS2 Packages

- nav2_msgs
- fleet_interfaces (custom)

## Conclusion

Clean Architecture 원칙을 따라 GUI 주문 통합 시스템을 성공적으로 구현하였습니다:

- ✓ Separation of Concerns
- ✓ Dependency Inversion
- ✓ Testability
- ✓ Scalability
- ✓ Maintainability

시스템은 현재 빌드되고 테스트 가능한 상태이며, 실제 환경에서 통합 테스트를 진행할 수 있습니다.

## Contact & Support

**Documentation**:
- `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/`

**Test Scripts**:
- `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/`

**Logs**:
- `~/.ros/log/`

---

**Implementation Date**: 2026-02-25
**Architecture**: Clean Architecture + SOLID Principles
**Status**: ✓ Complete and Ready for Integration Testing
