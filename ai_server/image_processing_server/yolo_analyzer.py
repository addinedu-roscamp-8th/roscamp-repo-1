"""
YOLO 분석 모듈.
설정(config/yolo_config.yaml)에서 모델 경로와 클래스명을 읽어 추론하며,
모델 교체 시 설정만 변경하면 됨.
"""
from pathlib import Path
import math
import yaml
from ultralytics import YOLO
import numpy as np
import cv2

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "yolo_config.yaml"


def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_model_path(cfg_path: str) -> str:
    """설정에 적힌 model_path를 절대 경로로 반환."""
    p = Path(cfg_path)
    if not p.is_absolute():
        p = ROOT / p
    return str(p.resolve())


def get_model_and_classes():
    """설정에서 모델과 클래스 목록 로드. 모델 교체 시 이 함수가 새 설정을 반영함."""
    cfg = _load_config()
    model_path = _resolve_model_path(cfg["model_path"])
    model = YOLO(model_path)
    class_names = list(cfg["class_names"])
    return model, class_names, cfg.get("inference", {})


def get_model_info() -> dict:
    """
    현재 설정 기준 모델 경로·파일 존재 여부·클래스 목록을 반환.
    best.pt 사용 여부 확인용.
    """
    cfg = _load_config()
    model_path = _resolve_model_path(cfg["model_path"])
    path_exists = Path(model_path).is_file()
    class_names = list(cfg["class_names"])
    load_status = "not_loaded"
    if _model is not None:
        load_status = "loaded"
    elif path_exists:
        try:
            _ensure_model()
            load_status = "loaded"
        except Exception as e:
            load_status = f"load_error: {e!s}"
    else:
        load_status = "file_not_found"
    return {
        "model_path": model_path,
        "model_path_exists": path_exists,
        "class_names": class_names,
        "load_status": load_status,
    }


# 싱글톤: 앱 구동 시 한 번만 로드
_model = None
_class_names = None
_inference_opts = None


def _ensure_model():
    global _model, _class_names, _inference_opts
    if _model is None:
        _model, _class_names, _inference_opts = get_model_and_classes()
    return _model, _class_names, _inference_opts


def reload_model():
    """설정 변경 후 모델을 다시 로드할 때 호출."""
    global _model, _class_names, _inference_opts
    _model, _class_names, _inference_opts = get_model_and_classes()
    return _model, _class_names, _inference_opts


def analyze_image(image: np.ndarray) -> list[dict]:
    """
    단일 이미지(프레임)에 대해 YOLO 추론 후 검출 목록 반환.

    Args:
        image: BGR numpy array (OpenCV 형식), shape (H, W, 3)

    Returns:
        [
            {
                "class_id": int,
                "class_name": str,
                "confidence": float,
                "bbox": [x1, y1, x2, y2]  # 픽셀 좌표
            },
            ...
        ]
    """
    model, class_names, opts = _ensure_model()
    conf = opts.get("conf_threshold", 0.25)
    iou = opts.get("iou_threshold", 0.45)
    stream = opts.get("stream", True)

    results = model(image, stream=stream, conf=conf, iou=iou, verbose=False)
    detections = []

    for r in results:
        if r.boxes is None:
            continue
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            confidence = float(math.ceil(box.conf[0].item() * 100) / 100)
            cls = int(box.cls[0].item())
            name = class_names[cls] if 0 <= cls < len(class_names) else f"class_{cls}"
            detections.append({
                "class_id": cls,
                "class_name": name,
                "confidence": confidence,
                "bbox": [x1, y1, x2, y2],
            })

    return detections


def analyze_and_draw(image: np.ndarray) -> tuple[np.ndarray, list[dict]]:
    """
    이미지에 대해 YOLO 추론 후, bbox와 검출 상태 문구를 그린 이미지와 검출 목록을 반환.
    스트리밍 프리뷰용.
    """
    detections = analyze_image(image)
    img = image.copy()
    # bbox 그리기 (opencv_yolov8.py 와 동일 스타일)
    for d in detections:
        x1, y1, x2, y2 = d["bbox"]
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
        cv2.putText(
            img, d["class_name"], (x1, y1),
            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2,
        )
    # 상단에 검출 여부 문구
    if detections:
        labels = sorted(set(d["class_name"] for d in detections))
        status_text = "Detected: " + ", ".join(labels)
        bg_color = (0, 200, 0)  # 녹색
    else:
        status_text = "No detection"
        bg_color = (0, 0, 200)  # 빨간색
    (tw, th), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 2)
    cv2.rectangle(img, (0, 0), (tw + 20, th + 30), bg_color, -1)
    cv2.putText(img, status_text, (10, th + 20), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    return img, detections
