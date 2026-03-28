# Barge-In Handler (Gap #19)

## Descripcion
Permite al usuario interrumpir al agente mientras habla (TTS activo).
SLO: cancelacion del TTS en < 500ms desde deteccion de voz.

## Estados del sistema
```
IDLE -> AGENT_SPEAKING -> USER_INTERRUPTING -> PROCESSING -> IDLE
```

## Uso basico
```python
from src.conversation.barge_in_handler import BargeInHandler

handler = BargeInHandler(interruption_threshold_s=0.3)
handler.set_interruption_callback(lambda: process_user_speech())
handler.start_agent_speech("Hola, ¿en que puedo ayudarle?", tts_func)

# Desde el loop de audio:
audio_chunk = get_audio_from_mic()
if handler.detect_user_speech(audio_chunk):
    handler.signal_user_speech()
```

## Configuracion
| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| interruption_threshold_s | 0.3 | Duracion minima de voz para activar barge-in |
| false_positive_guard_s | 0.1 | Tiempo de guarda contra falsos positivos |
| silence_after_interrupt | 0.3 | Silencio requerido antes de procesar |

## Metricas
```python
metrics = handler.get_metrics()
# {"interruption_count": 3, "avg_response_ms": 45.2, "meets_slo": True}
```

## SLO
- Objetivo: avg_response_ms < 500ms
- meets_slo = True si se cumple el objetivo
