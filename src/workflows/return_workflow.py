from __future__ import annotations
"""
Return Workflow — flujo completo de devolución en 7 pasos:
1. Verificar elegibilidad (plazo, estado del pedido)
2. Generar etiqueta de retorno
3. Notificar al almacén
4. Confirmar recepción del producto
5. Procesar reembolso
6. Notificar al cliente
7. Cerrar el caso
"""

import logging
from datetime import datetime, timedelta

from workflows.workflow_engine import WorkflowDefinition, workflow_engine

logger = logging.getLogger(__name__)

RETURN_WINDOW_DAYS = 30


async def _verify_eligibility(ctx: dict) -> dict:
    order_date_str = ctx.get("order_date", "")
    order_status = ctx.get("order_status", "")

    if order_status not in ("delivered", "completed"):
        raise ValueError("El pedido debe estar entregado para solicitar devolución.")

    if order_date_str:
        order_date = datetime.fromisoformat(order_date_str)
        if datetime.utcnow() - order_date > timedelta(days=RETURN_WINDOW_DAYS):
            raise ValueError(f"El plazo de devolución de {RETURN_WINDOW_DAYS} días ha vencido.")

    return {
        "eligibility_verified": True,
        "return_reason": ctx.get("reason", "sin especificar"),
        "return_authorized_at": datetime.utcnow().isoformat(),
    }


async def _generate_return_label(ctx: dict) -> dict:
    order_number = ctx.get("order_number", "UNKNOWN")
    # En producción: llamar API de transportadora
    label_code = f"RET-{order_number[-6:]}-{datetime.utcnow().strftime('%Y%m%d')}"
    return {
        "return_label_code": label_code,
        "return_label_url": f"https://etiquetas.eco.co/return/{label_code}.pdf",
        "pickup_scheduled": False,
    }


async def _notify_warehouse(ctx: dict) -> dict:
    label = ctx.get("return_label_code", "")
    logger.info("[Almacén] Preparar recepción de devolución %s", label)
    return {
        "warehouse_notified": True,
        "warehouse_notified_at": datetime.utcnow().isoformat(),
    }


async def _confirm_receipt(ctx: dict) -> dict:
    # En producción: esperar webhook del almacén o actualización manual
    # Como stub, marcamos como recibido
    return {
        "product_received": True,
        "product_received_at": datetime.utcnow().isoformat(),
        "product_condition": ctx.get("product_condition", "good"),
    }


async def _process_refund(ctx: dict) -> dict:
    order_id = ctx.get("order_id", "")
    refund_amount = ctx.get("refund_amount") or ctx.get("order_total", 0)
    logger.info("Procesando reembolso de %s para pedido %s", refund_amount, order_id)
    # En producción: llamar PaymentService.process_refund()
    return {
        "refund_processed": True,
        "refund_amount": refund_amount,
        "refund_id": f"REF-{order_id[-8:]}",
        "refund_processed_at": datetime.utcnow().isoformat(),
        "estimated_days": 5,
    }


async def _notify_customer(ctx: dict) -> dict:
    customer_id = ctx.get("customer_id", "")
    refund_id = ctx.get("refund_id", "")
    days = ctx.get("estimated_days", 5)
    logger.info("Notificando al cliente %s: reembolso %s en %d días", customer_id, refund_id, days)
    return {
        "customer_notified": True,
        "notification_sent_at": datetime.utcnow().isoformat(),
        "customer_message": (
            f"Tu devolución fue aprobada. Recibirás tu reembolso en {days} días hábiles."
        ),
    }


async def _close_case(ctx: dict) -> dict:
    return {
        "case_closed": True,
        "closed_at": datetime.utcnow().isoformat(),
        "resolution": "return_completed",
        "voice_summary": (
            f"Tu devolución del pedido {ctx.get('order_number', '')} fue procesada exitosamente. "
            f"Recibirás tu reembolso de ${ctx.get('refund_amount', 0):,.0f} COP en "
            f"{ctx.get('estimated_days', 5)} días hábiles."
        ),
    }


def build_return_workflow() -> WorkflowDefinition:
    wf = WorkflowDefinition(
        workflow_id="return_order",
        name="Devolución de Pedido",
        description="Flujo completo de devolución: verificación → etiqueta → almacén → reembolso → notificación",
    )
    wf.add_step("verify_eligibility", "Verificar elegibilidad", "Valida plazo y estado del pedido", _verify_eligibility)
    wf.add_step("generate_label", "Generar etiqueta", "Crea etiqueta de retorno", _generate_return_label)
    wf.add_step("notify_warehouse", "Notificar almacén", "Avisa al almacén de la llegada", _notify_warehouse)
    wf.add_step("confirm_receipt", "Confirmar recepción", "Registra recepción del producto", _confirm_receipt, requires_human_approval=True)
    wf.add_step("process_refund", "Procesar reembolso", "Ejecuta el reembolso", _process_refund)
    wf.add_step("notify_customer", "Notificar cliente", "Informa al cliente del reembolso", _notify_customer)
    wf.add_step("close_case", "Cerrar caso", "Marca el caso como resuelto", _close_case)
    return wf


def build_custom_order_workflow() -> WorkflowDefinition:
    """Flujo de pedido personalizado en 6 pasos."""

    async def _take_specifications(ctx: dict) -> dict:
        return {"specs_recorded": True, "specs": ctx.get("specifications", {})}

    async def _create_production_order(ctx: dict) -> dict:
        order_num = f"PROD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        return {"production_order": order_num, "production_start": datetime.utcnow().isoformat()}

    async def _notify_production_time(ctx: dict) -> dict:
        return {"production_days_estimate": 7, "customer_notified_production": True}

    async def _mark_production_ready(ctx: dict) -> dict:
        return {"production_ready": True, "ready_at": datetime.utcnow().isoformat()}

    async def _coordinate_shipping(ctx: dict) -> dict:
        return {"shipping_coordinated": True, "shipping_label": f"SHIP-{ctx.get('production_order', '')[:10]}"}

    async def _confirm_dispatch(ctx: dict) -> dict:
        return {
            "dispatched": True,
            "voice_summary": (
                f"Tu pedido personalizado {ctx.get('production_order', '')} fue despachado. "
                f"Llegará en 3-5 días hábiles."
            ),
        }

    wf = WorkflowDefinition(
        workflow_id="custom_order",
        name="Pedido Personalizado",
        description="Flujo de producción y envío de pedido personalizado",
    )
    wf.add_step("take_specs", "Tomar especificaciones", "Registra los requisitos del cliente", _take_specifications)
    wf.add_step("create_production", "Crear orden de producción", "Inicia producción", _create_production_order, requires_human_approval=True)
    wf.add_step("notify_time", "Notificar tiempo", "Informa tiempo de fabricación", _notify_production_time)
    wf.add_step("mark_ready", "Marcar listo", "Producto listo para envío", _mark_production_ready, requires_human_approval=True)
    wf.add_step("coordinate_shipping", "Coordinar envío", "Genera etiqueta y coordina courier", _coordinate_shipping)
    wf.add_step("confirm_dispatch", "Confirmar despacho", "Cierra el flujo", _confirm_dispatch)
    return wf


# Auto-registro al importar
def register_all_workflows() -> None:
    workflow_engine.register(build_return_workflow())
    workflow_engine.register(build_custom_order_workflow())
    logger.info("Workflows registrados: return_order, custom_order")


register_all_workflows()
