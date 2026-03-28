"""
API Versioning - AgenteDeVoz
Gap #27: Versionado semantico de la API REST

Soporta versiones via URL (/v1/, /v2/) y header Accept-Version.
Gestiona deprecaciones con avisos en las respuestas.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class VersionStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"          # Ya no funciona


@dataclass
class APIVersion:
    version: str               # "v1", "v2"
    status: VersionStatus
    release_date: str
    sunset_date: Optional[str] = None
    deprecation_message: Optional[str] = None
    supported_features: Set[str] = None

    def __post_init__(self):
        if self.supported_features is None:
            self.supported_features = set()

    def is_available(self) -> bool:
        return self.status != VersionStatus.SUNSET

    def needs_deprecation_header(self) -> bool:
        return self.status == VersionStatus.DEPRECATED


class APIVersioning:
    """
    Gestor de versiones de la API REST de AgenteDeVoz.
    Implementa el patron de versionado basado en URL path.
    """

    CURRENT_VERSION = "v2"
    DEFAULT_VERSION = "v1"

    def __init__(self):
        self._versions: Dict[str, APIVersion] = {}
        self._route_map: Dict[str, Dict[str, Callable]] = {}  # version -> {route: handler}
        self._register_default_versions()
        logger.info(
            "APIVersioning inicializado (current=%s, versions=%d)",
            self.CURRENT_VERSION, len(self._versions)
        )

    def _register_default_versions(self) -> None:
        self.register_version(APIVersion(
            version="v1",
            status=VersionStatus.DEPRECATED,
            release_date="2024-01-01",
            sunset_date="2026-12-31",
            deprecation_message="v1 sera eliminada el 2026-12-31. Migra a v2.",
            supported_features={"voice_process", "tickets", "health"},
        ))
        self.register_version(APIVersion(
            version="v2",
            status=VersionStatus.ACTIVE,
            release_date="2025-01-01",
            supported_features={
                "voice_process", "tickets", "health", "conversations",
                "emotion_detection", "multi_language", "crm_sync",
            },
        ))

    def register_version(self, version: APIVersion) -> None:
        self._versions[version.version] = version
        logger.debug("Version registrada: %s (%s)", version.version, version.status.value)

    def resolve_version(self, url_version: Optional[str] = None, header_version: Optional[str] = None) -> Optional[APIVersion]:
        """
        Resuelve la version de la API a usar.
        Precedencia: URL path > header Accept-Version > default.
        """
        version_str = url_version or header_version or self.DEFAULT_VERSION
        # Normalizar: aceptar "1", "v1", "1.0"
        if not version_str.startswith("v"):
            version_str = f"v{version_str.split('.')[0]}"
        version = self._versions.get(version_str)
        if not version:
            logger.warning("Version no encontrada: %s", version_str)
            return None
        if not version.is_available():
            logger.warning("Version %s esta en sunset (no disponible)", version_str)
            return None
        return version

    def get_deprecation_headers(self, version: APIVersion) -> Dict[str, str]:
        """Retorna headers HTTP para versiones deprecadas."""
        headers: Dict[str, str] = {}
        if version.needs_deprecation_header():
            headers["Deprecation"] = "true"
            if version.sunset_date:
                headers["Sunset"] = version.sunset_date
            if version.deprecation_message:
                headers["X-Deprecation-Notice"] = version.deprecation_message
            headers["Link"] = f'</{self.CURRENT_VERSION}/docs>; rel="successor-version"'
        return headers

    def is_feature_supported(self, version_str: str, feature: str) -> bool:
        """Verifica si una feature es soportada en una version especifica."""
        version = self._versions.get(version_str)
        if not version:
            return False
        return feature in version.supported_features

    def get_migration_guide(self, from_version: str, to_version: str) -> str:
        """Retorna guia de migracion entre versiones."""
        guides = {
            ("v1", "v2"): (
                "Cambios breaking en v2:\n"
                "1. /voice/transcribe -> /voice/process (parametro 'audio_base64' requerido)\n"
                "2. Campo 'result' renombrado a 'response' en respuestas de voz\n"
                "3. Autenticacion: agregar header X-Session-ID en todas las llamadas\n"
                "4. Errores: ahora usan RFC 7807 Problem Details\n"
            ),
        }
        return guides.get((from_version, to_version), f"No hay guia de {from_version} a {to_version}")

    def list_versions(self) -> List[Dict]:
        return [
            {
                "version": v.version,
                "status": v.status.value,
                "release_date": v.release_date,
                "sunset_date": v.sunset_date,
                "features": list(v.supported_features),
            }
            for v in self._versions.values()
        ]
