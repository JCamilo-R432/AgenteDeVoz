from __future__ import annotations
"""
Alert system for AgenteDeVoz.
Sends notifications to Slack, WhatsApp, or Email when critical events occur.

Environment variables:
    ALERT_SLACK_WEBHOOK   — Slack Incoming Webhook URL
    ALERT_EMAIL_TO        — Comma-separated recipient emails
    ALERT_WHATSAPP_TO     — WhatsApp number (e.g. +573001234567)
    SENDGRID_API_KEY      — Required for email alerts
    APP_ENV               — "production" | "development" (alerts skip in dev)
"""


import logging
import os
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_ENV = os.getenv("APP_ENV", "production")


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertManager:
    """Dispatches alerts to configured channels."""

    def __init__(self) -> None:
        self._slack_webhook = os.getenv("ALERT_SLACK_WEBHOOK", "")
        self._email_to = [
            e.strip()
            for e in os.getenv("ALERT_EMAIL_TO", "").split(",")
            if e.strip()
        ]
        self._whatsapp_to = os.getenv("ALERT_WHATSAPP_TO", "")

    # ── Public API ─────────────────────────────────────────────────────────────

    async def send(
        self,
        title: str,
        body: str,
        level: AlertLevel = AlertLevel.WARNING,
        *,
        tenant_id: Optional[str] = None,
    ) -> None:
        """Send alert to all configured channels."""
        if _ENV == "development":
            logger.info(f"[ALERT-DEV] [{level.upper()}] {title}: {body}")
            return

        tag = f"[{level.upper()}]"
        tenant_tag = f" [tenant={tenant_id}]" if tenant_id else ""
        full_title = f"{tag}{tenant_tag} {title}"

        results: List[str] = []

        if self._slack_webhook:
            ok = await self._send_slack(full_title, body, level)
            results.append(f"slack={'ok' if ok else 'error'}")

        if self._email_to:
            ok = await self._send_email(full_title, body, level)
            results.append(f"email={'ok' if ok else 'error'}")

        if self._whatsapp_to:
            ok = await self._send_whatsapp(full_title, body)
            results.append(f"whatsapp={'ok' if ok else 'error'}")

        if not results:
            logger.warning(
                f"Alert fired but no channels configured: [{level}] {title}"
            )
        else:
            logger.info(f"Alert dispatched: {', '.join(results)} | {title}")

    async def info(self, title: str, body: str, **kw) -> None:
        await self.send(title, body, AlertLevel.INFO, **kw)

    async def warning(self, title: str, body: str, **kw) -> None:
        await self.send(title, body, AlertLevel.WARNING, **kw)

    async def critical(self, title: str, body: str, **kw) -> None:
        await self.send(title, body, AlertLevel.CRITICAL, **kw)

    # ── Slack ──────────────────────────────────────────────────────────────────

    async def _send_slack(self, title: str, body: str, level: AlertLevel) -> bool:
        emoji = {"info": ":information_source:", "warning": ":warning:", "critical": ":rotating_light:"}.get(
            level.value, ":bell:"
        )
        payload = {
            "text": f"{emoji} *{title}*\n{body}",
            "username": "AgenteDeVoz Alerts",
        }
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(self._slack_webhook, json=payload)
                return r.status_code == 200
        except Exception as exc:
            logger.error(f"Slack alert failed: {exc}")
            return False

    # ── Email ──────────────────────────────────────────────────────────────────

    async def _send_email(self, title: str, body: str, level: AlertLevel) -> bool:
        api_key = os.getenv("SENDGRID_API_KEY", "")
        from_email = os.getenv("SENDGRID_FROM_EMAIL", "alerts@agentevoz.com")
        if not api_key:
            logger.warning("SENDGRID_API_KEY not set — email alert skipped")
            return False

        color = {"info": "#2196F3", "warning": "#FF9800", "critical": "#F44336"}.get(
            level.value, "#607D8B"
        )
        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          <div style="background:{color};padding:16px;border-radius:4px 4px 0 0">
            <h2 style="color:#fff;margin:0">{title}</h2>
          </div>
          <div style="background:#f5f5f5;padding:16px;border-radius:0 0 4px 4px">
            <pre style="white-space:pre-wrap;font-size:14px">{body}</pre>
          </div>
          <p style="color:#999;font-size:12px;text-align:center">AgenteDeVoz — Sistema de alertas automáticas</p>
        </div>
        """

        personalizations = [
            {"to": [{"email": addr}]} for addr in self._email_to
        ]

        payload = {
            "personalizations": personalizations,
            "from": {"email": from_email, "name": "AgenteDeVoz Alerts"},
            "subject": title,
            "content": [{"type": "text/html", "value": html_body}],
        }

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                return r.status_code in (200, 202)
        except Exception as exc:
            logger.error(f"Email alert failed: {exc}")
            return False

    # ── WhatsApp ───────────────────────────────────────────────────────────────

    async def _send_whatsapp(self, title: str, body: str) -> bool:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        from_number = os.getenv("TWILIO_WHATSAPP_FROM", "")

        if not all([account_sid, auth_token, from_number]):
            logger.warning("Twilio WhatsApp not configured — alert skipped")
            return False

        message = f"*{title}*\n{body[:1000]}"
        try:
            import httpx
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    url,
                    data={
                        "From": f"whatsapp:{from_number}",
                        "To": f"whatsapp:{self._whatsapp_to}",
                        "Body": message,
                    },
                    auth=(account_sid, auth_token),
                )
                return r.status_code == 201
        except Exception as exc:
            logger.error(f"WhatsApp alert failed: {exc}")
            return False


# Singleton
alert_manager = AlertManager()
