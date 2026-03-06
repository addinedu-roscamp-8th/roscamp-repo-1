# FMS GUI 주문 연동 - 빠른 시작 가이드

## 사전 요구사항

- ROS2 Humble
- Python 3.10+
- fleet_interfaces 패키지 빌드 완료
- 네트워크: kitchmatics WiFi (192.168.1.x)

## 1. FMS 패키지 빌드

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms

# 빌드
colcon build --packages-select fms

# 소싱
source install/setup.bash
```

## 2. FMS 노드 시작

### 터미널 1: FMS 노드

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms
source install/setup.bash

# pinky1에 맞게 ROS_DOMAIN_ID 설정
export ROS_DOMAIN_ID=11

# FMS 실행
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
```

**예상 출력**:
```
[INFO] Initializing Fleet Management System...
[INFO] GUI TCP server started on port 9000
[INFO] Order handler callbacks registered
[INFO] FMS Node is running...
```

## 3. GUI 주문 연동 테스트

### 터미널 2: 테스트 스크립트

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms/scripts

# 새 주문 테스트
python3 test_gui_order.py new_order
```

**예상 출력**:
```
============================================================
Testing New Order Workflow
============================================================
Connected to FMS at 192.168.1.3:9000

Sending order: {
  "command": "new_order",
  "table_number": 1,
  "order": {
    "items": [
      {"menu_id": "M001", "quantity": 1}
    ]
  }
}

Received response: {
  "status": "success",
  "data": {
    "order_id": "ORD-20260225123456-0001",
    "message": "Order ORD-20260225123456-0001 accepted"
  }
}

Order accepted! Order ID: ORD-20260225123456-0001

Waiting for delivery notification...
(Robot will navigate to point13 -> load food -> navigate to table1)

Received notification: {
  "type": "delivery_notification",
  "data": {
    "order_id": "ORD-20260225123456-0001",
    "table_number": 1,
    "robot_id": "pinky1",
    "status": "arrived"
  }
}

Robot arrived at table1!
Customer can now confirm delivery...

Sending delivery confirmation: {
  "command": "delivery_complete",
  "order_id": "ORD-20260225123456-0001",
  "table_number": 1
}

Confirmation response: {
  "status": "success",
  "data": {
    "message": "Delivery confirmed, robot returning home"
  }
}

Order workflow completed!
Connection closed
```

## 4. 로봇 내비게이션 모니터링

### 터미널 3: pinky1 자세 모니터링

```bash
export ROS_DOMAIN_ID=11
ros2 topic echo /pose
```

### 터미널 4: 내비게이션 상태 모니터링

```bash
export ROS_DOMAIN_ID=11
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{pose: {header: {frame_id: 'map'}, pose: {position: {x: 0.585, y: 0.63, z: 0.0}}}}"
```

## 5. 조리 주문 모니터링

### 터미널 5: 로봇 암 명령 모니터링

```bash
export ROS_DOMAIN_ID=25  # FMS 도메인
ros2 topic echo /cooking/order
```

**예상 출력**:
```
order_id: 'ORD-20260225123456-0001'
menu_id: 'M001'
quantity: 1
sauce_type: ''
assigned_robot_id: 'pinky1'
```

## 6. 전체 시스템 통합 테스트

### 모든 구성 요소 시작

1. **pinky1 시작**:
   ```bash
   # pinky1 로봇에서 (DOMAIN_ID=11)
   ros2 launch pinky_navigation pinky_navigation.launch.py
   ```

2. **FMS 시작**:
   ```bash
   # 메인 PC에서 (DOMAIN_ID=25이지만 DOMAIN_ID=11을 모니터링)
   export ROS_DOMAIN_ID=11
   ros2 run fms fms_node --ros-args -p skip_robot_arm:=true
   ```

3. **로봇 암 Coordinator 시작** (가능한 경우):
   ```bash
   export ROS_DOMAIN_ID=25
   ros2 run robot_arm arm_coordinator_node
   ```

4. **테스트 주문 전송**:
   ```bash
   python3 test_gui_order.py new_order
   ```

## 7. 문제 해결

### 문제: 연결 거부

```
ERROR: Could not connect to FMS at 192.168.1.3:9000
```

**해결 방법**:
- FMS 실행 확인: `ps aux | grep fms_node`
- 포트 개방 확인: `netstat -tulpn | grep 9000`
- IP 주소 확인: `ip addr show`

### 문제: 배달 알림을 받지 못함

**해결 방법**:
- pinky1 내비게이션 확인: `ros2 topic echo /pose`
- 주문 상태 확인: FMS 로그 확인
- `fms_config.yaml`에서 맵 위치 확인

### 문제: 로봇 암이 조리 주문을 받지 못함

**해결 방법**:
- FMS의 ROS_DOMAIN_ID=25 확인
- 토픽 모니터링: `ros2 topic echo /cooking/order`
- 로봇 암 Coordinator 실행 확인

## 8. 설정 변경

### TCP 포트 변경

`/home/gw/kitchmatics/roscamp-repo-1/fms/fms/fms_node.py` 편집:

```python
self.gui_tcp_server = GUITCPServer(host='0.0.0.0', port=9000)  # 여기서 포트 변경
```

### 로봇 선택 변경

`/home/gw/kitchmatics/roscamp-repo-1/fms/fms/order_handler.py` 편집:

```python
# _execute_order_workflow() 안에서
robot_id = "pinky1"  # pinky2 또는 pinky3로 변경
```

### 맵 위치 변경

`/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml` 편집:

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
```

## 9. API 레퍼런스

### TCP 메시지 형식

모든 메시지는 4바이트 길이 헤더 + JSON 페이로드를 사용합니다.

#### 요청: new_order
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

#### 응답: new_order
```json
{
    "status": "success",
    "data": {
        "order_id": "ORD-20260225123456-0001",
        "message": "Order accepted"
    }
}
```

#### 푸시 알림: delivery_notification
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

#### 요청: delivery_complete
```json
{
    "command": "delivery_complete",
    "order_id": "ORD-20260225123456-0001",
    "table_number": 1
}
```

#### 응답: delivery_complete
```json
{
    "status": "success",
    "data": {
        "message": "Delivery confirmed, robot returning home"
    }
}
```

## 10. 개발

### 유닛 테스트 실행

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms
pytest tests/
```

### 디버그 로깅 활성화

```python
# fms_node.py에서
logging.basicConfig(level=logging.DEBUG)
```

### 커스텀 주문 핸들러 추가

```python
# fms_node.py에서
def _handle_custom_command(self, message: Dict[str, Any]) -> Dict[str, Any]:
    # 커스텀 로직 구현
    return {'success': True, 'data': {}}

# 핸들러 등록
self.gui_tcp_server.register_handler('custom_command', self._handle_custom_command)
```

## 11. 다음 단계

1. **고객 GUI 연동**:
   - GUI TCP 클라이언트에 4바이트 길이 헤더 프로토콜 적용
   - 배달 알림 리스너 구현
   - 주문 상태 추적 UI 추가

2. **로봇 암 연동 추가**:
   - 로봇 암 Coordinator 노드 구현
   - `/cooking/order` 구독
   - `/cooking/loading_complete` 발행

3. **다중 로봇 지원 추가**:
   - 로봇 선택 알고리즘 구현
   - 동시 주문 처리
   - 로봇 가용성 확인 추가

4. **영속성 추가**:
   - 주문 이력을 데이터베이스에 저장
   - 재시작 시 주문 복구 구현
   - 주문 조회 API 추가

## 지원

문제나 질문이 있으면 다음을 확인하세요:
- FMS 로그: `~/.ros/log/`
- 문서: `/home/gw/kitchmatics/roscamp-repo-1/fms/docs/`
- 테스트 스크립트: `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/`
