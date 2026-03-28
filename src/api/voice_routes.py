"""
Twilio Voice Webhook Routes — AgenteDeVoz
Conecta las llamadas entrantes de Twilio directamente con CustomerServiceAgent.

Flujo:
  1. Twilio llama → POST /api/v1/voice/incoming → crea sesión + saludo TwiML
  2. Usuario habla → Twilio STT → POST /api/v1/voice/respond → respuesta TwiML
  3. Llamada termina → POST /api/v1/voice/status → limpia sesión
"""

import logging
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Form, Header, Request, Response
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])

# ── Almacén de sesiones en memoria ────────────────────────────────────────────
# Clave: CallSid de Twilio. En producción → Redis con TTL de 1 hora.
_sessions: Dict[str, "CustomerServiceAgent"] = {}  # type: ignore[name-defined]


# ── Helpers TwiML ──────────────────────────────────────────────────────────────

def _twiml_respond(text: str, gather_action: str, is_final: bool = False) -> str:
    """
    Construye un TwiML que:
    - Lee el texto con <Say> en español.
    - Escucha la respuesta del usuario con <Gather> (STT de Twilio).
    Si is_final=True, solo cuelga la llamada.
    """
    text_escaped = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )

    if is_final:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="es-MX" voice="Polly.Lupe">{text_escaped}</Say>
    <Hangup/>
</Response>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" language="es-MX" speechTimeout="auto"
            action="{gather_action}" method="POST" timeout="5">
        <Say language="es-MX" voice="Polly.Lupe">{text_escaped}</Say>
    </Gather>
    <Redirect method="POST">{gather_action}?SpeechResult=</Redirect>
</Response>"""


def _twiml_transfer(transfer_number: str, callback_url: str) -> str:
    """TwiML para transferir la llamada a un agente humano."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="es-MX" voice="Polly.Lupe">
        Espera un momento, te estoy transfiriendo con un agente.
    </Say>
    <Dial timeout="30" action="{callback_url}" method="POST">
        <Number>{transfer_number}</Number>
    </Dial>
</Response>"""


def _validate_twilio(request: Request, signature: Optional[str]) -> bool:
    """Valida la firma HMAC de Twilio (omite validación en desarrollo)."""
    from config.settings import settings

    if not settings.TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_AUTH_TOKEN no configurado — validación omitida")
        return True

    if not signature:
        logger.warning("X-Twilio-Signature ausente")
        return False

    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        url = str(request.url)
        return validator.validate(url, {}, signature)
    except Exception as e:
        logger.error(f"Error validando firma Twilio: {e}")
        return False


def _build_respond_url(request: Request) -> str:
    """Construye la URL absoluta de /api/v1/voice/respond para el TwiML."""
    from config.settings import settings
    base = settings.TWILIO_WEBHOOK_URL.rstrip("/") if settings.TWILIO_WEBHOOK_URL else str(request.base_url).rstrip("/")
    return f"{base}/api/v1/voice/respond"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/voice/incoming")
async def voice_incoming(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(default=""),
    x_twilio_signature: Optional[str] = Header(default=None),
) -> Response:
    """
    Webhook que Twilio llama cuando entra una nueva llamada.

    Configura en tu número de Twilio:
      Webhook URL (Voice): https://tu-dominio.com/api/v1/voice/incoming
      Method: HTTP POST
    """
    logger.info(f"Llamada entrante | CallSid={CallSid} | De={From}")

    # Crear sesión del agente
    session_id = f"twilio-{CallSid}"
    try:
        from core.agent import CustomerServiceAgent
        agent = CustomerServiceAgent(session_id=session_id)
        _sessions[CallSid] = agent

        # Guardar teléfono del llamante para lookup posterior
        phone = From.replace("whatsapp:", "").strip()
        agent.conversation.set_context("caller_phone", phone)

        # Iniciar llamada → devuelve el saludo
        greeting = agent.start_call()

    except Exception as e:
        logger.error(f"Error creando agente para {CallSid}: {e}", exc_info=True)
        greeting = "Bienvenido al servicio de atención al cliente. Estamos teniendo problemas técnicos. Por favor llame más tarde."

    respond_url = _build_respond_url(request)
    twiml = _twiml_respond(greeting, respond_url)
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/respond")
async def voice_respond(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default="0"),
    x_twilio_signature: Optional[str] = Header(default=None),
) -> Response:
    """
    Webhook que Twilio llama con el texto transcrito del usuario.
    Procesa el input con el agente y retorna la respuesta como TwiML.
    """
    logger.info(f"Respuesta usuario | CallSid={CallSid} | Texto='{SpeechResult}' | Confianza={Confidence}")

    respond_url = _build_respond_url(request)

    # Recuperar agente de la sesión
    agent = _sessions.get(CallSid)
    if not agent:
        logger.warning(f"Sesión no encontrada para CallSid={CallSid}, creando nueva")
        try:
            from core.agent import CustomerServiceAgent
            agent = CustomerServiceAgent(session_id=f"twilio-{CallSid}")
            _sessions[CallSid] = agent
        except Exception as e:
            logger.error(f"Error recreando agente: {e}")
            twiml = _twiml_respond(
                "Hubo un error técnico. Por favor llame más tarde.",
                respond_url,
                is_final=True,
            )
            return Response(content=twiml, media_type="application/xml")

    # Procesar input del usuario
    try:
        response_text = agent.process_input(text_input=SpeechResult or "")
    except Exception as e:
        logger.error(f"Error procesando input [{CallSid}]: {e}", exc_info=True)
        response_text = "Disculpa, tuve un error. ¿Podrías repetirlo?"

    # Si la sesión terminó (despedida o error), colgar
    is_final = not agent.is_active
    if is_final:
        del _sessions[CallSid]

    # Verificar si el agente escaló → transferir llamada
    if agent.conversation.get_context("escalated"):
        from config.settings import settings
        transfer_url = respond_url.replace("/respond", "/transfer-complete")
        twiml = _twiml_transfer(settings.ESCALATION_NUMBER, transfer_url)
        return Response(content=twiml, media_type="application/xml")

    twiml = _twiml_respond(response_text, respond_url, is_final=is_final)
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/transfer-complete")
async def voice_transfer_complete(
    request: Request,
    CallSid: str = Form(...),
    DialCallStatus: str = Form(default="completed"),
) -> Response:
    """Callback cuando termina la transferencia a agente humano."""
    logger.info(f"Transferencia completada | CallSid={CallSid} | Estado={DialCallStatus}")

    agent = _sessions.pop(CallSid, None)
    if agent:
        agent.is_active = False

    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="es-MX" voice="Polly.Lupe">
        Gracias por tu paciencia. Que tengas un excelente día.
    </Say>
    <Hangup/>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/status")
async def voice_status(
    CallSid: str = Form(...),
    CallStatus: str = Form(default=""),
) -> Response:
    """
    Callback de estado de Twilio (completed, no-answer, busy, failed).
    Limpia la sesión del agente cuando la llamada termina.
    """
    logger.info(f"Estado de llamada | CallSid={CallSid} | Estado={CallStatus}")

    if CallStatus in ("completed", "no-answer", "busy", "failed", "canceled"):
        agent = _sessions.pop(CallSid, None)
        if agent:
            try:
                agent.end_call()
            except Exception:
                pass
            logger.info(f"Sesión limpiada | CallSid={CallSid}")

    return Response(content="", status_code=204)


@router.get("/voice/sessions")
async def voice_sessions() -> dict:
    """Endpoint de diagnóstico: sesiones activas (solo usar en desarrollo)."""
    return {
        "active_sessions": len(_sessions),
        "sessions": list(_sessions.keys()),
    }
