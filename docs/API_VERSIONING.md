# API Versioning (Gap #27)

## Descripcion
Versionado semantico de la API REST con soporte para deprecaciones y migraciones.

## Versiones activas
| Version | Estado | Sunset |
|---------|--------|--------|
| v1 | DEPRECATED | 2026-12-31 |
| v2 | ACTIVE | - |

## Resolucion de version
Precedencia: URL path > Header Accept-Version > default (v1)

```
GET /v2/voice/process     <- URL path (recomendado)
GET /voice/process + Accept-Version: v2  <- Header
```

## Headers de deprecacion (v1)
```
Deprecation: true
Sunset: 2026-12-31
X-Deprecation-Notice: v1 sera eliminada el 2026-12-31. Migra a v2.
Link: </v2/docs>; rel="successor-version"
```

## Uso en codigo
```python
from src.api.versioning import APIVersioning

versioning = APIVersioning()
version = versioning.resolve_version(url_version="v2")
headers = versioning.get_deprecation_headers(version)

if not versioning.is_feature_supported("v1", "emotion_detection"):
    raise HTTPException(400, "Requiere v2+")
```

## Guia de migracion v1 -> v2
1. `/voice/transcribe` -> `/voice/process` (campo `audio_base64` requerido)
2. Campo `result` renombrado a `response`
3. Agregar header `X-Session-ID` en todas las llamadas
4. Errores usan RFC 7807 Problem Details
