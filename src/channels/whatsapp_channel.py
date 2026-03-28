from __future__ import annotations
"""
WhatsApp Business API adapter.
Usa la API oficial de Meta (Cloud API). Cae silenciosamente si WHATSAPP_TOKEN no está.
"""

import logging
from typing import Optional

import httpx

from channels.base_channel import BaseChannelAdapter, InboundMessage, OutboundMessage, SendResult

logger = logging.getLogger(__name__)


class WhatsAppChannel(BaseChannelAdapter):
    GRAPH_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, token: str = "", phone_number_id: str = ""):
        self._token = token
        self._phone_number_id = phone_number_id
        self._configured = bool(token and phone_number_id)
        if not self._configured:
            logger.info("WhatsApp: modo stub (WHATSAPP_TOKEN no configurado)")

    @property
    def name(self) -> str:
        return "whatsapp"

    def supports_rich_media(self) -> bool:
        return True

    def supports_quick_replies(self) -> bool:
        return True

    async def send(self, message: OutboundMessage) -> SendResult:
        if not self._configured:
            logger.debug("WhatsApp stub send → %s: %s", message.channel_user_id, message.text[:60])
            return SendResult(success=True, message_id="stub-wa-001", channel=self.name)

        payload = {
            "messaging_product": "whatsapp",
            "to": message.channel_user_id,
            "type": "text",
            "text": {"body": message.text},
        }
        if message.quick_replies:
            payload["type"] = "interactive"
            payload["interactive"] = {
                "type": "button",
                "body": {"text": message.text},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": f"qr_{i}", "title": r[:20]}}
                        for i, r in enumerate(message.quick_replies[:3])
                    ]
                },
            }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.GRAPH_URL}/{self._phone_number_id}/messages",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                msg_id = data.get("messages", [{}])[0].get("id", "")
                return SendResult(success=True, message_id=msg_id, channel=self.name)
        except Exception as exc:
            logger.error("WhatsApp send error: %s", exc)
            return SendResult(success=False, error=str(exc), channel=self.name)

    def parse_inbound(self, payload: dict) -> Optional[InboundMessage]:
        try:
            entry = payload["entry"][0]
            change = entry["changes"][0]["value"]
            msg = change["messages"][0]
            contact = change["contacts"][0]
            phone = contact["wa_id"]
            text = msg.get("text", {}).get("body", "")
            return InboundMessage(
                channel=self.name,
                channel_user_id=phone,
                session_id=f"wa_{phone}",
                text=text,
                phone=f"+{phone}",
                raw=payload,
            )
        except (KeyError, IndexError):
            return None
