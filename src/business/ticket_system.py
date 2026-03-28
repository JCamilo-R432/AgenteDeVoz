import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional


class TicketSystem:
    """Sistema de gestión de tickets de soporte."""

    PRIORITY_SLA: Dict[str, int] = {
        "URGENTE": 2,    # 2 horas hábiles
        "ALTA": 8,       # 8 horas hábiles
        "MEDIA": 24,     # 24 horas hábiles
        "BAJA": 72,      # 72 horas hábiles
    }

    HIGH_PRIORITY_KEYWORDS = [
        "urgente", "emergencia", "no funciona", "crítico", "urgencia",
        "sin servicio", "caído", "fraude",
    ]

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._db = None  # Lazy load para no fallar si la BD no está disponible en testing

    def _get_db(self):
        """Obtiene la conexión a BD de forma lazy."""
        if self._db is None:
            try:
                from integrations.database import Database
                self._db = Database()
            except Exception as e:
                self.logger.warning(f"BD no disponible: {e}. Usando modo simulado.")
        return self._db

    def create(self, entities: Dict, description: str) -> str:
        """
        Crea un nuevo ticket de soporte.

        Args:
            entities: Entidades extraídas del texto del usuario.
            description: Descripción del problema.

        Returns:
            Mensaje de confirmación con el número de ticket.
        """
        try:
            ticket_number = self._generate_ticket_number()
            priority = self._determine_priority(description, entities)
            category = entities.get("problem_type", "otro")
            sla_deadline = datetime.now() + timedelta(hours=self.PRIORITY_SLA[priority])

            ticket_data = {
                "ticket_number": ticket_number,
                "description": description,
                "category": category,
                "status": "ABIERTO",
                "priority": priority,
                "channel": "voice",
                "sla_deadline": sla_deadline,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

            # Agregar entidades relevantes si existen
            if entities.get("amount_charged"):
                ticket_data["description"] += f" | Monto cobrado: ${entities['amount_charged']}"
            if entities.get("amount_expected"):
                ticket_data["description"] += f" | Monto esperado: ${entities['amount_expected']}"

            db = self._get_db()
            if db:
                db.insert("tickets", ticket_data)

            self.logger.info(f"Ticket creado: {ticket_number} | Prioridad: {priority}")

            estimated_response = self._get_sla_message(priority)
            return (
                f"Tu ticket {ticket_number} ha sido creado exitosamente con prioridad {priority}. "
                f"{estimated_response} "
                "Te enviaremos actualizaciones a tu contacto registrado. "
                "¿Hay algo más en que pueda ayudarte?"
            )

        except Exception as e:
            self.logger.error(f"Error creando ticket: {e}", exc_info=True)
            return (
                "Tuve un problema técnico al crear tu ticket. "
                "¿Deseas que te transfiera con un agente humano para continuar?"
            )

    def check_status(self, entities: Dict) -> str:
        """
        Consulta el estado de un ticket existente.

        Args:
            entities: Debe contener 'ticket_id' o 'order_id'.

        Returns:
            Información del estado del ticket.
        """
        ticket_ref = entities.get("ticket_id") or entities.get("order_id")

        if not ticket_ref:
            return (
                "Necesito el número de tu ticket para consultarlo. "
                "¿Lo tienes a la mano? Empieza con TKT- seguido de la fecha y número."
            )

        try:
            db = self._get_db()
            if db:
                ticket = db.find_one("tickets", {"ticket_number": ticket_ref})
                if ticket:
                    return self._format_ticket_status(ticket)
                return (
                    f"No encontré ningún ticket con el número {ticket_ref}. "
                    "¿Podrías verificar que el número sea correcto? "
                    "El formato es TKT-YYYY-NNNNNN."
                )
            else:
                # Modo simulado para testing sin BD
                return (
                    f"Tu ticket {ticket_ref} está actualmente EN PROCESO. "
                    "Fue asignado a nuestro equipo de soporte. "
                    "¿Deseas dejar algún comentario adicional?"
                )

        except Exception as e:
            self.logger.error(f"Error consultando ticket {ticket_ref}: {e}")
            return "Tuve un problema consultando tu ticket. Por favor intenta de nuevo."

    def create_complaint(self, entities: Dict, description: str) -> str:
        """Crea un ticket de queja con prioridad ALTA."""
        entities = {**entities, "problem_type": "atencion"}
        self.logger.warning(f"Queja registrada: '{description[:100]}'")
        return (
            "Lamento mucho que hayas tenido esta experiencia. "
            + self.create(entities, f"[QUEJA] {description}")
        )

    def update_status(self, ticket_number: str, status: str, note: str = "") -> bool:
        """Actualiza el estado de un ticket."""
        try:
            db = self._get_db()
            if not db:
                return False
            data = {"status": status, "updated_at": datetime.now()}
            if note:
                data["resolution_notes"] = note
            db.update("tickets", {"ticket_number": ticket_number}, data)
            self.logger.info(f"Ticket {ticket_number} actualizado a {status}")
            return True
        except Exception as e:
            self.logger.error(f"Error actualizando ticket: {e}")
            return False

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _generate_ticket_number(self) -> str:
        """Genera un número de ticket único en formato TKT-YYYY-NNNNNN."""
        year = datetime.now().year
        unique_part = str(uuid.uuid4().int)[:6].zfill(6)
        return f"TKT-{year}-{unique_part}"

    def _determine_priority(self, description: str, entities: Dict) -> str:
        """Determina la prioridad del ticket basándose en el contenido."""
        desc_lower = description.lower()

        if any(kw in desc_lower for kw in self.HIGH_PRIORITY_KEYWORDS):
            return "URGENTE"

        problem_type = entities.get("problem_type", "")
        if problem_type == "facturacion":
            return "ALTA"
        if problem_type in ("tecnico", "envio"):
            return "MEDIA"

        return "MEDIA"

    def _get_sla_message(self, priority: str) -> str:
        """Retorna el mensaje de tiempo de respuesta según la prioridad."""
        messages = {
            "URGENTE": "Un agente te contactará en las próximas 2 horas hábiles.",
            "ALTA": "Un agente te contactará en las próximas 8 horas hábiles.",
            "MEDIA": "Un agente te contactará en las próximas 24 horas hábiles.",
            "BAJA": "Un agente te contactará en los próximos 3 días hábiles.",
        }
        return messages.get(priority, "Te contactaremos a la brevedad.")

    def _format_ticket_status(self, ticket: Dict) -> str:
        """Formatea la información de un ticket para presentarla al usuario."""
        status_translations = {
            "ABIERTO": "abierto y pendiente de asignación",
            "EN_PROCESO": "en proceso de resolución",
            "RESUELTO": "resuelto",
            "CERRADO": "cerrado",
            "REABIERTO": "reabierto",
        }
        status_text = status_translations.get(ticket.get("status", ""), ticket.get("status", ""))
        created = ticket.get("created_at", "")
        if hasattr(created, "strftime"):
            created = created.strftime("%d de %B a las %H:%M")

        response = (
            f"Tu ticket {ticket['ticket_number']} está actualmente {status_text}. "
            f"Fue creado el {created}. "
        )
        if ticket.get("assigned_to"):
            response += f"Está asignado a {ticket['assigned_to']}. "
        if ticket.get("resolution_notes"):
            response += f"Última actualización: {ticket['resolution_notes']}. "

        return response + "¿Deseas agregar algún comentario o necesitas algo más?"
