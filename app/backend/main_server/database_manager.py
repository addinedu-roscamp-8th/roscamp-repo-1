"""
Database Manager for Kitchmatic Main Server
Handles PostgreSQL connections and ORM models using SQLAlchemy
"""

from sqlalchemy import create_engine, Column, String, Integer, Boolean, Float, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import logging

Base = declarative_base()
logger = logging.getLogger(__name__)


# ========================================
# ORM Models
# ========================================

class Menu(Base):
    __tablename__ = 'menus'

    id = Column(String(10), primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Integer, nullable=False)
    category = Column(String(50), nullable=False)
    available = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint('price >= 0', name='chk_price'),
    )


class Ingredient(Base):
    __tablename__ = 'ingredients'

    id = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    unit = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    items_per_box = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Recipe(Base):
    __tablename__ = 'recipes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_id = Column(String(10), ForeignKey('menus.id'), nullable=False)
    name = Column(String(100), nullable=False)
    estimated_time_seconds = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    steps = relationship("RecipeStep", back_populates="recipe", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('estimated_time_seconds > 0', name='chk_estimated_time'),
    )


class RecipeStep(Base):
    __tablename__ = 'recipe_steps'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey('recipes.id', ondelete='CASCADE'), nullable=False)
    step_order = Column(Integer, nullable=False)
    action = Column(String(50), nullable=False)
    ingredient_id = Column(String(10), ForeignKey('ingredients.id'))
    quantity = Column(Integer)
    unit = Column(String(20))
    robot_arm = Column(String(10), nullable=False)
    duration_seconds = Column(Integer)

    recipe = relationship("Recipe", back_populates="steps")

    __table_args__ = (
        CheckConstraint("robot_arm IN ('ARM_1', 'ARM_2')", name='chk_robot_arm'),
        CheckConstraint('step_order > 0', name='chk_step_order'),
        UniqueConstraint('recipe_id', 'step_order'),
        Index('idx_recipe_steps_recipe', 'recipe_id'),
    )


class Inventory(Base):
    __tablename__ = 'inventory'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingredient_id = Column(String(10), ForeignKey('ingredients.id'), nullable=False)
    location = Column(String(20), nullable=False)
    current_stock = Column(Integer, nullable=False, default=0)
    min_threshold = Column(Integer, nullable=False, default=2)
    max_capacity = Column(Integer, nullable=False, default=10)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    transactions = relationship("InventoryTransaction", back_populates="inventory")

    __table_args__ = (
        CheckConstraint("location IN ('STOCK_AREA', 'INGREDIENT_BED')", name='chk_location'),
        CheckConstraint('current_stock >= 0', name='chk_stock'),
        UniqueConstraint('ingredient_id', 'location'),
    )


class InventoryTransaction(Base):
    __tablename__ = 'inventory_transactions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_id = Column(UUID(as_uuid=True), ForeignKey('inventory.id'), nullable=False)
    transaction_type = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    before_stock = Column(Integer, nullable=False)
    after_stock = Column(Integer, nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id'))
    robot_id = Column(UUID(as_uuid=True), ForeignKey('robots.id'))
    transaction_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    inventory = relationship("Inventory", back_populates="transactions")

    __table_args__ = (
        CheckConstraint("transaction_type IN ('REPLENISHMENT', 'CONSUMPTION', 'REPLACEMENT')", name='chk_transaction_type'),
        Index('idx_inv_trans_inventory', 'inventory_id'),
        Index('idx_inv_trans_time', 'transaction_at'),
    )


class Robot(Base):
    __tablename__ = 'robots'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False, unique=True)
    type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default='IDLE')
    ip_address = Column(String(15), nullable=False)
    port = Column(Integer, nullable=False)
    last_heartbeat = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("type IN ('ARM_1', 'ARM_2', 'SERVING_BOT_1', 'SERVING_BOT_2', 'SERVING_BOT_3')", name='chk_robot_type'),
        CheckConstraint("status IN ('IDLE', 'BUSY', 'ERROR', 'HALTED')", name='chk_robot_status'),
    )


class Order(Base):
    __tablename__ = 'orders'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_number = Column(String(10), nullable=False)
    menu_id = Column(String(10), ForeignKey('menus.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default='PENDING')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    voice_order = Column(Boolean, default=False)
    assigned_robot_arm_id = Column(UUID(as_uuid=True), ForeignKey('robots.id'))
    assigned_serving_bot_id = Column(UUID(as_uuid=True), ForeignKey('robots.id'))

    quality_checks = relationship("QualityCheckResult", back_populates="order")

    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'COOKING', 'READY', 'INSPECTED', 'DELIVERING', 'DELIVERED', 'COMPLETED', 'CANCELLED', 'HALTED')", name='chk_status'),
        CheckConstraint('quantity > 0', name='chk_quantity'),
        Index('idx_orders_status', 'status'),
        Index('idx_orders_table_number', 'table_number'),
        Index('idx_orders_created_at', 'created_at'),
    )


class QualityCheckResult(Base):
    __tablename__ = 'quality_check_results'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id'), nullable=False)
    status = Column(String(20), nullable=False)
    confidence_score = Column(Float)
    checked_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    attempt_number = Column(Integer, nullable=False, default=1)
    robot_arm_id = Column(UUID(as_uuid=True), ForeignKey('robots.id'))

    order = relationship("Order", back_populates="quality_checks")

    __table_args__ = (
        CheckConstraint("status IN ('NORMAL', 'ABNORMAL')", name='chk_quality_status'),
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 100', name='chk_confidence'),
        CheckConstraint('attempt_number > 0', name='chk_attempt'),
        Index('idx_quality_order', 'order_id'),
        Index('idx_quality_status', 'status'),
        Index('idx_quality_time', 'checked_at'),
    )


# ========================================
# Database Manager Class
# ========================================

class DatabaseManager:
    """
    Manages PostgreSQL database connections and operations
    """

    def __init__(self, db_host='localhost', db_port=5432, db_name='kitchmatic',
                 db_user='kitchmatic_user', db_password='your_password_here'):
        """
        Initialize database connection

        TODO: Configure these values in environment variables or config file:
        - db_host: Database server IP (default: localhost)
        - db_port: Database port (default: 5432)
        - db_name: Database name (default: kitchmatic)
        - db_user: Database user (default: kitchmatic_user)
        - db_password: Database password (TODO: Set secure password)
        """
        self.db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        self.engine = None
        self.Session = None

    def connect(self):
        """Establish database connection"""
        try:
            self.engine = create_engine(self.db_url, echo=False, pool_pre_ping=True)
            self.Session = sessionmaker(bind=self.engine)
            logger.info("Database connection established successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    def get_session(self):
        """Get a new database session"""
        if self.Session is None:
            raise Exception("Database not connected. Call connect() first.")
        return self.Session()

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")

    # ========================================
    # Order Operations
    # ========================================

    def create_order(self, table_number, menu_id, quantity=1, voice_order=False):
        """Create a new order"""
        session = self.get_session()
        try:
            order = Order(
                table_number=table_number,
                menu_id=menu_id,
                quantity=quantity,
                voice_order=voice_order,
                status='PENDING'
            )
            session.add(order)
            session.commit()
            order_id = order.id
            logger.info(f"Order created: {order_id} for table {table_number}")
            return order_id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create order: {e}")
            return None
        finally:
            session.close()

    def update_order_status(self, order_id, new_status, assigned_robot_arm_id=None, assigned_serving_bot_id=None):
        """Update order status"""
        session = self.get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            if order:
                order.status = new_status
                order.updated_at = datetime.utcnow()

                if assigned_robot_arm_id:
                    order.assigned_robot_arm_id = assigned_robot_arm_id
                if assigned_serving_bot_id:
                    order.assigned_serving_bot_id = assigned_serving_bot_id

                if new_status in ['COMPLETED', 'CANCELLED']:
                    order.completed_at = datetime.utcnow()

                session.commit()
                logger.info(f"Order {order_id} status updated to {new_status}")
                return True
            else:
                logger.warning(f"Order {order_id} not found")
                return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update order status: {e}")
            return False
        finally:
            session.close()

    def get_order(self, order_id):
        """Get order by ID"""
        session = self.get_session()
        try:
            order = session.query(Order).filter(Order.id == order_id).first()
            return order
        finally:
            session.close()

    def get_pending_orders(self):
        """Get all pending orders"""
        session = self.get_session()
        try:
            orders = session.query(Order).filter(Order.status == 'PENDING').order_by(Order.created_at).all()
            return orders
        finally:
            session.close()

    # ========================================
    # Robot Operations
    # ========================================

    def update_robot_status(self, robot_name, status, last_heartbeat=None):
        """Update robot status"""
        session = self.get_session()
        try:
            robot = session.query(Robot).filter(Robot.name == robot_name).first()
            if robot:
                robot.status = status
                if last_heartbeat:
                    robot.last_heartbeat = last_heartbeat
                else:
                    robot.last_heartbeat = datetime.utcnow()
                session.commit()
                logger.debug(f"Robot {robot_name} status updated to {status}")
                return True
            else:
                logger.warning(f"Robot {robot_name} not found")
                return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update robot status: {e}")
            return False
        finally:
            session.close()

    def get_robot_by_name(self, robot_name):
        """Get robot by name"""
        session = self.get_session()
        try:
            robot = session.query(Robot).filter(Robot.name == robot_name).first()
            return robot
        finally:
            session.close()

    def get_robots_by_type(self, robot_type):
        """Get all robots of a specific type"""
        session = self.get_session()
        try:
            robots = session.query(Robot).filter(Robot.type == robot_type).all()
            return robots
        finally:
            session.close()

    def get_idle_serving_bots(self):
        """Get all idle serving robots"""
        session = self.get_session()
        try:
            robots = session.query(Robot).filter(
                Robot.type.in_(['SERVING_BOT_1', 'SERVING_BOT_2', 'SERVING_BOT_3']),
                Robot.status == 'IDLE'
            ).all()
            return robots
        finally:
            session.close()

    # ========================================
    # Menu Operations
    # ========================================

    def get_menu(self, menu_id):
        """Get menu by ID"""
        session = self.get_session()
        try:
            menu = session.query(Menu).filter(Menu.id == menu_id).first()
            return menu
        finally:
            session.close()

    def get_available_menus(self):
        """Get all available menus"""
        session = self.get_session()
        try:
            menus = session.query(Menu).filter(Menu.available == True).all()
            return menus
        finally:
            session.close()

    # ========================================
    # Inventory Operations
    # ========================================

    def get_inventory(self, ingredient_id, location):
        """Get inventory for specific ingredient and location"""
        session = self.get_session()
        try:
            inventory = session.query(Inventory).filter(
                Inventory.ingredient_id == ingredient_id,
                Inventory.location == location
            ).first()
            return inventory
        finally:
            session.close()

    def update_inventory(self, ingredient_id, location, quantity_change, transaction_type, order_id=None, robot_id=None):
        """Update inventory and record transaction"""
        session = self.get_session()
        try:
            inventory = session.query(Inventory).filter(
                Inventory.ingredient_id == ingredient_id,
                Inventory.location == location
            ).first()

            if inventory:
                before_stock = inventory.current_stock
                after_stock = before_stock + quantity_change

                if after_stock < 0:
                    logger.error(f"Insufficient stock for {ingredient_id} at {location}")
                    return False

                inventory.current_stock = after_stock
                inventory.last_updated = datetime.utcnow()

                transaction = InventoryTransaction(
                    inventory_id=inventory.id,
                    transaction_type=transaction_type,
                    quantity=abs(quantity_change),
                    before_stock=before_stock,
                    after_stock=after_stock,
                    order_id=order_id,
                    robot_id=robot_id
                )
                session.add(transaction)
                session.commit()

                logger.info(f"Inventory updated: {ingredient_id} at {location}, {before_stock} -> {after_stock}")
                return True
            else:
                logger.warning(f"Inventory not found: {ingredient_id} at {location}")
                return False
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update inventory: {e}")
            return False
        finally:
            session.close()

    def check_low_stock(self):
        """Check for low stock items"""
        session = self.get_session()
        try:
            low_stock = session.query(Inventory).filter(
                Inventory.current_stock <= Inventory.min_threshold
            ).all()
            return low_stock
        finally:
            session.close()

    # ========================================
    # Quality Check Operations
    # ========================================

    def create_quality_check(self, order_id, status, confidence_score=None, attempt_number=1, robot_arm_id=None):
        """Record quality check result"""
        session = self.get_session()
        try:
            quality_check = QualityCheckResult(
                order_id=order_id,
                status=status,
                confidence_score=confidence_score,
                attempt_number=attempt_number,
                robot_arm_id=robot_arm_id
            )
            session.add(quality_check)
            session.commit()
            logger.info(f"Quality check recorded for order {order_id}: {status}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to record quality check: {e}")
            return False
        finally:
            session.close()
