"""
웨이크업: (A) 오디오 → STT → 텍스트 매칭 + LLM 의도 판별(ORDER_START).
설정: config/wakeword_reference.yaml, config/wakeword_prompt.yaml
"""
import json
import re
import logging
from typing import Any
from app.config import get_settings
from app.core.openai_client import get_openai_client
from app.core.stt import stt_audio_to_text

logger = logging.getLogger(__name__)

INTENT_ORDER_START = "ORDER_START"


def _normalize(s: str) -> str:
    """공백·구두점 정규화."""
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _get_reference_phrases() -> list[str]:
    """wakeword_reference.yaml 에서 flat_list 로드."""
    settings = get_settings()
    data = settings.load_wakeword_reference()
    flat = data.get("flat_list") or []
    return [str(p).strip() for p in flat if p]


def _get_wakeword_prompt_parts() -> dict[str, Any]:
    """wakeword_prompt.yaml 로드."""
    settings = get_settings()
    return settings.load_wakeword_prompt()


def check_wakeword_text(
    text: str,
    use_llm: bool = True,
    client=None,
) -> dict[str, Any]:
    """
    텍스트가 웨이크 워드(주문 시작 의도)인지 판별.
    1) 레퍼런스 목록과의 텍스트 매칭
    2) use_llm 이 True 이면 LLM으로 ORDER_START 의도 추가 판별

    Returns:
        {
            "is_wake": bool,
            "intent": str | None,  # ORDER_START 등
            "matched_phrase": str | None,  # 목록에서 매칭된 문장
            "text": str,
            "llm_intent": str | None,
        }
    """
    text_norm = _normalize(text)
    result: dict[str, Any] = {
        "is_wake": False,
        "intent": None,
        "matched_phrase": None,
        "text": text_norm,
        "llm_intent": None,
    }
    if not text_norm:
        return result

    phrases = _get_reference_phrases()
    for phrase in phrases:
        if _normalize(phrase) in text_norm or text_norm in _normalize(phrase):
            result["is_wake"] = True
            result["matched_phrase"] = phrase
            result["intent"] = INTENT_ORDER_START
            break

    if use_llm and text_norm:
        try:
            prompt_cfg = _get_wakeword_prompt_parts()
            system_role = (prompt_cfg.get("system_role") or "").strip()
            task = (prompt_cfg.get("task") or "").strip()
            constraint = (prompt_cfg.get("constraint") or "").strip()
            ref_list = prompt_cfg.get("reference_examples") or []
            ref_block = "\n".join(f'- "{r}"' for r in ref_list[:15])

            user_content = f"{task}\n\n[Reference Examples]\n{ref_block}\n\n[Constraint]\n{constraint}\n\n[User input]\n{text_norm}"
            if client is None:
                client = get_openai_client()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_role},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=200,
            )
            content = (resp.choices[0].message.content or "").strip()
            if INTENT_ORDER_START in content and "intent" in content.lower():
                try:
                    # JSON 블록 추출 (중괄호 쌍)
                    start = content.find("{")
                    if start >= 0:
                        depth = 0
                        end = -1
                        for i in range(start, len(content)):
                            if content[i] == "{":
                                depth += 1
                            elif content[i] == "}":
                                depth -= 1
                                if depth == 0:
                                    end = i
                                    break
                        if end > start:
                            obj = json.loads(content[start : end + 1])
                            if obj.get("intent") == INTENT_ORDER_START:
                                result["llm_intent"] = INTENT_ORDER_START
                                result["is_wake"] = True
                                result["intent"] = INTENT_ORDER_START
                except json.JSONDecodeError:
                    if INTENT_ORDER_START in content:
                        result["llm_intent"] = INTENT_ORDER_START
                        result["is_wake"] = True
                        result["intent"] = INTENT_ORDER_START
        except Exception as e:
            logger.warning("Wake word LLM check failed: %s", e)

    return result


def check_wakeword_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    오디오가 웨이크 워드인지 판별. STT 후 check_wakeword_text 호출.
    """
    text = stt_audio_to_text(audio_bytes, filename=filename)
    out = check_wakeword_text(text, use_llm=use_llm)
    out["stt_text"] = text
    return out
