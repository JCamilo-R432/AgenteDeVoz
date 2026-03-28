"""Endpoints de cupones y descuentos."""
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["coupons"])


class ValidateCouponRequest(BaseModel):
    customer_id: str
    order_amount: Decimal


class ApplyCouponRequest(BaseModel):
    customer_id: str
    order_id: str
    order_amount: Decimal


class CreateCouponRequest(BaseModel):
    code: str
    name: str
    type: str  # percentage / fixed_amount / free_shipping
    value: Decimal
    description: Optional[str] = None
    min_purchase_amount: Optional[Decimal] = None
    max_discount_amount: Optional[Decimal] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    usage_limit: Optional[int] = None
    usage_limit_per_customer: int = 1


def _get_service(db: AsyncSession):
    from services.coupon_service import CouponService
    return CouponService(db)


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/{code}/validate")
async def validate_coupon(
    code: str, customer_id: str, order_amount: Decimal, db: AsyncSession = Depends(get_db)
):
    """Valida un cupón sin aplicarlo."""
    svc = _get_service(db)
    result = await svc.validate_coupon(code, customer_id, order_amount)
    coupon_name = result.coupon.name if result.coupon else ""
    coupon_type = result.coupon.type if result.coupon else ""
    return {
        "valid": result.valid,
        "discount_amount": float(result.discount_amount),
        "message": result.message,
        "error_code": result.error_code,
        "coupon_name": coupon_name,
        "coupon_type": coupon_type,
    }


@router.post("/apply")
async def apply_coupon(req: ApplyCouponRequest, code: str, db: AsyncSession = Depends(get_db)):
    """Aplica un cupón a una orden."""
    svc = _get_service(db)
    result = await svc.apply_coupon(code, req.customer_id, req.order_id, req.order_amount)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.message)
    return {
        "applied": True,
        "discount_amount": float(result.discount_amount),
        "message": result.message,
    }


@router.get("/promotions/active")
async def get_active_promotions(db: AsyncSession = Depends(get_db)):
    """Lista promociones activas."""
    svc = _get_service(db)
    coupons = await svc.get_active_promotions()
    return [
        {
            "code": c.code,
            "name": c.name,
            "description": c.description,
            "type": c.type,
            "value": float(c.value),
            "valid_until": c.valid_until,
        }
        for c in coupons
    ]


# ── Endpoints admin ───────────────────────────────────────────────────────────

@router.post("/", dependencies=[Depends(get_current_admin)], status_code=201)
async def create_coupon(req: CreateCouponRequest, db: AsyncSession = Depends(get_db)):
    """Crea un nuevo cupón."""
    from datetime import datetime, timezone
    svc = _get_service(db)
    data = req.model_dump()
    if not data.get("valid_from"):
        data["valid_from"] = datetime.now(timezone.utc).isoformat()
    coupon = await svc.create_coupon(data)
    return {"id": coupon.id, "code": coupon.code, "name": coupon.name, "type": coupon.type}


@router.get("/", dependencies=[Depends(get_current_admin)])
async def list_coupons(db: AsyncSession = Depends(get_db)):
    """Lista todos los cupones."""
    from models.coupon import Coupon
    result = await db.execute(select(Coupon).order_by(Coupon.is_active.desc()))
    coupons = result.scalars().all()
    return [
        {
            "id": c.id, "code": c.code, "name": c.name, "type": c.type,
            "value": float(c.value), "is_active": c.is_active,
            "usage_count": c.usage_count, "usage_limit": c.usage_limit,
            "valid_until": c.valid_until,
        }
        for c in coupons
    ]


@router.get("/{code}/stats", dependencies=[Depends(get_current_admin)])
async def coupon_stats(code: str, db: AsyncSession = Depends(get_db)):
    """Estadísticas de uso de un cupón."""
    from models.coupon import Coupon
    result = await db.execute(select(Coupon).where(Coupon.code == code.upper()))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail=f"Cupón '{code}' no encontrado.")

    svc = _get_service(db)
    return await svc.get_usage_stats(coupon.id)


@router.delete("/{code}", dependencies=[Depends(get_current_admin)])
async def deactivate_coupon(code: str, db: AsyncSession = Depends(get_db)):
    """Desactiva un cupón."""
    from models.coupon import Coupon
    result = await db.execute(select(Coupon).where(Coupon.code == code.upper()))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail=f"Cupón '{code}' no encontrado.")
    coupon.is_active = False
    await db.commit()
    return {"code": code, "deactivated": True}


@router.post("/orders/{order_id}/apply-discount", dependencies=[Depends(get_current_admin)])
async def apply_manual_discount(order_id: str, amount: Decimal, reason: str = "", db: AsyncSession = Depends(get_db)):
    """Aplica descuento manual a una orden (admin)."""
    from sqlalchemy import select
    from models.order import Order
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden '{order_id}' no encontrada.")

    # Aplicar descuento directamente al total
    order.total_amount = max(Decimal("0"), order.total_amount - amount)
    if not order.metadata_json:
        order.metadata_json = {}
    order.metadata_json["manual_discount"] = float(amount)
    order.metadata_json["discount_reason"] = reason
    await db.commit()
    return {
        "order_id": order_id,
        "discount_applied": float(amount),
        "new_total": float(order.total_amount),
        "reason": reason,
    }
