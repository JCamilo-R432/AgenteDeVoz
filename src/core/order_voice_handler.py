from __future__ import annotations
"""
OrderVoiceHandler — mixin/helper that adds order query capability to the voice agent.
Can be mixed into CustomerServiceAgent or used standalone.
"""


import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OrderVoiceHandler:
    """
    Provides order query methods for the voice agent.
    Can be mixed into CustomerServiceAgent or called standalone.
    """

    async def handle_estado_pedido(
        self, entities: dict, user_text: str
    ) -> str:
        """Query real order status and return a natural language response."""
        order_number: Optional[str] = entities.get("order_number") or entities.get(
            "order_id"
        )
        phone: Optional[str] = entities.get("phone")

        try:
            from database import AsyncSessionLocal
            from services.order_service import OrderService
            from schemas.order import STATUS_TEXT_MAP

            async with AsyncSessionLocal() as session:
                service = OrderService(session)

                if order_number:
                    order = await service.get_by_order_number(order_number)
                    if not order:
                        return (
                            f"No encontré ningún pedido con el número {order_number}. "
                            "¿Podrías verificarlo?"
                        )
                    return service._format_for_voice(order)

                if phone:
                    orders = await service.get_by_customer_phone(phone)
                    if not orders:
                        return (
                            f"No encontré pedidos asociados al teléfono {phone}."
                        )
                    if len(orders) == 1:
                        return service._format_for_voice(orders[0])

                    # Multiple orders — summarise up to 3
                    lines = [f"Encontré {len(orders)} pedidos:"]
                    for o in orders[:3]:
                        status_text = STATUS_TEXT_MAP.get(o.status, o.status)
                        lines.append(
                            f"Pedido {o.order_number}: {status_text}."
                        )
                    if len(orders) > 3:
                        lines.append(
                            "¿Quieres que te dé más detalles de alguno en particular?"
                        )
                    return " ".join(lines)

                return (
                    "Para consultar el estado de tu pedido, "
                    "necesito tu número de orden o el teléfono asociado a la compra."
                )

        except Exception as exc:
            logger.error(f"[OrderVoiceHandler] Error querying order: {exc}", exc_info=True)
            return (
                "En este momento no puedo consultar el estado del pedido. "
                "¿Deseas que te transfiera con un asesor?"
            )

    async def handle_cancelar_pedido(
        self, entities: dict, user_text: str
    ) -> str:
        """Handle an order cancellation request from the voice agent."""
        order_number: Optional[str] = entities.get("order_number") or entities.get(
            "order_id"
        )
        if not order_number:
            return (
                "Para cancelar un pedido necesito el número de orden. "
                "¿Me lo puedes proporcionar?"
            )

        try:
            from database import AsyncSessionLocal
            from services.order_service import OrderService

            async with AsyncSessionLocal() as session:
                service = OrderService(session)
                order = await service.get_by_order_number(order_number)
                if not order:
                    return (
                        f"No encontré el pedido {order_number}. "
                        "Verifica el número e intenta de nuevo."
                    )

                if order.status in ("delivered", "cancelled"):
                    return (
                        f"El pedido {order_number} no se puede cancelar "
                        f"porque ya está en estado: {order.status}."
                    )

                await service.cancel_order(
                    order_id=order.id,
                    reason="Cancelación solicitada por el cliente via voz",
                )
                return (
                    f"Tu pedido {order_number} ha sido cancelado exitosamente. "
                    "Recibirás una confirmación en breve."
                )

        except Exception as exc:
            logger.error(
                f"[OrderVoiceHandler] Error cancelling order: {exc}", exc_info=True
            )
            return (
                "No pude procesar la cancelación en este momento. "
                "¿Deseas que te transfiera con un asesor?"
            )
