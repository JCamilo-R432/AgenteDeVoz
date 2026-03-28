from __future__ import annotations
"""
Loyalty / Fidelidad endpoints.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from api.deps import get_db, get_current_admin
from services.loyalty_service import LoyaltyService

router = APIRouter(tags=["loyalty"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class EarnRequest(BaseModel):
    customer_id: str
    order_amount: Decimal = Field(gt=0)
    order_id: str


class RedeemRequest(BaseModel):
    customer_id: str
    points: int = Field(gt=0)


class BonusRequest(BaseModel):
    customer_id: str
    points: int = Field(gt=0)
    reason: str


class ReferralRequest(BaseModel):
    referral_code: str
    new_customer_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{customer_id}/points")
async def get_loyalty_points(customer_id: str, db=Depends(get_db)):
    """Resumen de puntos y nivel del cliente."""
    svc = LoyaltyService(db)
    summary = await svc.get_summary(customer_id)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@router.get("/{customer_id}/history")
async def get_loyalty_history(customer_id: str, limit: int = 20, db=Depends(get_db)):
    """Historial de transacciones de puntos."""
    svc = LoyaltyService(db)
    return await svc.get_transaction_history(customer_id, limit=limit)


@router.get("/tiers")
async def get_tiers():
    """Información de todos los niveles de fidelidad."""
    svc = LoyaltyService(None)  # no DB needed
    return await svc.get_tiers_info()


@router.get("/{customer_id}/voice-summary")
async def get_voice_summary(customer_id: str, db=Depends(get_db)):
    """Resumen corto para respuesta de voz."""
    svc = LoyaltyService(db)
    summary = await svc.get_summary(customer_id)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return {"message": svc.get_voice_summary(summary)}


@router.post("/earn")
async def earn_points(req: EarnRequest, db=Depends(get_db)):
    """Acreditar puntos por una compra."""
    svc = LoyaltyService(db)
    result = await svc.earn_points_for_purchase(
        req.customer_id, req.order_amount, req.order_id
    )
    return {
        "points_earned": result.points_earned,
        "new_balance": result.new_balance,
        "tier": result.tier_after,
        "tier_upgraded": result.tier_upgraded,
        "message": result.message,
    }


@router.post("/redeem")
async def redeem_points(req: RedeemRequest, db=Depends(get_db)):
    """Canjear puntos por descuento."""
    svc = LoyaltyService(db)
    result = await svc.redeem_points(req.customer_id, req.points)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {
        "points_redeemed": result.points_redeemed,
        "discount_amount": float(result.discount_amount),
        "new_balance": result.new_balance,
        "message": result.message,
    }


@router.post("/referral")
async def process_referral(req: ReferralRequest, db=Depends(get_db)):
    """Procesar un referido y acreditar bonus a ambas partes."""
    svc = LoyaltyService(db)
    try:
        referrer_result, new_result = await svc.process_referral(
            req.referral_code, req.new_customer_id
        )
        return {
            "referrer_points_earned": referrer_result.points_earned,
            "new_customer_points_earned": new_result.points_earned,
            "message": "Referido procesado exitosamente.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bonus", dependencies=[Depends(get_current_admin)])
async def add_bonus(req: BonusRequest, db=Depends(get_db)):
    """[Admin] Agregar puntos de bonificación manualmente."""
    svc = LoyaltyService(db)
    result = await svc.add_bonus_points(req.customer_id, req.points, req.reason)
    return {"points_added": result.points_earned, "new_balance": result.new_balance}
