from openai import RateLimitError
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from app.core.tts import tts_text_to_audio

router = APIRouter(prefix="/tts", tags=["TTS"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description="변환할 텍스트")
    voice: str | None = Field(default=None, description="alloy, echo, fable, onyx, nova, shimmer")
    model: str | None = Field(default=None, description="tts-1 또는 tts-1-hd")


@router.post(
    "/",
    response_class=Response,
    summary="Text-to-Speech",
    description="텍스트를 음성(MP3)으로 변환합니다. OpenAI Audio API 사용.",
    responses={200: {"content": {"audio/mpeg": {}}, "description": "MP3 오디오 바이너리"}},
)
async def post_tts(body: TTSRequest) -> Response:
    try:
        audio_bytes = tts_text_to_audio(text=body.text, voice=body.voice, model=body.model)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="OpenAI API rate limit exceeded (429). Please try again in a moment.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/json",
    summary="Text-to-Speech (JSON)",
    description="텍스트를 음성으로 변환하고 base64 인코딩된 오디오를 JSON으로 반환.",
)
async def post_tts_json(body: TTSRequest) -> dict:
    import base64
    try:
        audio_bytes = tts_text_to_audio(text=body.text, voice=body.voice, model=body.model)
        return {"audio_base64": base64.b64encode(audio_bytes).decode("ascii"), "media_type": "audio/mpeg"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="OpenAI API rate limit exceeded (429). Please try again in a moment.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
