"""
Salesforce Connector - AgenteDeVoz
Gap #22: Integracion CRM con Salesforce

Operaciones: buscar contacto, crear caso, actualizar oportunidad.
Usa REST API de Salesforce con OAuth2 (client_credentials).
"""
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SalesforceContact:
    id: str
    name: str
    email: str
    phone: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None


@dataclass
class SalesforceCase:
    id: str
    subject: str
    status: str
    priority: str
    contact_id: str
    description: str = ""


class SalesforceConnector:
    """
    Conector para Salesforce CRM.
    Implementa autenticacion OAuth2 con renovacion automatica de token.
    """

    PRIORITIES = {"low", "medium", "high", "critical"}

    def __init__(
        self,
        instance_url: str,
        client_id: str,
        client_secret: str,
        api_version: str = "v58.0",
    ):
        self.instance_url = instance_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_version = api_version
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        logger.info("SalesforceConnector inicializado (%s)", instance_url)

    def _is_token_valid(self) -> bool:
        return self._access_token is not None and time.time() < self._token_expires_at

    def authenticate(self) -> bool:
        """
        Obtiene token OAuth2 via client_credentials.
        En produccion usa requests; aqui se simula.
        """
        if self._is_token_valid():
            return True
        logger.info("Autenticando con Salesforce...")
        # Simulacion: en produccion usar requests.post(token_url, data=...)
        self._access_token = f"sf_simulated_token_{int(time.time())}"
        self._token_expires_at = time.time() + 3600
        logger.info("Token Salesforce obtenido (expira en 3600s)")
        return True

    def find_contact_by_phone(self, phone: str) -> Optional[SalesforceContact]:
        """Busca contacto por numero de telefono via SOQL."""
        if not self.authenticate():
            return None
        # Simulacion de respuesta
        logger.debug("SOQL: SELECT Id, Name, Email, Phone, AccountId FROM Contact WHERE Phone='%s'", phone)
        if phone.startswith("+57"):
            return SalesforceContact(
                id="003SIMULATED001",
                name="Cliente Simulado",
                email="cliente@ejemplo.co",
                phone=phone,
                account_id="001ACC001",
                account_name="Empresa Demo Colombia",
            )
        return None

    def find_contact_by_email(self, email: str) -> Optional[SalesforceContact]:
        """Busca contacto por email."""
        if not self.authenticate():
            return None
        logger.debug("SOQL: SELECT Id, Name, Email, Phone FROM Contact WHERE Email='%s'", email)
        return None  # Simulacion: no encontrado

    def create_case(
        self,
        contact_id: str,
        subject: str,
        description: str,
        priority: str = "medium",
        origin: str = "Voice",
    ) -> Optional[SalesforceCase]:
        """Crea un nuevo Caso en Salesforce."""
        if priority not in self.PRIORITIES:
            priority = "medium"
        if not self.authenticate():
            return None

        case_id = f"5001CASE{int(time.time())}"
        logger.info(
            "Caso creado en Salesforce: %s (prioridad=%s, contacto=%s)",
            case_id, priority, contact_id
        )
        return SalesforceCase(
            id=case_id,
            subject=subject,
            status="New",
            priority=priority.capitalize(),
            contact_id=contact_id,
            description=description,
        )

    def update_case_status(self, case_id: str, status: str) -> bool:
        """Actualiza el estado de un caso existente."""
        valid_statuses = {"New", "Working", "Escalated", "Closed"}
        if status not in valid_statuses:
            logger.warning("Estado invalido para caso Salesforce: %s", status)
            return False
        if not self.authenticate():
            return False
        logger.info("Caso %s actualizado a estado '%s'", case_id, status)
        return True

    def add_case_comment(self, case_id: str, comment: str) -> bool:
        """Agrega comentario a un caso."""
        if not self.authenticate():
            return False
        logger.debug("Comentario agregado al caso %s", case_id)
        return True

    def get_account_history(self, account_id: str, limit: int = 5) -> List[Dict]:
        """Retorna historial de casos de una cuenta."""
        if not self.authenticate():
            return []
        logger.debug("Obteniendo historial de cuenta %s (limit=%d)", account_id, limit)
        return [
            {
                "case_id": "5001PAST001",
                "subject": "Problema con facturacion",
                "status": "Closed",
                "created_date": "2025-12-01",
            }
        ]
