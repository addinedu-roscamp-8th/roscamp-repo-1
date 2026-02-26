"""
음성 주문 플로우 상태: 추가주문/주문 완료 분기.
단일 세션 인메모리 상태. process_order_turn(session_id, text) -> (reply, state).
"""
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# session_id -> { "items": [{"menu_name": str, "quantity": int}], "stage": str }
_storage: dict[str, dict[str, Any]] = {}

STAGE_IDLE = "idle"
STAGE_COLLECTING = "collecting"
STAGE_ASK_MORE = "ask_more"
STAGE_CONFIRMING = "confirming"

PROMPT_ASK_MORE = (
    "더 주문하실 메뉴가 있으신가요? 있으면 '추가주문'을, 아니면 '주문 완료'를 말씀해주세요."
)
PROMPT_NEXT_MENU = "다음 메뉴를 말씀해주세요."
PROMPT_CONFIRM = "주문을 진행할까요?"
PROMPT_ORDER_ACCEPTED = "주문이 접수되었습니다."
PROMPT_MENU_EXAMPLES = "메뉴를 말씀해주세요. 예: 햄치즈샌드위치, 머쉬룸샌드위치, 올인원샌드위치."


def _get_state(session_id: str) -> dict[str, Any]:
    if session_id not in _storage:
        _storage[session_id] = {"items": [], "stage": STAGE_IDLE}
    return _storage[session_id]


def get_items(session_id: str) -> list[dict[str, Any]]:
    return list(_get_state(session_id)["items"])


def clear(session_id: str) -> None:
    if session_id in _storage:
        del _storage[session_id]


def _normalize(t: str) -> str:
    return (t or "").strip().replace(" ", "").lower()


def _match_menu_name(text: str, menu_names: list[str]) -> str | None:
    """텍스트에서 메뉴명 매칭 (포함 또는 정규화 일치)."""
    norm_text = _normalize(text)
    for name in menu_names:
        if not name:
            continue
        if name in text or _normalize(name) in norm_text or norm_text == _normalize(name):
            return name
    return None


def _resolve_menu_names(table_number: str | int | None) -> list[str]:
    """Backend get_menus로 메뉴 이름 목록 조회 (실패 시 기본 목록)."""
    try:
        from app.config import get_settings
        from app.core.backend_client import BackendClient
        s = get_settings()
        client = BackendClient(host=s.order_backend_host, port=s.order_backend_port)
        if client.connect():
            menus = client.get_menus(table_number=table_number or s.voice_order_table_number)
            client.disconnect()
            return [m.get("name") or m.get("menu_name") or "" for m in menus if m.get("name") or m.get("menu_name")]
    except Exception as e:
        logger.warning("get_menus for flow failed: %s", e)
    return ["햄치즈샌드위치", "머쉬룸샌드위치", "올인원샌드위치"]


def process_order_turn(
    session_id: str,
    text: str,
    table_number: str | int | None = None,
    menu_names: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    음성 주문 1턴 처리.
    text: 사용자 발화.
    menu_names: Backend get_menus에서 온 메뉴 이름 목록 (None이면 get_menus 호출).
    Returns:
        (reply_text, state_dict)
    """
    if menu_names is None:
        menu_names = _resolve_menu_names(table_number)
    state = _get_state(session_id)
    stage = state["stage"]
    items = state["items"]
    text_clean = (text or "").strip()

    # 키워드 감지
    has_add_more = "추가주문" in text_clean or "추가 주문" in text_clean
    has_done = "주문 완료" in text_clean or "주문완료" in text_clean
    has_yes = bool(re.search(r"^(예|네|응|그래|진행|해주세요|주문해)", text_clean))

    if stage == STAGE_IDLE:
        # 웨이크 후 첫 발화로 간주: 주문 모드 시작
        state["stage"] = STAGE_COLLECTING
        return (
            "샌드위치 주문을 도와드리겠습니다. 원하시는 메뉴를 말씀해주세요. "
            + PROMPT_MENU_EXAMPLES,
            {"stage": STAGE_COLLECTING, "items": []},
        )

    if stage == STAGE_COLLECTING:
        matched = None
        if menu_names:
            matched = _match_menu_name(text_clean, menu_names)
        if matched:
            items.append({"menu_name": matched, "quantity": 1})
            state["stage"] = STAGE_ASK_MORE
            n = len(items)
            return (
                f"{matched} 1건 담았습니다. {PROMPT_ASK_MORE}",
                {"stage": STAGE_ASK_MORE, "items": list(items)},
            )
        return (PROMPT_MENU_EXAMPLES, {"stage": STAGE_COLLECTING, "items": list(items)})

    if stage == STAGE_ASK_MORE:
        if has_add_more:
            state["stage"] = STAGE_COLLECTING
            return (PROMPT_NEXT_MENU, {"stage": STAGE_COLLECTING, "items": list(items)})
        if has_done:
            state["stage"] = STAGE_CONFIRMING
            return (PROMPT_CONFIRM, {"stage": STAGE_CONFIRMING, "items": list(items)})
        return (PROMPT_ASK_MORE, {"stage": STAGE_ASK_MORE, "items": list(items)})

    if stage == STAGE_CONFIRMING:
        if has_yes and items:
            from app.core.backend_client import submit_voice_order
            result = submit_voice_order(
                items=[{"menu_name": it["menu_name"], "quantity": it.get("quantity", 1)} for it in items],
                table_number=table_number,
            )
            clear(session_id)
            if result.get("success"):
                return (PROMPT_ORDER_ACCEPTED, {"stage": STAGE_IDLE, "items": [], "order_ids": result.get("order_ids", [])})
            return (f"주문 접수에 실패했습니다. {result.get('message', '')}", {"stage": STAGE_IDLE, "items": []})
        return (PROMPT_CONFIRM, {"stage": STAGE_CONFIRMING, "items": list(items)})

    return ("다시 말씀해주세요.", {"stage": state["stage"], "items": list(items)})
