"""
CDN Manager - AgenteDeVoz
Gap #26: Gestion de CDN para activos estaticos y cache

Abstraccion para Cloudflare y AWS CloudFront.
Optimiza entrega de audio TTS cacheado y assets estaticos.
"""
import hashlib
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CDNProvider(Enum):
    CLOUDFLARE = "cloudflare"
    CLOUDFRONT = "cloudfront"
    NONE = "none"


@dataclass
class CDNAsset:
    url: str
    cache_key: str
    content_type: str
    ttl_seconds: int
    size_bytes: int
    provider: str
    cached_at: float = 0.0

    def is_expired(self) -> bool:
        return time.time() > (self.cached_at + self.ttl_seconds)


@dataclass
class CacheConfig:
    ttl_static_s: int = 86400       # 24h para HTML/CSS/JS
    ttl_audio_s: int = 3600         # 1h para audio TTS
    ttl_api_s: int = 60             # 1min para respuestas API
    enable_compression: bool = True
    min_compress_size_bytes: int = 1024


class CDNManager:
    """
    Gestor de CDN para AgenteDeVoz.
    Cachea respuestas TTS y activos estaticos para reducir latencia.
    """

    def __init__(
        self,
        provider: CDNProvider = CDNProvider.CLOUDFLARE,
        base_url: str = "",
        cache_config: Optional[CacheConfig] = None,
    ):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.cache_config = cache_config or CacheConfig()
        self._local_cache: Dict[str, CDNAsset] = {}
        self._hit_count = 0
        self._miss_count = 0
        logger.info("CDNManager inicializado (provider=%s, base=%s)", provider.value, base_url)

    # ------------------------------------------------------------------
    # Audio TTS
    # ------------------------------------------------------------------

    def cache_audio_response(self, text: str, audio_data: bytes, voice_id: str) -> CDNAsset:
        """Cachea respuesta de audio TTS para reutilizacion."""
        cache_key = self._make_audio_cache_key(text, voice_id)
        url = f"{self.base_url}/audio/{cache_key}.mp3"
        asset = CDNAsset(
            url=url,
            cache_key=cache_key,
            content_type="audio/mpeg",
            ttl_seconds=self.cache_config.ttl_audio_s,
            size_bytes=len(audio_data),
            provider=self.provider.value,
            cached_at=time.time(),
        )
        self._local_cache[cache_key] = asset
        logger.debug("Audio TTS cacheado: %s (%.1f KB)", cache_key, len(audio_data) / 1024)
        return asset

    def get_cached_audio(self, text: str, voice_id: str) -> Optional[CDNAsset]:
        """Busca audio TTS en cache. Retorna None si no existe o expiro."""
        key = self._make_audio_cache_key(text, voice_id)
        asset = self._local_cache.get(key)
        if asset and not asset.is_expired():
            self._hit_count += 1
            return asset
        if asset and asset.is_expired():
            del self._local_cache[key]
        self._miss_count += 1
        return None

    def _make_audio_cache_key(self, text: str, voice_id: str) -> str:
        content = f"{voice_id}:{text.strip().lower()}"
        return hashlib.md5(content.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Activos estaticos
    # ------------------------------------------------------------------

    def get_static_url(self, path: str) -> str:
        """Retorna URL CDN para un activo estatico."""
        return f"{self.base_url}/static/{path.lstrip('/')}"

    def invalidate(self, patterns: List[str]) -> bool:
        """Invalida entradas de cache por patron de URL."""
        invalidated = 0
        for key in list(self._local_cache.keys()):
            for pattern in patterns:
                if pattern in self._local_cache[key].url:
                    del self._local_cache[key]
                    invalidated += 1
                    break
        logger.info("Cache invalidado: %d entradas (patrones=%s)", invalidated, patterns)
        return True

    def purge_expired(self) -> int:
        """Elimina entradas expiradas del cache local."""
        expired = [k for k, v in self._local_cache.items() if v.is_expired()]
        for key in expired:
            del self._local_cache[key]
        logger.debug("Cache purgado: %d entradas expiradas eliminadas", len(expired))
        return len(expired)

    # ------------------------------------------------------------------
    # Metricas
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        total = self._hit_count + self._miss_count
        hit_rate = (self._hit_count / total * 100) if total > 0 else 0.0
        cached_size = sum(a.size_bytes for a in self._local_cache.values())
        return {
            "provider": self.provider.value,
            "cache_entries": len(self._local_cache),
            "cache_size_kb": round(cached_size / 1024, 1),
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate_percent": round(hit_rate, 1),
        }
