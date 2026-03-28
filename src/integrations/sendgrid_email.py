"""
Integración con SendGrid para envío de correos.
Soporta plantillas HTML, notificaciones de ticket, escalaciones y alertas.
"""

import os
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("sendgrid_email")


class SendGridEmail:
    """
    Cliente de email usando SendGrid.
    Fallback a consola cuando no hay API key.
    """

    FROM_EMAIL = "noreply@agentevoz.com"
    FROM_NAME  = "Agente de Voz - Soporte"

    # IDs de plantillas dinámicas en SendGrid (reemplazar con IDs reales)
    TEMPLATE_IDS = {
        "ticket_creado":    "d-ticket-creado-template-id",
        "ticket_resuelto":  "d-ticket-resuelto-template-id",
        "escalacion":       "d-escalacion-template-id",
        "bienvenida":       "d-bienvenida-template-id",
        "encuesta":         "d-encuesta-template-id",
        "alerta_sistema":   "d-alerta-sistema-template-id",
    }

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("SENDGRID_API_KEY", "")
        self._configured = bool(self.api_key)
        if not self._configured:
            logger.warning("SendGrid no configurado. Los emails se loguearán.")

    # ── Envío genérico ─────────────────────────────────────────────────────────

    def send(self, to_email: str, to_name: str,
             subject: str, html_content: str,
             plain_text: str = "") -> bool:
        """Envía un email HTML genérico."""
        if not self._configured:
            logger.info(
                f"[Email SIMULADO] Para: {to_email} | "
                f"Asunto: {subject}"
            )
            return True
        return self._send_via_sendgrid(to_email, to_name, subject,
                                        html_content, plain_text)

    def send_template(self, to_email: str, to_name: str,
                       template_key: str, dynamic_data: dict) -> bool:
        """Envía un email usando una plantilla dinámica de SendGrid."""
        template_id = self.TEMPLATE_IDS.get(template_key)
        if not template_id:
            logger.error(f"Template desconocido: {template_key}")
            return False

        if not self._configured:
            logger.info(
                f"[Email SIMULADO] Template={template_key} "
                f"Para={to_email} Data={dynamic_data}"
            )
            return True
        return self._send_template_via_sendgrid(to_email, to_name,
                                                  template_id, dynamic_data)

    # ── Notificaciones de dominio ─────────────────────────────────────────────

    def notify_ticket_created(self, to_email: str, customer_name: str,
                               ticket_id: str, category: str,
                               description: str, eta: str) -> bool:
        """Envía confirmación de creación de ticket al cliente."""
        html = self._build_ticket_created_html(
            customer_name, ticket_id, category, description, eta
        )
        plain = (
            f"Hola {customer_name},\n"
            f"Tu caso ha sido registrado.\n"
            f"Numero de ticket: {ticket_id}\n"
            f"Categoria: {category}\n"
            f"Tiempo estimado de resolucion: {eta}\n"
        )
        return self.send(
            to_email, customer_name,
            f"Caso registrado: {ticket_id} - Agente de Voz",
            html, plain
        )

    def notify_ticket_resolved(self, to_email: str, customer_name: str,
                                ticket_id: str, resolution: str) -> bool:
        """Envía notificación de resolución al cliente."""
        html = self._build_ticket_resolved_html(customer_name, ticket_id, resolution)
        plain = (
            f"Hola {customer_name},\n"
            f"Tu caso {ticket_id} ha sido resuelto.\n"
            f"Resolucion: {resolution}\n"
        )
        return self.send(
            to_email, customer_name,
            f"Caso resuelto: {ticket_id} - Agente de Voz",
            html, plain
        )

    def notify_escalation(self, agent_email: str, agent_name: str,
                           customer_phone: str, context_summary: str,
                           call_duration: int) -> bool:
        """Notifica a un agente humano sobre una transferencia de llamada."""
        html = self._build_escalation_html(
            agent_name, customer_phone, context_summary, call_duration
        )
        minutes = call_duration // 60
        seconds = call_duration % 60
        plain = (
            f"Hola {agent_name},\n"
            f"Tienes una llamada transferida del Agente de Voz.\n"
            f"Cliente: {customer_phone}\n"
            f"Duracion previa: {minutes}m {seconds}s\n"
            f"Resumen: {context_summary}\n"
        )
        return self.send(
            agent_email, agent_name,
            "Llamada transferida - Accion requerida",
            html, plain
        )

    def send_system_alert(self, admin_emails: list, alert_type: str,
                          message: str, severity: str = "WARNING") -> bool:
        """Envía alerta de sistema a los administradores."""
        html = self._build_alert_html(alert_type, message, severity)
        success = True
        for email in admin_emails:
            ok = self.send(
                email, "Administrador",
                f"[{severity}] Alerta AgenteDeVoz: {alert_type}",
                html, message
            )
            success = success and ok
        return success

    # ── Construcción de HTML ──────────────────────────────────────────────────

    def _build_ticket_created_html(self, name: str, ticket_id: str,
                                    category: str, desc: str, eta: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Caso Registrado</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;}}
  .card{{background:#fff;border-radius:8px;padding:30px;max-width:600px;margin:auto;}}
  .header{{background:#1a73e8;color:#fff;padding:20px;border-radius:8px 8px 0 0;text-align:center;}}
  .ticket-box{{background:#f0f7ff;border-left:4px solid #1a73e8;padding:15px;margin:20px 0;}}
  .label{{color:#666;font-size:12px;text-transform:uppercase;}}
  .value{{font-size:16px;font-weight:bold;color:#222;}}
  .footer{{color:#999;font-size:12px;text-align:center;margin-top:20px;}}
</style></head>
<body>
<div class="card">
  <div class="header"><h2>Caso Registrado</h2></div>
  <p>Hola <strong>{name}</strong>,</p>
  <p>Tu solicitud ha sido registrada en nuestro sistema. A continuacion los detalles:</p>
  <div class="ticket-box">
    <div class="label">Numero de Ticket</div>
    <div class="value">{ticket_id}</div>
    <br>
    <div class="label">Categoria</div>
    <div class="value">{category}</div>
    <br>
    <div class="label">Descripcion</div>
    <div class="value">{desc}</div>
    <br>
    <div class="label">Tiempo Estimado de Resolucion</div>
    <div class="value">{eta}</div>
  </div>
  <p>Puedes consultar el estado de tu caso en cualquier momento llamando a nuestra linea de atencion.</p>
  <div class="footer">Agente de Voz - Servicio al Cliente | No responder este correo</div>
</div>
</body></html>"""

    def _build_ticket_resolved_html(self, name: str, ticket_id: str,
                                     resolution: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Caso Resuelto</title>
<style>
  body{{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px;}}
  .card{{background:#fff;border-radius:8px;padding:30px;max-width:600px;margin:auto;}}
  .header{{background:#34a853;color:#fff;padding:20px;border-radius:8px 8px 0 0;text-align:center;}}
  .res-box{{background:#f0fff4;border-left:4px solid #34a853;padding:15px;margin:20px 0;}}
  .footer{{color:#999;font-size:12px;text-align:center;margin-top:20px;}}
</style></head>
<body>
<div class="card">
  <div class="header"><h2>Caso Resuelto</h2></div>
  <p>Hola <strong>{name}</strong>,</p>
  <p>Nos complace informarte que tu caso <strong>{ticket_id}</strong> ha sido resuelto.</p>
  <div class="res-box">
    <strong>Resolucion aplicada:</strong><br>{resolution}
  </div>
  <p>Si el problema persiste, comunicate con nosotros para reabrir el caso.</p>
  <div class="footer">Agente de Voz - Servicio al Cliente</div>
</div>
</body></html>"""

    def _build_escalation_html(self, agent: str, phone: str,
                                summary: str, duration: int) -> str:
        minutes = duration // 60
        return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Llamada Transferida</title>
<style>
  body{{font-family:Arial,sans-serif;background:#fff8e1;margin:0;padding:20px;}}
  .card{{background:#fff;border-radius:8px;padding:30px;max-width:600px;margin:auto;border:2px solid #f9a825;}}
  .header{{background:#f9a825;color:#fff;padding:20px;border-radius:8px 8px 0 0;text-align:center;}}
  .info{{background:#fffde7;padding:15px;margin:15px 0;border-radius:4px;}}
</style></head>
<body>
<div class="card">
  <div class="header"><h2>Llamada Transferida - Accion Requerida</h2></div>
  <p>Hola <strong>{agent}</strong>,</p>
  <p>Se ha transferido una llamada del Agente de Voz automatico. Por favor atiende al cliente.</p>
  <div class="info">
    <strong>Telefono del cliente:</strong> {phone}<br>
    <strong>Duracion previa con bot:</strong> {minutes} minutos<br>
    <strong>Resumen de la conversacion:</strong><br>{summary}
  </div>
  <p>El cliente esta en espera. Responde lo antes posible.</p>
</div>
</body></html>"""

    def _build_alert_html(self, alert_type: str, message: str,
                           severity: str) -> str:
        colors = {"CRITICAL": "#d32f2f", "WARNING": "#f57c00", "INFO": "#1565c0"}
        color = colors.get(severity, "#333")
        return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Alerta del Sistema</title>
<style>
  body{{font-family:monospace;background:#1a1a1a;color:#eee;padding:20px;}}
  .box{{background:#2a2a2a;padding:20px;border-left:5px solid {color};border-radius:4px;}}
  .sev{{color:{color};font-weight:bold;font-size:18px;}}
</style></head>
<body>
<div class="box">
  <div class="sev">[{severity}] {alert_type}</div>
  <pre style="margin-top:15px;white-space:pre-wrap;">{message}</pre>
</div>
</body></html>"""

    # ── SendGrid HTTP directo ─────────────────────────────────────────────────

    def _send_via_sendgrid(self, to_email: str, to_name: str,
                            subject: str, html: str, plain: str) -> bool:
        try:
            import httpx
            payload = {
                "personalizations": [
                    {"to": [{"email": to_email, "name": to_name}]}
                ],
                "from": {"email": self.FROM_EMAIL, "name": self.FROM_NAME},
                "subject": subject,
                "content": [
                    {"type": "text/plain", "value": plain or "Ver version HTML."},
                    {"type": "text/html", "value": html},
                ],
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload, headers=headers
                )
            if resp.status_code in (200, 202):
                logger.info(f"Email enviado a {to_email}: {subject}")
                return True
            logger.error(f"SendGrid error {resp.status_code}: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"SendGrid excepcion: {e}")
            return False

    def _send_template_via_sendgrid(self, to_email: str, to_name: str,
                                     template_id: str, data: dict) -> bool:
        try:
            import httpx
            payload = {
                "personalizations": [
                    {
                        "to": [{"email": to_email, "name": to_name}],
                        "dynamic_template_data": data,
                    }
                ],
                "from": {"email": self.FROM_EMAIL, "name": self.FROM_NAME},
                "template_id": template_id,
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload, headers=headers
                )
            if resp.status_code in (200, 202):
                logger.info(f"Template email enviado a {to_email}: {template_id}")
                return True
            logger.error(f"SendGrid template error {resp.status_code}: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"SendGrid template excepcion: {e}")
            return False
