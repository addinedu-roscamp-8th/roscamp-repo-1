"""
JetBot 라즈베리파이에서 영상/이미지를 가져오는 모듈.
config/jetbot_config.yaml 에서 base_url 과 endpoints 를 읽음.
"""
from pathlib import Path
import time
import yaml
import cv2
import numpy as np
import requests
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "jetbot_config.yaml"


def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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


def get_video_frames(num_frames: int | None = None, interval_sec: float | None = None):
    """
    JetBot /video_feed MJPEG 스트림에서 프레임을 읽어 yield.

    Args:
        num_frames: 가져올 프레임 수. None 이면 config video.num_frames 사용.
        interval_sec: 프레임 간 간격(초). None 이면 config video.frame_interval_ms 기반.

    Yields:
        np.ndarray: BGR 이미지 (H, W, 3). 실패 시 예외.
    """
    cfg = _load_config()
    base = cfg["base_url"].rstrip("/")
    url = base + cfg["endpoints"]["video_feed"]
    video_cfg = cfg.get("video", {})
    timeout = video_cfg.get("timeout_seconds", 10)
    if num_frames is None:
        num_frames = video_cfg.get("num_frames", 5)
    if interval_sec is None:
        interval_sec = video_cfg.get("frame_interval_ms", 200) / 1000.0

    stream = requests.get(url, stream=True, timeout=timeout)
    stream.raise_for_status()

    bytes_buf = b""
    frame_count = 0
    deadline = time.monotonic() + timeout

    for chunk in stream.iter_content(chunk_size=8192):
        if time.monotonic() > deadline:
            break
        bytes_buf += chunk
        # MJPEG: JPEG 프레임은 0xff 0xd8 ... 0xff 0xd9 로 구분
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
                    break
            time.sleep(interval_sec)

    if frame_count == 0:
        raise ValueError("Could not read any frame from video stream")


def stream_video_frames(
    max_frames: int | None = None,
    timeout_sec: float | None = None,
    interval_sec: float | None = None,
):
    """
    JetBot /video_feed MJPEG 스트림을 연속으로 읽어 프레임을 yield.
    SSE 실시간 스트리밍용 (제한 없이 또는 max_frames/timeout 까지).

    Args:
        max_frames: 최대 프레임 수. None 이면 timeout_sec 까지 계속.
        timeout_sec: 스트림 읽기 타임아웃(초). None 이면 config video.stream_timeout_seconds 또는 3600.
        interval_sec: 프레임 간 간격(초). None 이면 config 기준.

    Yields:
        np.ndarray: BGR 이미지 (H, W, 3).
    """
    cfg = _load_config()
    base = cfg["base_url"].rstrip("/")
    url = base + cfg["endpoints"]["video_feed"]
    video_cfg = cfg.get("video", {})
    if timeout_sec is None:
        timeout_sec = video_cfg.get("stream_timeout_seconds", 3600)
    if interval_sec is None:
        interval_sec = video_cfg.get("frame_interval_ms", 200) / 1000.0

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
