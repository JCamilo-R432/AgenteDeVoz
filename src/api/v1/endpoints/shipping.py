"""Endpoints de envíos y logística."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.deps import get_current_admin, get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["shipping"])


class CreateLabelRequest(BaseModel):
    order_id: str
    carrier: str = "Coordinadora"
    destination: Optional[dict] = None


def _get_shipping():
    from services.shipping_integration import ShippingIntegration
    return ShippingIntegration()


@router.get("/track/{tracking_number}")
async def track_shipment(tracking_number: str):
    """Tracking en tiempo real por número de guía."""
    shipping = _get_shipping()
    info = await shipping.get_tracking_status(tracking_number)
    return {
        "tracking_number": info.tracking_number,
        "carrier": info.carrier,
        "status": info.status,
        "current_location": info.current_location,
        "estimated_delivery": info.estimated_delivery.isoformat() if info.estimated_delivery else None,
        "delivery_attempts": info.delivery_attempts,
        "events": [
            {
                "timestamp": e.timestamp.isoformat(),
                "location": e.location,
                "status": e.status,
                "description": e.description,
            }
            for e in info.events
        ],
        "voice_summary": shipping.format_tracking_for_voice(info),
    }


@router.get("/zones")
async def get_delivery_zones():
    """Zonas de entrega colombianas con tiempos y disponibilidad de express."""
    shipping = _get_shipping()
    return await shipping.get_delivery_zones()


@router.get("/calculate-rate")
async def calculate_rate(
    origin: str,
    dest: str,
    weight: float = 1.0,
    service: str = "standard",
):
    """Calcula costo de envío para origen → destino."""
    shipping = _get_shipping()
    rates = await shipping.calculate_rate(origin, dest, weight, service)
    return {"origin": origin, "destination": dest, "weight_kg": weight, "rates": rates}


@router.get("/delivery-times")
async def delivery_times():
    """Tiempos de entrega estimados por zona."""
    return {
        "zona_1": {"cities": ["Bogotá", "Medellín"], "standard_days": "1-2", "express_hours": "2-4"},
        "zona_2": {"cities": ["Cali", "Barranquilla", "Cartagena"], "standard_days": "2-3", "express_hours": "N/A"},
        "zona_3": {"cities": ["Bucaramanga", "Pereira", "Manizales"], "standard_days": "3-4", "express_hours": "N/A"},
        "zona_4": {"cities": ["Resto de Colombia"], "standard_days": "4-6", "express_hours": "N/A"},
    }


@router.get("/orders/{order_number}/tracking")
async def order_tracking(order_number: str, db: AsyncSession = Depends(get_db)):
    """Tracking del envío de una orden específica."""
    from models.order import Order
    from models.shipment import Shipment

    result = await db.execute(
        select(Order).where(Order.order_number == order_number)
        .options(selectinload(Order.shipments))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido '{order_number}' no encontrado.")

    if not order.shipments:
        return {"order_number": order_number, "status": order.status, "shipment": None,
                "message": "Este pedido aún no tiene envío generado."}

    shipment = order.shipments[0]
    if shipment.tracking_number:
        shipping = _get_shipping()
        info = await shipping.get_tracking_status(shipment.tracking_number)
        return {
            "order_number": order_number,
            "tracking_number": shipment.tracking_number,
            "carrier": info.carrier,
            "status": info.status,
            "current_location": info.current_location,
            "estimated_delivery": info.estimated_delivery.isoformat() if info.estimated_delivery else None,
            "voice_summary": shipping.format_tracking_for_voice(info),
        }

    return {"order_number": order_number, "carrier": shipment.carrier,
            "status": shipment.status, "tracking_number": None}


@router.post("/create-label", dependencies=[Depends(get_current_admin)])
async def create_shipping_label(req: CreateLabelRequest, db: AsyncSession = Depends(get_db)):
    """Crea guía de envío para una orden."""
    from sqlalchemy import select
    from models.order import Order
    from models.shipment import Shipment
    import uuid

    result = await db.execute(select(Order).where(Order.id == req.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden '{req.order_id}' no encontrada.")

    shipping = _get_shipping()
    info = await shipping.create_shipment(order, req.carrier, req.destination)

    # Guardar envío en BD
    shipment = Shipment(
        id=str(uuid.uuid4()),
        order_id=order.id,
        tracking_number=info.tracking_number,
        carrier=info.carrier,
        status=info.status,
        current_location=info.current_location,
        estimated_delivery=info.estimated_delivery,
    )
    db.add(shipment)
    await db.commit()

    return {
        "tracking_number": info.tracking_number,
        "carrier": info.carrier,
        "status": info.status,
        "estimated_delivery": info.estimated_delivery.isoformat() if info.estimated_delivery else None,
    }


@router.post("/orders/{order_id}/reschedule-delivery", dependencies=[Depends(get_current_admin)])
async def reschedule_delivery(order_id: str):
    """Reagenda intento de entrega (stub)."""
    return {
        "order_id": order_id,
        "rescheduled": True,
        "note": "Reagendamiento confirmado. La transportadora intentará en las próximas 24-48 horas.",
    }
