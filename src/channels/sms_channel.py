from __future__ import annotations
"""
SMS channel adapter via Twilio.
Cae silenciosamente si TWILIO_* no está configurado.
"""

import logging
from typing import Optional

from channels.base_channel import BaseChannelAdapter, InboundMessage, OutboundMessage, SendResult

logger = logging.getLogger(__name__)


class SMSChannel(BaseChannelAdapter):
    def __init__(
        self,
        account_sid: str = "",
        auth_token: str = "",
        from_number: str = "",
    ):
        self._sid = account_sid
        self._token = auth_token
        self._from = from_number
        self._configured = bool(account_sid and auth_token and from_number)
        if not self._configured:
            logger.info("SMS: modo stub (TWILIO_* no configurado)")

    @property
    def name(self) -> str:
        return "sms"

    async def send(self, message: OutboundMessage) -> SendResult:
        if not self._configured:
            logger.debug("SMS stub → %s: %s", message.channel_user_id, message.text[:60])
            return SendResult(success=True, message_id="stub-sms-001", channel=self.name)

        try:
            from twilio.rest import Client  # type: ignore

            client = Client(self._sid, self._token)
            msg = client.messages.create(
                body=message.text,
                from_=self._from,
                to=message.channel_user_id,
            )
            return SendResult(success=True, message_id=msg.sid, channel=self.name)
        except ImportError:
            logger.warning("twilio package not installed")
            return SendResult(success=False, error="twilio not installed", channel=self.name)
        except Exception as exc:
            logger.error("SMS send error: %s", exc)
            return SendResult(success=False, error=str(exc), channel=self.name)

    def parse_inbound(self, payload: dict) -> Optional[InboundMessage]:
        phone = payload.get("From", "")
        text = payload.get("Body", "")
        if not phone:
            return None
        return InboundMessage(
            channel=self.name,
            channel_user_id=phone,
            session_id=f"sms_{phone.replace('+', '')}",
            text=text,
            phone=phone,
            raw=payload,
        )
