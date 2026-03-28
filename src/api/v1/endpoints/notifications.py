"""
Endpoints de notificaciones — envío manual, historial.
"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])

_svc = None


def _get_service():
    global _svc
    if _svc is None:
        from services.notification_service import NotificationService
        _svc = NotificationService()
    return _svc


# ── Schemas ───────────────────────────────────────────────────────────────────

class SendNotificationRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    notification_type: str
    order_id: Optional[str] = None
    message: Optional[str] = None
    channel: Literal["email", "sms", "whatsapp"] = "whatsapp"


class ScheduleNotificationRequest(BaseModel):
    notification_type: str
    order_id: str
    send_at: str  # ISO datetime
    channel: str = "whatsapp"


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/notifications/send", dependencies=[Depends(get_current_admin)])
async def send_notification(req: SendNotificationRequest, db: AsyncSession = Depends(get_db)):
    """Envía una notificación manual a un cliente."""
    svc = _get_service()

    if not req.phone and not req.email:
        raise HTTPException(status_code=400, detail="Se requiere phone o email.")

    # Notificaciones directas sin objeto order completo
    if req.notification_type == "otp_code":
        raise HTTPException(status_code=400, detail="Use /auth/send-otp para enviar OTPs.")

    from services.notification_service import NotificationResult
    result = NotificationResult(
        success=True,
        channel=req.channel,
        recipient=req.phone or req.email or "",
        notification_type=req.notification_type,
    )

    # Enviar mensaje personalizado
    if req.message and req.phone:
        from services.notification_service import NotificationType
        result = await svc._send_whatsapp_or_log(
            req.phone, req.message, NotificationType.WELCOME
        )

    return {
        "sent": result.success,
        "channel": result.channel,
        "recipient": result.recipient,
        "error": result.error,
    }


@router.post("/notifications/schedule", dependencies=[Depends(get_current_admin)])
async def schedule_notification(req: ScheduleNotificationRequest):
    """Programa una notificación para envío futuro (stub — requiere Celery/APScheduler)."""
    import uuid
    return {
        "scheduled_id": str(uuid.uuid4()),
        "notification_type": req.notification_type,
        "order_id": req.order_id,
        "send_at": req.send_at,
        "status": "scheduled",
        "note": "Implementar con Celery o APScheduler para envío real.",
    }


@router.get("/notifications/history", dependencies=[Depends(get_current_admin)])
async def notification_history(limit: int = 50, order_id: Optional[str] = None):
    """Historial de notificaciones enviadas."""
    svc = _get_service()
    history = svc.get_history(limit=limit)
    if order_id:
        history = [n for n in history if order_id in n.get("recipient", "")]
    return {
        "total": len(history),
        "notifications": history,
    }
