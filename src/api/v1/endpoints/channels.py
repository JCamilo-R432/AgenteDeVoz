from __future__ import annotations
from typing import Dict, List, Optional, Any
"""
Omnichannel endpoints — webhooks de canales y preferencias.
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from channels.channel_router import channel_router, ChannelPreference

router = APIRouter(tags=["channels"])


class PreferenceRequest(BaseModel):
    customer_id: str
    preferred_channel: str
    fallback_channel: str = "sms"
    preferred_contact_hour_start: int = 9
    preferred_contact_hour_end: int = 20


class HandoffRequest(BaseModel):
    session_id: str
    from_channel: str
    to_channel: str
    reason: str = "user_request"


# ── Webhooks entrantes ────────────────────────────────────────────────────────

@router.post("/webhook/{channel}")
async def channel_webhook(channel: str, payload: dict = Body(...)):
    """Recibe mensajes entrantes de cualquier canal."""
    if channel not in channel_router.list_channels():
        raise HTTPException(status_code=404, detail=f"Canal '{channel}' no registrado")
    msg = channel_router.parse_inbound(channel, payload)
    if not msg:
        return {"status": "ignored"}
    # En producción: encolar para procesamiento por el agente
    return {
        "status": "received",
        "session_id": msg.session_id,
        "channel": channel,
        "text_preview": msg.text[:100],
    }


# ── Preferencias ──────────────────────────────────────────────────────────────

@router.post("/preferences")
async def set_channel_preference(req: PreferenceRequest):
    """Guarda la preferencia de canal del cliente."""
    pref = ChannelPreference(
        customer_id=req.customer_id,
        preferred_channel=req.preferred_channel,
        fallback_channel=req.fallback_channel,
    )
    channel_router.set_preference(pref)
    return {"status": "saved", "preference": req.dict()}


@router.get("/preferences/{customer_id}")
async def get_channel_preference(customer_id: str):
    """Devuelve la preferencia de canal del cliente."""
    pref = channel_router.get_preference(customer_id)
    if not pref:
        raise HTTPException(status_code=404, detail="Sin preferencia registrada")
    return {
        "customer_id": pref.customer_id,
        "preferred_channel": pref.preferred_channel,
        "fallback_channel": pref.fallback_channel,
    }


# ── Handoff ───────────────────────────────────────────────────────────────────

@router.post("/handoff")
async def channel_handoff(req: HandoffRequest):
    """Transfiere una sesión activa a otro canal."""
    from channels.channel_router import HandoffRequest as HR
    hr = HR(
        session_id=req.session_id,
        from_channel=req.from_channel,
        to_channel=req.to_channel,
        reason=req.reason,
    )
    success = await channel_router.handoff(hr)
    if not success:
        raise HTTPException(status_code=400, detail=f"Canal destino '{req.to_channel}' no disponible")
    return {"status": "transferred", "to_channel": req.to_channel}


# ── Info ──────────────────────────────────────────────────────────────────────

@router.get("/")
async def list_channels():
    """Lista los canales disponibles y estadísticas."""
    return channel_router.get_stats()
