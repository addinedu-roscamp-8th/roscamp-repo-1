"""
Mock Backend (Main Server) TCP 서버.
통합 테스트 시 Voice 서버의 ORDER_BACKEND_HOST/PORT를 이 서버로 지정해 사용.
프로토콜: 4바이트 big-endian 길이 + UTF-8 JSON (실제 Main Server와 동일).
"""
import argparse
import json
import socket
import sys
import threading
from datetime import datetime
from pathlib import Path

# 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# 수신 카운트 (로그/모니터링)
REQUEST_COUNTS = {"get_menus": 0, "order_request": 0}

MOCK_MENUS = [
    {"id": "M001", "name": "햄치즈샌드위치", "price": 5000, "description": "", "image_url": "", "available": True, "category": "샌드위치"},
    {"id": "M002", "name": "머쉬룸샌드위치", "price": 5500, "description": "", "image_url": "", "available": True, "category": "샌드위치"},
    {"id": "M003", "name": "올인원샌드위치", "price": 6500, "description": "", "image_url": "", "available": True, "category": "샌드위치"},
]

ORDER_ID_COUNTER = [0]  # mutable for closure


def recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return b""
        buf += chunk
    return buf


def send_response(sock: socket.socket, obj: dict) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sock.sendall(len(body).to_bytes(4, byteorder="big") + body)


def handle_client(conn: socket.socket, addr) -> None:
    try:
        while True:
            header = recv_exact(conn, 4)
            if not header or len(header) != 4:
                break
            length = int.from_bytes(header, byteorder="big")
            data = recv_exact(conn, length)
            if not data or len(data) != length:
                break
            msg = json.loads(data.decode("utf-8"))
            cmd = msg.get("type") or msg.get("command")

            if cmd == "get_menus":
                REQUEST_COUNTS["get_menus"] += 1
                print(f"[MockBackend] get_menus #{REQUEST_COUNTS['get_menus']} from {addr}")
                send_response(conn, {"status": "success", "data": {"menus": MOCK_MENUS}})
            elif cmd == "order_request":
                REQUEST_COUNTS["order_request"] += 1
                ORDER_ID_COUNTER[0] += 1
                oid = f"mock-order-{ORDER_ID_COUNTER[0]}"
                data_payload = msg.get("data", msg)
                table = data_payload.get("table_number", "?")
                menu_id = data_payload.get("menu_id", "?")
                print(f"[MockBackend] order_request #{REQUEST_COUNTS['order_request']} table={table} menu_id={menu_id} -> {oid}")
                send_response(conn, {"status": "success", "data": {"order_id": oid, "estimated_time": 120}})
            else:
                print(f"[MockBackend] unknown command: {cmd}")
                send_response(conn, {"status": "error", "message": f"Unknown: {cmd}"})
    except Exception as e:
        print(f"[MockBackend] handle_client error: {e}")
    finally:
        conn.close()


def run_server(host: str = "127.0.0.1", port: int = 9998) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    print(f"[MockBackend] Listening on {host}:{port} (Voice 서버 ORDER_BACKEND_HOST/PORT를 여기로 설정)")
    while True:
        conn, addr = sock.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()


def main():
    p = argparse.ArgumentParser(description="Mock Backend TCP server for voice order integration test")
    p.add_argument("--host", default="127.0.0.1", help="Bind host")
    p.add_argument("--port", type=int, default=9998, help="Bind port (Voice 서버 ORDER_BACKEND_PORT=9998 로 설정)")
    args = p.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
