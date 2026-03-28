from __future__ import annotations
from typing import Dict, List, Any
"""
voice_interface.py — REST + WebSocket endpoints for the web voice agent.
Bridges the browser VoiceAgent JS class to the core voice pipeline.
"""


import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/voice", tags=["voice-interface"])


# ── Request / Response models ──────────────────────────────────────

class VoiceProcessRequest(BaseModel):
    session_id: str = Field(..., description="Client-generated session identifier")
    text      : str = Field(..., min_length=1, max_length=2000)
    language  : str = Field("es-CO", description="BCP-47 language tag")
    channel   : str = Field("web", description="Originating channel")
    metadata  : Dict[str, Any] = Field(default_factory=dict)


class VoiceProcessResponse(BaseModel):
    session_id : str
    response   : str
    language   : str
    intent     : Optional[str] = None
    confidence : float  = None
    escalate   : bool = False
    timestamp  : str


# ── In-memory session store (replace with Redis in production) ─────

_sessions: Dict[str, Dict] = {}


def _get_or_create_session(session_id: str, language: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "id"          : session_id,
            "language"    : language,
            "history"     : [],
            "created_at"  : datetime.utcnow().isoformat(),
            "turn_count"  : 0,
        }
    return _sessions[session_id]


# ── Core agent call (delegates to VoiceAgent pipeline if available) -

async def _process_with_agent(session: dict, text: str) -> dict:
    """
    Attempts to use the real VoiceAgent pipeline.
    Falls back to a scripted demo response when the pipeline is not running.
    """
    try:
        # Dynamic import so the web layer doesn't hard-depend on the full stack
        from src.agent.voice_agent import VoiceAgent  # type: ignore
        agent = VoiceAgent()
        result = await asyncio.wait_for(
            asyncio.to_thread(agent.process_text, text, session["id"]),
            timeout=15.0,
        )
        return {
            "response"  : result.get("response", ""),
            "intent"    : result.get("intent"),
            "confidence": result.get("confidence"),
            "escalate"  : result.get("escalate", False),
        }
    except Exception as exc:
        logger.debug("Falling back to demo responses: %s", exc)
        return _demo_response(text, session["language"])


def _demo_response(text: str, language: str) -> dict:
    """Scripted fallback responses for demo / development."""
    text_lower = text.lower()

    responses_es = {
        ("hola", "buenos", "saludos"): (
            "¡Hola! Soy tu agente de voz inteligente. Puedo ayudarte con consultas sobre pedidos, "
            "soporte técnico y facturación. ¿En qué te puedo ayudar?"
        ),
        ("precio", "costo", "plan", "tarifa"): (
            "Tenemos tres planes: Gratis (100 conversaciones/mes), Pro a $49/mes (2 000 conversaciones), "
            "y Enterprise con precio personalizado. ¿Cuál se adapta mejor a tu negocio?"
        ),
        ("integr", "api", "twilio", "whatsapp"): (
            "Nos integramos con Twilio para llamadas, WhatsApp Business, chat web y cualquier app vía "
            "API REST. La integración típica tarda menos de un día."
        ),
        ("segur", "datos", "privacidad", "gdpr"): (
            "Tus datos están protegidos con cifrado AES-256-GCM. Cumplimos GDPR, LOPD y Ley 1581/2012 "
            "de Colombia. Nunca vendemos datos de ningún tipo."
        ),
        ("cancel", "reembols", "contrato"): (
            "No hay contratos de permanencia. Puedes cancelar desde tu panel en cualquier momento "
            "y te reembolsamos los días no usados del período en curso."
        ),
        ("tiempo", "latencia", "rápid", "velocidad"): (
            "La latencia promedio es menor a 1 segundo (STT + LLM + TTS). En condiciones óptimas "
            "la respuesta de voz llega en 600-900 ms."
        ),
        ("humano", "person", "agent", "escal"): (
            "Por supuesto, te transfiero con un agente humano ahora mismo. "
            "¿Puedes darme tu nombre y el motivo de tu consulta para agilizar la atención?"
        ),
    }

    responses_en = {
        ("hello", "hi", "hey"): (
            "Hi there! I'm your intelligent voice agent. I can help with order inquiries, "
            "technical support, and billing. How can I assist you today?"
        ),
        ("price", "cost", "plan", "pricing"): (
            "We offer three plans: Free (100 conversations/month), Pro at $49/month (2,000 conversations), "
            "and Enterprise with custom pricing. Which fits your needs best?"
        ),
        ("cancel", "refund"): (
            "No long-term contracts — cancel any time from your dashboard and we'll refund "
            "unused days in the current billing period."
        ),
    }

    pool = responses_en if language.startswith("en") else responses_es

    for keywords, reply in pool.items():
        if any(kw in text_lower for kw in keywords):
            return {"response": reply, "intent": "faq", "confidence": 0.9, "escalate": False}

    # Default
    default = {
        "es": (
            "Entendido. Puedo ayudarte con preguntas sobre precios, integraciones, soporte técnico "
            "y cancelaciones. También puedo conectarte con un agente humano si lo prefieres. "
            "¿Qué necesitas?"
        ),
        "en": (
            "Got it! I can help with pricing, integrations, technical support, and billing. "
            "I can also transfer you to a human agent if you prefer. What do you need?"
        ),
        "pt": (
            "Entendido! Posso ajudar com preços, integrações, suporte técnico e cancelamentos. "
            "Também posso conectar você a um agente humano. O que você precisa?"
        ),
    }
    lang_key = language[:2] if language[:2] in default else "es"
    return {"response": default[lang_key], "intent": "general", "confidence": 0.7, "escalate": False}


# ── REST endpoint ──────────────────────────────────────────────────

@router.post("/process", response_model=VoiceProcessResponse)
async def process_voice_text(req: VoiceProcessRequest):
    """
    Main endpoint called by the browser VoiceAgent after STT.
    Accepts text + session context, returns the agent's response text.
    """
    if len(req.text.strip()) == 0:
        raise HTTPException(status_code=422, detail="Empty text input")

    session = _get_or_create_session(req.session_id, req.language)
    session["turn_count"] += 1
    session["history"].append({"role": "user", "text": req.text, "ts": datetime.utcnow().isoformat()})

    result = await _process_with_agent(session, req.text)

    session["history"].append({"role": "agent", "text": result["response"], "ts": datetime.utcnow().isoformat()})

    return VoiceProcessResponse(
        session_id = req.session_id,
        response   = result["response"],
        language   = req.language,
        intent     = result.get("intent"),
        confidence = result.get("confidence"),
        escalate   = result.get("escalate", False),
        timestamp  = datetime.utcnow().isoformat(),
    )


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Return the conversation history for a session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    sess = _sessions[session_id]
    return {
        "session_id": session_id,
        "turn_count": sess["turn_count"],
        "language"  : sess["language"],
        "created_at": sess["created_at"],
        "history"   : sess["history"],
    }


@router.delete("/session/{session_id}", status_code=204)
async def clear_session(session_id: str):
    """Clear a session (called when user clicks 'Limpiar')."""
    _sessions.pop(session_id, None)


# ── WebSocket endpoint (optional streaming) ───────────────────────

@router.websocket("/ws/{session_id}")
async def voice_websocket(ws: WebSocket, session_id: str):
    """
    Optional WebSocket for streaming text chunks from the LLM.
    The browser can connect here instead of polling /process.
    """
    await ws.accept()
    session = _get_or_create_session(session_id, "es-CO")
    logger.info("WebSocket connected: %s", session_id)

    try:
        while True:
            data = await ws.receive_json()
            text = data.get("text", "").strip()
            if not text:
                continue

            session["turn_count"] += 1
            result = await _process_with_agent(session, text)

            await ws.send_json({
                "type"      : "response",
                "session_id": session_id,
                "response"  : result["response"],
                "intent"    : result.get("intent"),
                "escalate"  : result.get("escalate", False),
                "timestamp" : datetime.utcnow().isoformat(),
            })
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", session_id)
    except Exception as exc:
        logger.error("WebSocket error [%s]: %s", session_id, exc)
        await ws.close(code=1011)
