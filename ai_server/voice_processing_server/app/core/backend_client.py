"""
Backend(Main Server) TCP 클라이언트.
get_menus, order_request 호출 — 4바이트 길이 헤더 + JSON 프로토콜.
"""
import socket
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class BackendClient:
    """
    Main Server TCP 클라이언트.
    프로토콜: 4바이트 big-endian 길이 + UTF-8 JSON.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9999, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None

    def connect(self) -> bool:
        """서버에 연결."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
            logger.info("Backend connected: %s:%s", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Backend connect failed: %s", e)
            return False

    def disconnect(self) -> None:
        """연결 종료."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
            logger.debug("Backend disconnected")

    def is_connected(self) -> bool:
        return self._socket is not None

    def _send_request(self, message: dict) -> dict | None:
        """
        메시지 전송 후 응답 수신.
        요청: JSON. 응답: 4바이트 길이 + JSON.
        """
        if not self._socket:
            logger.error("Not connected")
            return None
        try:
            body = json.dumps(message, ensure_ascii=False).encode("utf-8")
            header = len(body).to_bytes(4, byteorder="big")
            self._socket.sendall(header + body)

            header_buf = self._recv_exact(4)
            if not header_buf or len(header_buf) != 4:
                return None
            length = int.from_bytes(header_buf, byteorder="big")
            data_buf = self._recv_exact(length)
            if not data_buf or len(data_buf) != length:
                return None
            return json.loads(data_buf.decode("utf-8"))
        except Exception as e:
            logger.error("Backend send/recv error: %s", e)
            return None

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._socket.recv(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return buf

    def get_menus(self, table_number: int | str = 1) -> list[dict[str, Any]]:
        """
        메뉴 목록 조회 (DB 기반).
        Backend get_menus 핸들러 호출.
        Returns:
            [{"id": "M001", "name": "햄치즈샌드위치", "price": 5000, ...}, ...]
        """
        req = {"command": "get_menus", "table_number": int(table_number)}
        resp = self._send_request(req)
        if not resp or resp.get("status") != "success":
            logger.warning("get_menus failed: %s", resp)
            return []
        data = resp.get("data", resp)
        menus = data.get("menus", [])
        return list(menus)

    def send_order_request(
        self,
        table_number: str,
        menu_id: str,
        quantity: int = 1,
        sauce_type: str = "mayo",
        voice_order: bool = True,
    ) -> dict | None:
        """
        주문 1건 전송 (order_request).
        Returns:
            {"order_id": "...", "estimated_time": 120} or None on error.
        """
        req = {
            "type": "order_request",
            "data": {
                "table_number": str(table_number),
                "menu_id": menu_id,
                "quantity": quantity,
                "sauce_type": sauce_type,
                "voice_order": voice_order,
            },
        }
        resp = self._send_request(req)
        if not resp or resp.get("status") != "success":
            logger.warning("order_request failed: %s", resp)
            return None
        return resp.get("data")


def get_menus(host: str, port: int, table_number: int | str = 1) -> list[dict[str, Any]]:
    """편의: 연결 → get_menus → 연결 종료."""
    client = BackendClient(host=host, port=port)
    try:
        if not client.connect():
            return []
        return client.get_menus(table_number=table_number)
    finally:
        client.disconnect()


def send_order_request(
    host: str,
    port: int,
    table_number: str,
    menu_id: str,
    quantity: int = 1,
    voice_order: bool = True,
) -> dict | None:
    """편의: 연결 → order_request 1건 → 연결 종료."""
    client = BackendClient(host=host, port=port)
    try:
        if not client.connect():
            return None
        return client.send_order_request(
            table_number=table_number,
            menu_id=menu_id,
            quantity=quantity,
            voice_order=voice_order,
        )
    finally:
        client.disconnect()


def _menu_name_to_id_map(menus: list[dict[str, Any]]) -> dict[str, str]:
    """메뉴 목록에서 name -> id 매핑 (공백 제거, 정규화)."""
    out: dict[str, str] = {}
    for m in menus:
        mid = m.get("id") or m.get("menu_id")
        name = (m.get("name") or m.get("menu_name") or "").strip()
        if mid and name:
            out[name] = str(mid)
            # 'All-in-one' / '올인원' 등 별칭 허용를 위해 소문자 키도 추가
            out[name.replace(" ", "").lower()] = str(mid)
    return out


def submit_voice_order(
    items: list[dict[str, Any]],
    table_number: str | int | None = None,
    host: str | None = None,
    port: int | None = None,
) -> dict[str, Any]:
    """
    음성 주문 다건 전송. 항목별 order_request 호출 (voice_order=True).
    items: [ {"menu_id": "M001", "quantity": 1}, ... ] 또는
            [ {"menu_name": "햄치즈샌드위치", "quantity": 1}, ... ]
    menu_name만 있으면 get_menus로 menu_id 조회.
    Returns:
        { "success": bool, "order_ids": list[str], "message": str }
    """
    try:
        from app.config import get_settings
        s = get_settings()
        h = host or s.order_backend_host
        p = port or s.order_backend_port
        tbl = str(table_number if table_number is not None else s.voice_order_table_number)
    except Exception:
        h = host or "127.0.0.1"
        p = port or 9999
        tbl = str(table_number if table_number is not None else "1")

    if not items:
        return {"success": False, "order_ids": [], "message": "주문 항목이 없습니다."}

    client = BackendClient(host=h, port=p)
    order_ids: list[str] = []
    try:
        if not client.connect():
            return {"success": False, "order_ids": [], "message": "Backend 연결 실패."}

        menus = client.get_menus(table_number=tbl)
        name_to_id = _menu_name_to_id_map(menus)

        for it in items:
            menu_id = it.get("menu_id")
            if not menu_id:
                name = (it.get("menu_name") or it.get("name") or "").strip()
                menu_id = name_to_id.get(name) or name_to_id.get(name.replace(" ", "").lower())
            if not menu_id:
                logger.warning("Unknown menu name: %s", it)
                continue
            qty = int(it.get("quantity", 1))
            for _ in range(qty):
                res = client.send_order_request(
                    table_number=tbl,
                    menu_id=menu_id,
                    quantity=1,
                    voice_order=True,
                )
                if res and res.get("order_id"):
                    order_ids.append(str(res["order_id"]))
    finally:
        client.disconnect()

    success = len(order_ids) > 0
    return {
        "success": success,
        "order_ids": order_ids,
        "message": f"주문 {len(order_ids)}건 접수되었습니다." if success else "주문 접수에 실패했습니다.",
    }
