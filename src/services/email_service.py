from __future__ import annotations
"""
Email Service — sends OTP codes and transactional emails via SendGrid.
Falls back to console logging when API key is absent.
"""


import logging
from typing import Optional

logger = logging.getLogger(__name__)

_OTP_HTML = """
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f9f9f9;padding:32px">
  <div style="max-width:480px;margin:auto;background:white;border-radius:12px;padding:32px;
              box-shadow:0 2px 8px rgba(0,0,0,.08)">
    <h2 style="color:#4F46E5;margin-top:0">{brand_name}</h2>
    <p style="color:#374151;font-size:15px">Tu código de verificación es:</p>
    <div style="background:#F3F4F6;border-radius:8px;padding:20px;text-align:center;margin:24px 0">
      <span style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#111827">{code}</span>
    </div>
    <p style="color:#6B7280;font-size:13px">
      Este código expira en <strong>5 minutos</strong>.<br>
      No lo compartas con nadie.
    </p>
    <hr style="border:none;border-top:1px solid #E5E7EB;margin:24px 0">
    <p style="color:#9CA3AF;font-size:11px">
      Si no solicitaste este código, ignora este mensaje.
    </p>
  </div>
</body>
</html>
"""


class EmailService:
    """
    Sends emails via SendGrid HTTP API.
    Requires: SENDGRID_API_KEY, EMAIL_FROM
    """

    def __init__(self) -> None:
        from config.settings import settings
        self.api_key   = settings.SENDGRID_API_KEY
        self.from_email = settings.EMAIL_FROM
        self.from_name  = settings.EMAIL_FROM_NAME
        self._ready = bool(self.api_key)
        if not self._ready:
            logger.warning("SendGrid not configured — emails will be simulated.")

    def send_otp(self, email: str, code: str, brand_name: str = "Agente de Voz") -> bool:
        """Send a 6-digit OTP code to the given email address."""
        subject = f"Tu código de verificación: {code}"
        html = _OTP_HTML.format(code=code, brand_name=brand_name)
        plain = f"Tu código de verificación es: {code}. Válido por 5 minutos."
        return self._send(email, subject, html, plain)

    def send_welcome(self, email: str, name: str, api_key: str, brand_name: str = "Agente de Voz") -> bool:
        """Send welcome email after tenant registration."""
        subject = f"¡Bienvenido a {brand_name}!"
        html = f"""
        <div style="font-family:Arial,sans-serif;padding:32px">
          <h2>¡Hola {name}!</h2>
          <p>Tu cuenta ha sido creada exitosamente.</p>
          <p><strong>Tu API Key:</strong></p>
          <code style="background:#f3f4f6;padding:8px;border-radius:4px">{api_key}</code>
          <p>Guarda esta clave de forma segura — la necesitarás para conectar tus sistemas.</p>
        </div>
        """
        return self._send(email, subject, html)

    def _send(self, to_email: str, subject: str, html: str, plain: str = "") -> bool:
        if not self._ready:
            logger.info(f"[EMAIL SIMULADO] → {to_email} | Asunto: {subject}")
            return True

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": self.from_email, "name": self.from_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": plain or subject},
                {"type": "text/html",  "value": html},
            ],
        }
        try:
            import httpx
            resp = httpx.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            if resp.status_code in (200, 202):
                logger.info(f"Email sent to {to_email} | status={resp.status_code}")
                return True
            logger.error(f"SendGrid error {resp.status_code}: {resp.text}")
            return False
        except Exception as exc:
            logger.error(f"Email send error: {exc}")
            return False
