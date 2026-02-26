# FMS Integration Quickstart

## 빠른 시작 (5분)

### 1. 빌드

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/robot_arm/sandwich_arm_ws
colcon build --packages-select mycobot_kitchen_nodes
source install/setup.bash
```

### 2. Mock 모드로 테스트

#### 터미널 1: FMS 인터페이스 실행

```bash
source install/setup.bash
ros2 launch mycobot_kitchen_nodes fms_interface.launch.py mock_mode:=true
```

#### 터미널 2: 조리 명령 전송

```bash
source install/setup.bash
cd src/mycobot_kitchen_nodes/scripts

# START 명령 전송
python3 test_fms_command.py start

# 5초 후 자동으로 조리 완료 (ready) 상태로 변경됩니다
```

#### 터미널 3: 상태 모니터링

```bash
source install/setup.bash
ros2 topic echo /arm/status
```

예상 출력:
```
data: '{"job_id": "TEST-1234567890", "status": "cooking", "progress": 20, "message": "Mock cooking in progress", "recipe": ""}'
---
data: '{"job_id": "TEST-1234567890", "status": "cooking", "progress": 40, "message": "Mock cooking in progress", "recipe": ""}'
---
data: '{"job_id": "TEST-1234567890", "status": "cooking", "progress": 60, "message": "Mock cooking in progress", "recipe": ""}'
---
data: '{"job_id": "TEST-1234567890", "status": "cooking", "progress": 80, "message": "Mock cooking in progress", "recipe": ""}'
---
data: '{"job_id": "TEST-1234567890", "status": "ready", "progress": 100, "message": "Mock cooking completed", "recipe": ""}'
```

### 3. 다양한 명령 테스트

```bash
# 특정 job_id로 START
python3 test_fms_command.py start --job-id JOB-001 --menu-name "치즈버거"

# PAUSE
python3 test_fms_command.py pause --job-id JOB-001

# RESUME
python3 test_fms_command.py resume --job-id JOB-001

# CANCEL
python3 test_fms_command.py cancel --job-id JOB-001
```

### 4. 실제 로봇팔 연동 (선택사항)

실제 로봇팔이 있는 경우:

#### 터미널 1: 기존 로봇팔 노드 실행

```bash
source install/setup.bash
ros2 launch mycobot_kitchen_nodes kitchen.launch.py
```

#### 터미널 2: FMS 인터페이스 실행 (실제 모드)

```bash
source install/setup.bash
ros2 launch mycobot_kitchen_nodes fms_interface.launch.py mock_mode:=false
```

#### 터미널 3: 조리 명령 전송

```bash
source install/setup.bash
cd src/mycobot_kitchen_nodes/scripts
python3 test_fms_command.py start
```

## 토픽 구조

```
┌─────────────────────────────────────────────────┐
│                    FMS                          │
└────────┬────────────────────────────┬───────────┘
         │                            │
         │ /arm/command               │ /arm/status
         │ (JSON)                     │ (JSON)
         │                            │
┌────────▼────────────────────────────▼───────────┐
│         fms_command_interface_node              │
└────────┬────────────────────────────┬───────────┘
         │                            │
         │ /arm_a/cmd                 │ /arm_a/status
         │ (기존 프로토콜)               │ (기존 프로토콜)
         │                            │
┌────────▼────────────────────────────▼───────────┐
│         recipe_executor_node (기존)              │
└──────────────────────────────────────────────────┘
```

## 메시지 예제

### FMS → 로봇팔 (Command)

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

### 로봇팔 → FMS (Status)

```json
{
    "job_id": "JOB-001",
    "status": "cooking",
    "progress": 50,
    "message": "",
    "recipe": "sandwich_recipe_1"
}
```

## 문제 해결

### 빌드 오류

```bash
# 의존성 설치
cd /home/gw/kitchmatics/roscamp-repo-1/robot_arm/sandwich_arm_ws
rosdep install --from-paths src --ignore-src -r -y

# 클린 빌드
rm -rf build/ install/ log/
colcon build --packages-select mycobot_kitchen_nodes
```

### 토픽이 보이지 않음

```bash
# 토픽 목록 확인
ros2 topic list

# 특정 토픽 확인
ros2 topic info /arm/command
ros2 topic info /arm/status
```

### Python 스크립트 실행 오류

```bash
# 실행 권한 부여
chmod +x src/mycobot_kitchen_nodes/scripts/test_fms_command.py

# 직접 Python으로 실행
python3 src/mycobot_kitchen_nodes/scripts/test_fms_command.py start
```

## 다음 단계

- FMS와 실제 통합: `FMS_INTEGRATION.md` 참조
- 메뉴 매핑 커스터마이징
- 에러 처리 고도화
- 배치 처리 구현

## 참고

- 자세한 내용: `FMS_INTEGRATION.md`
- 기존 로봇팔 문서: 프로젝트 루트 docs 폴더
