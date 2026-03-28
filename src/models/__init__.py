"""
Models package — import all ORM models so SQLAlchemy metadata is fully populated.
"""

# Tenant must be imported first: Customer and Order reference it via FK
from models.tenant import Tenant
from models.customer import Customer
from models.order import Order, OrderItem, OrderStatusHistory, OrderStatus
from models.auth import OTPCode, AuthAuditLog
from models.shipment import Shipment, ShipmentStatus
from models.product import Category, Product, ProductVariant, Inventory
from models.order_payment import OrderPayment
from models.coupon import Coupon, CouponUsage
from models.review import Review, SatisfactionSurvey
from models.loyalty import LoyaltyAccount, LoyaltyTransaction, LoyaltyReward
from models.billing import Subscription, Invoice

__all__ = [
    "Tenant",
    "Customer",
    "OTPCode",
    "AuthAuditLog",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "OrderStatus",
    "Shipment",
    "ShipmentStatus",
    "Category",
    "Product",
    "ProductVariant",
    "Inventory",
    "OrderPayment",
    "Coupon",
    "CouponUsage",
    "Review",
    "SatisfactionSurvey",
    "LoyaltyAccount",
    "LoyaltyTransaction",
    "LoyaltyReward",
    "Subscription",
    "Invoice",
]
