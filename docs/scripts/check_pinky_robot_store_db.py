#!/usr/bin/env python3
"""
pinky_robot_store DB 연결 및 9개 Kitchmatic 테이블 존재 여부 점검.
db_server .env 값을 사용하여 접속 후 public 스키마 테이블 목록을 확인합니다.
사용: repo 루트에서 실행
  python docs/scripts/check_pinky_robot_store_db.py
  또는 DB 설정이 필요하면:
  export $(grep -v '^#' database/db_server/.env | xargs) && python docs/scripts/check_pinky_robot_store_db.py
"""
import os
import sys
from pathlib import Path

# Repo root: script is docs/scripts/check_pinky_robot_store_db.py
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

REQUIRED_TABLES = [
    "menus",
    "ingredients",
    "recipes",
    "recipe_steps",
    "inventory",
    "inventory_transactions",
    "robots",
    "orders",
    "quality_check_results",
]


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


def main() -> int:
    env_file = REPO_ROOT / "database" / "db_server" / ".env"
    load_env(env_file)

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    dbname = os.getenv("DB_NAME", "pinky_robot_store")
    user = os.getenv("DB_USER", "deepdive")
    password = os.getenv("DB_PASSWORD", "")

    if not password:
        print("DB_PASSWORD not set. Load from database/db_server/.env or set env.", file=sys.stderr)
        return 1

    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
        return 1

    print(f"Connecting to {host}:{port} db={dbname} user={user} ...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5,
        )
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
            existing = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    print("Connection OK.")
    print(f"Public tables: {sorted(existing)}")
    missing = [t for t in REQUIRED_TABLES if t not in existing]
    if missing:
        print(f"Missing required tables: {missing}", file=sys.stderr)
        return 1
    print("All 9 required Kitchmatic tables present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
