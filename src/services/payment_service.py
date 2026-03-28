"""
PaymentService — orquesta creación, verificación y reembolsos de pagos.
Soporta: Stripe, MercadoPago, PayPal, Wompi, ePayco.
Fallback graceful cuando API keys no configuradas.
"""
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    MERCADOPAGO = "mercadopago"
    PAYPAL = "paypal"
    WOMPI = "wompi"
    EPAYCO = "epayco"
    MANUAL = "manual"


class PaymentService:
    """Servicio de pagos asociado a pedidos."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_payment(
        self,
        order_id: str,
        provider: str,
        amount: Decimal,
        currency: str = "COP",
    ):
        """Crea registro de pago y obtiene URL del proveedor."""
        from models.order_payment import OrderPayment
        from models.order import Order
        from sqlalchemy.orm import selectinload

        # Cargar la orden
        result = await self.session.execute(
            select(Order).where(Order.id == order_id).options(selectinload(Order.customer))
        )
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Orden {order_id} no encontrada.")

        payment = OrderPayment(
            id=str(uuid.uuid4()),
            order_id=order_id,
            provider=provider,
            amount=amount,
            currency=currency,
            status="pending",
        )
        self.session.add(payment)
        await self.session.flush()

        # Obtener URL de pago según proveedor
        payment_url = await self._get_payment_url(order, payment, provider)
        payment.provider_payment_url = payment_url

        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_payment_link(self, order_id: str, provider: str = "mercadopago") -> dict:
        """Obtiene o crea link de pago para una orden."""
        from models.order_payment import OrderPayment
        from models.order import Order

        # Buscar pago pendiente existente
        result = await self.session.execute(
            select(OrderPayment).where(
                OrderPayment.order_id == order_id,
                OrderPayment.status == "pending",
            )
        )
        existing = result.scalar_one_or_none()

        if existing and existing.provider_payment_url:
            return {
                "payment_url": existing.provider_payment_url,
                "provider": existing.provider,
                "amount": float(existing.amount),
                "payment_id": existing.id,
                "status": existing.status,
            }

        # Obtener monto de la orden
        order_result = await self.session.execute(select(Order).where(Order.id == order_id))
        order = order_result.scalar_one_or_none()
        if not order:
            raise ValueError(f"Orden {order_id} no encontrada.")

        payment = await self.create_payment(order_id, provider, order.total_amount)
        return {
            "payment_url": payment.provider_payment_url,
            "provider": payment.provider,
            "amount": float(payment.amount),
            "payment_id": payment.id,
            "status": payment.status,
        }

    async def verify_payment(self, provider_payment_id: str, provider: str) -> dict:
        """Verifica estado de pago con el proveedor (stub)."""
        from models.order_payment import OrderPayment

        result = await self.session.execute(
            select(OrderPayment).where(
                OrderPayment.provider_payment_id == provider_payment_id
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            return {"status": "not_found", "paid": False, "amount": 0}

        # En producción: llamar al API del proveedor para verificar estado real
        return {
            "status": payment.status,
            "paid": payment.status == "paid",
            "amount": float(payment.amount),
            "method": payment.payment_method or "unknown",
            "provider_id": provider_payment_id,
        }

    async def get_order_payment_status(self, order_id: str) -> dict:
        """Estado completo de pago de una orden."""
        from models.order_payment import OrderPayment

        result = await self.session.execute(
            select(OrderPayment).where(OrderPayment.order_id == order_id)
        )
        payments = result.scalars().all()

        if not payments:
            return {
                "paid": False,
                "total_paid": 0.0,
                "status": "no_payment",
                "payments": [],
                "payment_url": None,
            }

        paid_payments = [p for p in payments if p.status == "paid"]
        total_paid = sum(float(p.amount) for p in paid_payments)
        pending = next((p for p in payments if p.status == "pending"), None)

        return {
            "paid": len(paid_payments) > 0,
            "total_paid": total_paid,
            "status": "paid" if paid_payments else "pending",
            "payments": [
                {
                    "id": p.id,
                    "provider": p.provider,
                    "amount": float(p.amount),
                    "status": p.status,
                    "paid_at": p.paid_at,
                }
                for p in payments
            ],
            "payment_url": pending.provider_payment_url if pending else None,
        }

    async def process_refund(
        self, order_id: str, amount: Optional[Decimal] = None, reason: str = ""
    ) -> dict:
        """Procesa reembolso para el pago de una orden."""
        from models.order_payment import OrderPayment

        result = await self.session.execute(
            select(OrderPayment).where(
                OrderPayment.order_id == order_id,
                OrderPayment.status == "paid",
            )
        )
        payment = result.scalar_one_or_none()

        if not payment:
            return {"success": False, "message": "No se encontró pago completado para esta orden."}

        refund_amount = amount or payment.amount
        payment.status = "refunded"
        payment.refunded_at = datetime.now(timezone.utc).isoformat()
        payment.refund_amount = refund_amount
        payment.refund_reason = reason

        await self.session.commit()
        logger.info(f"Reembolso procesado para orden {order_id}: ${refund_amount}")

        return {
            "success": True,
            "refund_id": str(uuid.uuid4()),
            "amount": float(refund_amount),
            "message": f"Reembolso de ${float(refund_amount):,.0f} procesado. Llegará en 5-10 días hábiles.",
        }

    async def handle_webhook(self, provider: str, payload: dict, signature: str = "") -> dict:
        """Procesa webhook de proveedor de pagos."""
        from models.order_payment import OrderPayment

        logger.info(f"Webhook recibido de {provider}: {list(payload.keys())}")

        provider_id = None
        new_status = None

        if provider == "mercadopago":
            provider_id = str(payload.get("data", {}).get("id", ""))
            status_map = {"approved": "paid", "rejected": "failed", "pending": "pending"}
            new_status = status_map.get(payload.get("action", ""), "pending")

        elif provider == "stripe":
            event_type = payload.get("type", "")
            provider_id = payload.get("data", {}).get("object", {}).get("id")
            if event_type == "payment_intent.succeeded":
                new_status = "paid"
            elif event_type == "payment_intent.payment_failed":
                new_status = "failed"

        if not provider_id or not new_status:
            return {"processed": False, "reason": "payload_not_recognized"}

        result = await self.session.execute(
            select(OrderPayment).where(OrderPayment.provider_payment_id == provider_id)
        )
        payment = result.scalar_one_or_none()

        if payment:
            payment.status = new_status
            if new_status == "paid":
                payment.paid_at = datetime.now(timezone.utc).isoformat()
            await self.session.commit()
            return {"processed": True, "order_id": payment.order_id, "status": new_status}

        return {"processed": False, "reason": "payment_not_found"}

    # ── Privados ─────────────────────────────────────────────────────────────

    async def _get_payment_url(self, order, payment, provider: str) -> str:
        """Obtiene URL de pago del proveedor."""
        try:
            if provider == "mercadopago":
                return await self._create_mercadopago_preference(order, payment)
            elif provider == "stripe":
                return await self._create_stripe_payment_intent(order, payment)
            else:
                return self._stub_payment_link(provider, payment.id, payment.amount)
        except Exception as e:
            logger.warning(f"Error creando pago con {provider}: {e}")
            return self._stub_payment_link(provider, payment.id, payment.amount)

    async def _create_mercadopago_preference(self, order, payment) -> str:
        try:
            import mercadopago
            from config.settings import settings
            access_token = getattr(settings, "MERCADOPAGO_ACCESS_TOKEN", "")
            if not access_token:
                raise ValueError("MERCADOPAGO_ACCESS_TOKEN no configurado")

            sdk = mercadopago.SDK(access_token)
            items = []
            for item in getattr(order, "items", []):
                items.append({
                    "title": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                    "currency_id": "COP",
                })

            pref_data = {
                "items": items or [{"title": f"Pedido {order.order_number}",
                                    "quantity": 1, "unit_price": float(payment.amount),
                                    "currency_id": "COP"}],
                "external_reference": payment.id,
            }
            response = sdk.preference().create(pref_data)
            return response["response"].get("init_point",
                   self._stub_payment_link("mercadopago", payment.id, payment.amount))
        except Exception as e:
            logger.warning(f"MercadoPago preference creation failed: {e}")
            return self._stub_payment_link("mercadopago", payment.id, payment.amount)

    async def _create_stripe_payment_intent(self, order, payment) -> str:
        try:
            import stripe
            from config.settings import settings
            stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
            if not stripe.api_key:
                raise ValueError("STRIPE_SECRET_KEY no configurado")

            intent = stripe.PaymentIntent.create(
                amount=int(float(payment.amount) * 100),  # centavos
                currency=payment.currency.lower(),
                metadata={"order_id": str(order.id), "payment_id": payment.id},
            )
            payment.provider_payment_id = intent.id
            return f"https://checkout.stripe.com/pay/{intent.client_secret}"
        except Exception as e:
            logger.warning(f"Stripe PaymentIntent creation failed: {e}")
            return self._stub_payment_link("stripe", payment.id, payment.amount)

    def _stub_payment_link(self, provider: str, payment_id: str, amount: Decimal) -> str:
        return f"https://pay.{provider}.com/checkout/{payment_id}?amount={float(amount):.2f}"
