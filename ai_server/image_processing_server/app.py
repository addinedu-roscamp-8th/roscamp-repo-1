"""
YOLO 영상/이미지 분석 Flask API 서버.
JetBot(라즈베리파이)에서 영상·스냅샷을 가져와 YOLO로 분석한 결과를 JSON으로 반환합니다.
"""
import json
import os
from pathlib import Path

import yaml
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

import cv2
from source_fetcher import (
    get_snapshot_image,
    get_snapshot_image_ws,
    get_video_frames,
    stream_video_frames,
    stream_video_frames_ws,
)
from yolo_analyzer import analyze_image, analyze_and_draw, get_model_info, reload_model
from arm_ros_publisher import detection_to_command, publish_arm_cmd

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "server_config.yaml"


def _server_config():
    if not CONFIG_PATH.exists():
        return {"port": 5001, "host": "0.0.0.0"}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


app = Flask(__name__)


@app.route("/")
def index():
    """API 정보 및 엔드포인트 목록."""
    return jsonify({
        "service": "yolo-analysis",
        "description": "YOLO 기반 영상/이미지 분석 API (JetBot 소스 연동)",
        "endpoints": {
            "health": "/health",
            "model_info": "GET /model_info",
            "analyze_image": "GET /analyze/image",
            "analyze_image_ws": "GET /analyze/image/ws (WebSocket 스냅샷, 동일 응답 형식)",
            "analyze_video": "GET /analyze/video",
            "analyze_video_ws": "GET /analyze/video/ws (WebSocket 영상, 동일 응답 형식)",
            "analyze_video_stream": "GET /analyze/video/stream (SSE)",
            "analyze_video_stream_ws": "GET /analyze/video/stream/ws (WebSocket+SSE, 동일 이벤트 형식)",
            "stream_preview": "GET /stream/preview (MJPEG)",
            "view": "GET /view (스트리밍 + 검출 상태 표시)",
            "reload_model": "POST /reload_model",
            "analyze_arm_cmd": "GET /analyze/arm_cmd (이미지 분석 후 ROS2 토픽 발행)",
            "analyze_arm_cmd_ws": "GET /analyze/arm_cmd/ws (WebSocket 스냅샷, 동일 응답 형식)",
            "api_docs": "GET /api_docs (API 문서 페이지)",
            "interface_spec": "See INTERFACE_SPEC.md",
        },
    })


@app.route("/api_docs")
def api_docs():
    """API 사용법, 스펙, Request/Response, 에러 메시지가 정리된 문서 페이지."""
    return render_template("api_docs.html")


@app.route("/health")
def health():
    """서버 및 YOLO 모델 로드 상태."""
    try:
        from yolo_analyzer import _ensure_model
        _ensure_model()
        model_status = "loaded"
    except Exception as e:
        model_status = f"error: {str(e)}"
    return jsonify({
        "status": "ok",
        "model": model_status,
    })


@app.route("/model_info")
def model_info():
    """
    현재 사용 중인 YOLO 모델 정보 반환.
    best.pt 사용 여부 확인: model_path, model_path_exists, load_status 를 확인하세요.
    """
    try:
        info = get_model_info()
        return jsonify(info)
    except Exception as e:
        return jsonify({
            "error": str(e),
            "model_path": None,
            "model_path_exists": False,
            "class_names": [],
            "load_status": f"error: {e!s}",
        }), 500


@app.route("/analyze/image", methods=["GET"])
def analyze_image_endpoint():
    """
    JetBot /snapshot 에서 이미지를 다운로드한 뒤 YOLO 분석 결과를 반환합니다.
    별도 요청 바디 없음. GET 호출만 하면 됩니다.
    """
    try:
        img = get_snapshot_image()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "source_fetch_failed",
            "message": str(e),
        }), 503

    try:
        detections = analyze_image(img)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "inference_failed",
            "message": str(e),
        }), 500

    return jsonify({
        "success": True,
        "source": "snapshot",
        "image_size": {"width": img.shape[1], "height": img.shape[0]},
        "detections": detections,
        "count": len(detections),
    })


@app.route("/analyze/image/ws", methods=["GET"])
def analyze_image_ws_endpoint():
    """
    WebSocket /ws/video 에서 프레임 1장 수신 후 YOLO 분석. 응답 형식은 GET /analyze/image 와 동일.
    실시간성 확보용 — 호출 URL만 /analyze/image/ws 로 변경하면 됨.
    """
    try:
        img = get_snapshot_image_ws()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "source_fetch_failed",
            "message": str(e),
        }), 503
    try:
        detections = analyze_image(img)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "inference_failed",
            "message": str(e),
        }), 500
    return jsonify({
        "success": True,
        "source": "websocket",
        "image_size": {"width": img.shape[1], "height": img.shape[0]},
        "detections": detections,
        "count": len(detections),
    })


@app.route("/analyze/video", methods=["GET"])
def analyze_video_endpoint():
    """
    JetBot /video_feed 스트림에서 프레임을 읽어 YOLO 분석 후,
    프레임별 검출 결과를 묶어 반환합니다.
    Query: num_frames (선택) — 분석할 프레임 수. 기본값은 config 기준.
    """
    num_frames = request.args.get("num_frames", type=int)

    try:
        frames = list(get_video_frames(num_frames=num_frames or None))
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "source_fetch_failed",
            "message": str(e),
        }), 503

    frame_results = []
    all_detections = []
    for i, img in enumerate(frames):
        try:
            detections = analyze_image(img)
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "inference_failed",
                "message": str(e),
                "frame_index": i,
            }), 500
        frame_results.append({
            "frame_index": i,
            "image_size": {"width": img.shape[1], "height": img.shape[0]},
            "detections": detections,
            "count": len(detections),
        })
        all_detections.extend(detections)

    return jsonify({
        "success": True,
        "source": "video_feed",
        "num_frames": len(frames),
        "frames": frame_results,
        "detections": all_detections,
        "total_detections": len(all_detections),
    })


@app.route("/analyze/video/ws", methods=["GET"])
def analyze_video_ws_endpoint():
    """
    WebSocket /ws/video 에서 프레임을 읽어 YOLO 분석. 응답 형식은 GET /analyze/video 와 동일.
    실시간성 확보용 — 호출 URL만 /analyze/video/ws 로 변경하면 됨.
    Query: num_frames (선택)
    """
    num_frames = request.args.get("num_frames", type=int)
    video_cfg = _load_jetbot_config().get("video", {}) or {}
    n = num_frames or video_cfg.get("num_frames", 5)
    timeout = video_cfg.get("timeout_seconds", 10)
    try:
        frames = list(stream_video_frames_ws(max_frames=n, timeout_sec=float(timeout)))
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "source_fetch_failed",
            "message": str(e),
        }), 503
    frame_results = []
    all_detections = []
    for i, img in enumerate(frames):
        try:
            detections = analyze_image(img)
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "inference_failed",
                "message": str(e),
                "frame_index": i,
            }), 500
        frame_results.append({
            "frame_index": i,
            "image_size": {"width": img.shape[1], "height": img.shape[0]},
            "detections": detections,
            "count": len(detections),
        })
        all_detections.extend(detections)
    return jsonify({
        "success": True,
        "source": "websocket",
        "num_frames": len(frames),
        "frames": frame_results,
        "detections": all_detections,
        "total_detections": len(all_detections),
    })


def _load_jetbot_config():
    path = Path(__file__).resolve().parent / "config" / "jetbot_config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _generate_preview_mjpeg():
    """JetBot 영상을 받아 YOLO 분석 후 bbox·검출 상태를 그려 MJPEG 스트리밍."""
    boundary = "frame"
    try:
        for img in stream_video_frames():
            try:
                annotated, detections = analyze_and_draw(img)
            except Exception:
                annotated = img
                detections = []
            _, jpeg = cv2.imencode(".jpg", annotated)
            yield b"--" + boundary.encode() + b"\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
    except Exception as e:
        # 에러 시 검은 화면 + 텍스트는 어렵으므로 스트림 종료
        pass


@app.route("/stream/preview", methods=["GET"])
def stream_preview_endpoint():
    """
    영상 스트리밍 + 프레임마다 YOLO 분석 후 bbox와
    'Detected: m1, m2' / 'No detection' 문구를 그려 MJPEG로 스트리밍.
    """
    return Response(
        stream_with_context(_generate_preview_mjpeg()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )


@app.route("/view")
def view_page():
    """스트리밍 영상 + 검출 여부를 보여주는 HTML 페이지."""
    return """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YOLO 스트리밍 · 검출 상태</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: sans-serif; margin: 16px; background: #1a1a1a; color: #eee; }
    h1 { font-size: 1.2rem; }
    .wrap { max-width: 900px; margin: 0 auto; }
    .preview { width: 100%; background: #000; border-radius: 8px; display: block; }
    .status { margin-top: 12px; padding: 12px; border-radius: 8px; font-weight: bold; }
    .status.detected { background: #0d4d0d; color: #b8ffb8; }
    .status.none { background: #4d0d0d; color: #ffb8b8; }
    .meta { margin-top: 8px; font-size: 0.9rem; color: #888; }
    a { color: #6af; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>YOLO 실시간 스트리밍 · 검출 상태</h1>
    <p class="meta">영상 위 상단에 <strong>Detected: 클래스명</strong> 또는 <strong>No detection</strong> 표시</p>
    <img class="preview" src="/stream/preview" alt="스트리밍 프리뷰">
    <p class="meta"><a href="/model_info">/model_info</a>에서 사용 중인 모델(best.pt) 경로 확인</p>
  </div>
</body>
</html>
"""


def _generate_video_stream_sse():
    """SSE: JetBot 영상 스트림에서 프레임을 읽어 YOLO 분석 후 이벤트로 전송."""
    try:
        max_frames = request.args.get("max_frames", type=int)  # None = config timeout까지
        for frame_index, img in enumerate(stream_video_frames(max_frames=max_frames)):
            try:
                detections = analyze_image(img)
            except Exception as e:
                yield f"data: {json.dumps({'error': 'inference_failed', 'message': str(e), 'frame_index': frame_index})}\n\n"
                continue
            payload = {
                "frame_index": frame_index,
                "image_size": {"width": img.shape[1], "height": img.shape[0]},
                "detections": detections,
                "count": len(detections),
            }
            yield f"data: {json.dumps(payload)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': 'source_fetch_failed', 'message': str(e)})}\n\n"


def _generate_video_stream_sse_ws():
    """SSE: WebSocket /ws/video 에서 프레임을 읽어 YOLO 분석 후 이벤트로 전송. 형식은 /analyze/video/stream 와 동일."""
    try:
        max_frames = request.args.get("max_frames", type=int)
        video_cfg = _load_jetbot_config().get("video", {}) or {}
        timeout_sec = video_cfg.get("stream_timeout_seconds", 3600)
        for frame_index, img in enumerate(
            stream_video_frames_ws(max_frames=max_frames, timeout_sec=float(timeout_sec))
        ):
            try:
                detections = analyze_image(img)
            except Exception as e:
                yield f"data: {json.dumps({'error': 'inference_failed', 'message': str(e), 'frame_index': frame_index})}\n\n"
                continue
            payload = {
                "frame_index": frame_index,
                "image_size": {"width": img.shape[1], "height": img.shape[0]},
                "detections": detections,
                "count": len(detections),
            }
            yield f"data: {json.dumps(payload)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': 'source_fetch_failed', 'message': str(e)})}\n\n"


@app.route("/analyze/video/stream", methods=["GET"])
def analyze_video_stream_endpoint():
    """
    JetBot /video_feed 스트림을 실시간으로 읽어 프레임마다 YOLO 분석 결과를
    Server-Sent Events(SSE)로 스트리밍합니다. 클라이언트는 연결을 끊으면 수신 종료.

    Query:
        max_frames (선택): 최대 전송할 프레임 수. 없으면 stream_timeout_seconds 까지 계속.
    """
    return Response(
        stream_with_context(_generate_video_stream_sse()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/analyze/video/stream/ws", methods=["GET"])
def analyze_video_stream_ws_endpoint():
    """
    WebSocket /ws/video 에서 프레임을 실시간 수신하며 YOLO 분석 결과를 SSE로 스트리밍.
    이벤트 형식은 GET /analyze/video/stream 와 동일. 실시간성 확보용.
    Query: max_frames (선택)
    """
    return Response(
        stream_with_context(_generate_video_stream_sse_ws()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/analyze/arm_cmd", methods=["GET"])
def analyze_arm_cmd_endpoint():
    """
    이미지 분석 후 결과에 따라 ROS2 토픽 발행 (ROS_DOMAIN_ID=21).
    - 샌드위치 클래스(Hamcheese, Mushroom, All-in-one) -> HANDOFF_PINKY
    - NG 클래스 -> DISCARD
    - 검출 없음 -> 발행 안 함 (또는 config에서 no_detection_command 설정 시 CANCEL 등)
    """
    try:
        img = get_snapshot_image()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "source_fetch_failed",
            "message": str(e),
            "ros_published": None,
        }), 503
    try:
        detections = analyze_image(img)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "inference_failed",
            "message": str(e),
            "ros_published": None,
        }), 500

    command_key = detection_to_command(detections)
    ros_result = None
    if command_key:
        ros_result = publish_arm_cmd(command_key)

    return jsonify({
        "success": True,
        "source": "snapshot",
        "image_size": {"width": img.shape[1], "height": img.shape[0]},
        "detections": detections,
        "count": len(detections),
        "command_key": command_key,
        "ros_published": ros_result,
    })


@app.route("/analyze/arm_cmd/ws", methods=["GET"])
def analyze_arm_cmd_ws_endpoint():
    """
    WebSocket /ws/video 에서 프레임 1장 수신 후 분석·ROS2 토픽 발행. 응답 형식은 GET /analyze/arm_cmd 와 동일.
    실시간성 확보용 — 호출 URL만 /analyze/arm_cmd/ws 로 변경하면 됨.
    """
    try:
        img = get_snapshot_image_ws()
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "source_fetch_failed",
            "message": str(e),
            "ros_published": None,
        }), 503
    try:
        detections = analyze_image(img)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "inference_failed",
            "message": str(e),
            "ros_published": None,
        }), 500
    command_key = detection_to_command(detections)
    ros_result = None
    if command_key:
        ros_result = publish_arm_cmd(command_key)
    return jsonify({
        "success": True,
        "source": "websocket",
        "image_size": {"width": img.shape[1], "height": img.shape[0]},
        "detections": detections,
        "count": len(detections),
        "command_key": command_key,
        "ros_published": ros_result,
    })


@app.route("/reload_model", methods=["POST"])
def reload_model_endpoint():
    """config 변경 후 YOLO 모델을 다시 로드합니다. 모델 교체 시 유용."""
    try:
        reload_model()
        return jsonify({"success": True, "message": "Model reloaded from config."})
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


def main():
    cfg = _server_config()
    port = int(os.environ.get("YOLO_SERVER_PORT", cfg.get("port", 5001)))
    host = os.environ.get("YOLO_SERVER_HOST", cfg.get("host", "0.0.0.0"))
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
