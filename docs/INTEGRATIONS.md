# Integraciones - AgenteDeVoz

## Indice

1. [Google Cloud STT/TTS](#1-google-cloud-stttts)
2. [Twilio Voice](#2-twilio-voice)
3. [WhatsApp Business API](#3-whatsapp-business-api)
4. [SendGrid Email](#4-sendgrid-email)
5. [Redis Cache](#5-redis-cache)
6. [PostgreSQL](#6-postgresql)
7. [CRM (HubSpot)](#7-crm-hubspot)
8. [OpenAI / Anthropic](#8-openai--anthropic)

---

## 1. Google Cloud STT/TTS

### Configuracion

1. Crear proyecto en Google Cloud Console
2. Habilitar APIs: Cloud Speech-to-Text, Cloud Text-to-Speech
3. Crear cuenta de servicio con rol "Cloud Speech Client"
4. Descargar JSON de credenciales
5. Configurar variable:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/ruta/al/credentials.json
GOOGLE_CLOUD_PROJECT=mi-proyecto-gcp
```

### STT (Speech-to-Text)

- Idioma: es-CO (Colombia)
- Modelo: latest_long (llamadas largas) o telephony (Twilio)
- Fallback: Whisper local si Google falla

### TTS (Text-to-Speech)

- Voz: es-US-Neural2-B (femenina, neutral)
- Audio: LINEAR16, 8kHz (compatible con Twilio)
- Cache: Redis por hash MD5 del texto (TTL 1 hora)

---

## 2. Twilio Voice

### Configuracion

1. Crear cuenta Twilio (twilio.com)
2. Adquirir numero de telefono con capacidad de voz
3. Configurar webhook en Twilio Console:
   - Voice URL: `https://tu-dominio.com/api/v1/webhooks/twilio/voice`
   - Method: POST
4. Configurar variables:

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+15551234567
```

### Flujo de llamada

```
[Llamada entrante]
        |
        v
[Twilio -> POST /webhooks/twilio/voice]
        |
        v
[TwiML: <Connect><Stream>]  <-- WebSocket Media Stream
        |
        v
[ws://tu-dominio/ws/twilio/media]
        |
        v
[STT -> NLP -> TTS -> Audio de vuelta a Twilio]
```

### TwiML de respuesta

El endpoint retorna TwiML que establece un WebSocket de audio bidireccional:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="wss://tu-dominio.com/ws/twilio/media">
      <Parameter name="session_id" value="sess_abc123"/>
    </Stream>
  </Connect>
</Response>
```

---

## 3. WhatsApp Business API

### Configuracion

1. Crear app en Meta for Developers
2. Agregar producto WhatsApp Business
3. Obtener token de acceso permanente
4. Registrar webhook:
   - URL: `https://tu-dominio.com/api/v1/webhooks/whatsapp`
   - Verify Token: valor de `WHATSAPP_VERIFY_TOKEN`
5. Variables:

```bash
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxxxxxxxx
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=mi_token_secreto
```

### Plantillas requeridas

Crear en Meta Business Suite las siguientes plantillas (categoria: UTILITY):

| Template Key         | Variables                            |
|---------------------|--------------------------------------|
| agente_ticket_creado_v1 | {{1}}=ticket_id, {{2}}=categoria, {{3}}=ETA |
| agente_encuesta_v1   | sin variables                        |
| agente_callback_v1   | {{1}}=fecha_hora                     |

---

## 4. SendGrid Email

### Configuracion

1. Crear cuenta SendGrid (sendgrid.com)
2. Verificar dominio de envio
3. Crear API Key con permisos "Mail Send"
4. Variable:

```bash
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Templates dinamicos

Los templates HTML se construyen localmente (sin depender de SendGrid Dynamic Templates) para mayor control. Para usar templates de SendGrid, reemplazar los IDs en `SendGridEmail.TEMPLATE_IDS`.

---

## 5. Redis Cache

### Configuracion

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=password_seguro
REDIS_DB=0
```

### Uso de claves

| Patron            | TTL      | Descripcion                    |
|-------------------|----------|-------------------------------|
| `tts:es-CO:<md5>` | 1 hora   | Audio TTS cacheado             |
| `session:<id>`    | 30 min   | Estado de sesion de conversacion |
| `rate:<id>:<ts>`  | variable | Rate limiting por IP/telefono  |

### Fallback

Si Redis no esta disponible, el sistema usa un diccionario en memoria (con TTL manual). El fallback no persiste entre reinicios ni entre instancias.

---

## 6. PostgreSQL

### Configuracion

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=agentevoz
DB_USER=agentevoz
DB_PASSWORD=password_seguro
```

### Schema

Ver `src/integrations/database_schema.sql` para el DDL completo.

Tablas principales:
- `users` - Usuarios del sistema (agentes, admins)
- `conversations` - Registro de llamadas (particionada por ano)
- `tickets` - Tickets de soporte
- `intents_log` - Historico de intenciones clasificadas
- `escalations` - Registro de escalaciones a humano
- `callbacks` - Callbacks programados
- `audit_log` - Log inmutable de auditoría (trigger BEFORE UPDATE/DELETE)

---

## 7. CRM (HubSpot)

### Configuracion

```bash
CRM_API_KEY=pat-na1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CRM_BASE_URL=https://api.hubapi.com
```

### Funcionalidades

- `get_customer_by_phone(phone)` - Busca cliente por telefono
- `create_interaction(phone, summary, ticket_id)` - Registra interaccion
- Circuit Breaker: 5 fallas -> 60s de pausa automatica

### Degraded Mode

Cuando el CRM no esta disponible, el agente opera en modo degradado:
- No autentica al cliente por nombre
- Crea tickets sin customer_id del CRM
- Registra la interaccion cuando el CRM se recupera (TODO: cola de reintentos)

---

## 8. OpenAI / Anthropic

### Configuracion

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini

ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
```

### Uso en el clasificador de intenciones

El `IntentClassifier` usa LLM cuando la clasificacion por palabras clave tiene baja confianza:

1. Intenta OpenAI (si API key configurada)
2. Fallback a Anthropic (si API key configurada)
3. Fallback final a clasificacion por keywords

Timeout: 2 segundos (para no impactar latencia de la llamada).

### Prompt usado

```
Clasifica la siguiente frase de un cliente en una de estas intenciones:
saludo, faq, crear_ticket, consultar_estado, queja, escalar_humano, despedida

Frase: "{texto}"
Responde SOLO con el nombre de la intencion.
```
