# 이미지 분석 → ROS2 토픽 발행 API 연동 가이드 (로봇 팔)

이미지 분석 서버의 **GET /analyze/arm_cmd** API를 호출하면, 서버가 스냅샷을 분석한 뒤 결과에 따라 **ROS_DOMAIN_ID=21** 환경에서 `/verify/cmd` 토픽으로 명령을 발행합니다. 로봇 팔 패키지에서 이 API를 호출하여 연동할 수 있습니다.

---

## 0. 테스트 준비 (의존성 설치 및 서버 실행)

**`requests not installed`** 오류는 테스트를 실행하는 환경(venv)에 `requests`가 없을 때 발생합니다. 서버와 테스트 스크립트 모두 아래 의존성이 필요합니다.

### 0.1 의존성 설치

이미지 분석 서버 디렉터리에서 가상환경을 활성화한 뒤 한 번만 설치합니다.

```bash
cd ai_server/image_processing_server
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

- **서버(192.168.0.27 등)**: 이 경로에서 서버를 띄우는 경우에도 동일하게 `pip install -r requirements.txt` 실행.
- **테스트만 실행하는 PC**: 테스트 스크립트(`tests/test_arm_cmd_api.py`)가 API를 호출할 때 `requests`가 필요하므로, 테스트를 실행하는 쪽에서도 위와 동일하게 `requirements.txt`로 설치.

### 0.2 서버 실행 (이미지 분석 서버가 돌아갈 머신)

ROS2는 서버가 설치된 머신에 있으면 됩니다. 테스트 시 서버가 먼저 떠 있어야 합니다.

```bash
cd ai_server/image_processing_server
source venv/bin/activate
pip install -r requirements.txt   # 최초 1회
python app.py
```

기본 주소: `http://0.0.0.0:5001` (다른 PC에서는 `http://<서버IP>:5001` 로 접근).

### 0.3 API 테스트 스크립트 실행

테스트는 **서버에 요청을 보내는 PC**에서 실행합니다. 같은 머신에서 서버와 테스트를 같이 돌릴 수도 있습니다.

```bash
cd ai_server/image_processing_server
source venv/bin/activate
python tests/test_arm_cmd_api.py
```

스크립트 기본값은 `http://192.168.0.27:5001` 입니다. 다른 주소로 테스트하려면 `test_arm_cmd_api.py` 내 `call_analyze_arm_cmd(api_base="http://<IP>:5001")` 로 변경하거나, 코드에서 `api_base` 인자를 수정해 사용하세요.

- **성공 시**: `success: True`, `command_key`, `ros_published` 등이 출력됩니다.
- **실패 시**: `success: False`, `error`/`message`를 확인하세요. (연결 실패, 타임아웃, 서버 내부 오류 등)

### 0.4 ROS2 토픽 수신 확인 (선택, ROS2 설치된 환경)

서버가 **ROS_DOMAIN_ID=21** 로 `/verify/cmd` 를 발행하므로, 같은 도메인에서 echo 하려면:

```bash
ROS_DOMAIN_ID=21 ros2 topic echo /verify/cmd
```

그 다음 다른 터미널에서 `python tests/test_arm_cmd_api.py` 또는 `curl "http://<서버IP>:5001/analyze/arm_cmd"` 를 호출하면, echo 터미널에 수신 메시지가 출력됩니다.

---

## 1. API 개요

| 항목 | 내용 |
|------|------|
| URL | `GET http://192.168.0.27:5001/analyze/arm_cmd` |
| 동작 | 1) JetBot 스냅샷 수집 → 2) YOLO 분석 → 3) 클래스에 따라 ROS2 토픽 발행 |
| ROS | `ROS_DOMAIN_ID=21`, 토픽 `/verify/cmd`, 메시지 `std_msgs/msg/String` |

### 클래스 → 명령 매핑

| 검출 클래스 | 발행 데이터 |
|-------------|-------------|
| Hamcheese, Mushroom, All-in-one | `j1\|HANDOFF_PINKY` (배달로봇 인수) |
| NG | `j1\|DISCARD` (폐기) |
| 검출 없음 | 발행 안 함 (config에서 no_detection_command 설정 시 CANCEL 등 가능) |

---

## 2. 로봇 팔 패키지에서 API 호출 (Python)

```python
import requests

def call_analyze_arm_cmd(api_base: str = "http://192.168.0.27:5001", timeout: float = 15.0) -> dict:
    """GET /analyze/arm_cmd 호출. 분석 결과에 따라 서버가 이미 ros2 topic pub 수행함."""
    url = f"{api_base.rstrip('/')}/analyze/arm_cmd"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

# 사용 예
data = call_analyze_arm_cmd()
if data.get("success"):
    command_key = data.get("command_key")   # "handoff_pinky" | "discard" | None
    ros_published = data.get("ros_published")  # 서버에서 ros2 topic pub 결과
    detections = data.get("detections", [])
```

응답 예시:

```json
{
  "success": true,
  "source": "snapshot",
  "image_size": {"width": 640, "height": 480},
  "detections": [{"class_name": "Hamcheese", "confidence": 0.92, "bbox": [...]}],
  "count": 1,
  "command_key": "handoff_pinky",
  "ros_published": {"success": true, "command": "handoff_pinky", "data": "j1|HANDOFF_PINKY", "returncode": 0}
}
```

---

## 3. 테스트용 ROS2 패키지 (arm_cmd_api_client)

이미지 분석 서버 프로젝트에 테스트용 클라이언트 패키지가 포함되어 있습니다.

- **위치**: `ai_server/image_processing_server/docs/sample_ros2_package/arm_cmd_api_client/`
- **복사 후 빌드**:
  ```bash
  cp -r .../image_processing_server/docs/sample_ros2_package/arm_cmd_api_client ~/ros2_ws/src/
  cd ~/ros2_ws && colcon build --packages-select arm_cmd_api_client && source install/setup.bash
  ```

### 노드

| 실행 명령 | 설명 |
|-----------|------|
| `ros2 run arm_cmd_api_client arm_cmd_api_client_node` | 주기적으로 /analyze/arm_cmd 호출 (파라미터: api_base, interval_sec) |
| `ros2 run arm_cmd_api_client arm_cmd_echo_test` | /verify/cmd 구독하여 API가 발행한 명령 수신 확인 (ROS_DOMAIN_ID=21 필요) |

### 연동 테스트 절차

1. 터미널 1: 이미지 분석 서버 실행  
   `python app.py` (또는 해당 서버 실행)
2. 터미널 2: `ROS_DOMAIN_ID=21 ros2 run arm_cmd_api_client arm_cmd_echo_test`  
   → /verify/cmd 수신 대기
3. 터미널 3: `curl "http://192.168.0.27:5001/analyze/arm_cmd"`  
   → 서버가 분석 후 ros2 topic pub 실행, 터미널 2에서 메시지 확인

---

## 4. 로봇 팔 패키지 삽입용 테스트 코드

서버 프로젝트 내 **tests/test_arm_cmd_api.py** 에서 `call_analyze_arm_cmd()` 함수를 복사해 로봇 팔 패키지에 넣어 사용할 수 있습니다.

```bash
# 서버 프로젝트에서 단독 실행 테스트
cd ai_server/image_processing_server
python tests/test_arm_cmd_api.py
```

---

## 5. 설정 (서버 측)

- **config/arm_ros_config.yaml**: ROS_DOMAIN_ID, 토픽 이름, 클래스→명령 매핑, handoff_pinky/discard/cancel 데이터 값.
- **config/yolo_config.yaml**: 클래스명(Hamcheese, Mushroom, All-in-one, NG)은 여기와 arm_ros_config.yaml 이 일치해야 함.

---

## 6. 토픽 명령어 참고 (수동 확인용)

```bash
# HANDOFF_PINKY (배달로봇 인수)
ros2 topic pub --once /verify/cmd std_msgs/msg/String "data: 'j1|HANDOFF_PINKY'"

# DISCARD (폐기)
ros2 topic pub --once /verify/cmd std_msgs/msg/String "data: 'j1|DISCARD'"

# CANCEL
ros2 topic pub --once /verify/cmd std_msgs/msg/String "data: 'j1|CANCEL'"
```

위 명령은 **ROS_DOMAIN_ID=21** 환경에서 실행해야 로봇 팔 노드와 동일 도메인에서 수신됩니다.
