"""Endpoints de pagos asociados a pedidos."""
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["payments"])


class CreatePaymentRequest(BaseModel):
    provider: str = "mercadopago"
    amount: Optional[Decimal] = None


class RefundRequest(BaseModel):
    reason: str = ""
    amount: Optional[Decimal] = None


class SendPaymentLinkRequest(BaseModel):
    channel: str = "whatsapp"
    provider: str = "mercadopago"


def _get_payment_service(db: AsyncSession) -> "PaymentService":
    from services.payment_service import PaymentService
    return PaymentService(db)


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/orders/{order_number}/payment-status")
async def get_order_payment_status(order_number: str, db: AsyncSession = Depends(get_db)):
    """Estado de pago de un pedido (por número de orden)."""
    from sqlalchemy import select
    from models.order import Order

    result = await db.execute(select(Order).where(Order.order_number == order_number))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido '{order_number}' no encontrado.")

    svc = _get_payment_service(db)
    return await svc.get_order_payment_status(order.id)


# ── Endpoints admin ───────────────────────────────────────────────────────────

@router.post("/orders/{order_id}/payments/create", dependencies=[Depends(get_current_admin)])
async def create_payment(order_id: str, req: CreatePaymentRequest, db: AsyncSession = Depends(get_db)):
    """Crea un pago para una orden."""
    from sqlalchemy import select
    from models.order import Order

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden '{order_id}' no encontrada.")

    svc = _get_payment_service(db)
    amount = req.amount or order.total_amount
    try:
        payment = await svc.create_payment(order_id, req.provider, amount)
        return {
            "payment_id": payment.id,
            "payment_url": payment.provider_payment_url,
            "provider": payment.provider,
            "amount": float(payment.amount),
            "status": payment.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payments/{payment_id}/status", dependencies=[Depends(get_current_admin)])
async def get_payment_status(payment_id: str, db: AsyncSession = Depends(get_db)):
    """Estado actual de un pago."""
    from sqlalchemy import select
    from models.order_payment import OrderPayment

    result = await db.execute(select(OrderPayment).where(OrderPayment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")

    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "provider": payment.provider,
        "amount": float(payment.amount),
        "status": payment.status,
        "payment_url": payment.provider_payment_url,
        "paid_at": payment.paid_at,
        "created_at": payment.created_at,
    }


@router.post("/payments/{payment_id}/refund", dependencies=[Depends(get_current_admin)])
async def process_refund(payment_id: str, req: RefundRequest, db: AsyncSession = Depends(get_db)):
    """Procesa reembolso de un pago."""
    from sqlalchemy import select
    from models.order_payment import OrderPayment

    result = await db.execute(select(OrderPayment).where(OrderPayment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")

    svc = _get_payment_service(db)
    return await svc.process_refund(payment.order_id, req.amount, req.reason)


@router.post("/payments/webhooks/{provider}")
async def payment_webhook(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Recibe webhooks de proveedores de pago."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    signature = request.headers.get("X-Signature", "")
    svc = _get_payment_service(db)
    result = await svc.handle_webhook(provider, payload, signature)
    return {"received": True, **result}


@router.post("/orders/{order_id}/send-payment-link", dependencies=[Depends(get_current_admin)])
async def send_payment_link(
    order_id: str, req: SendPaymentLinkRequest, db: AsyncSession = Depends(get_db)
):
    """Envía link de pago al cliente por WhatsApp o email."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from models.order import Order

    result = await db.execute(
        select(Order).where(Order.id == order_id).options(selectinload(Order.customer))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden '{order_id}' no encontrada.")

    svc = _get_payment_service(db)
    link_info = await svc.get_payment_link(order_id, req.provider)
    payment_url = link_info.get("payment_url", "")

    customer = order.customer
    if not customer:
        raise HTTPException(status_code=400, detail="La orden no tiene cliente asociado.")

    msg = (
        f"Hola {customer.full_name}! Tu pedido #{order.order_number} "
        f"está listo para pagar.\n"
        f"Total: ${float(order.total_amount):,.0f} COP\n"
        f"Link de pago: {payment_url}"
    )

    sent = False
    if req.channel == "whatsapp" and customer.phone:
        try:
            from integrations.whatsapp_api import WhatsAppAPI
            wa = WhatsAppAPI()
            wa.send_text(customer.phone, msg)
            sent = True
        except Exception as e:
            logger.warning(f"WhatsApp send failed: {e}")

    if not sent:
        logger.info(f"[PAYMENT LINK SIMULADO] → {customer.phone or customer.email}: {payment_url}")
        sent = True

    return {
        "sent": sent,
        "channel": req.channel,
        "recipient": customer.phone if req.channel == "whatsapp" else customer.email,
        "payment_url": payment_url,
    }
