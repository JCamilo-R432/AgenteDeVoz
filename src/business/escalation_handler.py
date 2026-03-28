import logging
from datetime import datetime
from typing import Dict, Optional

from config.settings import settings


class EscalationHandler:
    """Manejador de escalaciones a agentes humanos."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.escalation_number = settings.ESCALATION_NUMBER

    def transfer(self) -> str:
        """Inicia la transferencia a un agente humano (sin contexto)."""
        return self.transfer_with_context({})

    def transfer_with_context(self, session_summary: Dict) -> str:
        """
        Transfiere la llamada a un agente humano enviando el contexto de la sesión.

        Args:
            session_summary: Resumen de la conversación hasta el momento.

        Returns:
            Mensaje informando la transferencia.
        """
        try:
            self.logger.info(
                f"Escalando a humano | Sesión: {session_summary.get('session_id')} | "
                f"Motivo: {session_summary.get('last_intent')}"
            )

            # Registrar la escalación
            self._log_escalation(session_summary)

            # Notificar al equipo (en producción: WebSocket push al panel de agentes)
            self._notify_human_agents(session_summary)

            return (
                "Perfecto, voy a transferirte con uno de nuestros agentes ahora mismo. "
                "Le informaré sobre tu consulta para que no tengas que repetir todo. "
                "Por favor mantente en línea, el tiempo de espera estimado es de 2 a 5 minutos. "
                "No cuelgues."
            )

        except Exception as e:
            self.logger.error(f"Error en transferencia: {e}")
            return (
                f"No pude completar la transferencia automáticamente. "
                f"Por favor llama directamente al {self.escalation_number} "
                f"o escríbenos y te contactaremos a la brevedad."
            )

    def schedule_callback(self, phone: str, preferred_time: Optional[str] = None) -> str:
        """
        Agenda una devolución de llamada.

        Args:
            phone: Número de teléfono del cliente.
            preferred_time: Horario preferido (ej: "mañana entre 9 y 11").

        Returns:
            Confirmación del callback agendado.
        """
        try:
            self.logger.info(f"Callback agendado: {phone} | Horario: {preferred_time}")

            callback_data = {
                "phone": phone,
                "preferred_time": preferred_time or "próximo horario disponible",
                "scheduled_at": datetime.now(),
                "status": "pending",
            }

            try:
                from integrations.database import Database
                db = Database()
                db.insert("callbacks", callback_data)
            except Exception:
                self.logger.warning("BD no disponible para guardar callback.")

            time_msg = f"a {preferred_time}" if preferred_time else "en el próximo horario disponible"
            return (
                f"Hemos agendado una devolución de llamada al {phone} {time_msg}. "
                "Un agente especializado te contactará. "
                "¿Hay algo más en que pueda ayudarte por ahora?"
            )

        except Exception as e:
            self.logger.error(f"Error agendando callback: {e}")
            return (
                "No pude agendar la devolución de llamada. "
                "¿Prefieres que te transfiera con un agente ahora mismo?"
            )

    def check_agent_availability(self) -> Dict:
        """
        Verifica disponibilidad de agentes humanos.

        Returns:
            Dict con estado de disponibilidad y tiempo de espera estimado.
        """
        from datetime import time as dt_time

        now = datetime.now()
        is_business_hours = (
            now.weekday() < 5  # Lunes a Viernes
            and dt_time(8, 0) <= now.time() <= dt_time(18, 0)
        ) or (
            now.weekday() == 5  # Sábado
            and dt_time(9, 0) <= now.time() <= dt_time(13, 0)
        )

        return {
            "available": is_business_hours,
            "business_hours": is_business_hours,
            "estimated_wait_minutes": 3 if is_business_hours else None,
            "message": (
                "Hay agentes disponibles ahora."
                if is_business_hours
                else "Nuestros agentes atienden de lunes a viernes 8AM-6PM y sábados 9AM-1PM."
            ),
        }

    # ── Privados ──────────────────────────────────────────────────────────────

    def _log_escalation(self, session_summary: Dict) -> None:
        """Registra la escalación en base de datos."""
        try:
            from integrations.database import Database
            db = Database()
            db.insert("escalations", {
                "session_id": session_summary.get("session_id"),
                "type": "escalation",
                "reason": session_summary.get("last_intent", "solicitud_cliente"),
                "conversation_summary": str(session_summary),
                "timestamp": datetime.now(),
            })
        except Exception as e:
            self.logger.warning(f"No se pudo registrar escalación en BD: {e}")

    def _notify_human_agents(self, session_summary: Dict) -> None:
        """
        Notifica a los agentes humanos disponibles.
        En producción: push por WebSocket al dashboard o sistema de cola.
        """
        self.logger.info(
            f"[NOTIFICACIÓN AGENTES] Nueva llamada en espera | "
            f"Sesión: {session_summary.get('session_id')} | "
            f"Motivo: {session_summary.get('last_intent')} | "
            f"Duración previa: {session_summary.get('duration_seconds', 0)}s"
        )
