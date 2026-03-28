"""
CouponService — validación, aplicación y estadísticas de cupones.
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class CouponValidationResult:
    valid: bool
    coupon=None
    discount_amount: Decimal = Decimal("0")
    message: str = ""
    error_code: str = ""


class CouponService:
    """Servicio de cupones y descuentos."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def validate_coupon(
        self,
        code: str,
        customer_id: str,
        order_amount: Decimal,
        category_ids: Optional[List[str]] = None,
    ) -> CouponValidationResult:
        """Valida un cupón de forma completa."""
        from models.coupon import Coupon, CouponUsage

        result = await self.session.execute(
            select(Coupon).where(Coupon.code == code.upper().strip())
        )
        coupon = result.scalar_one_or_none()

        if not coupon:
            return CouponValidationResult(False, error_code="not_found",
                                          message="Cupón no encontrado.")

        if not coupon.is_active:
            return CouponValidationResult(False, error_code="inactive",
                                          message="Este cupón no está activo.")

        now_str = datetime.now(timezone.utc).isoformat()
        if coupon.valid_from and now_str < coupon.valid_from:
            return CouponValidationResult(False, error_code="not_yet_valid",
                                          message="Este cupón aún no está vigente.")

        if coupon.valid_until and now_str > coupon.valid_until:
            return CouponValidationResult(False, error_code="expired",
                                          message="Este cupón ha expirado.")

        if coupon.usage_limit and coupon.usage_count >= coupon.usage_limit:
            return CouponValidationResult(False, error_code="limit_reached",
                                          message="Este cupón ya alcanzó su límite de usos.")

        if coupon.min_purchase_amount and order_amount < coupon.min_purchase_amount:
            return CouponValidationResult(
                False, error_code="min_purchase",
                message=f"Compra mínima de ${float(coupon.min_purchase_amount):,.0f} COP requerida."
            )

        # Límite por cliente
        usage_result = await self.session.execute(
            select(func.count(CouponUsage.id)).where(
                CouponUsage.coupon_id == coupon.id,
                CouponUsage.customer_id == customer_id,
            )
        )
        customer_uses = usage_result.scalar() or 0
        limit_per = coupon.usage_limit_per_customer or 1
        if customer_uses >= limit_per:
            return CouponValidationResult(False, error_code="already_used",
                                          message="Ya usaste este cupón el máximo de veces permitido.")

        # Restricción por categoría
        if coupon.applicable_categories and category_ids:
            overlap = set(coupon.applicable_categories) & set(category_ids)
            if not overlap:
                return CouponValidationResult(False, error_code="category_restriction",
                                              message="Este cupón no aplica para los productos de tu carrito.")

        discount = self.calculate_discount(coupon, order_amount)
        return CouponValidationResult(
            valid=True,
            coupon=coupon,
            discount_amount=discount,
            message=f"Cupón válido. Descuento: ${float(discount):,.0f} COP.",
        )

    async def apply_coupon(
        self, code: str, customer_id: str, order_id: str, order_amount: Decimal
    ) -> CouponValidationResult:
        """Valida y aplica un cupón (lo marca como usado)."""
        from models.coupon import Coupon, CouponUsage

        validation = await self.validate_coupon(code, customer_id, order_amount)
        if not validation.valid:
            return validation

        coupon = validation.coupon

        # Registrar uso
        usage = CouponUsage(
            id=str(uuid.uuid4()),
            coupon_id=coupon.id,
            customer_id=customer_id,
            order_id=order_id,
            discount_applied=validation.discount_amount,
        )
        coupon.usage_count = (coupon.usage_count or 0) + 1
        self.session.add(usage)
        await self.session.commit()

        logger.info(f"Cupón {code} aplicado a orden {order_id}: descuento ${float(validation.discount_amount):,.0f}")
        return validation

    async def get_active_promotions(self):
        """Retorna todos los cupones activos."""
        from models.coupon import Coupon
        now_str = datetime.now(timezone.utc).isoformat()
        result = await self.session.execute(
            select(Coupon).where(
                Coupon.is_active == True,
                Coupon.valid_from <= now_str,
            )
        )
        coupons = result.scalars().all()
        return [c for c in coupons if not c.valid_until or c.valid_until >= now_str]

    async def create_coupon(self, data: dict):
        """Crea un nuevo cupón."""
        from models.coupon import Coupon
        coupon = Coupon(
            id=str(uuid.uuid4()),
            code=data["code"].upper().strip(),
            name=data["name"],
            type=data["type"],
            value=Decimal(str(data["value"])),
            description=data.get("description"),
            min_purchase_amount=data.get("min_purchase_amount"),
            max_discount_amount=data.get("max_discount_amount"),
            valid_from=data.get("valid_from", datetime.now(timezone.utc).isoformat()),
            valid_until=data.get("valid_until"),
            usage_limit=data.get("usage_limit"),
            usage_limit_per_customer=data.get("usage_limit_per_customer", 1),
        )
        self.session.add(coupon)
        await self.session.commit()
        await self.session.refresh(coupon)
        return coupon

    async def get_usage_stats(self, coupon_id: str) -> dict:
        """Estadísticas de uso de un cupón."""
        from models.coupon import Coupon, CouponUsage

        result = await self.session.execute(select(Coupon).where(Coupon.id == coupon_id))
        coupon = result.scalar_one_or_none()
        if not coupon:
            return {}

        stats_result = await self.session.execute(
            select(
                func.count(CouponUsage.id).label("total_uses"),
                func.sum(CouponUsage.discount_applied).label("total_discount"),
            ).where(CouponUsage.coupon_id == coupon_id)
        )
        row = stats_result.one()
        return {
            "coupon_code": coupon.code,
            "usage_count": coupon.usage_count,
            "total_uses": row.total_uses or 0,
            "total_discount_given": float(row.total_discount or 0),
        }

    def calculate_discount(self, coupon, order_amount: Decimal) -> Decimal:
        """Calcula el monto de descuento real."""
        if coupon.type == "percentage":
            discount = order_amount * coupon.value / Decimal("100")
            if coupon.max_discount_amount:
                discount = min(discount, coupon.max_discount_amount)
            return discount.quantize(Decimal("0.01"))
        elif coupon.type == "fixed_amount":
            return min(coupon.value, order_amount)
        elif coupon.type == "free_shipping":
            return Decimal("15000")  # Valor promedio de envío en Colombia
        return Decimal("0")
