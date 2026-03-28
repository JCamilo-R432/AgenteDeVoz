import logging
from typing import Dict, Optional

from config.settings import settings


class CRMConnector:
    """
    Conector al CRM externo (HubSpot / Salesforce).

    Implementa el patrón Circuit Breaker básico:
    - Si falla 5 veces consecutivas, entra en modo 'open' por 60 segundos.
    - En modo degradado retorna datos mínimos del usuario.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = settings.CRM_BASE_URL
        self.api_key = settings.CRM_API_KEY
        self._fail_count = 0
        self._circuit_open = False
        self._circuit_open_until: Optional[float] = None

    def get_customer_by_phone(self, phone: str) -> Optional[Dict]:
        """
        Busca un cliente en el CRM por número de teléfono.

        Args:
            phone: Número de teléfono (10 dígitos).

        Returns:
            Dict con datos del cliente o None si no se encuentra.
        """
        if not self._can_call():
            return self._get_degraded_response(phone)

        try:
            import httpx

            response = httpx.get(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=self._get_headers(),
                json={
                    "filterGroups": [{
                        "filters": [{
                            "propertyName": "phone",
                            "operator": "EQ",
                            "value": phone,
                        }]
                    }],
                    "properties": ["firstname", "lastname", "email", "phone", "hs_object_id"],
                    "limit": 1,
                },
                timeout=3.0,
            )
            response.raise_for_status()
            data = response.json()

            self._reset_circuit()

            results = data.get("results", [])
            if not results:
                return None

            contact = results[0]
            props = contact.get("properties", {})
            return {
                "crm_id": contact["id"],
                "full_name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                "email": props.get("email"),
                "phone": props.get("phone"),
            }

        except Exception as e:
            self.logger.warning(f"CRM error para teléfono {phone}: {e}")
            self._record_failure()
            return self._get_degraded_response(phone)

    def create_interaction(self, customer_id: str, summary: str, channel: str = "voice") -> bool:
        """
        Registra una interacción en el CRM.

        Args:
            customer_id: ID del cliente en el CRM.
            summary: Resumen de la interacción.
            channel: Canal de contacto.

        Returns:
            True si se registró correctamente.
        """
        if not self._can_call():
            self.logger.warning("CRM circuit open, interacción no registrada.")
            return False

        try:
            import httpx

            httpx.post(
                f"{self.base_url}/crm/v3/objects/notes",
                headers=self._get_headers(),
                json={
                    "properties": {
                        "hs_note_body": summary,
                        "hs_timestamp": str(int(__import__("time").time() * 1000)),
                        "hubspot_owner_id": customer_id,
                    },
                    "associations": [{
                        "to": {"id": customer_id},
                        "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
                    }],
                },
                timeout=3.0,
            ).raise_for_status()

            self._reset_circuit()
            self.logger.info(f"Interacción registrada en CRM para cliente {customer_id}")
            return True

        except Exception as e:
            self.logger.warning(f"Error registrando interacción en CRM: {e}")
            self._record_failure()
            return False

    # ── Circuit Breaker ───────────────────────────────────────────────────────

    def _can_call(self) -> bool:
        """Verifica si el circuit breaker permite llamar al CRM."""
        if not self.base_url or not self.api_key:
            return False

        if self._circuit_open:
            import time
            if self._circuit_open_until and time.time() > self._circuit_open_until:
                self.logger.info("Circuit breaker CRM: intentando cerrar circuito.")
                self._circuit_open = False
                self._fail_count = 0
            else:
                return False

        return True

    def _record_failure(self) -> None:
        """Registra un fallo y abre el circuito si se supera el umbral."""
        import time

        self._fail_count += 1
        if self._fail_count >= 5:
            self._circuit_open = True
            self._circuit_open_until = time.time() + 60
            self.logger.error("Circuit breaker CRM: circuito ABIERTO por 60 segundos.")

    def _reset_circuit(self) -> None:
        """Resetea el contador de fallos ante una llamada exitosa."""
        self._fail_count = 0
        self._circuit_open = False
        self._circuit_open_until = None

    def _get_headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get_degraded_response(self, phone: str) -> Optional[Dict]:
        """Retorna respuesta mínima cuando el CRM no está disponible."""
        self.logger.warning(f"CRM no disponible, modo degradado para: {phone}")
        return None  # El agente continuará sin datos del CRM
