#!/usr/bin/env python3
"""
Backend DatabaseManager로 pinky_robot_store 연결 검증.
app/backend/config/database.env 를 로드한 뒤 connect + get_session + 최소 쿼리 수행.

사용 (repo 루트에서):
  cd /path/to/roscamp-repo-1
  PYTHONPATH=app/backend python3 docs/scripts/verify_backend_db.py
"""
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent


def load_db_config():
    env_file = REPO_ROOT / "app" / "backend" / "config" / "database.env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
    return {
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": int(os.getenv("DB_PORT", "5432")),
        "db_name": os.getenv("DB_NAME", "kitchmatic"),
        "db_user": os.getenv("DB_USER", "kitchmatic_user"),
        "db_password": os.getenv("DB_PASSWORD", "your_password_here"),
    }


def main():
    # Load database_manager without pulling in main_server (rclpy)
    import importlib.util
    dm_path = REPO_ROOT / "app" / "backend" / "main_server" / "database_manager.py"
    spec = importlib.util.spec_from_file_location("database_manager", dm_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["database_manager"] = mod
    spec.loader.exec_module(mod)
    DatabaseManager = mod.DatabaseManager

    cfg = load_db_config()
    print(f"Config: host={cfg['db_host']} port={cfg['db_port']} db={cfg['db_name']} user={cfg['db_user']}")

    db = DatabaseManager(**cfg)
    if not db.connect():
        print("DatabaseManager.connect() failed.", file=sys.stderr)
        return 1
    print("DatabaseManager.connect() OK.")

    try:
        session = db.get_session()
        try:
            from sqlalchemy import text
            r = session.execute(text("SELECT COUNT(*) FROM menus")).scalar()
            print(f"Query OK: menus count = {r}")
        finally:
            session.close()
    except Exception as e:
        print("Session/query failed:", e, file=sys.stderr)
        return 1
    finally:
        db.close()

    print("Backend DB verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
