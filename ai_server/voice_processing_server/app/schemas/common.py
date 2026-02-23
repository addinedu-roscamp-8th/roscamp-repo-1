from pydantic import BaseModel, Field


class WakewordResult(BaseModel):
    is_wake: bool = False
    intent: str | None = None
    matched_phrase: str | None = None
    text: str = ""
    llm_intent: str | None = None
    stt_text: str | None = None


class FunctionCallResult(BaseModel):
    success: bool = False
    message: str = ""
    result: dict | None = None
    logged: bool = False


class PipelineResult(BaseModel):
    success: bool = True
    stt_text: str = ""
    wake: WakewordResult | None = None
    function_called: bool = False
    function_result: dict | None = None
    tts_audio_base64: str | None = None
    reply_text: str | None = None
    error: str | None = None
