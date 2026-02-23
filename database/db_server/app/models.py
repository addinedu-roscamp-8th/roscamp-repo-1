from sqlalchemy import Column, String, Numeric, DateTime, Text, ForeignKey, Index, Boolean, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()


class StoreOrder(Base):
    __tablename__ = 'store_order'
    
    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default='placed')
    customer_name = Column(Text)
    customer_phone = Column(Text)
    items = Column(JSONB, nullable=False)
    currency = Column(Text)
    total_amount = Column(Numeric(10, 2))
    payment_status = Column(Text)
    ordered_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    meta = Column(JSONB)
    
    __table_args__ = (
        Index('idx_store_order_ordered_at', 'ordered_at'),
        Index('idx_store_order_status', 'status'),
    )


class StoreInventoryTxn(Base):
    __tablename__ = 'store_inventory_txn'
    
    inventory_txn_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sku = Column(Text, nullable=False)
    display_name = Column(Text)
    unit = Column(Text)
    qty_delta = Column(Numeric(10, 2), nullable=False)
    txn_type = Column(Text, nullable=False)  # in/out/adjust/waste/return
    reason = Column(Text)
    order_id = Column(UUID(as_uuid=True), ForeignKey('store_order.order_id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meta = Column(JSONB)
    
    __table_args__ = (
        Index('idx_store_inventory_txn_occurred_at', 'occurred_at'),
        Index('idx_store_inventory_txn_sku', 'sku'),
        Index('idx_store_inventory_txn_order_id', 'order_id'),
        Index('idx_store_inventory_txn_type', 'txn_type'),
    )


class StoreIngredientMst(Base):
    __tablename__ = 'store_ingredient_mst'
    
    ingredient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingredient_sku = Column(Text, unique=True, nullable=False)
    ingredient_name = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    base_unit = Column(Text, nullable=False, default='g')
    is_active = Column(Boolean, nullable=False, default=True)
    meta = Column(JSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_ingredient_category', 'category'),
    )


class StoreIngredientTxn(Base):
    __tablename__ = 'store_ingredient_txn'
    
    ingredient_txn_id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4, primary_key=True)
    ingredient_sku = Column(Text, ForeignKey('store_ingredient_mst.ingredient_sku'), nullable=False)
    unit = Column(Text, nullable=False, default='g')
    qty_delta = Column(Numeric(12, 3), nullable=False)
    txn_type = Column(Text, nullable=False)  # in/out/waste/adjust
    reason = Column(Text)
    order_id = Column(UUID(as_uuid=True), ForeignKey('store_order.order_id'))
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meta = Column(JSONB, nullable=False, default={})
    
    __table_args__ = (
        Index('idx_ing_txn_sku_time', 'ingredient_sku', 'occurred_at'),
        Index('idx_ing_txn_order', 'order_id'),
        Index('idx_ing_txn_type_time', 'txn_type', 'occurred_at'),
    )


class StoreMenuRecipeBom(Base):
    __tablename__ = 'store_menu_recipe_bom'
    
    menu_sku = Column(Text, nullable=False, primary_key=True)
    ingredient_sku = Column(Text, ForeignKey('store_ingredient_mst.ingredient_sku'), nullable=False, primary_key=True)
    qty_per_menu = Column(Numeric(12, 3), nullable=False)
    
    __table_args__ = (
        Index('idx_bom_menu', 'menu_sku'),
    )
