from __future__ import annotations
"""
Personalization endpoints — preferencias y recomendaciones por cliente.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from services.personalization_service import personalization_service

router = APIRouter(tags=["personalization"])


class PreferencesUpdateRequest(BaseModel):
    preferred_tone: Optional[str] = None
    preferred_channel: Optional[str] = None
    speech_rate: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    notifications_enabled: Optional[bool] = None
    preferred_contact_hour_start: Optional[int] = Field(default=None, ge=0, le=23)
    preferred_contact_hour_end: Optional[int] = Field(default=None, ge=0, le=23)


class GreetingRequest(BaseModel):
    customer_id: str
    name: str
    purchase_count: int = 0
    last_order_date: Optional[str] = None


@router.get("/{customer_id}/preferences")
async def get_preferences(customer_id: str):
    """Devuelve las preferencias del cliente."""
    pref = personalization_service.get_preferences(customer_id)
    return {
        "customer_id": customer_id,
        "preferred_tone": pref.preferred_tone,
        "preferred_channel": pref.preferred_channel,
        "speech_rate": pref.speech_rate,
        "notifications_enabled": pref.notifications_enabled,
        "preferred_contact_hours": f"{pref.preferred_contact_hour_start}:00-{pref.preferred_contact_hour_end}:00",
    }


@router.patch("/{customer_id}/preferences")
async def update_preferences(customer_id: str, req: PreferencesUpdateRequest):
    """Actualiza preferencias del cliente."""
    updates = {k: v for k, v in req.dict().items() if v is not None}
    pref = personalization_service.update_preferences(customer_id, updates)
    return {"status": "updated", "customer_id": customer_id}


@router.get("/{customer_id}/recommendations")
async def get_recommendations(customer_id: str, limit: int = 5):
    """Recomendaciones de productos para el cliente."""
    result = personalization_service.get_recommendations(customer_id, limit=limit)
    return {
        "product_ids": result.product_ids,
        "reasons": result.reasons,
        "confidence": result.confidence,
        "strategy": result.strategy,
    }


@router.get("/{customer_id}/recommendations/voice")
async def get_voice_recommendation(customer_id: str):
    """Recomendación corta para respuesta de voz."""
    return {"message": personalization_service.get_voice_recommendation(customer_id)}


@router.post("/greeting")
async def get_personalized_greeting(req: GreetingRequest):
    """Genera saludo personalizado según preferencias y historial."""
    greeting = personalization_service.get_personalized_greeting(
        req.customer_id, req.name, req.purchase_count, req.last_order_date
    )
    return {"greeting": greeting}


@router.get("/{customer_id}/tts-config")
async def get_tts_config(customer_id: str):
    """Configuración de TTS adaptada al cliente."""
    return personalization_service.get_tts_config(customer_id)
