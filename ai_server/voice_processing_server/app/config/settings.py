"""
설정 로드: 환경 변수 및 .env. API Key 등 비밀은 여기서만 참조.
"""
import os
from pathlib import Path
from functools import lru_cache
import yaml
from pydantic_settings import BaseSettings
from pydantic import Field


def _config_dir() -> Path:
    env_dir = os.environ.get("CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parent.parent.parent / "config"


@lru_cache
def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    """앱 설정. OPENAI_API_KEY는 .env 또는 환경변수에서 로드."""

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    config_dir: Path = Field(default_factory=_config_dir, exclude=True)

    # STT/TTS
    whisper_model: str = Field(default="whisper-1", alias="WHISPER_MODEL")
    tts_model: str = Field(default="tts-1", alias="TTS_MODEL")
    tts_voice: str = Field(default="alloy", alias="TTS_VOICE")

    # Server
    host: str = Field(default="0.0.0.0", alias="VOICE_SERVER_HOST")
    port: int = Field(default=8000, alias="VOICE_SERVER_PORT")

    # Order Backend (Main Server TCP)
    order_backend_host: str = Field(default="127.0.0.1", alias="ORDER_BACKEND_HOST")
    order_backend_port: int = Field(default=9999, alias="ORDER_BACKEND_PORT")
    voice_order_table_number: int = Field(default=1, alias="VOICE_ORDER_TABLE_NUMBER")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def wakeword_reference_path(self) -> Path:
        return self.config_dir / "wakeword_reference.yaml"

    @property
    def wakeword_prompt_path(self) -> Path:
        return self.config_dir / "wakeword_prompt.yaml"

    def load_wakeword_reference(self) -> dict:
        return _load_yaml(self.wakeword_reference_path)

    def load_wakeword_prompt(self) -> dict:
        return _load_yaml(self.wakeword_prompt_path)


@lru_cache
def get_settings() -> Settings:
    config_dir = _config_dir()
    env_file = config_dir.parent / ".env"
    if env_file.exists():
        return Settings(_env_file=env_file)
    return Settings()
