"""
Phase 1 TDD: Backend TCP 클라이언트 get_menus / order_request.
Mock TCP 서버로 프로토콜(4바이트 길이 + JSON) 검증.
"""
import importlib.util
import json
import socket
import threading
import pytest
import sys
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# backend_client만 로드 (app.core.__init__ 의존성 회피) - Phase 1 단위 테스트용
spec = importlib.util.spec_from_file_location(
    "backend_client",
    ROOT / "app" / "core" / "backend_client.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
BackendClient = mod.BackendClient
get_menus = mod.get_menus
send_order_request = mod.send_order_request
submit_voice_order = mod.submit_voice_order


class MockBackendServer:
    """프로토콜: 4바이트 big-endian 길이 + JSON. get_menus / order_request 응답."""

    def __init__(self, port: int = 0):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", port))
        if port == 0:
            self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.started = threading.Event()
        self.thread: threading.Thread | None = None

    def _handle(self, conn: socket.socket) -> None:
        try:
            order_count = [0]  # mutable for closure
            while True:
                header = conn.recv(4)
                if len(header) != 4:
                    break
                length = int.from_bytes(header, byteorder="big")
                data = b""
                while len(data) < length:
                    chunk = conn.recv(length - len(data))
                    if not chunk:
                        break
                    data += chunk
                if len(data) != length:
                    break
                msg = json.loads(data.decode("utf-8"))
                cmd = msg.get("type") or msg.get("command")
                if cmd == "get_menus":
                    out = {"status": "success", "data": {"menus": [
                        {"id": "M001", "name": "햄치즈샌드위치", "price": 5000},
                        {"id": "M002", "name": "머쉬룸샌드위치", "price": 5500},
                        {"id": "M003", "name": "올인원샌드위치", "price": 6500},
                    ]}}
                elif cmd == "order_request":
                    order_count[0] += 1
                    out = {"status": "success", "data": {"order_id": f"order-{order_count[0]}", "estimated_time": 120}}
                else:
                    out = {"status": "error", "message": "unknown"}
                body = json.dumps(out, ensure_ascii=False).encode("utf-8")
                conn.sendall(len(body).to_bytes(4, byteorder="big") + body)
        finally:
            conn.close()

    def run(self) -> None:
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        self.started.wait(timeout=2)

    def _serve(self) -> None:
        self.started.set()
        while True:
            try:
                conn, _ = self.sock.accept()
                self._handle(conn)
            except (OSError, BrokenPipeError):
                break

    def stop(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


@pytest.fixture
def mock_backend():
    server = MockBackendServer(port=0)
    server.run()
    yield server
    server.stop()


def test_backend_client_get_menus(mock_backend):
    """get_menus 호출 시 메뉴 목록 반환."""
    client = BackendClient(host="127.0.0.1", port=mock_backend.port)
    assert client.connect() is True
    try:
        menus = client.get_menus(table_number=1)
        assert len(menus) == 3
        assert menus[0]["id"] == "M001" and menus[0]["name"] == "햄치즈샌드위치"
        assert menus[1]["id"] == "M002"
        assert menus[2]["id"] == "M003"
    finally:
        client.disconnect()


def test_backend_client_order_request(mock_backend):
    """order_request 호출 시 order_id, estimated_time 반환."""
    client = BackendClient(host="127.0.0.1", port=mock_backend.port)
    assert client.connect() is True
    try:
        result = client.send_order_request(
            table_number="1",
            menu_id="M001",
            quantity=1,
            voice_order=True,
        )
        assert result is not None
        assert "order_id" in result
        assert result.get("estimated_time") == 120
    finally:
        client.disconnect()


def test_get_menus_convenience(mock_backend):
    """get_menus(host, port) 편의 함수."""
    menus = get_menus("127.0.0.1", mock_backend.port, table_number=1)
    assert len(menus) == 3
    assert menus[0]["id"] == "M001"


def test_send_order_request_convenience(mock_backend):
    """send_order_request(host, port, ...) 편의 함수."""
    result = send_order_request(
        "127.0.0.1", mock_backend.port,
        table_number="1", menu_id="M002", quantity=1, voice_order=True,
    )
    assert result is not None
    assert "order_id" in result


def test_submit_voice_order_multi(mock_backend):
    """submit_voice_order: get_menus 후 항목별 order_request."""
    result = submit_voice_order(
        items=[
            {"menu_id": "M001", "quantity": 1},
            {"menu_id": "M002", "quantity": 2},
        ],
        table_number="1",
        host="127.0.0.1",
        port=mock_backend.port,
    )
    assert result["success"] is True
    assert len(result["order_ids"]) == 3  # 1 + 2
    assert "주문 3건 접수" in result["message"]


def test_submit_voice_order_by_menu_name(mock_backend):
    """submit_voice_order: menu_name만 있으면 get_menus로 menu_id 조회."""
    result = submit_voice_order(
        items=[{"menu_name": "햄치즈샌드위치", "quantity": 1}],
        table_number="1",
        host="127.0.0.1",
        port=mock_backend.port,
    )
    assert result["success"] is True
    assert len(result["order_ids"]) == 1
