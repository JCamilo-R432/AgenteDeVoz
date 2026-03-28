"""Modelos de Producto, Variante e Inventario."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import relationship

from database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    parent_id = Column(String(36), ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(String(36), ForeignKey("categories.id"), nullable=True)
    base_price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="COP")
    weight_kg = Column(Numeric(6, 3), nullable=True)
    is_active = Column(Boolean, default=True)
    metadata_json = Column("metadata", JSON, nullable=True)

    category = relationship("Category", back_populates="products")
    inventory = relationship("Inventory", back_populates="product", uselist=False,
                             primaryjoin="and_(Product.id==Inventory.product_id, Inventory.variant_id==None)")
    variants = relationship("ProductVariant", back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    price_modifier = Column(Numeric(10, 2), default=0)
    attributes = Column(JSON, nullable=True)

    product = relationship("Product", back_populates="variants")
    inventory = relationship("Inventory", back_populates="variant", uselist=False)


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.id"), nullable=True, index=True)
    variant_id = Column(String(36), ForeignKey("product_variants.id"), nullable=True)
    quantity_available = Column(Integer, default=0)
    quantity_reserved = Column(Integer, default=0)
    quantity_minimum = Column(Integer, default=5)
    warehouse_location = Column(String(100), nullable=True)
    last_restocked_at = Column(String(30), nullable=True)

    product = relationship("Product", back_populates="inventory",
                           foreign_keys=[product_id])
    variant = relationship("ProductVariant", back_populates="inventory")

    @property
    def quantity_actual(self) -> int:
        return max(0, (self.quantity_available or 0) - (self.quantity_reserved or 0))

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_actual <= (self.quantity_minimum or 5)

    @property
    def is_in_stock(self) -> bool:
        return self.quantity_actual > 0
