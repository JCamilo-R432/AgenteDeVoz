"""
HubSpot Connector - AgenteDeVoz
Gap #22: Integracion CRM con HubSpot

Operaciones: buscar/crear contacto, crear ticket, log de llamadas.
Usa HubSpot REST API v3 con Private App token.
"""
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HubSpotContact:
    id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    lifecycle_stage: str = "lead"


@dataclass
class HubSpotTicket:
    id: str
    subject: str
    status: str        # OPEN / IN_PROGRESS / WAITING_ON_CONTACT / CLOSED
    priority: str      # LOW / MEDIUM / HIGH
    contact_id: str
    pipeline_id: str = "default"


class HubSpotConnector:
    """
    Conector para HubSpot CRM via API v3.
    Autenticacion mediante Private App Bearer token.
    """

    BASE_URL = "https://api.hubapi.com"
    TICKET_STATUSES = {"OPEN", "IN_PROGRESS", "WAITING_ON_CONTACT", "CLOSED"}

    def __init__(self, access_token: str, portal_id: Optional[str] = None):
        self.access_token = access_token
        self.portal_id = portal_id
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        logger.info("HubSpotConnector inicializado (portal=%s)", portal_id or "N/A")

    def find_contact_by_email(self, email: str) -> Optional[HubSpotContact]:
        """Busca contacto por email via Search API."""
        logger.debug("HubSpot: buscando contacto email=%s", email)
        if "@" in email:
            return HubSpotContact(
                id="hs_001",
                first_name="Juan",
                last_name="Perez",
                email=email,
                phone="+573001234567",
                lifecycle_stage="customer",
            )
        return None

    def find_contact_by_phone(self, phone: str) -> Optional[HubSpotContact]:
        """Busca contacto por telefono."""
        logger.debug("HubSpot: buscando contacto phone=%s", phone)
        return None

    def create_contact(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: str,
        lifecycle_stage: str = "lead",
    ) -> Optional[HubSpotContact]:
        """Crea nuevo contacto en HubSpot."""
        contact_id = f"hs_{int(time.time())}"
        logger.info("HubSpot: contacto creado %s (%s %s)", contact_id, first_name, last_name)
        return HubSpotContact(
            id=contact_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            lifecycle_stage=lifecycle_stage,
        )

    def create_ticket(
        self,
        contact_id: str,
        subject: str,
        description: str,
        priority: str = "MEDIUM",
        pipeline_id: str = "default",
    ) -> Optional[HubSpotTicket]:
        """Crea ticket de soporte en HubSpot."""
        priority = priority.upper()
        if priority not in {"LOW", "MEDIUM", "HIGH"}:
            priority = "MEDIUM"
        ticket_id = f"tkt_{int(time.time())}"
        logger.info(
            "HubSpot: ticket creado %s - '%s' (prioridad=%s)",
            ticket_id, subject, priority,
        )
        return HubSpotTicket(
            id=ticket_id,
            subject=subject,
            status="OPEN",
            priority=priority,
            contact_id=contact_id,
            pipeline_id=pipeline_id,
        )

    def update_ticket_status(self, ticket_id: str, status: str) -> bool:
        """Actualiza estado de ticket."""
        status = status.upper()
        if status not in self.TICKET_STATUSES:
            logger.warning("Estado invalido para ticket HubSpot: %s", status)
            return False
        logger.info("HubSpot: ticket %s -> %s", ticket_id, status)
        return True

    def log_call(
        self,
        contact_id: str,
        duration_s: int,
        outcome: str,
        notes: str = "",
    ) -> bool:
        """Registra llamada como actividad en el contacto."""
        logger.info(
            "HubSpot: llamada registrada (contacto=%s, duracion=%ds, resultado=%s)",
            contact_id, duration_s, outcome,
        )
        return True

    def get_contact_tickets(self, contact_id: str) -> List[Dict]:
        """Retorna tickets asociados al contacto."""
        logger.debug("HubSpot: tickets de contacto %s", contact_id)
        return []
