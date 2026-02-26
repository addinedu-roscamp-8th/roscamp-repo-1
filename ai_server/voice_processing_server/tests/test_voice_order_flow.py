"""
Phase 3: 추가주문/주문 완료 플로우 테스트.
"""
import sys
from pathlib import Path
import pytest

pytest.importorskip("openai")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.voice_order_state import (
    process_order_turn,
    get_items,
    clear,
    STAGE_IDLE,
    STAGE_COLLECTING,
    STAGE_ASK_MORE,
    STAGE_CONFIRMING,
)


def test_flow_idle_to_collecting():
    """idle -> 첫 발화 -> collecting."""
    sid = "test1"
    clear(sid)
    reply, state = process_order_turn(sid, "주문할게요", menu_names=[])
    assert state["stage"] == STAGE_COLLECTING
    assert "주문을 도와드리겠습니다" in reply or "메뉴를 말씀해주세요" in reply


def test_flow_collecting_menu_then_ask_more():
    """collecting -> 메뉴명 -> ask_more."""
    sid = "test2"
    clear(sid)
    process_order_turn(sid, "주문해", menu_names=["햄치즈샌드위치", "머쉬룸샌드위치"])
    reply, state = process_order_turn(sid, "햄치즈샌드위치", menu_names=["햄치즈샌드위치", "머쉬룸샌드위치"])
    assert state["stage"] == STAGE_ASK_MORE
    assert len(state["items"]) == 1
    assert "추가주문" in reply or "주문 완료" in reply


def test_flow_ask_more_add_then_done():
    """ask_more -> 추가주문 -> collecting -> 메뉴 -> ask_more -> 주문 완료 -> confirming."""
    sid = "test3"
    clear(sid)
    menus = ["햄치즈샌드위치", "머쉬룸샌드위치"]
    process_order_turn(sid, "여기", menu_names=menus)
    process_order_turn(sid, "햄치즈샌드위치", menu_names=menus)
    reply, state = process_order_turn(sid, "추가주문", menu_names=menus)
    assert state["stage"] == STAGE_COLLECTING
    reply2, state2 = process_order_turn(sid, "머쉬룸샌드위치", menu_names=menus)
    assert state2["stage"] == STAGE_ASK_MORE
    assert len(state2["items"]) == 2
    reply3, state3 = process_order_turn(sid, "주문 완료", menu_names=menus)
    assert state3["stage"] == STAGE_CONFIRMING
    assert "진행할까요" in reply3


def test_flow_confirm_yes_mocks_submit(monkeypatch):
    """confirming -> 네 -> submit_voice_order 호출, 주문 접수 메시지."""
    submitted = []

    def fake_submit(items, table_number=None, host=None, port=None):
        submitted.append({"items": items, "table_number": table_number})
        return {"success": True, "order_ids": ["oid-1"], "message": "주문 1건 접수되었습니다."}

    monkeypatch.setattr("app.core.backend_client.submit_voice_order", fake_submit)

    sid = "test4"
    clear(sid)
    menus = ["햄치즈샌드위치"]
    process_order_turn(sid, "주문", menu_names=menus)
    process_order_turn(sid, "햄치즈샌드위치", menu_names=menus)
    process_order_turn(sid, "주문 완료", menu_names=menus)

    reply, state = process_order_turn(sid, "네", menu_names=menus)
    assert "접수" in reply
    assert state["stage"] == STAGE_IDLE
    assert len(submitted) == 1
    assert len(submitted[0]["items"]) == 1
