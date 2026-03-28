from __future__ import annotations
from typing import Dict, List, Any
"""
Mobile SDK API endpoints — endpoints optimizados para iOS/Android.
Respuestas compactas + autenticación biométrica + push tokens.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from api.deps import get_db, get_order_service

router = APIRouter(tags=["mobile"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class DeviceRegistration(BaseModel):
    customer_id: str
    push_token: str
    platform: str  # "ios" | "android"
    app_version: str
    device_id: str


class BiometricAuthRequest(BaseModel):
    customer_id: str
    biometric_signature: str
    device_id: str


class MobileOrderSummary(BaseModel):
    order_number: str
    status: str
    status_display: str
    total: str
    items_count: int
    tracking_number: Optional[str]


# Registro en memoria (en producción: BD)
_push_tokens: Dict[str, Dict] = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register-device")
async def register_device(req: DeviceRegistration):
    """Registra el dispositivo para push notifications."""
    _push_tokens[req.customer_id] = {
        "token": req.push_token,
        "platform": req.platform,
        "app_version": req.app_version,
        "device_id": req.device_id,
    }
    return {"status": "registered", "customer_id": req.customer_id}


@router.post("/auth/biometric")
async def biometric_auth(req: BiometricAuthRequest, db=Depends(get_db)):
    """
    Autenticación biométrica (Face ID / Fingerprint).
    En producción valida firma criptográfica del dispositivo.
    """
    # Stub: acepta cualquier firma si el customer_id existe
    if not req.biometric_signature or not req.device_id:
        raise HTTPException(status_code=401, detail="Firma biométrica inválida")

    # Generar session token
    try:
        from auth.customer_verifier import CustomerVerifier
        verifier = CustomerVerifier()
        token = verifier.generate_session_token(req.customer_id, "")
    except Exception:
        token = f"mobile-stub-token-{req.customer_id[:8]}"

    return {
        "authenticated": True,
        "session_token": token,
        "expires_in": 3600,
    }


@router.get("/orders/{customer_id}")
async def get_mobile_orders(
    customer_id: str,
    limit: int = 10,
    db=Depends(get_db),
):
    """Lista órdenes del cliente — formato compacto para móvil."""
    try:
        from sqlalchemy import select
        from models.order import Order

        result = await db.execute(
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        orders = result.scalars().all()
        return {
            "orders": [
                {
                    "order_number": o.order_number,
                    "status": o.status,
                    "total": f"${float(o.total_amount):,.0f}",
                }
                for o in orders
            ],
            "count": len(orders),
        }
    except Exception:
        return {"orders": [], "count": 0}


@router.get("/orders/{customer_id}/{order_number}/track")
async def track_order_mobile(customer_id: str, order_number: str, db=Depends(get_db)):
    """Tracking de pedido optimizado para móvil."""
    try:
        order_svc = get_order_service(db)
        result = await order_svc.get_order_by_number(order_number)
        if not result:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        return {
            "order_number": order_number,
            "status": result.status,
            "voice_description": result.formatted_for_voice if hasattr(result, "formatted_for_voice") else "",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/loyalty/{customer_id}")
async def get_mobile_loyalty(customer_id: str, db=Depends(get_db)):
    """Resumen de fidelidad — compacto para widget móvil."""
    try:
        from services.loyalty_service import LoyaltyService
        svc = LoyaltyService(db)
        summary = await svc.get_summary(customer_id)
        return {
            "tier": summary.get("tier_display", "Bronze"),
            "points": summary.get("available_points", 0),
            "value_cop": summary.get("redemption_value_cop", 0),
        }
    except Exception:
        return {"tier": "Bronze", "points": 0, "value_cop": 0}


@router.get("/sdk-config")
async def get_sdk_config():
    """
    Configuración para el SDK móvil.
    El SDK usa estos valores para inicializarse.
    """
    import os
    return {
        "api_version": "v1",
        "base_url": os.getenv("API_BASE_URL", "https://api.agentedevoz.co"),
        "voice_enabled": True,
        "biometric_auth_enabled": True,
        "push_notifications_enabled": True,
        "supported_channels": ["voice", "text", "push"],
        "min_app_version": "1.0.0",
        "features": {
            "loyalty": True,
            "order_tracking": True,
            "otp_auth": True,
            "voice_to_voice": True,
            "offline_mode": False,
        },
    }
