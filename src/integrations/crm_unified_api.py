"""
CRM Unified API - AgenteDeVoz
Gap #22: API unificada para multiples CRMs

Abstraccion que permite usar Salesforce o HubSpot
sin cambiar el codigo de negocio.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from .salesforce_connector import SalesforceConnector, SalesforceContact, SalesforceCase
from .hubspot_connector import HubSpotConnector, HubSpotContact, HubSpotTicket

logger = logging.getLogger(__name__)


class CRMProvider(Enum):
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"


@dataclass
class UnifiedContact:
    id: str
    name: str
    email: str
    phone: str
    provider: str
    account_id: Optional[str] = None
    raw: Optional[Dict] = None


@dataclass
class UnifiedTicket:
    id: str
    subject: str
    status: str
    priority: str
    contact_id: str
    provider: str


class CRMUnifiedAPI:
    """
    API unificada para interactuar con cualquier CRM soportado.
    Patron de diseno: Facade + Strategy.
    """

    def __init__(
        self,
        provider: CRMProvider,
        salesforce_connector: Optional[SalesforceConnector] = None,
        hubspot_connector: Optional[HubSpotConnector] = None,
    ):
        self.provider = provider
        self._sf = salesforce_connector
        self._hs = hubspot_connector
        self._validate_provider()
        logger.info("CRMUnifiedAPI inicializado (provider=%s)", provider.value)

    def _validate_provider(self) -> None:
        if self.provider == CRMProvider.SALESFORCE and self._sf is None:
            raise ValueError("SalesforceConnector requerido para provider=SALESFORCE")
        if self.provider == CRMProvider.HUBSPOT and self._hs is None:
            raise ValueError("HubSpotConnector requerido para provider=HUBSPOT")

    # ------------------------------------------------------------------
    # Contactos
    # ------------------------------------------------------------------

    def find_contact_by_phone(self, phone: str) -> Optional[UnifiedContact]:
        """Busca contacto por telefono en el CRM activo."""
        if self.provider == CRMProvider.SALESFORCE:
            result = self._sf.find_contact_by_phone(phone)
            if result:
                return UnifiedContact(
                    id=result.id,
                    name=result.name,
                    email=result.email,
                    phone=result.phone,
                    provider="salesforce",
                    account_id=result.account_id,
                )
        elif self.provider == CRMProvider.HUBSPOT:
            result = self._hs.find_contact_by_phone(phone)
            if result:
                return UnifiedContact(
                    id=result.id,
                    name=f"{result.first_name} {result.last_name}".strip(),
                    email=result.email,
                    phone=result.phone,
                    provider="hubspot",
                )
        return None

    def find_contact_by_email(self, email: str) -> Optional[UnifiedContact]:
        """Busca contacto por email en el CRM activo."""
        if self.provider == CRMProvider.SALESFORCE:
            result = self._sf.find_contact_by_email(email)
            if result:
                return UnifiedContact(
                    id=result.id,
                    name=result.name,
                    email=result.email,
                    phone=result.phone,
                    provider="salesforce",
                )
        elif self.provider == CRMProvider.HUBSPOT:
            result = self._hs.find_contact_by_email(email)
            if result:
                return UnifiedContact(
                    id=result.id,
                    name=f"{result.first_name} {result.last_name}".strip(),
                    email=result.email,
                    phone=result.phone,
                    provider="hubspot",
                )
        return None

    # ------------------------------------------------------------------
    # Tickets / Casos
    # ------------------------------------------------------------------

    def create_ticket(
        self,
        contact_id: str,
        subject: str,
        description: str,
        priority: str = "medium",
    ) -> Optional[UnifiedTicket]:
        """Crea ticket/caso en el CRM activo."""
        if self.provider == CRMProvider.SALESFORCE:
            result = self._sf.create_case(
                contact_id=contact_id,
                subject=subject,
                description=description,
                priority=priority,
            )
            if result:
                return UnifiedTicket(
                    id=result.id,
                    subject=result.subject,
                    status=result.status,
                    priority=result.priority,
                    contact_id=result.contact_id,
                    provider="salesforce",
                )
        elif self.provider == CRMProvider.HUBSPOT:
            result = self._hs.create_ticket(
                contact_id=contact_id,
                subject=subject,
                description=description,
                priority=priority.upper(),
            )
            if result:
                return UnifiedTicket(
                    id=result.id,
                    subject=result.subject,
                    status=result.status,
                    priority=result.priority,
                    contact_id=result.contact_id,
                    provider="hubspot",
                )
        return None

    def update_ticket_status(self, ticket_id: str, status: str) -> bool:
        """Actualiza estado de ticket en el CRM activo."""
        if self.provider == CRMProvider.SALESFORCE:
            # Mapear a estados de Salesforce
            sf_map = {
                "open": "New",
                "in_progress": "Working",
                "escalated": "Escalated",
                "closed": "Closed",
            }
            return self._sf.update_case_status(ticket_id, sf_map.get(status.lower(), status))
        elif self.provider == CRMProvider.HUBSPOT:
            return self._hs.update_ticket_status(ticket_id, status)
        return False

    def log_call(
        self,
        contact_id: str,
        duration_s: int,
        outcome: str,
        notes: str = "",
    ) -> bool:
        """Registra llamada en el CRM activo."""
        if self.provider == CRMProvider.HUBSPOT:
            return self._hs.log_call(contact_id, duration_s, outcome, notes)
        elif self.provider == CRMProvider.SALESFORCE:
            return self._sf.add_case_comment(contact_id, f"Llamada: {outcome} ({duration_s}s). {notes}")
        return False

    def get_supported_providers(self) -> List[str]:
        return [p.value for p in CRMProvider]

    def get_active_provider(self) -> str:
        return self.provider.value
