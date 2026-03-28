from __future__ import annotations
"""
Telegram Bot API adapter.
Cae silenciosamente si TELEGRAM_BOT_TOKEN no está configurado.
"""

import logging
from typing import Optional

import httpx

from channels.base_channel import BaseChannelAdapter, InboundMessage, OutboundMessage, SendResult

logger = logging.getLogger(__name__)


class TelegramChannel(BaseChannelAdapter):
    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self, bot_token: str = ""):
        self._token = bot_token
        self._configured = bool(bot_token)
        if not self._configured:
            logger.info("Telegram: modo stub (TELEGRAM_BOT_TOKEN no configurado)")

    @property
    def name(self) -> str:
        return "telegram"

    def supports_rich_media(self) -> bool:
        return True

    def supports_quick_replies(self) -> bool:
        return True

    async def send(self, message: OutboundMessage) -> SendResult:
        if not self._configured:
            logger.debug("Telegram stub send → %s", message.channel_user_id)
            return SendResult(success=True, message_id="stub-tg-001", channel=self.name)

        payload: dict = {
            "chat_id": message.channel_user_id,
            "text": message.text,
            "parse_mode": "Markdown",
        }
        if message.quick_replies:
            payload["reply_markup"] = {
                "keyboard": [[{"text": r}] for r in message.quick_replies[:6]],
                "one_time_keyboard": True,
                "resize_keyboard": True,
            }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}{self._token}/sendMessage",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                msg_id = str(data.get("result", {}).get("message_id", ""))
                return SendResult(success=True, message_id=msg_id, channel=self.name)
        except Exception as exc:
            logger.error("Telegram send error: %s", exc)
            return SendResult(success=False, error=str(exc), channel=self.name)

    def parse_inbound(self, payload: dict) -> Optional[InboundMessage]:
        try:
            msg = payload["message"]
            chat_id = str(msg["chat"]["id"])
            text = msg.get("text", "")
            return InboundMessage(
                channel=self.name,
                channel_user_id=chat_id,
                session_id=f"tg_{chat_id}",
                text=text,
                raw=payload,
            )
        except KeyError:
            return None
