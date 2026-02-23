"""
Voice order FastAPI 서버.
OpenAI STT/TTS, 웨이크업, 펑션 콜링, 파이프라인, Agent, A2A 엔드포인트 제공.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from openai import RateLimitError
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import stt, tts, wakeword, function_calling, pipeline, agent, a2a

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 프로젝트 루트 (voice_processing_server)
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Voice Order API",
    description="OpenAI 기반 STT, TTS, 웨이크업, 펑션 콜링, 파이프라인, Agent, A2A API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stt.router)
app.include_router(tts.router)
app.include_router(wakeword.router)
app.include_router(function_calling.router)
app.include_router(pipeline.router)
app.include_router(agent.router)
app.include_router(a2a.router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.exception_handler(RateLimitError)
async def openai_rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "OpenAI API rate limit exceeded (429). Please try again in a moment.",
        },
    )


@app.get("/")
async def root():
    return {
        "service": "voice-order",
        "docs": "/docs",
        "redoc": "/redoc",
        "test_gui": "/static/index.html",
        "endpoints": {
            "stt": "POST /stt/",
            "tts": "POST /tts/",
            "tts_json": "POST /tts/json",
            "wakeword_text": "POST /wakeword/check/text",
            "wakeword_audio": "POST /wakeword/check/audio",
            "wakeword_reference": "GET /wakeword/reference",
            "function_call": "POST /functions/call",
            "function_list": "GET /functions/list",
            "pipeline_run": "POST /pipeline/run",
            "agent_voice": "POST /agent/voice",
            "agent_voice_text": "POST /agent/voice/text",
            "a2a_voice": "POST /a2a/voice",
            "a2a_voice_text": "POST /a2a/voice/text",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get(
    "/debug/api-key-check",
    summary="[개발] API 키 로드 여부 확인",
    description="서버가 사용 중인 OpenAI API 키가 설정되었는지, 키 끝 4자만 표시해 플랫폼과 대조할 수 있습니다. 키는 노출되지 않습니다.",
)
async def debug_api_key_check():
    from app.config import get_settings
    s = get_settings()
    key = (s.openai_api_key or "").strip()
    if not key:
        return {"key_configured": False, "key_suffix": None, "hint": "OPENAI_API_KEY is not set in .env or environment."}
    # 끝 4자만 표시 (sk-xxxx...Ab12 형태)
    suffix = key[-4:] if len(key) >= 4 else "****"
    return {
        "key_configured": True,
        "key_suffix": suffix,
        "hint": "Platform에서 사용 중인 API 키 끝 4자와 일치하는지 확인하세요. 다르면 .env 또는 환경변수를 점검하세요.",
    }


def create_app() -> FastAPI:
    return app
