"""
최근 주문 시도 모니터링: API + 대시보드용 데이터 저장.
"""
from collections import deque
from datetime import datetime
from typing import Any

from fastapi import APIRouter

# 최근 N건 유지
MAX_ATTEMPTS = 100
_attempts: deque = deque(maxlen=MAX_ATTEMPTS)


def add_attempt(
    session_id: str,
    text: str,
    reply_text: str,
    state: dict[str, Any],
) -> None:
    """/agent/order_turn 호출 시 한 건 기록."""
    _attempts.append({
        "session_id": session_id,
        "text": text,
        "reply_text": reply_text,
        "state": state,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


def get_attempts(limit: int = 50) -> list[dict[str, Any]]:
    """최근 주문 시도 목록 (최신 순)."""
    out = list(_attempts)
    out.reverse()
    return out[:limit]


router = APIRouter(prefix="/monitor", tags=["Monitor"])


@router.get(
    "/order_attempts",
    summary="최근 주문 시도 목록",
    description="음성 주문 플로우에서 /agent/order_turn 호출 시 기록된 최근 N건.",
)
def order_attempts(limit: int = 50) -> dict:
    return {"attempts": get_attempts(limit=limit), "total": len(_attempts)}
