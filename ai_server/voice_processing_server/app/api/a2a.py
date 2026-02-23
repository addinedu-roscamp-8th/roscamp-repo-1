from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from app.a2a.handlers import handle_a2a_voice_request

router = APIRouter(prefix="/a2a", tags=["A2A"])


class A2ATextRequest(BaseModel):
    text: str = Field(..., description="텍스트 입력")
    caller_id: str | None = None
    request_id: str | None = None
    metadata: dict | None = None
    run_wakeword: bool = True
    run_function_on_wake: bool = True
    tts_reply: bool = True


@router.post(
    "/voice",
    summary="A2A voice (오디오)",
    description="다른 에이전트/시스템이 호출. 파이프라인 실행 + caller_id, request_id 보존.",
)
async def post_a2a_voice(
    file: UploadFile = File(..., description="오디오 파일"),
    caller_id: str | None = None,
    request_id: str | None = None,
    run_wakeword: bool = True,
    run_function_on_wake: bool = True,
    tts_reply: bool = True,
) -> dict:
    try:
        content = await file.read()
        filename = file.filename or "audio.webm"
        return handle_a2a_voice_request(
            audio_bytes=content,
            filename=filename,
            caller_id=caller_id,
            request_id=request_id,
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
    summary="A2A voice (텍스트)",
)
async def post_a2a_voice_text(body: A2ATextRequest) -> dict:
    try:
        return handle_a2a_voice_request(
            text_input=body.text,
            caller_id=body.caller_id,
            request_id=body.request_id,
            metadata=body.metadata,
            run_wakeword=body.run_wakeword,
            run_function_on_wake=body.run_function_on_wake,
            tts_reply=body.tts_reply,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
