from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from app.core.wakeword import check_wakeword_text, check_wakeword_audio
from app.config import get_settings

router = APIRouter(prefix="/wakeword", tags=["Wake word"])


class WakewordTextRequest(BaseModel):
    text: str = Field(..., description="판별할 텍스트")
    use_llm: bool = Field(default=True, description="LLM 의도 판별 사용 여부")


class WakewordTextResponse(BaseModel):
    is_wake: bool
    intent: str | None
    matched_phrase: str | None
    text: str
    llm_intent: str | None


@router.post(
    "/check/text",
    response_model=WakewordTextResponse,
    summary="Wake word (텍스트)",
    description="텍스트가 주문 시작 웨이크 워드(ORDER_START)인지 판별.",
)
async def post_wakeword_check_text(body: WakewordTextRequest) -> WakewordTextResponse:
    try:
        out = check_wakeword_text(body.text, use_llm=body.use_llm)
        return WakewordTextResponse(
            is_wake=out["is_wake"],
            intent=out.get("intent"),
            matched_phrase=out.get("matched_phrase"),
            text=out.get("text", body.text),
            llm_intent=out.get("llm_intent"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/check/audio",
    summary="Wake word (오디오)",
    description="오디오를 STT 후 웨이크 워드 판별.",
)
async def post_wakeword_check_audio(
    file: UploadFile = File(..., description="오디오 파일"),
    use_llm: bool = True,
) -> dict:
    try:
        content = await file.read()
        filename = file.filename or "audio.webm"
        out = check_wakeword_audio(content, filename=filename, use_llm=use_llm)
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/reference",
    summary="Wake word 레퍼런스 목록",
    description="config/wakeword_reference.yaml 에 정의된 웨이크 워드 문장 목록.",
)
async def get_wakeword_reference() -> dict:
    try:
        settings = get_settings()
        data = settings.load_wakeword_reference()
        return {"flat_list": data.get("flat_list", []), "categories": data.get("categories", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
