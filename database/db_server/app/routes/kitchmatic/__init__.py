# Kitchmatic REST API (schema.sql) - /kitchmatic prefix
from .menus import bp as menus_bp
from .ingredients import bp as ingredients_bp
from .recipes import bp as recipes_bp
from .robots import bp as robots_bp
from .inventory import bp as inventory_bp, bp_txn as inventory_txn_bp
from .orders import bp as orders_bp
from .quality_checks import bp as quality_checks_bp

__all__ = [
    "menus_bp",
    "ingredients_bp",
    "recipes_bp",
    "robots_bp",
    "inventory_bp",
    "inventory_txn_bp",
    "orders_bp",
    "quality_checks_bp",
]
