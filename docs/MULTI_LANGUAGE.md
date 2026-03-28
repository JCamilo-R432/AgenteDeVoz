# Soporte Multi-idioma (Gap #21)

## Idiomas soportados
| Idioma | Codigo | BCP-47 | Voz TTS |
|--------|--------|--------|---------|
| Espanol | es | es-CO | es-US-Neural2-B |
| Ingles | en | en-US | en-US-Neural2-D |
| Portugues | pt | pt-BR | pt-BR-Neural2-B |

## Deteccion automatica
```python
from src.i18n.language_detector import LanguageDetector
from src.i18n.multi_language import MultiLanguageSupport

detector = LanguageDetector()
lang, confidence = detector.detect("Hello, I need help")
# (Language.ENGLISH, 0.75)

mls = MultiLanguageSupport()
mls.set_session_language("sess_001", lang)
config = mls.get_stt_config("sess_001")
```

## Cambio de idioma por voz
El usuario puede decir:
- "speak english" / "in english" -> cambia a ingles
- "en espanol" / "espanol por favor" -> cambia a espanol
- "em portugues" / "portugues por favor" -> cambia a portugues

```python
new_lang = detector.detect_language_switch(text, current_language)
if new_lang != current_language:
    confirmation = mls.set_session_language(session_id, new_lang)
    tts_speak(confirmation)
```

## Mensajes del sistema
```python
from src.i18n.translation_manager import TranslationManager

tm = TranslationManager()
msg = tm.get("ticket_created", Language.ENGLISH, ticket_id="TKT-001")
# "I've created a support ticket with number TKT-001."
```

## Agregar nuevo idioma
1. Agregar entrada en `Language` enum
2. Agregar `LanguageConfig` en `LANGUAGE_CONFIGS`
3. Agregar keywords en `LanguageDetector.LANGUAGE_MARKERS`
4. Agregar traducciones en `TranslationManager` (MESSAGES dict)
