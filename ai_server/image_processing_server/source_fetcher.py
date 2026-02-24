"""
JetBot 또는 로봇 팔 스트리밍 서버에서 영상/이미지를 가져오는 모듈.
config/jetbot_config.yaml 에서 base_url, endpoints, video.use_websocket(선택) 을 읽음.
"""
from pathlib import Path
import socket
import time
import urllib.parse
import yaml
import cv2
import numpy as np
import requests
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "jetbot_config.yaml"


def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _base_url_to_ws(base_url: str, path: str) -> str:
    """http(s) base_url을 ws(s) URL로 변환."""
    parsed = urllib.parse.urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc or parsed.path
    path = path if path.startswith("/") else "/" + path
    return f"{scheme}://{netloc}{path}"


def get_snapshot_image() -> np.ndarray:
    """
    JetBot /snapshot 에서 이미지 한 장을 다운로드해 OpenCV BGR 배열로 반환.

    Returns:
        np.ndarray: shape (H, W, 3), BGR. 실패 시 예외.
    """
    cfg = _load_config()
    base = cfg["base_url"].rstrip("/")
    url = base + cfg["endpoints"]["snapshot"]
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    arr = np.frombuffer(resp.content, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode snapshot image")
    return img


def get_snapshot_image_ws(timeout_sec: float = 10.0) -> np.ndarray:
    """
    WebSocket /ws/video 에서 프레임 1장을 수신해 OpenCV BGR 배열로 반환.
    실시간성 확보용. (기존 get_snapshot_image 와 동일한 반환 형식)

    Returns:
        np.ndarray: shape (H, W, 3), BGR. 실패 시 예외.
    """
    try:
        import websocket
    except ImportError:
        raise ImportError("WebSocket 사용 시 websocket-client 가 필요합니다: pip install websocket-client")

    cfg = _load_config()
    base = cfg["base_url"].rstrip("/")
    video_cfg = cfg.get("video", {})
    path = video_cfg.get("ws_video_path", "/ws/video")
    ws_url = _base_url_to_ws(base, path)
    ws = websocket.create_connection(ws_url, timeout=min(15, int(timeout_sec)))
    try:
        ws.sock.settimeout(timeout_sec)
        data = ws.recv()
        if not data:
            raise ValueError("Empty frame from WebSocket")
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode WebSocket frame as image")
        return img
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _get_video_frames_http(
    num_frames: int,
    interval_sec: float,
    timeout: int,
):
    """HTTP MJPEG /video_feed 에서 num_frames개 프레임 yield. (내부용)"""
    cfg = _load_config()
    base = cfg["base_url"].rstrip("/")
    url = base + cfg["endpoints"]["video_feed"]
    stream = requests.get(url, stream=True, timeout=timeout)
    stream.raise_for_status()
    bytes_buf = b""
    frame_count = 0
    deadline = time.monotonic() + timeout
    for chunk in stream.iter_content(chunk_size=8192):
        if time.monotonic() > deadline:
            break
        bytes_buf += chunk
        a = bytes_buf.find(b"\xff\xd8")
        b = bytes_buf.find(b"\xff\xd9", a)
        if a != -1 and b != -1:
            jpg = bytes_buf[a : b + 2]
            bytes_buf = bytes_buf[b + 2 :]
            arr = np.frombuffer(jpg, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                frame_count += 1
                yield img
                if frame_count >= num_frames:
                    return
            time.sleep(interval_sec)
    if frame_count == 0:
        raise ValueError("Could not read any frame from video stream")


def stream_video_frames_ws(
    max_frames: int | None = None,
    timeout_sec: float | None = None,
):
    """
    WebSocket /ws/video 에서 JPEG 프레임을 수신해 BGR 이미지로 yield.
    config base_url, video.ws_video_path 사용. use_websocket 이 True일 때만 호출 권장.

    Args:
        max_frames: 최대 프레임 수. None 이면 timeout_sec 까지 계속.
        timeout_sec: 수신 타임아웃(초). None 이면 config video.stream_timeout_seconds 또는 3600.

    Yields:
        np.ndarray: BGR 이미지 (H, W, 3).
    """
    try:
        import websocket
    except ImportError:
        raise ImportError("WebSocket 사용 시 websocket-client 가 필요합니다: pip install websocket-client")

    cfg = _load_config()
    base = cfg["base_url"].rstrip("/")
    video_cfg = cfg.get("video", {})
    if timeout_sec is None:
        timeout_sec = video_cfg.get("stream_timeout_seconds", 3600)
    path = video_cfg.get("ws_video_path", "/ws/video")
    ws_url = _base_url_to_ws(base, path)
    recv_timeout = 1.0
    deadline = time.monotonic() + timeout_sec
    frame_count = 0

    ws = websocket.create_connection(ws_url, timeout=min(15, int(timeout_sec)))
    try:
        ws.sock.settimeout(recv_timeout)
        while time.monotonic() < deadline:
            if max_frames is not None and frame_count >= max_frames:
                break
            try:
                data = ws.recv()
            except socket.timeout:
                continue
            if not data:
                continue
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                frame_count += 1
                yield img
    finally:
        try:
            ws.close()
        except Exception:
            pass

    if frame_count == 0:
        raise ValueError("Could not read any frame from WebSocket video stream")


def get_video_frames(num_frames: int | None = None, interval_sec: float | None = None):
    """
    소스(/video_feed MJPEG 또는 WebSocket /ws/video)에서 프레임을 읽어 yield.
    config video.use_websocket 에 따라 HTTP 또는 WebSocket 사용.

    Args:
        num_frames: 가져올 프레임 수. None 이면 config video.num_frames 사용.
        interval_sec: (HTTP만) 프레임 간 간격(초). None 이면 config 기준.

    Yields:
        np.ndarray: BGR 이미지 (H, W, 3). 실패 시 예외.
    """
    cfg = _load_config()
    video_cfg = cfg.get("video", {})
    timeout = video_cfg.get("timeout_seconds", 10)
    if num_frames is None:
        num_frames = video_cfg.get("num_frames", 5)
    if interval_sec is None:
        interval_sec = video_cfg.get("frame_interval_ms", 200) / 1000.0

    if video_cfg.get("use_websocket"):
        # WebSocket: num_frames만큼 수신
        count = 0
        for img in stream_video_frames_ws(max_frames=num_frames, timeout_sec=float(timeout)):
            count += 1
            yield img
            if count >= num_frames:
                return
        if count == 0:
            raise ValueError("Could not read any frame from WebSocket video stream")
        return

    yield from _get_video_frames_http(num_frames, interval_sec, timeout)


def _stream_video_frames_http(
    max_frames: int | None,
    timeout_sec: float,
    interval_sec: float,
):
    """HTTP MJPEG /video_feed 연속 읽기. (내부용)"""
    cfg = _load_config()
    base = cfg["base_url"].rstrip("/")
    url = base + cfg["endpoints"]["video_feed"]
    stream = requests.get(url, stream=True, timeout=15)
    stream.raise_for_status()
    bytes_buf = b""
    frame_count = 0
    deadline = time.monotonic() + timeout_sec
    for chunk in stream.iter_content(chunk_size=8192):
        if time.monotonic() > deadline:
            break
        if max_frames is not None and frame_count >= max_frames:
            break
        bytes_buf += chunk
        a = bytes_buf.find(b"\xff\xd8")
        b = bytes_buf.find(b"\xff\xd9", a)
        if a != -1 and b != -1:
            jpg = bytes_buf[a : b + 2]
            bytes_buf = bytes_buf[b + 2 :]
            arr = np.frombuffer(jpg, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                frame_count += 1
                yield img
            time.sleep(interval_sec)
    if frame_count == 0:
        raise ValueError("Could not read any frame from video stream")


def stream_video_frames(
    max_frames: int | None = None,
    timeout_sec: float | None = None,
    interval_sec: float | None = None,
):
    """
    소스(/video_feed MJPEG 또는 WebSocket /ws/video)를 연속으로 읽어 프레임을 yield.
    config video.use_websocket 에 따라 HTTP 또는 WebSocket 사용.
    SSE 실시간 스트리밍용 (제한 없이 또는 max_frames/timeout 까지).

    Args:
        max_frames: 최대 프레임 수. None 이면 timeout_sec 까지 계속.
        timeout_sec: 스트림 읽기 타임아웃(초). None 이면 config video.stream_timeout_seconds 또는 3600.
        interval_sec: (HTTP만) 프레임 간 간격(초). None 이면 config 기준.

    Yields:
        np.ndarray: BGR 이미지 (H, W, 3).
    """
    cfg = _load_config()
    video_cfg = cfg.get("video", {})
    if timeout_sec is None:
        timeout_sec = video_cfg.get("stream_timeout_seconds", 3600)
    if interval_sec is None:
        interval_sec = video_cfg.get("frame_interval_ms", 200) / 1000.0

    if video_cfg.get("use_websocket"):
        yield from stream_video_frames_ws(max_frames=max_frames, timeout_sec=timeout_sec)
    else:
        yield from _stream_video_frames_http(max_frames, timeout_sec, interval_sec)
