# CDN Setup (Gap #26)

## Descripcion
Cache de respuestas TTS y activos estaticos via Cloudflare.
Reduce latencia de audio en un 60-80% para usuarios recurrentes.

## Cache de audio TTS
```python
from src.infrastructure.cdn_manager import CDNManager, CDNProvider

cdn = CDNManager(
    provider=CDNProvider.CLOUDFLARE,
    base_url="https://cdn.agentevoz.com",
)

# Cachear respuesta TTS
asset = cdn.cache_audio_response(
    text="Bienvenido a AgenteDeVoz",
    audio_data=tts_bytes,
    voice_id="es-US-Neural2-B",
)

# Obtener del cache (None si no existe o expiro)
cached = cdn.get_cached_audio("Bienvenido a AgenteDeVoz", "es-US-Neural2-B")
if cached:
    return cached.url  # Retornar URL del CDN directamente
```

## Configuracion Cloudflare
```bash
export CF_API_TOKEN=tu_token
export CF_ZONE_ID=tu_zone_id
scripts/configure_cdn.sh
```

## TTLs configurados
| Tipo | TTL Edge | TTL Browser |
|------|----------|-------------|
| Audio TTS | 3600s (1h) | 1800s |
| Estaticos | 86400s (24h) | 86400s |
| API calls | bypass | bypass |

## Page Rules
Definidas en `config/cdn/cloudflare_rules.json`.

## Metricas
```python
stats = cdn.get_stats()
# {"hit_rate_percent": 67.5, "cache_entries": 1250, "cache_size_kb": 8400}
```

## Cache hit rate objetivo: >= 60%
