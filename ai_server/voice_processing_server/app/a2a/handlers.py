"""
A2A(Agent-to-Agent): 다른 에이전트/시스템이 호출하는 진입점.
동일 파이프라인을 호출하되, 호출 주체·메타데이터를 받아 로그/추적 가능하게 함.
"""
from typing import Any
from app.agent.voice_agent import run_agent_turn


def handle_a2a_voice_request(
    audio_bytes: bytes | None = None,
    text_input: str | None = None,
    filename: str = "audio.webm",
    *,
    caller_id: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_wakeword: bool = True,
    run_function_on_wake: bool = True,
    tts_reply: bool = True,
) -> dict[str, Any]:
    """
    A2A 요청 처리: Agent와 동일 파이프라인 실행 + caller_id, request_id 등 부가 정보 보존.
    """
    result = run_agent_turn(
        audio_bytes=audio_bytes,
        text_input=text_input,
        filename=filename,
        run_wakeword=run_wakeword,
        run_function_on_wake=run_function_on_wake,
        tts_reply=tts_reply,
    )
    result["a2a"] = {
        "caller_id": caller_id,
        "request_id": request_id,
        "metadata": metadata or {},
    }
    return result
