# FMS Integration Guide

## 개요

로봇팔이 FMS(Fleet Management System)로부터 조리 명령을 받아 조리를 수행하고, 상태를 피드백하는 통합 시스템입니다.

## 아키텍처

### Clean Architecture 레이어

```
┌─────────────────────────────────────────────────┐
│           Presentation Layer                     │
│  FMS Interface (JSON over ROS2 Topics)          │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│           Application Layer                      │
│  - CookingCommandHandler (Use Case)             │
│  - ArmStatusParser (Use Case)                   │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│           Domain Layer                           │
│  - CookingCommand (Entity)                      │
│  - CookingStatus (Entity)                       │
│  - Order, MenuItem (Value Objects)              │
└──────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│           Infrastructure Layer                   │
│  - recipe_executor_node (기존)                   │
│  - arm_driver_node (기존)                        │
└──────────────────────────────────────────────────┘
```

### 노드 구조

```
FMS
  │
  │ (JSON)
  ▼
┌──────────────────────────┐
│ fms_command_interface    │  ← 새로 추가
│ - /arm/command (sub)     │
│ - /arm/status (pub)      │
└───────┬──────────────────┘
        │
        │ (기존 프로토콜)
        ▼
┌──────────────────────────┐
│ recipe_executor          │  ← 기존
│ - /arm_a/cmd (sub)       │
│ - /arm_a/status (pub)    │
└───────┬──────────────────┘
        │
        ▼
┌──────────────────────────┐
│ arm_driver               │  ← 기존
└──────────────────────────┘
```

## 메시지 형식

### FMS → 로봇팔 (Command)

토픽: `/arm/command`
타입: `std_msgs/String` (JSON)

```json
{
    "job_id": "JOB-001",
    "operation": "START",
    "order": {
        "order_id": "ORD-001",
        "items": [
            {
                "menu_id": 1,
                "name": "햄버거",
                "quantity": 1
            }
        ]
    }
}
```

**Operations:**
- `START`: 조리 시작
- `PAUSE`: 일시정지
- `RESUME`: 재개
- `CANCEL`: 취소

### 로봇팔 → FMS (Status)

토픽: `/arm/status`
타입: `std_msgs/String` (JSON)

```json
{
    "job_id": "JOB-001",
    "status": "cooking",
    "progress": 50,
    "message": "",
    "recipe": "sandwich_recipe_1"
}
```

**Status Types:**
- `idle`: 대기 중
- `cooking`: 조리 중
- `ready`: 조리 완료
- `paused`: 일시정지
- `error`: 오류
- `wait_for_sauce`: 소스 대기

## 사용 방법

### 1. Mock 모드 실행 (실제 로봇팔 없이 테스트)

```bash
# 빌드
cd /home/gw/kitchmatics/roscamp-repo-1/robot_arm/sandwich_arm_ws
colcon build --packages-select mycobot_kitchen_nodes

# 실행
source install/setup.bash
ros2 run mycobot_kitchen_nodes fms_command_interface --ros-args \
  -p mock_mode:=true \
  -p status_publish_rate:=2.0
```

Mock 모드에서는:
- START 명령 수신 후 5초 뒤 자동으로 `ready` 상태 전송
- 실제 로봇팔 없이 테스트 가능
- 진행률 자동 업데이트 (0% → 100%)

### 2. 실제 로봇팔 연동

```bash
# 기존 노드들 실행
ros2 launch mycobot_kitchen_nodes kitchen.launch.py

# FMS 인터페이스 실행 (별도 터미널)
source install/setup.bash
ros2 run mycobot_kitchen_nodes fms_command_interface --ros-args \
  -p mock_mode:=false
```

### 3. 테스트 스크립트 사용

```bash
source install/setup.bash

# START 명령 전송
python3 src/mycobot_kitchen_nodes/scripts/test_fms_command.py start

# 다른 job_id로 START
python3 src/mycobot_kitchen_nodes/scripts/test_fms_command.py start \
  --job-id JOB-123 \
  --menu-id 1 \
  --menu-name "햄버거"

# PAUSE 명령
python3 src/mycobot_kitchen_nodes/scripts/test_fms_command.py pause \
  --job-id JOB-123

# RESUME 명령
python3 src/mycobot_kitchen_nodes/scripts/test_fms_command.py resume \
  --job-id JOB-123

# CANCEL 명령
python3 src/mycobot_kitchen_nodes/scripts/test_fms_command.py cancel \
  --job-id JOB-123

# 상태 모니터링
python3 src/mycobot_kitchen_nodes/scripts/test_fms_command.py monitor \
  --duration 60
```

### 4. ROS2 CLI로 직접 테스트

```bash
# 명령 전송
ros2 topic pub /arm/command std_msgs/String \
  "{data: '{\"job_id\":\"JOB-001\",\"operation\":\"START\",\"order\":{\"order_id\":\"ORD-001\",\"items\":[{\"menu_id\":1,\"name\":\"햄버거\",\"quantity\":1}]}}'}" \
  --once

# 상태 확인
ros2 topic echo /arm/status
```

## 파일 구조

```
mycobot_kitchen_nodes/
├── mycobot_kitchen_nodes/
│   ├── fms_command_interface_node.py  ← 새로 추가 (FMS 통합)
│   ├── recipe_executor_node.py        ← 기존 (수정 없음)
│   └── arm_driver_node.py             ← 기존 (수정 없음)
├── scripts/
│   └── test_fms_command.py            ← 새로 추가 (테스트 스크립트)
├── setup.py                            ← 수정 (새 노드 등록)
└── FMS_INTEGRATION.md                  ← 새로 추가 (이 문서)
```

## 설계 원칙

### SOLID 원칙 적용

1. **Single Responsibility Principle**
   - `CookingCommandHandler`: 명령 처리만 담당
   - `ArmStatusParser`: 상태 파싱만 담당
   - `FMSCommandInterfaceNode`: ROS2 통신만 담당

2. **Open/Closed Principle**
   - 새로운 Operation 타입 추가 시 Enum 확장
   - 기존 코드 수정 없이 새 메뉴 추가 가능 (menu_map)

3. **Liskov Substitution Principle**
   - Mock 모드와 실제 모드 모두 동일한 인터페이스 사용

4. **Interface Segregation Principle**
   - Domain 엔티티와 Use Case 분리
   - ROS2 통신과 비즈니스 로직 분리

5. **Dependency Inversion Principle**
   - Use Case가 ROS2에 의존하지 않음
   - Domain 엔티티가 Infrastructure에 의존하지 않음

### Scalability 고려사항

1. **상태 비저장 (Stateless)**
   - 노드가 재시작해도 job_id로 추적 가능
   - FMS가 상태의 원천 (Source of Truth)

2. **비동기 처리**
   - 명령 수신과 상태 발행이 독립적
   - 로봇팔과의 통신도 비동기

3. **오류 처리**
   - JSON 파싱 실패 시 로깅하고 무시
   - 명령 처리 실패 시 FMS에 알리지 않음 (멱등성)

4. **확장 가능성**
   - 메뉴 ID → 레시피 매핑을 외부 설정으로 분리 가능
   - 여러 로봇팔 지원 가능 (/arm_a, /arm_b)

## 향후 개선사항

1. **메뉴 매핑 외부화**
   - YAML 설정 파일로 메뉴 ID → 레시피 매핑
   - 런타임에 설정 변경 가능

2. **상태 저장소**
   - Redis 등을 활용한 상태 영속화
   - 노드 재시작 시 복구 가능

3. **에러 리포팅**
   - 상세한 에러 코드 체계
   - 에러 발생 시 FMS에 즉시 알림

4. **로깅 및 모니터링**
   - 구조화된 로그 (JSON)
   - 메트릭 수집 (Prometheus)

5. **배치 처리**
   - 여러 주문을 큐에 담아 순차 처리
   - 우선순위 기반 스케줄링

## 문제 해결

### Q: Mock 모드에서 상태가 발행되지 않습니다.

A: `status_publish_rate` 파라미터를 확인하세요. 기본값은 1.0Hz입니다.

```bash
ros2 run mycobot_kitchen_nodes fms_command_interface --ros-args \
  -p mock_mode:=true \
  -p status_publish_rate:=2.0
```

### Q: 실제 로봇팔에서 명령이 실행되지 않습니다.

A: 다음을 확인하세요:
1. `recipe_executor_node`가 실행 중인지 확인
2. `/arm_a/cmd` 토픽이 발행되는지 확인
3. Mock 모드가 꺼져있는지 확인 (`-p mock_mode:=false`)

```bash
# 토픽 확인
ros2 topic list | grep arm

# 메시지 확인
ros2 topic echo /arm_a/cmd
```

### Q: 메뉴 ID를 레시피로 어떻게 매핑하나요?

A: 현재는 `CookingCommandHandler._menu_to_recipe()` 메서드에 하드코딩되어 있습니다.

```python
menu_map = {
    1: "sandwich_recipe_1",
    2: "sandwich_recipe_2",
}
```

실제 레시피 이름은 `recipes.yaml` 파일을 참조하세요.

## 연락처

문제가 발생하면 이슈를 등록하거나 팀에 문의하세요.
