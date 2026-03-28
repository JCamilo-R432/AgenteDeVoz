"""
Integración con WhatsApp Business API (Meta Cloud API).
Envía mensajes de seguimiento post-llamada, confirmaciones de ticket,
y notificaciones de estado.
"""

import httpx
import json
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("whatsapp_api")


class WhatsAppAPI:
    """
    Cliente para la API de WhatsApp Business de Meta.
    Fallback a log cuando no hay credenciales configuradas.
    """

    BASE_URL = "https://graph.facebook.com/v19.0"

    # Plantillas preaprobadas en Meta
    TEMPLATES = {
        "bienvenida": "agente_bienvenida_v1",
        "ticket_creado": "agente_ticket_creado_v1",
        "ticket_resuelto": "agente_ticket_resuelto_v1",
        "encuesta_satisfaccion": "agente_encuesta_v1",
        "recordatorio_callback": "agente_callback_v1",
    }

    def __init__(self, access_token: str = "", phone_number_id: str = "",
                 verify_token: str = ""):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.verify_token = verify_token
        self._configured = bool(access_token and phone_number_id)

        if not self._configured:
            logger.warning("WhatsApp API no configurada. Los mensajes se loguearán.")

    # ── Envío de mensajes ──────────────────────────────────────────────────────

    def send_text(self, to: str, message: str) -> bool:
        """Envía un mensaje de texto libre a un número de WhatsApp."""
        to = self._normalize_phone(to)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }
        return self._send(payload)

    def send_template(self, to: str, template_name: str,
                      components: Optional[list] = None,
                      language_code: str = "es") -> bool:
        """Envía un mensaje usando una plantilla aprobada por Meta."""
        to = self._normalize_phone(to)
        template = {
            "name": template_name,
            "language": {"code": language_code},
        }
        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template,
        }
        return self._send(payload)

    def send_ticket_confirmation(self, to: str, ticket_id: str,
                                  category: str, eta: str) -> bool:
        """
        Envía confirmación de ticket creado.
        Usa plantilla con variables: {{1}}=ticket_id, {{2}}=category, {{3}}=eta
        """
        components = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": ticket_id},
                    {"type": "text", "text": category},
                    {"type": "text", "text": eta},
                ],
            }
        ]
        success = self.send_template(
            to,
            self.TEMPLATES["ticket_creado"],
            components=components,
        )
        if success:
            logger.info(f"Confirmacion de ticket {ticket_id} enviada a {to}")
        return success

    def send_post_call_survey(self, to: str, agent_name: str = "Ava") -> bool:
        """Envía encuesta de satisfacción post-llamada (escala 1-5)."""
        message = (
            f"Hola, soy {agent_name} del servicio al cliente. "
            "Acabamos de atenderte por llamada. "
            "Por favor califica la atención del 1 al 5:\n"
            "1-Muy malo  2-Malo  3-Regular  4-Bueno  5-Excelente\n"
            "Responde solo con el numero."
        )
        return self.send_text(to, message)

    def send_callback_reminder(self, to: str, scheduled_time: str) -> bool:
        """Notifica al cliente sobre un callback programado."""
        message = (
            f"Te recordamos que tienes una llamada de retorno programada para: "
            f"{scheduled_time}. Un agente se comunicara contigo en ese horario. "
            "Si necesitas reprogramar, llama al 01-800-XXX-XXXX."
        )
        return self.send_text(to, message)

    def send_ticket_resolved(self, to: str, ticket_id: str) -> bool:
        """Notifica que un ticket ha sido resuelto."""
        message = (
            f"Tu caso {ticket_id} ha sido resuelto. "
            "Si el problema persiste, puedes reabrir el caso llamando "
            "o respondiendo este mensaje. Gracias por tu paciencia."
        )
        return self.send_text(to, message)

    # ── Webhook ───────────────────────────────────────────────────────────────

    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """
        Verifica la suscripción del webhook de Meta.
        Retorna el challenge si es válido, None si no.
        """
        if mode == "subscribe" and token == self.verify_token:
            logger.info("Webhook de WhatsApp verificado correctamente.")
            return challenge
        logger.warning("Intento de verificacion de webhook con token incorrecto.")
        return None

    def parse_incoming(self, payload: dict) -> list:
        """
        Parsea el payload de un webhook entrante.
        Retorna lista de mensajes con estructura normalizada.
        """
        messages = []
        try:
            entries = payload.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    incoming = value.get("messages", [])
                    for msg in incoming:
                        parsed = {
                            "id": msg.get("id"),
                            "from": msg.get("from"),
                            "timestamp": msg.get("timestamp"),
                            "type": msg.get("type", "text"),
                            "text": msg.get("text", {}).get("body", ""),
                        }
                        messages.append(parsed)
        except Exception as e:
            logger.error(f"Error parseando webhook: {e}")
        return messages

    def mark_as_read(self, message_id: str) -> bool:
        """Marca un mensaje entrante como leído."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        url = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        return self._post(url, payload)

    # ── Helpers privados ───────────────────────────────────────────────────────

    def _send(self, payload: dict) -> bool:
        if not self._configured:
            logger.info(f"[WhatsApp SIMULADO] Payload: {json.dumps(payload, ensure_ascii=False)}")
            return True
        url = f"{self.BASE_URL}/{self.phone_number_id}/messages"
        return self._post(url, payload)

    def _post(self, url: str, payload: dict) -> bool:
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                return True
            logger.error(f"WhatsApp API error {resp.status_code}: {resp.text}")
            return False
        except httpx.TimeoutException:
            logger.error("WhatsApp API timeout")
            return False
        except Exception as e:
            logger.error(f"WhatsApp API excepcion: {e}")
            return False

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Asegura formato E.164 para Colombia (+57...)."""
        phone = phone.strip().replace(" ", "").replace("-", "")
        if phone.startswith("0"):
            phone = phone[1:]
        if not phone.startswith("+"):
            if len(phone) == 10:          # número colombiano sin código
                phone = f"+57{phone}"
            elif not phone.startswith("57"):
                phone = f"+{phone}"
            else:
                phone = f"+{phone}"
        return phone
