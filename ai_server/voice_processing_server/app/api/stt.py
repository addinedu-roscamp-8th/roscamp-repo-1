from openai import RateLimitError
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from app.core.stt import stt_audio_to_text

router = APIRouter(prefix="/stt", tags=["STT"])


class STTResponse(BaseModel):
    text: str


@router.post(
    "/",
    response_model=STTResponse,
    summary="Speech-to-Text",
    description="오디오 파일을 텍스트로 변환합니다. OpenAI Whisper API 사용.",
)
async def post_stt(
    file: UploadFile = File(..., description="오디오 파일 (webm, mp3, wav 등)"),
) -> STTResponse:
    try:
        content = await file.read()
        filename = file.filename or "audio.webm"
        text = stt_audio_to_text(content, filename=filename)
        return STTResponse(text=text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="OpenAI API rate limit exceeded (429). Please try again in a moment.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
