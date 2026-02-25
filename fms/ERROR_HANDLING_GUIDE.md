# SC-74: 서빙 오류 대응 구현 가이드

## 개요

SC-74는 로봇 서빙 과정에서 발생하는 오류를 감지하고, 운영자에게 알림을 발송하며, 운영자의 개입을 통해 복구하는 시스템입니다.

## 구현 범위

### SC-191/329: 서빙 오류 감지 로직
- Navigation 실패 감지 (ABORTED, CANCELED 상태)
- 로봇 통신 끊김 감지 (heartbeat timeout)
- 배터리 부족 감지 (low_battery_threshold)
- 작업 타임아웃 감지 (pickup_timeout, delivery_timeout)
- 에러 상태 정의: NAV_FAILED, COMM_LOST, LOW_BATTERY, TIMEOUT, OBSTACLE

### SC-192/330: 오류 알림 발송
- /fms/error_alert ROS 2 토픽 발행
- ErrorAlert 메시지 정의: robot_id, error_type, error_message, timestamp
- Main Server를 통해 Admin GUI에 실시간 알림
- TCP broadcast: {"type": "error_alert", "data": {...}}

### SC-193/331: 운영자 개입 인터페이스
- Admin GUI에 에러 로봇 표시 (빨간색 하이라이트)
- 에러 상세 정보 팝업
- 운영자 액션 버튼:
  * "재시도": 현재 작업 재시도
  * "복귀": 주차 위치로 강제 복귀
  * "정지": 로봇 긴급 정지
  * "해제": 에러 상태 해제

## 아키텍처

```
┌──────────────────┐
│   로봇 (pinky)   │
│  - pose topic    │
│  - battery topic │
└────────┬─────────┘
         │
    heartbeat
    battery update
         │
┌────────▼─────────────────────────┐
│      FMS Node                     │
│  ┌──────────────────────────────┐│
│  │ ErrorDetector                ││
│  │ - Register heartbeat         ││
│  │ - Check COMM_LOST            ││
│  │ - Check LOW_BATTERY          ││
│  │ - Check NAV_FAILED           ││
│  │ - Check TIMEOUT              ││
│  └──────────────────────────────┘│
│  ┌──────────────────────────────┐│
│  │ ErrorRecoveryHandler         ││
│  │ - Submit operator command    ││
│  │ - Execute recovery actions   ││
│  │ - Track action history       ││
│  └──────────────────────────────┘│
└────────┬─────────────────────────┘
         │ /fms/error_alert
         │ /fms/operator_command
         │
┌────────▼──────────────────┐
│   Main Server             │
│ - Relay error alerts      │
│ - Route operator commands │
└────────┬─────────────────┘
         │ TCP broadcast
         │ (error_alert)
         │
┌────────▼──────────────────┐
│   Admin GUI               │
│  ErrorHandlerWidget       │
│  - Display active errors  │
│  - Show error details     │
│  - Execute operator actions
└───────────────────────────┘
```

## 파일 구조

### FMS (Fleet Management System)

```
fms/fms/
├── fms_node.py              # FMS 노드 (수정됨)
│   ├── ErrorDetector 초기화
│   ├── ErrorRecoveryHandler 초기화
│   ├── error_alert 발행자 생성
│   ├── operator_command 구독자 생성
│   ├── _monitor_errors() 타이머
│   ├── _process_recovery_actions() 타이머
│   └── 콜백: operator_command_callback, robot_pose_callback 등
│
├── error_detector.py         # 새 파일 - 오류 감지 로직
│   ├── ErrorType enum
│   ├── RobotError 클래스
│   └── ErrorDetector 클래스
│       ├── register_heartbeat()
│       ├── check_communication_loss()
│       ├── check_low_battery()
│       ├── check_navigation_failure()
│       ├── check_task_timeout()
│       ├── register_error()
│       └── get_error_statistics()
│
└── error_recovery.py         # 새 파일 - 오류 복구 로직
    ├── OperatorCommand enum
    ├── OperatorAction 클래스
    └── ErrorRecoveryHandler 클래스
        ├── submit_operator_command()
        ├── execute_action()
        ├── register_action_callback()
        └── get_action_history()
```

### ROS 2 Messages

```
fleet_interfaces/msg/
├── ErrorAlert.msg           # 새 파일 - 오류 알림 메시지
│   ├── robot_id
│   ├── error_type
│   ├── error_message
│   ├── current_pose
│   ├── battery_voltage
│   └── timestamp
│
└── OperatorCommand.msg      # 새 파일 - 운영자 명령 메시지
    ├── robot_id
    ├── command
    ├── order_id
    ├── reason
    └── timestamp
```

### Admin GUI

```
app/gui/admin_gui/src/
├── ui_error_handler.py       # 새 파일 - 에러 핸들링 UI
│   ├── ErrorAlertDialog 클래스
│   │   └── 에러 상세 정보 및 액션 선택
│   │
│   └── ErrorHandlerWidget 클래스
│       ├── 활성 에러 테이블
│       ├── 빠른 액션 버튼
│       └── 에러 히스토리
│
└── error_client.py           # 새 파일 - TCP 클라이언트
    ├── ErrorClient 클래스
    │   ├── connect()
    │   ├── send_operator_command()
    │   └── _receive_loop()
    │
    └── MockErrorClient 클래스
        └── 테스트용 모의 클라이언트
```

## 사용 방법

### 1. FMS 시작

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
source install/setup.bash
ros2 run fms fms_node
```

FMS는 자동으로 오류 감지 및 모니터링을 시작합니다:
- 0.5Hz (2초마다) 통신 및 배터리 확인
- 1Hz (1초마다) 복구 액션 처리

### 2. Admin GUI 시작

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/admin_gui
python3 src/main.py
```

Admin GUI는 자동으로 Main Server에 연결되고, 에러 알림을 수신합니다.

### 3. 오류 감지 및 대응

#### 오류 감지 프로세스

1. **로봇이 오류 상태 진입**
   - Navigation 실패
   - 통신 끊김 (5초 이상 heartbeat 없음)
   - 배터리 부족 (20V 이하)
   - 작업 타임아웃

2. **FMS가 오류 감지**
   - ErrorDetector가 주기적으로 확인
   - 오류 등록 및 FleetController 업데이트

3. **오류 알림 발송**
   - /fms/error_alert 토픽 발행
   - Main Server가 TCP로 Admin GUI에 전달

4. **Admin GUI가 알림 표시**
   - 활성 에러 테이블 업데이트
   - 팝업 다이얼로그 표시

#### 운영자 대응 프로세스

1. **Admin GUI에서 액션 선택**
   - "재시도 (RETRY)" - 현재 위치에서 다시 시도
   - "복귀 (RETURN_HOME)" - 주차 위치로 강제 복귀
   - "정지 (EMERGENCY_STOP)" - 긴급 정지
   - "해제 (CLEAR_ERROR)" - 에러 상태만 해제

2. **명령 전송**
   - Admin GUI → Main Server → FMS
   - /fms/operator_command 토픽으로 전달

3. **FMS가 명령 실행**
   - ErrorRecoveryHandler에서 처리
   - 로봇에 적절한 명령 전송
   - 완료 후 에러 상태 정리

## 오류 타입 정의

### NAV_FAILED (Navigation 실패)
- 원인: Navigation 액션이 ABORTED 또는 CANCELED 상태
- 대응: 현재 위치에서 재시도 또는 강제 복귀
- 임계값: 없음 (즉시 감지)

### COMM_LOST (통신 끊김)
- 원인: Heartbeat (pose 토픽) 수신 없음
- 대응: 통신 복구 대기 또는 강제 정지
- 임계값: 5초

### LOW_BATTERY (배터리 부족)
- 원인: 배터리 전압 20V 이하
- 대응: 강제 복귀 (안전)
- 임계값: 20.0V

### TIMEOUT (작업 타임아웃)
- 원인: 작업이 설정된 시간을 초과
- Pickup timeout: 60초
- Delivery timeout: 120초
- 대응: 재시도 또는 강제 복귀

### OBSTACLE (장애물)
- 원인: Navigation이 반복적으로 실패
- 대응: 수동 개입 필요
- 임계값: 3회 실패 시

## 설정

ErrorDetector의 임계값은 fms_node.py에서 설정할 수 있습니다:

```python
error_detector = ErrorDetector()
error_detector.heartbeat_timeout = 5.0        # 통신 타임아웃
error_detector.battery_low_threshold = 20.0   # 저배터리 임계값
error_detector.pickup_timeout = 60.0          # 픽업 타임아웃
error_detector.delivery_timeout = 120.0       # 배송 타임아웃
error_detector.nav_retry_timeout = 10.0       # 네비게이션 재시도 타임아웃
```

## TCP 통신 프로토콜

### 오류 알림 (FMS → Main Server → Admin GUI)

```json
{
  "type": "error_alert",
  "data": {
    "robot_id": "pinky1",
    "error_type": "NAV_FAILED",
    "error_message": "Navigation failed: ABORTED",
    "battery_voltage": 25.5,
    "pose": {
      "x": 0.5,
      "y": 1.0,
      "z": 0.0
    },
    "timestamp": "2026-02-25T10:30:45.123456"
  }
}
```

### 운영자 명령 (Admin GUI → Main Server → FMS)

```json
{
  "type": "operator_command",
  "data": {
    "robot_id": "pinky1",
    "command": "RETRY",
    "order_id": "order_123",
    "reason": "Operator intervention",
    "timestamp": "2026-02-25T10:30:50.123456"
  }
}
```

## 테스트

### 오류 시뮬레이션

Admin GUI에서 MockErrorClient를 사용하여 테스트:

```python
# app/gui/admin_gui/src/ui_error_handler.py
client = MockErrorClient()

# 오류 시뮬레이션
client.simulate_error(
    'pinky1',
    'NAV_FAILED',
    'Navigation failed: ABORTED',
    battery=25.5,
    pose={'x': 0.5, 'y': 1.0}
)
```

### 전체 흐름 테스트

```bash
# Terminal 1: FMS 시작
ros2 run fms fms_node

# Terminal 2: Admin GUI 시작
cd app/gui/admin_gui
python3 src/main.py

# Terminal 3: 오류 시뮬레이션 (선택사항)
ros2 topic pub -1 /fms/error_alert fleet_interfaces/ErrorAlert \
  '{robot_id: pinky1, error_type: NAV_FAILED, error_message: "Test error", battery_voltage: 25.5, timestamp: now}'
```

## 로깅

모든 오류 감지 및 복구 작업은 로깅됩니다:

```
[FMS] Error detected for pinky1: NAV_FAILED
[FMS] Published error alert for pinky1: Navigation failed: ABORTED
[FMS] Operator command RETRY queued for robot pinky1
[FMS] Executing RETRY for robot pinky1
[FMS] Successfully executed RETRY for robot pinky1
```

## 향후 개선사항

1. **자동 복구**: 특정 오류에 대해 자동으로 재시도
2. **거리 기반 선택**: 가장 가까운 로봇에게 작업 재할당
3. **배터리 예측**: 남은 주행 시간 기반 배터리 관리
4. **장애물 회피**: 동적 경로 재계획
5. **알림 우선순위**: 긴급한 오류부터 처리
6. **통계 대시보드**: 오류 발생 패턴 분석

## 관련 Jira 이슈

- SC-74: 서빙 오류 대응 구현
- SC-191/329: 서빙 오류 감지 로직
- SC-192/330: 오류 알림 발송
- SC-193/331: 운영자 개입 인터페이스
