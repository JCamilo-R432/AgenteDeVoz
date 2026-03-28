"""
LOPD Compliance - AgenteDeVoz
Gap #9: Cumplimiento Ley Organica de Proteccion de Datos (Espana)
        y Ley 1581/2012 (Colombia - equivalente GDPR)

Extiende GDPRComplianceManager con requisitos especificos
de la normativa hispanohablante.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LOPDComplianceManager:
    """
    Gestor de cumplimiento LOPD (ES) y Ley 1581/2012 (CO).
    Complementa la implementacion GDPR con requisitos locales.
    """

    # Colombia: Superintendencia de Industria y Comercio (SIC)
    # Espana: Agencia Espanola de Proteccion de Datos (AEPD)
    AUTHORITIES = {
        "CO": {"name": "SIC", "url": "https://www.sic.gov.co", "breach_deadline_hours": 15 * 24},
        "ES": {"name": "AEPD", "url": "https://www.aepd.es", "breach_deadline_hours": 72},
    }

    # Ley 1581/2012 Colombia: categorias de datos sensibles
    SENSITIVE_DATA_CATEGORIES_CO = [
        "origen_racial_etnico",
        "orientacion_politica",
        "convicciones_religiosas",
        "datos_sindicales",
        "datos_salud",
        "vida_sexual",
        "datos_biometricos",
    ]

    def __init__(self, country: str = "CO"):
        self.country = country.upper()
        self._consents: Dict[str, Dict] = {}
        self._transfers: List[Dict] = []
        logger.info(
            "LOPDComplianceManager inicializado (pais=%s, autoridad=%s)",
            self.country,
            self.AUTHORITIES.get(self.country, {}).get("name", "N/A"),
        )

    def register_consent(
        self,
        user_id: str,
        purpose: str,
        data_categories: List[str],
        is_sensitive: bool = False,
    ) -> Dict:
        """
        Registra consentimiento informado.
        Colombia: Art. 9 Ley 1581/2012 - datos sensibles requieren autorizacion expresa.
        Espana: Art. 9 LOPD-GDD.
        """
        if is_sensitive and self.country == "CO":
            logger.info(
                "Consentimiento expreso requerido para datos sensibles (Art. 9 Ley 1581/2012)"
            )

        record = {
            "user_id": user_id,
            "purpose": purpose,
            "data_categories": data_categories,
            "is_sensitive": is_sensitive,
            "country": self.country,
            "timestamp": datetime.now().isoformat(),
            "method": "explicit_opt_in",
            "withdrawn": False,
        }
        key = f"{user_id}:{purpose}"
        self._consents[key] = record
        logger.info("Consentimiento registrado: %s - %s", user_id, purpose)
        return record

    def withdraw_consent(self, user_id: str, purpose: str) -> bool:
        key = f"{user_id}:{purpose}"
        if key not in self._consents:
            return False
        self._consents[key]["withdrawn"] = True
        self._consents[key]["withdrawn_at"] = datetime.now().isoformat()
        logger.info("Consentimiento retirado: %s - %s", user_id, purpose)
        return True

    def has_valid_consent(self, user_id: str, purpose: str) -> bool:
        key = f"{user_id}:{purpose}"
        consent = self._consents.get(key)
        return consent is not None and not consent["withdrawn"]

    def register_international_transfer(
        self,
        destination_country: str,
        recipient: str,
        purpose: str,
        safeguard: str,
        data_categories: List[str],
    ) -> Dict:
        """
        Registra transferencia internacional de datos.
        Colombia: Art. 26 Ley 1581/2012 - requiere nivel adecuado de proteccion.
        GDPR: Art. 44-49.
        """
        ADEQUATE_COUNTRIES = [
            "EU", "EEA", "UK", "CA", "JP", "KR", "NZ", "IL", "AR", "UY",
        ]
        adequate_protection = destination_country in ADEQUATE_COUNTRIES or "SCC" in safeguard or "BCR" in safeguard

        record = {
            "destination": destination_country,
            "recipient": recipient,
            "purpose": purpose,
            "safeguard": safeguard,
            "data_categories": data_categories,
            "adequate_protection": adequate_protection,
            "registered_at": datetime.now().isoformat(),
        }
        if not adequate_protection:
            logger.warning(
                "Transferencia a pais sin nivel adecuado: %s - verificar salvaguardias",
                destination_country,
            )
        self._transfers.append(record)
        return record

    def get_data_officer_info(self) -> Dict:
        """Informacion del responsable / DPO segun pais."""
        if self.country == "CO":
            return {
                "title": "Responsable del Tratamiento",
                "legal_ref": "Art. 10 Ley 1581/2012",
                "contact": "protecciondatos@agentevoz.com",
                "authority": self.AUTHORITIES["CO"],
            }
        return {
            "title": "Delegado de Proteccion de Datos (DPO)",
            "legal_ref": "Art. 37 RGPD / Art. 34 LOPD-GDD",
            "contact": "dpo@agentevoz.com",
            "authority": self.AUTHORITIES.get(self.country),
        }

    def generate_privacy_notice(self, language: str = "es") -> str:
        """Genera aviso de privacidad conforme a legislacion local."""
        if self.country == "CO":
            return (
                "AVISO DE PRIVACIDAD - Ley 1581 de 2012 (Colombia)\n"
                "Responsable: AgenteDeVoz SAS - NIT: XXX-X\n"
                "Finalidad: Atencion al cliente automatizada\n"
                "Derechos: Conocer, actualizar, rectificar y suprimir sus datos\n"
                "Contacto: protecciondatos@agentevoz.com\n"
            )
        return (
            "POLITICA DE PRIVACIDAD - LOPD-GDD / RGPD\n"
            "Responsable: AgenteDeVoz S.L.\n"
            "DPO: dpo@agentevoz.com\n"
            "Derechos: ARCO+P (Acceso, Rectificacion, Cancelacion, Oposicion, Portabilidad)\n"
            "Autoridad: AEPD - www.aepd.es\n"
        )

    def get_compliance_summary(self) -> Dict:
        valid_consents = sum(1 for c in self._consents.values() if not c["withdrawn"])
        return {
            "country": self.country,
            "authority": self.AUTHORITIES.get(self.country, {}).get("name"),
            "total_consents": len(self._consents),
            "valid_consents": valid_consents,
            "international_transfers": len(self._transfers),
            "transfers_with_safeguards": sum(1 for t in self._transfers if t["adequate_protection"]),
        }
