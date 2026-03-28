from __future__ import annotations
"""
SMS Service — sends OTP codes via Twilio.
Falls back to console logging in dev/test when credentials are absent.
"""


import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SMSService:
    """
    Thin wrapper around Twilio Messages API.
    Requires: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
    """

    def __init__(self) -> None:
        from config.settings import settings
        self.sid   = settings.TWILIO_ACCOUNT_SID
        self.token = settings.TWILIO_AUTH_TOKEN
        self.from_ = settings.TWILIO_PHONE_NUMBER
        self._ready = bool(self.sid and self.token and self.from_)
        if not self._ready:
            logger.warning("Twilio not configured — SMS will be simulated (check logs).")

    def send_otp(self, phone: str, code: str) -> bool:
        """
        Send a 6-digit OTP code to the given phone number.
        Returns True on success (or simulated success in dev mode).
        """
        message = (
            f"Tu código de verificación es: {code}\n"
            f"Válido por 5 minutos. No lo compartas con nadie."
        )
        return self._send(phone, message)

    def _send(self, to: str, body: str) -> bool:
        if not self._ready:
            logger.info(f"[SMS SIMULADO] → {to}: {body}")
            return True  # Simulate success

        try:
            from twilio.rest import Client
            client = Client(self.sid, self.token)
            msg = client.messages.create(body=body, from_=self.from_, to=to)
            logger.info(f"SMS sent to {to[-4:]:>4}**** | SID={msg.sid}")
            return True
        except Exception as exc:
            logger.error(f"Twilio error sending to {to}: {exc}")
            return False

    def send_whatsapp_otp(self, phone: str, code: str) -> bool:
        """Send OTP via WhatsApp (requires Twilio WhatsApp sandbox/number)."""
        if not self._ready:
            logger.info(f"[WA SIMULADO] → {phone}: código {code}")
            return True

        message = f"Tu código de verificación es: *{code}*. Válido por 5 minutos."
        wa_to = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
        wa_from = f"whatsapp:{self.from_}" if not self.from_.startswith("whatsapp:") else self.from_
        try:
            from twilio.rest import Client
            client = Client(self.sid, self.token)
            msg = client.messages.create(body=message, from_=wa_from, to=wa_to)
            logger.info(f"WhatsApp OTP sent | SID={msg.sid}")
            return True
        except Exception as exc:
            logger.error(f"WhatsApp error: {exc}")
            return False
