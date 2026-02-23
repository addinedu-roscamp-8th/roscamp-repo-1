"""
Agent 진입점: 단일 오디오/텍스트 입력에 대해 파이프라인(STT→웨이크업→펑션콜→TTS) 실행.
"""
from typing import Any
from app.pipeline.voice_pipeline import run_voice_pipeline


def run_agent_turn(
    audio_bytes: bytes | None = None,
    text_input: str | None = None,
    filename: str = "audio.webm",
    *,
    run_wakeword: bool = True,
    run_function_on_wake: bool = True,
    tts_reply: bool = True,
) -> dict[str, Any]:
    """
    Agent 1턴: 음성(또는 텍스트) 입력 → 파이프라인 실행 → 응답.

    - audio_bytes 가 있으면 STT 후 파이프라인 진행.
    - text_input 만 있으면 STT 생략하고 해당 텍스트로 웨이크업·펑션·응답 생성.
    """
    if audio_bytes:
        return run_voice_pipeline(
            audio_bytes,
            filename=filename,
            run_wakeword=run_wakeword,
            run_function_on_wake=run_function_on_wake,
            tts_reply=tts_reply,
        )
    if text_input:
        # 텍스트만 있는 경우: 웨이크업 체크 후 펑션/응답
        from app.core.wakeword import check_wakeword_text
        from app.core.function_calling import run_test_function
        import base64
        from app.core.tts import tts_text_to_audio

        result = {
            "success": True,
            "stt_text": text_input,
            "wake": None,
            "function_called": False,
            "function_result": None,
            "tts_audio_base64": None,
            "reply_text": None,
            "error": None,
        }
        wake = check_wakeword_text(text_input, use_llm=True)
        result["wake"] = wake
        if wake.get("is_wake"):
            fc = run_test_function("test_voice_order", arguments={"source": "agent", "text": text_input})
            result["function_called"] = True
            result["function_result"] = fc
            result["reply_text"] = "주문 모드를 시작했습니다. 무엇을 도와드릴까요?"
        else:
            result["reply_text"] = "네, 말씀하세요."
        if result["reply_text"]:
            audio_out = tts_text_to_audio(result["reply_text"])
            result["tts_audio_base64"] = base64.b64encode(audio_out).decode("ascii")
        return result
    return {
        "success": False,
        "stt_text": "",
        "wake": None,
        "function_called": False,
        "function_result": None,
        "tts_audio_base64": None,
        "reply_text": None,
        "error": "Provide audio_bytes or text_input",
    }
