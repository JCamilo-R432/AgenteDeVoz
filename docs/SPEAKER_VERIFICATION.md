# Verificacion de Hablante (Gap #18)

## Descripcion
Biometria de voz para autenticar usuarios por su patron vocal.

## Flujo de enrollment
```
1. Recopilar 3+ muestras de voz (5-10 segundos c/u)
2. Extraer embeddings (128-dim)
3. Calcular embedding promedio
4. Almacenar VoiceProfile cifrado
```

## Flujo de verificacion
```
1. Capturar muestra de voz en tiempo real
2. Extraer embedding de la muestra
3. Calcular similitud coseno vs perfil almacenado
4. Aceptar si similitud >= 0.85 (configurable)
```

## Uso
```python
from src.security.speaker_verification import SpeakerVerification

sv = SpeakerVerification()
sv.enroll_user("user_123", [sample1, sample2, sample3])
verified, score = sv.verify_speaker("user_123", new_sample)
```

## Parametros
| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| threshold | 0.85 | Similitud minima para verificar |
| max_failed_attempts | 3 | Bloqueo tras N fallos |

## Anti-spoofing
Detecta: replay attacks, voz sintetizada (TTS), conversion de voz.

## GDPR / Ley 1581
Los embeddings de voz son datos biometricos. Requieren consentimiento explicito.
Implementar `delete_user()` para ejercicio del derecho al olvido.
