"""
펑션 콜링: 테스트 함수 호출 시 로그로 동작 여부 확인.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

TEST_FUNCTION_NAME = "test_voice_order"


def run_test_function(
    function_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    등록된 함수 이름에 따라 함수를 호출하고 결과 반환.
    테스트 함수는 로그만 남기고 성공 반환.

    Args:
        function_name: 호출할 함수 이름 (현재 test_voice_order 만 지원)
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
    ]
