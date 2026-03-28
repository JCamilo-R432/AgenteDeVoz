# Optimizacion de Acentos STT (Gap #17)

## Descripcion
Mejora la precision del reconocimiento de voz para acentos regionales hispanohablantes.

## Acentos soportados
| Acento | Codigo | Palabras clave |
|--------|--------|----------------|
| Colombia | es-CO | parce, chevere, bacano |
| Mexico | es-MX | wey, orale, chido |
| Argentina | es-AR | che, boludo, copado |
| Espana | es-ES | tio, guay, vale |
| Chile | es-CL | weon, cachai, fome |
| Peru | es-PE | pata, chamba, bacalao |

## Uso
```python
from src.speech.accent_optimizer import AccentOptimizer, RegionalAccent

optimizer = AccentOptimizer()
accent = optimizer.detect_accent({"transcribed_words": ["parce", "chevere"]})
config = optimizer.get_stt_config(accent)
```

## Configuracion Google STT por acento
```python
config = {
    "language_code": "es-CO",
    "model": "latest_long",
    "enable_automatic_punctuation": True,
    "use_enhanced": True
}
```

## Reduccion de ruido
SNR < 10dB: reduccion agresiva | 10-20dB: moderada | >20dB: limpio

## Metricas objetivo
- WER (Word Error Rate) < 8% para acentos soportados
- CER (Character Error Rate) < 5%
- Latencia de deteccion de acento < 200ms
