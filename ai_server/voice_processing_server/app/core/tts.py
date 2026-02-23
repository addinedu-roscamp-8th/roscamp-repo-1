"""
TTS: 텍스트 → 음성. OpenAI Audio API 사용.
"""
from openai import OpenAI
from app.config import get_settings
from app.core.openai_client import get_openai_client


def tts_text_to_audio(
    text: str,
    voice: str | None = None,
    model: str | None = None,
    client: OpenAI | None = None,
) -> bytes:
    """
    텍스트를 오디오 바이너리로 변환.

    Args:
        text: 변환할 텍스트
        voice: alloy, echo, fable, onyx, nova, shimmer 중 하나
        model: tts-1 또는 tts-1-hd
        client: OpenAI 클라이언트. None이면 새로 생성.

    Returns:
        오디오 바이너리 (mp3)
    """
    if client is None:
        client = get_openai_client()
    settings = get_settings()
    voice = voice or settings.tts_voice
    model = model or settings.tts_model
    resp = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
    )
    return resp.content
