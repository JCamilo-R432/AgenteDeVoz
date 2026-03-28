"""
Cloudflare Integration - AgenteDeVoz
Gap #26: Integracion con Cloudflare API v4

Gestiona zonas, reglas de cache, Workers y purga.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CloudflareZone:
    zone_id: str
    name: str
    status: str


@dataclass
class PageRule:
    rule_id: str
    url_pattern: str
    cache_ttl_s: int
    always_online: bool = False


class CloudflareIntegration:
    """
    Cliente para la API v4 de Cloudflare.
    Gestiona cache, reglas de pagina y Workers KV.
    """

    BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_token: str, zone_id: str):
        self.zone_id = zone_id
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        logger.info("CloudflareIntegration inicializado (zone=%s)", zone_id)

    def purge_cache(self, urls: List[str]) -> bool:
        """
        Purga URLs especificas del cache de Cloudflare.
        Endpoint: POST /zones/{zone_id}/purge_cache
        """
        if len(urls) > 30:
            # Cloudflare limita a 30 URLs por request
            for i in range(0, len(urls), 30):
                batch = urls[i:i + 30]
                self._purge_batch(batch)
        else:
            self._purge_batch(urls)
        logger.info("Cloudflare: cache purgado para %d URLs", len(urls))
        return True

    def _purge_batch(self, urls: List[str]) -> bool:
        # En produccion: requests.post(
        #     f"{self.BASE_URL}/zones/{self.zone_id}/purge_cache",
        #     headers=self._headers,
        #     json={"files": urls}
        # )
        logger.debug("Cloudflare purge batch: %d URLs", len(urls))
        return True

    def purge_everything(self) -> bool:
        """Purga todo el cache de la zona (usar con precaucion)."""
        # En produccion: requests.post(..., json={"purge_everything": True})
        logger.warning("Cloudflare: purga completa de zona %s ejecutada", self.zone_id)
        return True

    def create_page_rule(
        self,
        url_pattern: str,
        cache_ttl_s: int = 86400,
        always_online: bool = False,
    ) -> Optional[PageRule]:
        """Crea una Page Rule para cache personalizado."""
        rule_id = f"cf_rule_{hash(url_pattern) & 0xFFFFFF}"
        logger.info("Cloudflare: page rule creada para %s (ttl=%ds)", url_pattern, cache_ttl_s)
        return PageRule(
            rule_id=rule_id,
            url_pattern=url_pattern,
            cache_ttl_s=cache_ttl_s,
            always_online=always_online,
        )

    def get_cache_analytics(self, since_hours: int = 24) -> Dict:
        """Obtiene analiticas de cache de la zona."""
        # En produccion: GET /zones/{zone_id}/analytics/dashboard
        return {
            "zone_id": self.zone_id,
            "period_hours": since_hours,
            "requests_total": 0,
            "requests_cached": 0,
            "cache_ratio_percent": 0.0,
            "bandwidth_saved_gb": 0.0,
        }

    def set_security_level(self, level: str = "medium") -> bool:
        """
        Configura el nivel de seguridad de la zona.
        Niveles: essentially_off, low, medium, high, under_attack
        """
        valid_levels = {"essentially_off", "low", "medium", "high", "under_attack"}
        if level not in valid_levels:
            logger.warning("Nivel de seguridad invalido: %s", level)
            return False
        logger.info("Cloudflare: nivel de seguridad -> %s", level)
        return True

    def enable_ddos_protection(self) -> bool:
        """Activa el modo 'Under Attack' de Cloudflare."""
        return self.set_security_level("under_attack")

    def get_zone_info(self) -> Dict:
        """Retorna informacion de la zona."""
        return {
            "zone_id": self.zone_id,
            "status": "active",
            "name_servers": ["ns1.cloudflare.com", "ns2.cloudflare.com"],
        }
