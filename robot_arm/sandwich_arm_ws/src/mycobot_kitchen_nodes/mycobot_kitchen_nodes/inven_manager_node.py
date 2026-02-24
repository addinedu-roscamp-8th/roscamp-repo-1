import os
import threading
from contextlib import contextmanager

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor

# NOTE:
# Arm A(ROS_DOMAIN_ID=20) recipe/refill nodes use mycobot_kitchen_msgs.
# Inventory manager must provide the SAME srv types, otherwise domain_bridge 연결이 되어도 호출이 실패한다.
from mycobot_kitchen_msgs.srv import GetInventory, ConsumeInventory, ConsumeVat

try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
except Exception:
    psycopg2 = None
    ThreadedConnectionPool = None


class InventoryManagerNode(Node):
    """
    Postgres-backed inventory manager (2-level stock):
      - units_in_open_vat: 현재 개봉 vat 안 남은 개수 (0..units_per_vat)
      - vats_remaining: 창고 미개봉 vat 개수 (0..vat_capacity - open_vat_count)

    ROS2 services (유지):
      - inventory/get
      - inventory/consume  (원자적 consume + open vat 자동 교체 포함)
      - inventory/set      (관리/초기화용: total remaining을 2계층으로 매핑)
    """

    def __init__(self):
        super().__init__("inventory_manager_node")

        if psycopg2 is None:
            raise RuntimeError("psycopg2 not installed. try: pip install psycopg2-binary")

        # --- DB params (env 우선) ---
        self.declare_parameter("pg_host", os.getenv("PGHOST", "127.0.0.1"))
        self.declare_parameter("pg_port", int(os.getenv("PGPORT", "5432")))
        self.declare_parameter("pg_db", os.getenv("PGDATABASE", "kitchen"))
        self.declare_parameter("pg_user", os.getenv("PGUSER", "kitchen"))
        self.declare_parameter("pg_password", os.getenv("PGPASSWORD", "kitchen"))
        self.declare_parameter("pg_sslmode", os.getenv("PGSSLMODE", "disable"))

        self.declare_parameter("pool_min", 1)
        self.declare_parameter("pool_max", 5)

        # 테이블명 (팀 DB에 맞춰 변경 가능)
        self.declare_parameter("table_name", "inventory_item")

        host = str(self.get_parameter("pg_host").value)
        port = int(self.get_parameter("pg_port").value)
        db = str(self.get_parameter("pg_db").value)
        user = str(self.get_parameter("pg_user").value)
        pw = str(self.get_parameter("pg_password").value)
        sslmode = str(self.get_parameter("pg_sslmode").value)

        self._table = str(self.get_parameter("table_name").value)

        self._dsn = f"host={host} port={port} dbname={db} user={user} password={pw} sslmode={sslmode}"
        pool_min = int(self.get_parameter("pool_min").value)
        pool_max = int(self.get_parameter("pool_max").value)

        self._pool = ThreadedConnectionPool(pool_min, pool_max, dsn=self._dsn)
        self._pool_lock = threading.Lock()

        # --- ROS services ---
        self.create_service(GetInventory, "inventory/get", self.on_get)
        self.create_service(ConsumeInventory, "inventory/consume", self.on_consume)
        self.create_service(ConsumeVat, "inventory/consume_vat", self.on_consume_vat)
        self.get_logger().info("Ready: inventory/get, inventory/consume, inventory/consume_vat (Postgres, vat-aware)")

    @contextmanager
    def _conn_cursor(self):
        with self._pool_lock:
            conn = self._pool.getconn()
        try:
            cur = conn.cursor()
            yield conn, cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            try:
                cur.close()
            except Exception:
                pass
            with self._pool_lock:
                self._pool.putconn(conn)

    # -----------------------------
    # inventory/get
    # -----------------------------
    def on_get(self, req: GetInventory.Request, res: GetInventory.Response):
        item_key = str(req.item_key).strip()
        if not item_key:
            res.ok = False
            res.message = "empty item_key"
            res.remaining_inven = 0
            res.remaining_vat = 0
            return res

        try:
            with self._conn_cursor() as (_, cur):
                cur.execute(
                    f"""
                    SELECT units_per_vat, vat_capacity, vats_remaining, units_in_open_vat
                    FROM {self._table}
                    WHERE item_key = %s;
                    """,
                    (item_key,),
                )
                row = cur.fetchone()

            if row is None:
                res.ok = False
                res.message = "not_found"
                res.remaining_inven = 0
                res.remaining_vat = 0
                return res

            units_per_vat, vat_capacity, vats_remaining, units_in_open_vat = map(int, row)

            rem_vats =  vats_remaining
            rem_units = units_in_open_vat

            res.ok = True
            res.message = "ok"
            res.remaining_inven = int(rem_units)
            res.remaining_vat = int(rem_vats)
            return res

        except Exception as e:
            res.ok = False
            res.message = f"exception: {e}"
            res.remaining_inven = 0
            res.remaining_vat = 0
            return res

    # -----------------------------
    # inventory/consume (원자적 + 자동 vat 교체)
    # -----------------------------
    def on_consume(self, req: ConsumeInventory.Request, res: ConsumeInventory.Response):
        item_key = str(req.item_key).strip()
        amount = int(req.amount) if int(req.amount) > 0 else 1

        if not item_key:
            res.ok = False
            res.message = "empty item_key"
            res.remaining = 0
            return res

        try:
            with self._conn_cursor() as (_, cur):
                cur.execute(
                    f"""
                    SELECT units_per_vat, vat_capacity, vats_remaining, units_in_open_vat
                    FROM {self._table}
                    WHERE item_key = %s
                    FOR UPDATE;
                    """,
                    (item_key,),
                )
                row = cur.fetchone()
                if row is None:
                    res.ok = False
                    res.message = "not_found"
                    res.remaining = 0
                    return res

                units_per_vat, vat_capacity, vats_remaining, units_in_open_vat = map(int, row)

                # 방어
                units_per_vat = max(1, units_per_vat)
                vat_capacity = max(0, vat_capacity)
                vats_remaining = max(0, vats_remaining)
                units_in_open_vat = max(0, units_in_open_vat)

                # ✅ 내용물(오픈 vat)만 소비. 부족하면 실패.
                if units_in_open_vat < amount:
                    res.ok = False
                    res.message = "insufficient_open_units"
                    res.remaining = int(units_in_open_vat)
                    return res

                units_in_open_vat -= amount

                cur.execute(
                    f"""
                    UPDATE {self._table}
                    SET units_in_open_vat = %s,
                        updated_at = now()
                    WHERE item_key = %s;
                    """,
                    (int(units_in_open_vat), item_key),
                )

                rem_units = units_in_open_vat

            res.ok = True
            res.message = "ok"
            res.remaining = int(rem_units)
            return res

        except Exception as e:
            res.ok = False
            res.message = f"exception:{type(e).__name__}:{e}"
            res.remaining = 0
            return res


    def on_consume_vat(self, req: ConsumeVat.Request, res: ConsumeVat.Response):
        item_key = str(req.item_key).strip()
        vats = int(req.vats) if int(req.vats) > 0 else 1

        if not item_key:
            res.ok = False
            res.message = "empty item_key"
            res.vats_remaining = 0
            res.open_units = 0
            return res

        try:
            with self._conn_cursor() as (_, cur):
                cur.execute(
                    f"""
                    SELECT units_per_vat, vat_capacity, vats_remaining, units_in_open_vat
                    FROM {self._table}
                    WHERE item_key = %s
                    FOR UPDATE;
                    """,
                    (item_key,),
                )
                row = cur.fetchone()
                if row is None:
                    res.ok = False
                    res.message = "not_found"
                    res.vats_remaining = 0
                    res.open_units = 0
                    return res

                units_per_vat, vat_capacity, vats_remaining, units_in_open_vat = map(int, row)

                # 방어
                units_per_vat = max(1, units_per_vat)
                vat_capacity = max(0, vat_capacity)
                vats_remaining = max(0, vats_remaining)
                units_in_open_vat = max(0, units_in_open_vat)

                # ✅ 미개봉 vat 재고 체크
                if vats_remaining < vats:
                    res.ok = False
                    res.message = "insufficient_vats"
                    res.vats_remaining = int(vats_remaining)
                    res.open_units = int(units_in_open_vat)
                    return res

                # ✅ vat 개봉 처리: vats_remaining 감소, open units 증가
                vats_remaining -= vats
                units_in_open_vat += vats * units_per_vat

                cur.execute(
                    f"""
                    UPDATE {self._table}
                    SET vats_remaining = %s,
                        units_in_open_vat = %s,
                        updated_at = now()
                    WHERE item_key = %s;
                    """,
                    (int(vats_remaining), int(units_in_open_vat), item_key),
                )

            res.ok = True
            res.message = "ok"
            res.vats_remaining = int(vats_remaining)
            res.open_units = int(units_in_open_vat)
            return res

        except Exception as e:
            res.ok = False
            res.message = f"exception:{type(e).__name__}:{e}"
            res.vats_remaining = 0
            res.open_units = 0
            return res

    def destroy_node(self):
        try:
            if self._pool is not None:
                self._pool.closeall()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = InventoryManagerNode()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    try:
        ex.spin()
    finally:
        ex.shutdown()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()