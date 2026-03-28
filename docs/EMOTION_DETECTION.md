# Deteccion de Emociones (Gap #20)

## Descripcion
Detecta 6 emociones basicas + neutral en tiempo real.
Activa escalacion automatica cuando la frustracion supera umbral configurable.

## Emociones detectadas
| Emocion | Keywords ES | Accion |
|---------|-------------|--------|
| JOY | feliz, alegre, contento | Flujo normal |
| SADNESS | triste, deprimido, mal | Tono empatico |
| ANGER | furioso, rabia, odio | Priorizar resolucion |
| FEAR | miedo, panico, nervioso | Calmar, informar |
| SURPRISE | increible, inesperado | Confirmar informacion |
| DISGUST | asco, repugnante, vergonzoso | Escalar |
| NEUTRAL | (sin keywords) | Flujo normal |

## Uso
```python
from src.nlp.emotion_detector import EmotionDetector

detector = EmotionDetector(frustration_threshold=0.6)
result = detector.detect_emotion(
    text="Esto no funciona nunca, estoy furioso",
    audio_features={"pitch": 0.8, "energy": 0.9, "speech_rate": 1.3}
)

if result.should_escalate:
    transfer_to_human_agent()
```

## FrustrationTracker
```python
from src.nlp.frustration_tracker import FrustrationTracker

tracker = FrustrationTracker(session_id="sess_001")
summary = tracker.update(result.frustration_level, text=user_text)
print(summary.recommended_action)
# "offer_human_agent" | "monitor" | "transfer_to_human_immediately"
```

## Umbrales de escalacion
- Frustracion >= 0.6: ofrecer agente humano
- Frustracion >= 0.8: transferencia inmediata
- Tendencia "escalating" en 5+ turnos: escalacion preventiva
