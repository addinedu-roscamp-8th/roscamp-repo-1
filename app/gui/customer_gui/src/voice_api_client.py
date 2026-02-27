"""
Voice 처리 서버 HTTP API 클라이언트
STT, 웨이크업(agent/voice), order_turn, TTS 호출.
"""
import sys
import os
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config

# 요청 타임아웃 (초)
DEFAULT_TIMEOUT = 30
STT_TTS_TIMEOUT = 60


def _base():
    return Config.VOICE_SERVER_URL


def _headers():
    return {"Accept": "application/json"}


def stt(audio_bytes: bytes, filename: str = "audio.webm") -> tuple[str | None, str | None]:
    """
    POST /stt/ - 오디오를 텍스트로 변환합니다.
    Returns: (text, error_message). 성공 시 error_message는 None.
    """
    url = f"{_base()}/stt/"
    try:
        r = requests.post(
            url,
            files={"file": (filename, audio_bytes)},
            timeout=STT_TTS_TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("text", ""), None
    except requests.exceptions.RequestException as e:
        err = getattr(e, "response", None)
        if err is not None and hasattr(err, "text"):
            try:
                detail = err.json().get("detail", err.text)
            except Exception:
                detail = err.text
        else:
            detail = str(e)
        return None, detail


def agent_voice(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    run_wakeword: bool = True,
    run_function_on_wake: bool = True,
    tts_reply: bool = True,
) -> tuple[dict | None, str | None]:
    """
    POST /agent/voice - 오디오 1회 처리: STT → 웨이크업 → (웨이크 시 function) → TTS
    Returns: (result_dict, error_message). result에 stt_text, wake, reply_text, tts_audio_base64 등 포함.
    """
    url = f"{_base()}/agent/voice"
    try:
        r = requests.post(
            url,
            files={"file": (filename, audio_bytes)},
            data={
                "run_wakeword": run_wakeword,
                "run_function_on_wake": run_function_on_wake,
                "tts_reply": tts_reply,
            },
            timeout=STT_TTS_TIMEOUT,
        )
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.RequestException as e:
        err = getattr(e, "response", None)
        if err is not None and hasattr(err, "text"):
            try:
                detail = err.json().get("detail", err.text)
            except Exception:
                detail = err.text
        else:
            detail = str(e)
        return None, detail


def order_turn(
    session_id: str,
    text: str,
    table_number: int | None = None,
) -> tuple[dict | None, str | None]:
    """
    POST /agent/order_turn - 음성 주문 1턴을 처리합니다.
    Returns: ({"reply_text": str, "state": dict}, error_message).
    """
    url = f"{_base()}/agent/order_turn"
    payload = {"session_id": session_id, "text": text}
    if table_number is not None:
        payload["table_number"] = table_number
    try:
        r = requests.post(url, json=payload, headers=_headers(), timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.RequestException as e:
        err = getattr(e, "response", None)
        if err is not None and hasattr(err, "text"):
            try:
                detail = err.json().get("detail", err.text)
            except Exception:
                detail = err.text
        else:
            detail = str(e)
        return None, detail


def tts_json(text: str, voice: str | None = None) -> tuple[dict | None, str | None]:
    """
    POST /tts/json - 텍스트를 base64 오디오로 변환합니다.
    Returns: ({"audio_base64": str, "media_type": str}, error_message).
    """
    url = f"{_base()}/tts/json"
    body = {"text": text}
    if voice:
        body["voice"] = voice
    try:
        r = requests.post(url, json=body, headers=_headers(), timeout=STT_TTS_TIMEOUT)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.RequestException as e:
        err = getattr(e, "response", None)
        if err is not None and hasattr(err, "text"):
            try:
                detail = err.json().get("detail", err.text)
            except Exception:
                detail = err.text
        else:
            detail = str(e)
        return None, detail
