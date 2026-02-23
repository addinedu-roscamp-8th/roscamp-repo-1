from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from app.pipeline.voice_pipeline import run_voice_pipeline

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


class PipelineOptions(BaseModel):
    run_wakeword: bool = True
    run_function_on_wake: bool = True
    tts_reply: bool = True
    use_llm_wakeword: bool = True


@router.post(
    "/run",
    summary="Voice pipeline 실행",
    description="오디오 → STT → 웨이크업 판별 → (웨이크 시 펑션 콜) → TTS 응답. 결과에 stt_text, wake, function_result, tts_audio_base64, reply_text 포함.",
)
async def post_pipeline_run(
    file: UploadFile = File(..., description="오디오 파일"),
    run_wakeword: bool = True,
    run_function_on_wake: bool = True,
    tts_reply: bool = True,
    use_llm_wakeword: bool = True,
) -> dict:
    try:
        content = await file.read()
        filename = file.filename or "audio.webm"
        result = run_voice_pipeline(
            content,
            filename=filename,
            run_wakeword=run_wakeword,
            run_function_on_wake=run_function_on_wake,
            tts_reply=tts_reply,
            use_llm_wakeword=use_llm_wakeword,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
