"""
펑션 콜링: 테스트 함수 및 음성 주문 전송(submit_voice_order).
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

TEST_FUNCTION_NAME = "test_voice_order"
SUBMIT_VOICE_ORDER_NAME = "submit_voice_order"


def run_test_function(
    function_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    등록된 함수 이름에 따라 함수를 호출하고 결과 반환.

    Args:
        function_name: 호출할 함수 이름 (test_voice_order, submit_voice_order 등)
        arguments: 함수에 넘길 인자

    Returns:
        { "success": bool, "message": str, "result": Any, "logged": bool }
    """
    arguments = arguments or {}
    result: dict[str, Any] = {
        "success": False,
        "message": "",
        "result": None,
        "logged": False,
    }

    if function_name == TEST_FUNCTION_NAME:
        logger.info(
            "[FUNCTION_CALL] test_voice_order invoked with arguments: %s",
            arguments,
            extra={"function": TEST_FUNCTION_NAME, "arguments": arguments},
        )
        result["success"] = True
        result["message"] = "Test function called successfully; check logs for confirmation."
        result["result"] = {"action": "test_voice_order", "received_args": arguments}
        result["logged"] = True
        return result

    if function_name == SUBMIT_VOICE_ORDER_NAME:
        from app.core.backend_client import submit_voice_order as do_submit
        items = arguments.get("items") or []
        table_number = arguments.get("table_number")
        out = do_submit(items=items, table_number=table_number)
        result["success"] = out.get("success", False)
        result["message"] = out.get("message", "")
        result["result"] = out
        result["logged"] = True
        return result

    result["message"] = f"Unknown function: {function_name}"
    logger.warning("[FUNCTION_CALL] Unknown function requested: %s", function_name)
    return result


def list_registered_functions() -> list[dict[str, Any]]:
    """등록된 펑션 목록 (문서/Agent용)."""
    return [
        {
            "name": TEST_FUNCTION_NAME,
            "description": "테스트용 음성 주문 펑션. 호출 시 로그로 동작 여부 확인.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "호출 소스 (e.g. voice, agent)"},
                    "payload": {"type": "object", "description": "추가 데이터"},
                },
            },
        },
        {
            "name": SUBMIT_VOICE_ORDER_NAME,
            "description": "음성 주문 확정 시 Backend로 주문 전송. items(메뉴 목록), table_number(선택).",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "주문 항목 [{ menu_id 또는 menu_name, quantity }]",
                        "items": {
                            "type": "object",
                            "properties": {
                                "menu_id": {"type": "string"},
                                "menu_name": {"type": "string"},
                                "quantity": {"type": "integer"},
                            },
                        },
                    },
                    "table_number": {"type": "integer", "description": "테이블 번호 (1~4, 기본 1)"},
                },
            },
        },
    ]
