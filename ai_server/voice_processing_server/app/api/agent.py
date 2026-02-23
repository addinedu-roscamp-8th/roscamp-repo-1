from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from app.agent.voice_agent import run_agent_turn

router = APIRouter(prefix="/agent", tags=["Agent"])


class AgentTextRequest(BaseModel):
    text: str = Field(..., description="텍스트 입력 (STT 생략)")
    run_wakeword: bool = True
    run_function_on_wake: bool = True
    tts_reply: bool = True


@router.post(
    "/voice",
    summary="Agent voice turn (오디오)",
    description="오디오 1회 입력에 대해 STT → 웨이크업 → 펑션콜 → TTS 파이프라인 실행.",
)
async def post_agent_voice(
    file: UploadFile = File(..., description="오디오 파일"),
    run_wakeword: bool = True,
    run_function_on_wake: bool = True,
    tts_reply: bool = True,
) -> dict:
    try:
        content = await file.read()
        filename = file.filename or "audio.webm"
        return run_agent_turn(
            audio_bytes=content,
            filename=filename,
            run_wakeword=run_wakeword,
            run_function_on_wake=run_function_on_wake,
            tts_reply=tts_reply,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/voice/text",
    summary="Agent voice turn (텍스트)",
    description="텍스트 입력에 대해 웨이크업 → 펑션콜 → TTS 파이프라인 실행 (STT 생략).",
)
async def post_agent_voice_text(body: AgentTextRequest) -> dict:
    try:
        return run_agent_turn(
            text_input=body.text,
            run_wakeword=body.run_wakeword,
            run_function_on_wake=body.run_function_on_wake,
            tts_reply=body.tts_reply,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
