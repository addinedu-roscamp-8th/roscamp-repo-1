# Kitchmatic schema (database/schema.sql) - SQLAlchemy models
from sqlalchemy import Column, String, Integer, Boolean, Float, ForeignKey, DateTime, UniqueConstraint, CheckConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.models import Base


def gen_uuid():
    return uuid.uuid4()


class Menu(Base):
    __tablename__ = "menus"
    __table_args__ = (CheckConstraint("price >= 0", name="chk_price"),)

    id = Column(String(10), primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)
    available = Column(Boolean, default=True)
    description = Column(Text, default="", nullable=True)
    image_url = Column(String(500), default="", nullable=True)
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    unit = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    items_per_box = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (CheckConstraint("estimated_time_seconds > 0", name="chk_estimated_time"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    menu_id = Column(String(10), ForeignKey("menus.id"), nullable=False)
    name = Column(String(100), nullable=False)
    estimated_time_seconds = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())

    steps = relationship("RecipeStep", back_populates="recipe", cascade="all, delete-orphan")


class RecipeStep(Base):
    __tablename__ = "recipe_steps"
    __table_args__ = (
        CheckConstraint("robot_arm IN ('ARM_1', 'ARM_2')", name="chk_robot_arm"),
        CheckConstraint("step_order > 0", name="chk_step_order"),
        UniqueConstraint("recipe_id", "step_order", name="recipe_steps_recipe_id_step_order_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    ingredient_id = Column(String(10), ForeignKey("ingredients.id"))
    quantity = Column(Integer)
    unit = Column(String(20))
    robot_arm = Column(String(10), nullable=False)
    duration_seconds = Column(Integer)

    recipe = relationship("Recipe", back_populates="steps")


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("location IN ('STOCK_AREA', 'INGREDIENT_BED')", name="chk_location"),
        CheckConstraint("current_stock >= 0", name="chk_stock"),
        UniqueConstraint("ingredient_id", "location", name="inventory_ingredient_id_location_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    ingredient_id = Column(String(10), ForeignKey("ingredients.id"), nullable=False)
    location = Column(String(20), nullable=False)
    current_stock = Column(Integer, nullable=False, default=0)
    min_threshold = Column(Integer, nullable=False, default=2)
    max_capacity = Column(Integer, nullable=False, default=10)
    last_updated = Column(DateTime(timezone=False), nullable=False, server_default=func.now())


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('REPLENISHMENT', 'CONSUMPTION', 'REPLACEMENT')",
            name="chk_transaction_type",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    inventory_id = Column(UUID(as_uuid=True), ForeignKey("inventory.id"), nullable=False)
    transaction_type = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    before_stock = Column(Integer, nullable=False)
    after_stock = Column(Integer, nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"))
    robot_id = Column(UUID(as_uuid=True), ForeignKey("robots.id"))
    transaction_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())


class Robot(Base):
    __tablename__ = "robots"
    __table_args__ = (
        CheckConstraint(
            "type IN ('ARM_1', 'ARM_2', 'SERVING_BOT_1', 'SERVING_BOT_2', 'SERVING_BOT_3')",
            name="chk_robot_type",
        ),
        CheckConstraint(
            "status IN ('IDLE', 'BUSY', 'ERROR', 'HALTED')",
            name="chk_robot_status",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    name = Column(String(50), nullable=False, unique=True)
    type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="IDLE")
    ip_address = Column(String(15), nullable=False)
    port = Column(Integer, nullable=False)
    last_heartbeat = Column(DateTime(timezone=False))
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'PENDING', 'CONFIRMED', 'COOKING', 'READY', 'INSPECTED', "
            "'DELIVERING', 'DELIVERED', 'COMPLETED', 'CANCELLED', 'HALTED'"
            ")",
            name="chk_status",
        ),
        CheckConstraint("quantity > 0", name="chk_quantity"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    table_number = Column(String(10), nullable=False)
    menu_id = Column(String(10), ForeignKey("menus.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=False))
    voice_order = Column(Boolean, default=False)
    assigned_robot_arm_id = Column(UUID(as_uuid=True), ForeignKey("robots.id"))
    assigned_serving_bot_id = Column(UUID(as_uuid=True), ForeignKey("robots.id"))


class QualityCheckResult(Base):
    __tablename__ = "quality_check_results"
    __table_args__ = (
        CheckConstraint("status IN ('NORMAL', 'ABNORMAL')", name="chk_quality_status"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name="chk_confidence",
        ),
        CheckConstraint("attempt_number > 0", name="chk_attempt"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    status = Column(String(20), nullable=False)
    confidence_score = Column(Float)
    checked_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())
    attempt_number = Column(Integer, nullable=False, default=1)
    robot_arm_id = Column(UUID(as_uuid=True), ForeignKey("robots.id"))
