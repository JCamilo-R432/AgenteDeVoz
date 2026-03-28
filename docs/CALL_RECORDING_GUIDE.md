# Call Recording Guide - AgenteDeVoz

Gap #10: Grabacion de llamadas con consentimiento, cifrado y retencion.

## Flujo de consentimiento

1. Sistema solicita consentimiento (`request_consent()`)
2. Usuario responde verbalmente (SI/NO en ES/EN/PT)
3. `process_consent_response()` evalua la respuesta
4. Si acepta: `start_recording()` inicia grabacion cifrada
5. Si rechaza: se registra el rechazo, no se graba

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/recording/call_recording.py` | Gestor principal de grabaciones |
| `src/recording/secure_storage.py` | AES-256-GCM para grabaciones |
| `src/recording/consent_recording.py` | Hash chain inmutable de consentimientos |
| `src/recording/recording_retention.py` | Politicas de retencion automatica |

## Uso rapido

```python
from src.recording.call_recording import CallRecordingManager

mgr = CallRecordingManager(storage_path="/var/recordings", retention_days=90)

# Pedir consentimiento
msg = mgr.request_consent("session_123", language="es")
# -> "Esta llamada puede ser grabada con fines de calidad..."

# Procesar respuesta del usuario
consented = mgr.process_consent_response("session_123", "si", language="es")

# Iniciar grabacion
rec = mgr.start_recording("session_123", "user_456", consent_obtained=consented)
if rec:
    # ... llamada en curso ...
    mgr.stop_recording(rec.recording_id)
```

## Politicas de retencion

| Politica | Dias | Auto-delete | Aplica a |
|----------|------|-------------|----------|
| standard | 90 | Si | voice, whatsapp |
| quality_review | 30 | Si | escalated |
| legal_hold | 1825 (5 anos) | No | legal, dispute |
| training_consent | 365 | Si | training_approved |

## Cifrado

Formato del archivo cifrado:
```
[AVREC1 magic 6 bytes][IV 16 bytes][AES-256-GCM ciphertext + tag 16 bytes]
```

Variable de entorno requerida en produccion:
```bash
export RECORDING_ENCRYPTION_KEY="your-32-char-secret-key-here!!"
```
