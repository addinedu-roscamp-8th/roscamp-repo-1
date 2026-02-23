"""
파이프라인: 오디오 입력 → STT → 웨이크업 판별 → (선택) 펑션 콜링 → TTS 응답.
"""
import base64
import logging
from typing import Any
from app.core.stt import stt_audio_to_text
from app.core.tts import tts_text_to_audio
from app.core.wakeword import check_wakeword_text, INTENT_ORDER_START
from app.core.function_calling import run_test_function

logger = logging.getLogger(__name__)


def run_voice_pipeline(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    *,
    run_wakeword: bool = True,
    run_function_on_wake: bool = True,
    tts_reply: bool = True,
    use_llm_wakeword: bool = True,
) -> dict[str, Any]:
    """
    단일 오디오 입력에 대해 STT → 웨이크업 → (웨이크 시 펑션 콜) → (선택) TTS 응답.

    Returns:
        success, stt_text, wake, function_called, function_result, tts_audio_base64, reply_text, error
    """
    result: dict[str, Any] = {
        "success": True,
        "stt_text": "",
        "wake": None,
        "function_called": False,
        "function_result": None,
        "tts_audio_base64": None,
        "reply_text": None,
        "error": None,
    }

    try:
        # 1) STT
        text = stt_audio_to_text(audio_bytes, filename=filename)
        result["stt_text"] = text

        # 2) Wake word
        if run_wakeword:
            wake = check_wakeword_text(text, use_llm=use_llm_wakeword)
            result["wake"] = wake
            if wake.get("is_wake") and run_function_on_wake:
                # 3) Function calling (테스트 함수)
                fc = run_test_function("test_voice_order", arguments={"source": "pipeline", "stt_text": text})
                result["function_called"] = True
                result["function_result"] = fc
                reply = "주문 모드를 시작했습니다. 무엇을 도와드릴까요?"
            else:
                reply = "네, 말씀하세요." if text else "음성이 인식되지 않았습니다."
        else:
            reply = "처리되었습니다." if text else ""

        result["reply_text"] = reply

        # 4) TTS (선택)
        if tts_reply and reply:
            audio_out = tts_text_to_audio(reply)
            result["tts_audio_base64"] = base64.b64encode(audio_out).decode("ascii")

    except Exception as e:
        logger.exception("Voice pipeline error: %s", e)
        result["success"] = False
        result["error"] = str(e)

    return result
