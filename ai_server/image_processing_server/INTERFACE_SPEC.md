# YOLO 분석 서버 API 인터페이스 명세

## 개요

- **서비스**: JetBot(라즈베리파이)의 영상/이미지를 가져와 YOLO로 객체 검출 후 결과를 JSON으로 반환하는 Flask API.
- **기본 URL**: `http://<서버IP>:5001` (포트는 `config/server_config.yaml` 또는 환경변수로 변경 가능)
- **데이터 형식**: 요청/응답 모두 JSON (이미지·영상 바이너리는 API가 내부적으로 JetBot에서 취득).

---

## 공통 사항

- **Base URL**: `http://<host>:5001`
- **Content-Type**: `application/json`
- **에러 시**: HTTP 4xx/5xx + JSON body `{ "success": false, "error": "...", "message": "..." }`

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | API 정보 및 엔드포인트 목록 |
| GET | `/health` | 서버·모델 상태 확인 |
| GET | `/model_info` | 사용 중인 YOLO 모델 경로(best.pt)·로드 상태 확인 |
| GET | `/analyze/image` | 스냅샷 이미지 분석 결과 반환 |
| GET | `/analyze/video` | 영상 스트림 분석 결과 반환 (일괄 JSON) |
| GET | `/analyze/video/stream` | 영상 분석 결과 실시간 스트리밍 (SSE) |
| GET | `/stream/preview` | 영상 MJPEG 스트리밍 + bbox·검출 상태 오버레이 |
| GET | `/view` | 스트리밍 + 검출 상태 표시용 HTML 페이지 |
| GET | `/analyze/arm_cmd` | 이미지 분석 후 결과에 따라 ROS2 토픽 발행 (로봇 팔 연동) |
| POST | `/reload_model` | YOLO 모델 재로드 (설정 변경 후) |

---

## 1. API 정보 (GET `/`)

서비스 설명과 사용 가능한 엔드포인트를 반환합니다.

**요청**

- 메서드: `GET`
- 경로: `/`
- Body: 없음

**응답 (200 OK)**

```json
{
  "service": "yolo-analysis",
  "description": "YOLO 기반 영상/이미지 분석 API (JetBot 소스 연동)",
  "endpoints": {
    "health": "/health",
    "analyze_image": "GET /analyze/image",
    "analyze_video": "GET /analyze/video",
    "reload_model": "POST /reload_model",
    "interface_spec": "See INTERFACE_SPEC.md"
  }
}
```

---

## 2. 모델 정보 (GET `/model_info`) — best.pt 사용 여부 확인

현재 사용 중인 YOLO 모델의 **절대 경로**, **파일 존재 여부**, **클래스 목록**, **로드 상태**를 반환합니다. `best.pt` 사용 여부 및 검출이 안 될 때 경로·설정 점검용입니다.

**요청**: `GET /model_info`

**응답 (200 OK)**

```json
{
  "model_path": "/home/addinedu/Documents/ai_server/image_processing/best.pt",
  "model_path_exists": true,
  "class_names": ["m1", "m2", "m3"],
  "load_status": "loaded"
}
```

| 필드 | 설명 |
|------|------|
| `model_path` | 실제 로드에 사용된 모델 파일의 절대 경로 |
| `model_path_exists` | 해당 경로에 파일이 있는지 여부. `false`면 best.pt가 없음 |
| `class_names` | config에 정의된 클래스명 (m1, m2, m3 등) |
| `load_status` | `loaded`(정상), `file_not_found`(파일 없음), `load_error: ...`(로드 예외) |

---

## 3. 헬스 체크 (GET `/health`)

서버가 동작 중인지, YOLO 모델이 정상 로드되었는지 확인합니다. 상세 모델 경로·파일 존재 여부는 `/model_info` 사용.

**요청**

- 메서드: `GET`
- 경로: `/health`
- Body: 없음

**응답 (200 OK)**

```json
{
  "status": "ok",
  "model": "loaded"
}
```

모델 로드 실패 시 `model` 필드에 `"error: <메시지>"` 형태로 들어갑니다.

---

## 4. 이미지 분석 결과 반환 (GET `/analyze/image`)

- **동작**: JetBot의 `/snapshot` URL에서 **이미지를 직접 다운로드**한 뒤, 해당 이미지에 대해 YOLO 추론을 수행하고 검출 결과를 반환합니다.
- **호출 측**: 별도로 이미지를 전송할 필요 없이 GET 요청만 하면 됩니다.

**요청**

- 메서드: `GET`
- 경로: `/analyze/image`
- Query: 없음
- Body: 없음

**성공 응답 (200 OK)**

```json
{
  "success": true,
  "source": "snapshot",
  "image_size": {
    "width": 640,
    "height": 480
  },
  "detections": [
    {
      "class_id": 0,
      "class_name": "m1",
      "confidence": 0.92,
      "bbox": [100, 150, 300, 400]
    }
  ],
  "count": 1
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `success` | boolean | 성공 여부 |
| `source` | string | `"snapshot"` (JetBot /snapshot) |
| `image_size` | object | `width`, `height` (픽셀) |
| `detections` | array | 검출 객체 목록 |
| `detections[].class_id` | int | 클래스 ID |
| `detections[].class_name` | string | 클래스 이름 (config의 class_names 기준) |
| `detections[].confidence` | float | 신뢰도 (0~1) |
| `detections[].bbox` | [x1,y1,x2,y2] | 바운딩 박스 픽셀 좌표 |
| `count` | int | 검출 개수 |

**에러 응답**

- **503 Service Unavailable**: JetBot에서 스냅샷을 가져오지 못한 경우 (연결 실패, 타임아웃 등)

```json
{
  "success": false,
  "error": "source_fetch_failed",
  "message": "Connection error ..."
}
```

- **500 Internal Server Error**: YOLO 추론 중 오류

```json
{
  "success": false,
  "error": "inference_failed",
  "message": "..."
}
```

---

## 5. 영상 분석 결과 반환 (GET `/analyze/video`)

- **동작**: JetBot의 `/video_feed` **영상 스트림을 직접 읽어** 여러 프레임을 샘플링한 뒤, 각 프레임에 YOLO 추론을 수행하고 프레임별·전체 검출 결과를 반환합니다.
- **호출 측**: 영상을 전송할 필요 없이 GET 요청만 하면 됩니다.

**요청**

- 메서드: `GET`
- 경로: `/analyze/video`
- Query:
  - `num_frames` (optional, integer): 분석할 프레임 수. 생략 시 `config/jetbot_config.yaml`의 `video.num_frames` 사용 (기본 5).
- Body: 없음

**성공 응답 (200 OK)**

```json
{
  "success": true,
  "source": "video_feed",
  "num_frames": 5,
  "frames": [
    {
      "frame_index": 0,
      "image_size": { "width": 640, "height": 480 },
      "detections": [
        {
          "class_id": 1,
          "class_name": "m2",
          "confidence": 0.88,
          "bbox": [120, 100, 350, 380]
        }
      ],
      "count": 1
    }
  ],
  "detections": [ ... ],
  "total_detections": 3
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `success` | boolean | 성공 여부 |
| `source` | string | `"video_feed"` (JetBot /video_feed) |
| `num_frames` | int | 분석한 프레임 수 |
| `frames` | array | 프레임별 결과 |
| `frames[].frame_index` | int | 프레임 인덱스 (0부터) |
| `frames[].image_size` | object | 해당 프레임 해상도 |
| `frames[].detections` | array | 해당 프레임 검출 목록 (형식은 이미지 분석과 동일) |
| `frames[].count` | int | 해당 프레임 검출 개수 |
| `detections` | array | 모든 프레임의 검출을 합친 목록 |
| `total_detections` | int | 전체 검출 개수 |

**에러 응답**

- **503**: 스트림 연결/읽기 실패 (`source_fetch_failed`)
- **500**: 특정 프레임 추론 실패 시 `frame_index` 포함

```json
{
  "success": false,
  "error": "inference_failed",
  "message": "...",
  "frame_index": 2
}
```

---

## 6. 이미지 분석 + ROS2 토픽 발행 (GET `/analyze/arm_cmd`) — 로봇 팔 연동

이미지(스냅샷)를 분석한 뒤, 검출 클래스에 따라 **ROS_DOMAIN_ID=21** 환경에서 **ros2 topic pub --once /arm_b/cmd std_msgs/msg/String** 를 실행합니다. 로봇 팔 패키지에서 이 API를 호출하면, 서버가 분석과 토픽 발행까지 수행합니다.

**클래스 → 명령**

- **Hamcheese, Mushroom, All-in-one** → `data: 'j1|HANDOFF_PINKY'` (배달로봇 인수)
- **NG** → `data: 'j1|DISCARD'` (폐기)
- 검출 없음 → 발행 안 함 (설정 시 CANCEL 가능)

**요청**: `GET /analyze/arm_cmd` (Body 없음)

**성공 응답 (200 OK)**

```json
{
  "success": true,
  "source": "snapshot",
  "image_size": {"width": 640, "height": 480},
  "detections": [{"class_name": "Hamcheese", "confidence": 0.92, "bbox": [100, 150, 300, 400]}],
  "count": 1,
  "command_key": "handoff_pinky",
  "ros_published": {"success": true, "command": "handoff_pinky", "data": "j1|HANDOFF_PINKY", "returncode": 0}
}
```

- `command_key`: `handoff_pinky` | `discard` | null
- `ros_published`: 서버가 실행한 ros2 topic pub 결과. `success`, `returncode` 등 포함.

설정: `config/arm_ros_config.yaml`. 상세 연동 방법: **docs/03_arm_cmd_API_연동_가이드.md**.

---

## 7. 영상 분석 실시간 스트리밍 (GET `/analyze/video/stream`)

JetBot `/video_feed` 스트림을 **실시간**으로 읽어, 프레임마다 YOLO 분석 결과를 **Server-Sent Events(SSE)** 로 전송합니다. 클라이언트는 스트림을 구독하다가 연결을 끊으면 수신이 종료됩니다.

**요청**

- 메서드: `GET`
- 경로: `/analyze/video/stream`
- **Content-Type**: 응답은 `text/event-stream`
- Query:
  - `max_frames` (optional, integer): 최대 전송할 프레임 수. 생략 시 `config/jetbot_config.yaml`의 `video.stream_timeout_seconds`(기본 3600초)까지 계속 전송.

**응답 (200 OK, stream)**

- **Content-Type**: `text/event-stream`
- **Cache-Control**: `no-cache`
- **Connection**: `keep-alive`

각 이벤트는 한 줄: `data: <JSON>\n\n`. JSON 형식은 아래와 같습니다.

**정상 프레임 이벤트**

```json
{
  "frame_index": 0,
  "image_size": { "width": 640, "height": 480 },
  "detections": [
    {
      "class_id": 1,
      "class_name": "m2",
      "confidence": 0.88,
      "bbox": [120, 100, 350, 380]
    }
  ],
  "count": 1
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `frame_index` | int | 0부터 증가하는 프레임 인덱스 |
| `image_size` | object | 해당 프레임 해상도 |
| `detections` | array | 검출 목록 (형식은 이미지 분석과 동일) |
| `count` | int | 검출 개수 |

**에러 이벤트 (같은 스트림 내에서 전송)**

소스 연결 실패 또는 추론 오류 시 해당 이벤트 한 번 보낸 뒤 스트림 종료될 수 있음.

```json
{
  "error": "source_fetch_failed",
  "message": "Connection error ..."
}
```

또는

```json
{
  "error": "inference_failed",
  "message": "...",
  "frame_index": 3
}
```

**클라이언트 사용 예 (JavaScript)**

```javascript
const es = new EventSource("http://<서버>:5001/analyze/video/stream");
es.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.error) {
    console.error(data.message);
    es.close();
    return;
  }
  console.log("Frame", data.frame_index, "detections:", data.detections);
};
es.onerror = () => es.close();
// 종료 시: es.close();
```

**참고**

- 스트림은 `stream_timeout_seconds`(기본 3600초) 또는 `max_frames` 도달 시, 또는 JetBot 연결이 끊기면 종료됩니다.
- 클라이언트에서 `EventSource` 연결을 닫으면 수신만 중단되며, 서버는 다음 프레임부터 버퍼를 비우고 곧 루프가 끝나 스트림이 정리됩니다.

---

## 8. 스트리밍 프리뷰 (GET `/stream/preview`) 및 뷰 페이지 (GET `/view`)

- **GET /stream/preview**: JetBot 영상을 받아 프레임마다 YOLO 분석 후, bbox와 상단에 **Detected: m1, m2** 또는 **No detection** 문구를 그려 **MJPEG** 스트리밍. `Content-Type: multipart/x-mixed-replace; boundary=frame`.
- **GET /view**: 위 스트림을 보여주는 HTML 페이지. 브라우저에서 `http://<서버>:5001/view` 로 접속하면 영상과 검출 여부를 함께 볼 수 있음.

---

## 9. 모델 재로드 (POST `/reload_model`)

`config/yolo_config.yaml`에서 모델 경로·클래스명 등을 변경한 뒤, 서버를 재시작하지 않고 YOLO 모델만 다시 로드할 때 사용합니다.

**요청**

- 메서드: `POST`
- 경로: `/reload_model`
- Body: 없음 (또는 빈 JSON `{}`)

**성공 응답 (200 OK)**

```json
{
  "success": true,
  "message": "Model reloaded from config."
}
```

**에러 응답 (500)**

```json
{
  "success": false,
  "error": "모델 파일을 찾을 수 없음 ..."
}
```

---

## 설정 파일 요약

| 파일 | 용도 |
|------|------|
| `config/yolo_config.yaml` | YOLO 모델 경로(`model_path`), 클래스명(`class_names`), 추론 옵션. **모델 교체 시 이 파일만 수정** |
| `config/jetbot_config.yaml` | JetBot base URL, `/snapshot`, `/video_feed` 경로, 영상 프레임 수·타임아웃, **stream_timeout_seconds**(SSE 최대 유지 시간) 등 |
| `config/server_config.yaml` | 서버 `host`, `port` (기본 5001). 환경변수 `YOLO_SERVER_PORT`, `YOLO_SERVER_HOST`로 오버라이드 가능 |

---

## 포트 및 충돌 방지

- 기본 포트: **5001** (JetBot 웹캠 서버 5000과 충돌하지 않도록 별도 사용).
- 다른 포트 사용: `config/server_config.yaml`의 `port` 변경 또는 실행 전 `YOLO_SERVER_PORT=5002` 등으로 지정.

---

## 추가 제안 기능 (선택)

- **GET `/analyze/image?url=...`**: 외부 이미지 URL을 직접 지정해 분석 (JetBot 이외 소스 테스트용).
- **POST `/analyze/upload`**: 클라이언트가 multipart로 이미지 파일을 올려 분석 (로컬 파일·다른 카메라 연동).
- **스트리밍 응답**: `/analyze/video/stream` 에서 SSE로 실시간 프레임별 결과 스트리밍 (구현됨).
- **썸네일/디버그 이미지**: `?draw=1` 같은 옵션으로 bbox가 그려진 이미지를 base64로 함께 반환 (디버깅·미리보기용).

필요 시 위 기능을 엔드포인트로 확장할 수 있습니다.
