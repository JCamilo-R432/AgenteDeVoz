from __future__ import annotations
from typing import Dict, List, Any
"""
Channel Router — enrutador omnicanal unificado.
- Registra adaptadores de canal
- Mantiene contexto compartido entre canales para el mismo cliente
- Permite handoff entre canales
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from channels.base_channel import BaseChannelAdapter, InboundMessage, OutboundMessage, SendResult

logger = logging.getLogger(__name__)


@dataclass
class ChannelPreference:
    """Preferencia de canal de un cliente."""
    customer_id: str
    preferred_channel: str
    preferred_schedule: Optional[str] = None  # "09:00-18:00"
    fallback_channel: str = "sms"
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class HandoffRequest:
    """Solicitud de transferencia entre canales."""
    session_id: str
    from_channel: str
    to_channel: str
    reason: str
    context_snapshot: dict = field(default_factory=dict)


class ChannelRouter:
    """
    Router principal de omnicanalidad.
    Registra adaptadores y enruta mensajes entrantes/salientes.
    """

    def __init__(self):
        self._adapters: dict[str, BaseChannelAdapter] = {}
        self._preferences: dict[str, ChannelPreference] = {}
        # session_id → channel (para handoffs)
        self._active_channels: Dict[str, str] = {}

    # ── Registro ──────────────────────────────────────────────────────────────

    def register(self, adapter: BaseChannelAdapter) -> None:
        self._adapters[adapter.name] = adapter
        logger.info("Canal registrado: %s", adapter.name)

    def get_adapter(self, channel: str) -> Optional[BaseChannelAdapter]:
        return self._adapters.get(channel)

    def list_channels(self) -> List[str]:
        return list(self._adapters.keys())

    # ── Envío ─────────────────────────────────────────────────────────────────

    async def send(
        self,
        channel: str,
        channel_user_id: str,
        text: str,
        quick_replies: List[str]  = None,
    ) -> SendResult:
        adapter = self._adapters.get(channel)
        if not adapter:
            logger.warning("Canal no registrado: %s", channel)
            return SendResult(success=False, error=f"Canal '{channel}' no disponible", channel=channel)

        msg = OutboundMessage(
            channel=channel,
            channel_user_id=channel_user_id,
            text=text,
            quick_replies=quick_replies or [],
        )
        return await adapter.send(msg)

    async def send_to_preferred(
        self,
        customer_id: str,
        text: str,
        quick_replies: List[str]  = None,
        channel_user_id: Optional[str] = None,
    ) -> SendResult:
        pref = self._preferences.get(customer_id)
        channel = pref.preferred_channel if pref else "web"
        uid = channel_user_id or customer_id
        return await self.send(channel, uid, text, quick_replies)

    # ── Parseo entrante ───────────────────────────────────────────────────────

    def parse_inbound(self, channel: str, payload: dict) -> Optional[InboundMessage]:
        adapter = self._adapters.get(channel)
        if not adapter:
            return None
        msg = adapter.parse_inbound(payload)
        if msg:
            self._active_channels[msg.session_id] = channel
        return msg

    # ── Handoff ───────────────────────────────────────────────────────────────

    async def handoff(self, request: HandoffRequest) -> bool:
        """Transfiere una sesión activa a otro canal."""
        to_adapter = self._adapters.get(request.to_channel)
        if not to_adapter:
            logger.error("Handoff fallido: canal destino '%s' no registrado", request.to_channel)
            return False

        self._active_channels[request.session_id] = request.to_channel
        logger.info(
            "Handoff %s → %s (sesión %s, razón: %s)",
            request.from_channel, request.to_channel,
            request.session_id, request.reason,
        )
        return True

    # ── Preferencias ──────────────────────────────────────────────────────────

    def set_preference(self, pref: ChannelPreference) -> None:
        self._preferences[pref.customer_id] = pref

    def get_preference(self, customer_id: str) -> Optional[ChannelPreference]:
        return self._preferences.get(customer_id)

    def get_active_channel(self, session_id: str) -> Optional[str]:
        return self._active_channels.get(session_id)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "registered_channels": self.list_channels(),
            "active_sessions": len(self._active_channels),
            "customers_with_preferences": len(self._preferences),
        }


# ── Singleton pre-configurado con adaptadores stub ────────────────────────────

def build_default_router() -> ChannelRouter:
    """Construye router con todos los canales (stub si no hay credenciales)."""
    from channels.whatsapp_channel import WhatsAppChannel
    from channels.telegram_channel import TelegramChannel
    from channels.sms_channel import SMSChannel
    import os

    router = ChannelRouter()
    router.register(WhatsAppChannel(
        token=os.getenv("WHATSAPP_TOKEN", ""),
        phone_number_id=os.getenv("WHATSAPP_PHONE_ID", ""),
    ))
    router.register(TelegramChannel(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
    ))
    router.register(SMSChannel(
        account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
    ))
    return router


channel_router = build_default_router()
