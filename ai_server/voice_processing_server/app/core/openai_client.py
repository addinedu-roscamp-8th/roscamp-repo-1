"""
OpenAI API 클라이언트 래퍼. 설정에서 API Key 로드.
"""
from openai import OpenAI
from app.config import get_settings


def get_openai_client() -> OpenAI:
    settings = get_settings()
    key = settings.openai_api_key
    if not key:
        raise ValueError("OPENAI_API_KEY is not set. Check .env or environment.")
    return OpenAI(api_key=key)
