"""
NotificationService — notificaciones multicanal completas.
Canales: Email (SendGrid), SMS/WhatsApp (Twilio/Meta).
Auto-fallback graceful cuando APIs no configuradas.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_notification_log: List[dict] = []
MAX_LOG_SIZE = 1000


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class NotificationType(str, Enum):
    ORDER_CONFIRMED = "order_confirmed"
    ORDER_PROCESSING = "order_processing"
    ORDER_SHIPPED = "order_shipped"
    ORDER_IN_TRANSIT = "order_in_transit"
    ORDER_OUT_FOR_DELIVERY = "out_for_delivery"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_DELAYED = "order_delayed"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_REMINDER = "payment_reminder"
    OTP_CODE = "otp_code"
    WELCOME = "welcome"
    POST_PURCHASE_SURVEY = "post_purchase_survey"


@dataclass
class NotificationResult:
    success: bool
    channel: str
    recipient: str
    notification_type: str
    error: Optional[str] = None
    provider_id: Optional[str] = None


class NotificationService:
    """Servicio de notificaciones multicanal con fallback graceful."""

    def __init__(self):
        self._email = None
        self._whatsapp = None
        self._init_channels()

    def _init_channels(self) -> None:
        try:
            from integrations.sendgrid_email import SendGridEmail
            from config.settings import settings
            self._email = SendGridEmail(settings.SENDGRID_API_KEY)
        except Exception as e:
            logger.debug(f"SendGrid no disponible: {e}")

        try:
            from integrations.whatsapp_api import WhatsAppAPI
            self._whatsapp = WhatsAppAPI()
        except Exception as e:
            logger.debug(f"WhatsApp API no disponible: {e}")

    async def send_otp(self, phone: str, code: str, channel: str = "sms") -> NotificationResult:
        """Envía código OTP por SMS o WhatsApp."""
        message = (
            f"Tu código de verificación es: {code}\n"
            f"Válido por 10 minutos. No lo compartas con nadie."
        )
        return await self._send_sms_or_whatsapp(phone, message, channel, NotificationType.OTP_CODE)

    async def send_order_confirmation(self, order, customer) -> List[NotificationResult]:
        """Confirmación de pedido por email + WhatsApp."""
        results = []
        order_num = getattr(order, "order_number", "N/A")
        total = getattr(order, "total_amount", 0)
        est_del = getattr(order, "estimated_delivery", None)
        est_str = est_del.strftime("%d/%m/%Y") if est_del else "Por confirmar"

        wa_msg = (
            f"Pedido confirmado #{order_num}\n"
            f"Total: ${float(total):,.0f} COP\n"
            f"Entrega estimada: {est_str}\n"
            f"Gracias por tu compra."
        )
        subject = f"Pedido confirmado #{order_num}"
        html = self._render_order_email("confirmed", order, customer)

        if getattr(customer, "email", None) and self._email:
            results.append(await self._send_email(
                customer.email, customer.full_name, subject, html, NotificationType.ORDER_CONFIRMED
            ))
        if getattr(customer, "phone", None):
            results.append(await self._send_whatsapp_or_log(
                customer.phone, wa_msg, NotificationType.ORDER_CONFIRMED
            ))
        return results

    async def send_status_update(self, order, customer, new_status: str) -> List[NotificationResult]:
        """Actualización de estado del pedido."""
        results = []
        order_num = getattr(order, "order_number", "N/A")

        STATUS_MESSAGES = {
            "processing": f"Tu pedido #{order_num} esta siendo preparado.",
            "shipped": f"Tu pedido #{order_num} fue enviado.",
            "in_transit": f"Tu pedido #{order_num} esta en camino.",
            "out_for_delivery": f"Tu pedido #{order_num} sale para entrega hoy.",
            "delivered": f"Tu pedido #{order_num} fue entregado.",
            "cancelled": f"Tu pedido #{order_num} fue cancelado.",
        }

        msg = STATUS_MESSAGES.get(new_status, f"Estado de pedido #{order_num}: {new_status}")
        subject = f"Actualizacion de tu pedido #{order_num}"
        html = self._render_order_email(new_status, order, customer)

        if getattr(customer, "email", None) and self._email:
            results.append(await self._send_email(
                customer.email, customer.full_name, subject, html, NotificationType.ORDER_IN_TRANSIT
            ))
        if getattr(customer, "phone", None):
            results.append(await self._send_whatsapp_or_log(
                customer.phone, msg, NotificationType.ORDER_IN_TRANSIT
            ))
        return results

    async def send_delivery_notification(self, order, customer) -> List[NotificationResult]:
        """Notificacion especial de entrega."""
        order_num = getattr(order, "order_number", "N/A")
        msg = (
            f"Tu pedido #{order_num} fue entregado!\n"
            f"Esperamos que todo llegara perfecto.\n"
            f"Como calificarias tu experiencia del 1 al 5?"
        )
        results = []
        if getattr(customer, "phone", None):
            results.append(await self._send_whatsapp_or_log(
                customer.phone, msg, NotificationType.ORDER_DELIVERED
            ))
        return results

    async def send_payment_reminder(self, order, customer) -> List[NotificationResult]:
        """Recordatorio de pago pendiente."""
        order_num = getattr(order, "order_number", "N/A")
        total = getattr(order, "total_amount", 0)
        msg = (
            f"Pago pendiente para pedido #{order_num}\n"
            f"Total: ${float(total):,.0f} COP\n"
            f"Completa tu pago para confirmar."
        )
        results = []
        if getattr(customer, "phone", None):
            results.append(await self._send_whatsapp_or_log(
                customer.phone, msg, NotificationType.PAYMENT_REMINDER
            ))
        return results

    async def send_payment_failed(self, order, customer, reason: str = "") -> List[NotificationResult]:
        """Notificacion de pago fallido."""
        order_num = getattr(order, "order_number", "N/A")
        msg = (
            f"Pago rechazado para pedido #{order_num}\n"
            f"Por favor intenta con otro metodo de pago."
            f"{(' Motivo: ' + reason) if reason else ''}"
        )
        results = []
        if getattr(customer, "phone", None):
            results.append(await self._send_whatsapp_or_log(
                customer.phone, msg, NotificationType.PAYMENT_FAILED
            ))
        return results

    async def send_post_purchase_survey(self, order, customer) -> List[NotificationResult]:
        """Encuesta NPS post-compra."""
        order_num = getattr(order, "order_number", "N/A")
        msg = (
            f"Como fue tu experiencia con el pedido #{order_num}?\n"
            f"Del 0 al 10, que tan probable es que nos recomiendes?\n"
            f"Responde con tu puntuacion."
        )
        results = []
        if getattr(customer, "phone", None):
            results.append(await self._send_whatsapp_or_log(
                customer.phone, msg, NotificationType.POST_PURCHASE_SURVEY
            ))
        return results

    # ── Privados ─────────────────────────────────────────────────────────────

    async def _send_email(
        self, email: str, name: str, subject: str, html: str, ntype: NotificationType
    ) -> NotificationResult:
        result = NotificationResult(
            success=False, channel="email", recipient=email, notification_type=ntype.value
        )
        try:
            if self._email:
                sent = self._email.send(email, name, subject, html)
                result.success = bool(sent)
            else:
                self._log_notification(ntype.value, email, subject)
                result.success = True
        except Exception as e:
            result.error = str(e)
            logger.warning(f"Error enviando email a {email}: {e}")
        self._record_log(result)
        return result

    async def _send_whatsapp_or_log(
        self, phone: str, message: str, ntype: NotificationType
    ) -> NotificationResult:
        result = NotificationResult(
            success=False, channel="whatsapp", recipient=phone, notification_type=ntype.value
        )
        try:
            if self._whatsapp and hasattr(self._whatsapp, "send_text"):
                sent = self._whatsapp.send_text(phone, message)
                result.success = bool(sent)
            else:
                self._log_notification(ntype.value, phone, message)
                result.success = True
        except Exception as e:
            result.error = str(e)
            logger.warning(f"Error enviando WhatsApp a {phone}: {e}")
        self._record_log(result)
        return result

    async def _send_sms_or_whatsapp(
        self, phone: str, message: str, channel: str, ntype: NotificationType
    ) -> NotificationResult:
        result = NotificationResult(
            success=False, channel=channel, recipient=phone, notification_type=ntype.value
        )
        try:
            from config.settings import settings
            if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
                from twilio.rest import Client
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                to = f"whatsapp:{phone}" if channel == "whatsapp" else phone
                msg = client.messages.create(
                    body=message, from_=settings.TWILIO_PHONE_NUMBER, to=to
                )
                result.success = True
                result.provider_id = msg.sid
            else:
                self._log_notification(ntype.value, phone, message)
                result.success = True
        except Exception as e:
            result.error = str(e)
            logger.warning(f"Error enviando {channel} a {phone}: {e}")
        self._record_log(result)
        return result

    def _render_order_email(self, template: str, order, customer) -> str:
        order_num = getattr(order, "order_number", "N/A")
        total = getattr(order, "total_amount", 0)
        status = getattr(order, "status", template)
        est_del = getattr(order, "estimated_delivery", None)
        est_str = est_del.strftime("%d/%m/%Y") if est_del else "Por confirmar"
        name = getattr(customer, "full_name", "Cliente")

        return (
            f"<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px'>"
            f"<h2 style='color:#2c3e50'>Actualizacion de tu pedido</h2>"
            f"<p>Hola <strong>{name}</strong>,</p>"
            f"<table style='width:100%;border-collapse:collapse'>"
            f"<tr><td style='padding:10px;border:1px solid #ddd'><b>Pedido</b></td>"
            f"<td style='padding:10px;border:1px solid #ddd'>{order_num}</td></tr>"
            f"<tr><td style='padding:10px;border:1px solid #ddd'><b>Estado</b></td>"
            f"<td style='padding:10px;border:1px solid #ddd'>{status}</td></tr>"
            f"<tr><td style='padding:10px;border:1px solid #ddd'><b>Total</b></td>"
            f"<td style='padding:10px;border:1px solid #ddd'>${float(total):,.0f} COP</td></tr>"
            f"<tr><td style='padding:10px;border:1px solid #ddd'><b>Entrega estimada</b></td>"
            f"<td style='padding:10px;border:1px solid #ddd'>{est_str}</td></tr>"
            f"</table></div>"
        )

    def _log_notification(self, ntype: str, recipient: str, message: str) -> None:
        logger.info(f"[NOTIF SIMULADA] {ntype} → {recipient}: {message[:80]}")

    def _record_log(self, result: NotificationResult) -> None:
        global _notification_log
        _notification_log.append({
            "type": result.notification_type,
            "channel": result.channel,
            "recipient": result.recipient,
            "success": result.success,
            "error": result.error,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(_notification_log) > MAX_LOG_SIZE:
            _notification_log = _notification_log[-MAX_LOG_SIZE:]

    def get_history(self, limit: int = 50) -> List[dict]:
        return list(reversed(_notification_log))[:limit]
