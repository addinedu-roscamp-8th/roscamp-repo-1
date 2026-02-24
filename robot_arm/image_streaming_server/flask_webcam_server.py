#!/usr/bin/env python3
"""
Flask 웹캠 서버 - 라즈베리 파이용
- 영상(MJPEG) 송출: 공유 JPEG 버퍼 1개로 프레임당 인코딩 1회
- WebSocket /ws/video 로 브라우저 푸시 스트리밍
- 호출 시점의 프레임을 이미지로 다운로드 (AI 서버 분석용)
"""
import io
import threading
import time
from pathlib import Path
from flask import Flask, Response, send_file, send_from_directory

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from flask_sock import Sock
except ImportError:
    Sock = None

# --------------- 설정 ---------------
# 카메라
CAMERA_DEVICE = "/dev/jetcocam0"

# 스트리밍: 분석에 용이한 수준 유지, Pi 부하 완화
DEFAULT_FPS = 10
STREAM_MAX_WIDTH = 640          # 스트림 해상도 (가로, 0이면 리사이즈 없음)
STREAM_JPEG_QUALITY = 82        # 스트림 JPEG 품질 (0-100, 분석 용이 수준)
SNAPSHOT_JPEG_QUALITY = 85     # 스냅샷 품질 (분석용)

# 카메라 재연결
CAMERA_READ_FAIL_MAX = 30       # 연속 실패 시 재연결 (약 3초)
CAMERA_REOPEN_DELAY = 2.0      # 재연결 전 대기(초)

app = Flask(__name__)
sock = Sock(app) if Sock else None

# 전역: 최신 raw 프레임 (카메라 스레드)
_frame_lock = threading.Lock()
_latest_frame = None
_cap = None
_camera_ok = False

# 전역: 공유 JPEG 버퍼 (인코더 스레드 1개만 쓰기, 스트리밍은 읽기만)
_jpeg_lock = threading.Lock()
_latest_jpeg_bytes = None
_jpeg_ready = threading.Event()  # 첫 프레임 준비 알림


def _camera_loop():
    """백그라운드에서 카메라 프레임을 읽어 _latest_frame 갱신. 실패 시 재연결."""
    global _cap, _latest_frame, _camera_ok
    fail_count = 0

    while True:
        _cap = cv2.VideoCapture(CAMERA_DEVICE)
        if not _cap.isOpened():
            _camera_ok = False
            time.sleep(CAMERA_REOPEN_DELAY)
            continue

        _camera_ok = True
        fail_count = 0

        while _cap is not None and _cap.isOpened():
            ret, frame = _cap.read()
            if not ret:
                fail_count += 1
                if fail_count >= CAMERA_READ_FAIL_MAX:
                    break  # 재연결
                time.sleep(0.1)
                continue
            fail_count = 0
            with _frame_lock:
                _latest_frame = frame.copy()
            time.sleep(1.0 / 30)  # 최대 30fps로 읽기

        if _cap:
            _cap.release()
            _cap = None
        _camera_ok = False
        time.sleep(CAMERA_REOPEN_DELAY)


def _resize_for_stream(frame):
    """스트림용 해상도 조정 (분석 용이 수준 유지)."""
    if STREAM_MAX_WIDTH <= 0 or frame is None:
        return frame
    h, w = frame.shape[:2]
    if w <= STREAM_MAX_WIDTH:
        return frame
    r = STREAM_MAX_WIDTH / w
    new_w = STREAM_MAX_WIDTH
    new_h = int(h * r)
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _encoder_loop():
    """최신 프레임을 JPEG로 인코딩해 _latest_jpeg_bytes 에만 씀 (프레임당 1회)."""
    global _latest_jpeg_bytes
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY]

    while True:
        with _frame_lock:
            frame = _latest_frame.copy() if _latest_frame is not None else None
        if frame is None:
            time.sleep(0.1)
            continue

        frame = _resize_for_stream(frame)
        _, jpeg = cv2.imencode(".jpg", frame, encode_params)
        jpeg_bytes = jpeg.tobytes()

        with _jpeg_lock:
            _latest_jpeg_bytes = jpeg_bytes
        _jpeg_ready.set()

        time.sleep(1.0 / DEFAULT_FPS)


def _get_latest_frame():
    """스레드 세이프하게 최신 프레임 복사본 반환 (None 가능)."""
    with _frame_lock:
        if _latest_frame is None:
            return None
        return _latest_frame.copy()


def _get_latest_jpeg():
    """스레드 세이프하게 최신 JPEG 바이트 복사본 반환 (None 가능)."""
    with _jpeg_lock:
        if _latest_jpeg_bytes is None:
            return None
        return _latest_jpeg_bytes  # bytes는 immutable이라 복사 불필요


# --------------- API ---------------

@app.route("/")
def index():
    """서버 및 카메라 상태 안내."""
    endpoints = {
        "video": "/video_feed",
        "snapshot": "/snapshot",
        "health": "/health",
    }
    if sock:
        endpoints["ws_video"] = "/ws/video"
        endpoints["test_page"] = "/test"
    return {
        "service": "webcam",
        "endpoints": endpoints,
    }, 200


@app.route("/test")
def test_page():
    """WebSocket 영상 테스트용 HTML (정적 파일)."""
    static_dir = Path(__file__).resolve().parent / "static"
    return send_from_directory(static_dir, "ws_video_test.html")


@app.route("/health")
def health():
    """헬스체크: 서버/카메라 동작 여부 (AI 서버에서 호출 가능)."""
    return {
        "ok": True,
        "camera_ready": _camera_ok,
        "device": CAMERA_DEVICE,
    }, 200


@app.route("/video_feed")
def video_feed():
    """영상 송출 (MJPEG 스트림). 공유 JPEG 버퍼만 읽어 전달."""
    def generate():
        _jpeg_ready.wait(timeout=5.0)  # 최대 5초 대기
        try:
            while True:
                jpeg = _get_latest_jpeg()
                if jpeg is None:
                    time.sleep(0.05)
                    continue
                chunk = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                )
                yield chunk
                time.sleep(1.0 / DEFAULT_FPS)
        except GeneratorExit:
            pass  # 클라이언트 끊김 시 서버가 next() 중단 → 정상 종료

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/snapshot")
def snapshot():
    """호출 시점의 이미지를 JPEG로 다운로드 (AI 서버에서 분석용)."""
    frame = _get_latest_frame()
    if frame is None:
        return {"error": "No frame available", "camera_ready": _camera_ok}, 503
    _, jpeg = cv2.imencode(
        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_JPEG_QUALITY]
    )
    buf = io.BytesIO(jpeg.tobytes())
    return send_file(
        buf,
        mimetype="image/jpeg",
        as_attachment=True,
        download_name="snapshot.jpg",
    )


@app.route("/snapshot/inline")
def snapshot_inline():
    """호출 시점의 이미지를 JPEG로 반환 (브라우저에서 바로 보기)."""
    frame = _get_latest_frame()
    if frame is None:
        return {"error": "No frame available", "camera_ready": _camera_ok}, 503
    _, jpeg = cv2.imencode(
        ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_JPEG_QUALITY]
    )
    return Response(jpeg.tobytes(), mimetype="image/jpeg")


# --------------- WebSocket ---------------

if sock is not None:

    @sock.route("/ws/video")
    def ws_video(ws):
        """WebSocket으로 JPEG 프레임 푸시 (브라우저용)."""
        _jpeg_ready.wait(timeout=5.0)
        try:
            while True:
                jpeg = _get_latest_jpeg()
                if jpeg is not None:
                    ws.send(jpeg)
                time.sleep(1.0 / DEFAULT_FPS)
        except Exception:
            pass  # 클라이언트 끊김 등
        finally:
            try:
                ws.close()
            except Exception:
                pass


def main():
    if cv2 is None:
        raise RuntimeError("opencv-python(cv2)이 필요합니다: pip install opencv-python-headless")
    if Sock is None:
        raise RuntimeError("flask-sock이 필요합니다: pip install flask-sock")

    # 카메라 스레드
    t_cam = threading.Thread(target=_camera_loop, daemon=True)
    t_cam.start()
    time.sleep(1.0)

    # 인코더 스레드 (공유 JPEG 버퍼 갱신)
    t_enc = threading.Thread(target=_encoder_loop, daemon=True)
    t_enc.start()

    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)


if __name__ == "__main__":
    main()
