"""
STT: 음성(오디오) → 텍스트. OpenAI Whisper API 사용.
"""
import io
from openai import OpenAI
from app.config import get_settings
from app.core.openai_client import get_openai_client


def stt_audio_to_text(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    client: OpenAI | None = None,
) -> str:
    """
    오디오 바이너리를 텍스트로 변환.

    Args:
        audio_bytes: 오디오 파일 바이트 (webm, mp3, wav 등)
        filename: 확장자 힌트용 파일명
        client: OpenAI 클라이언트. None이면 새로 생성.

    Returns:
        인식된 텍스트
    """
    if client is None:
        client = get_openai_client()
    settings = get_settings()
    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = filename
    resp = client.audio.transcriptions.create(
        model=settings.whisper_model,
        file=file_obj,
    )
    return (resp.text or "").strip()
