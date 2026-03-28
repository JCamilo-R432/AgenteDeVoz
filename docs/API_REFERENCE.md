# Referencia de API - AgenteDeVoz

Base URL: `https://agentevoz.tuempresa.com/api/v1`

## Autenticacion

Todos los endpoints (excepto `/ping`, `/health`, webhooks) requieren token Bearer:

```
Authorization: Bearer <token>
```

Obtener token:

```bash
curl -X POST /api/v1/auth/token \
  -d "username=admin&password=admin123"
```

Respuesta:
```json
{"access_token": "demo_admin_a1b2c3d4", "token_type": "bearer"}
```

---

## Sistema

### GET /ping

Verificacion rapida (sin autenticacion).

**Respuesta:**
```json
{"pong": true, "ts": 1711234567}
```

### GET /health

Estado detallado del sistema.

**Respuesta:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 3600.5,
  "components": {
    "api": "ok",
    "nlp": "ok",
    "stt": "ok",
    "tts": "ok",
    "database": "ok",
    "redis": "redis"
  }
}
```

### GET /metrics

Metricas del sistema (requiere auth).

**Respuesta:**
```json
{
  "active_sessions": 3,
  "uptime_seconds": 3600.5,
  "version": "1.0.0"
}
```

---

## Conversaciones

### POST /sessions/start

Inicia una nueva sesion de conversacion.

**Cuerpo:**
```json
{
  "channel": "voice",
  "customer_phone": "+573001234567",
  "language": "es-CO"
}
```

**Respuesta:**
```json
{
  "session_id": "sess_a1b2c3d4e5f6",
  "greeting": "Buen dia, gracias por llamar. ¿En que le puedo ayudar?",
  "state": "AUTENTICANDO"
}
```

---

### POST /sessions/process

Procesa input de texto en una sesion activa.

**Cuerpo:**
```json
{
  "session_id": "sess_a1b2c3d4e5f6",
  "text_input": "Tengo un problema con mi factura"
}
```

**Respuesta:**
```json
{
  "session_id": "sess_a1b2c3d4e5f6",
  "response_text": "Entiendo que tienes un problema con tu factura. He creado el ticket TKT-2026-000123...",
  "intent": "crear_ticket",
  "state": "RESPONDIENDO"
}
```

---

### POST /sessions/{session_id}/end

Finaliza una sesion.

**Respuesta:**
```json
{
  "session_id": "sess_a1b2c3d4e5f6",
  "farewell": "Ha sido un placer ayudarte. Hasta pronto.",
  "summary": {
    "session_id": "sess_a1b2c3d4e5f6",
    "state": "FIN",
    "duration_seconds": 125,
    "total_turns": 5,
    "fallback_count": 0,
    "intent_counts": {"faq": 1, "crear_ticket": 1},
    "authenticated": false,
    "started_at": "2026-03-22T10:30:00"
  }
}
```

---

### GET /sessions

Lista sesiones activas (requiere auth).

**Respuesta:**
```json
{
  "active_sessions": 2,
  "sessions": [
    {"session_id": "sess_001", "state": "ESCUCHANDO", "is_active": true},
    {"session_id": "sess_002", "state": "RESPONDIENDO", "is_active": true}
  ]
}
```

---

## Tickets

### POST /tickets

Crea un ticket directamente (sin flujo de voz).

**Cuerpo:**
```json
{
  "customer_phone": "3001234567",
  "category": "facturacion",
  "description": "Me llegó una factura con cobro incorrecto de $150,000"
}
```

**Respuesta:**
```json
{
  "ticket_id": "TKT-2026-000124",
  "status": "ABIERTO",
  "priority": "ALTA",
  "eta": "8 horas",
  "created_at": "2026-03-22T10:35:00"
}
```

---

### GET /tickets/{ticket_id}

Consulta el estado de un ticket.

**Ejemplo:** `GET /tickets/TKT-2026-000124`

**Respuesta:**
```json
{
  "ticket_id": "TKT-2026-000124",
  "status": "EN_PROGRESO",
  "priority": "ALTA",
  "category": "facturacion",
  "created_at": "2026-03-22T10:35:00",
  "eta": "8 horas"
}
```

---

## Webhooks

### POST /webhooks/twilio/voice

Webhook de Twilio para llamadas entrantes. Retorna TwiML.
No requiere autenticacion (validacion por firma HMAC de Twilio).

**Headers esperados de Twilio:**
- `X-Twilio-Signature`: firma HMAC del request

---

### POST /webhooks/twilio/status

Recibe actualizaciones de estado de llamada de Twilio.
No retorna contenido significativo.

---

### GET /webhooks/whatsapp

Verificacion del webhook de Meta/WhatsApp.
Parametros: `hub.mode`, `hub.verify_token`, `hub.challenge`

---

### POST /webhooks/whatsapp

Recibe mensajes entrantes de WhatsApp Business.

---

## WebSocket

### ws://dominio/ws/chat/{session_id}

WebSocket para clientes web en tiempo real.

**Mensajes del cliente:**
```json
{"type": "text", "content": "Hola, ¿pueden ayudarme?"}
{"type": "ping"}
{"type": "end"}
```

**Mensajes del servidor:**
```json
{"type": "response", "content": "...", "intent": "saludo", "state": "ESCUCHANDO"}
{"type": "pong"}
{"type": "error", "message": "..."}
```

---

### ws://dominio/ws/twilio/media

WebSocket para Twilio Media Streams (protocolo propietario de Twilio).
Solo usar con Twilio TwiML `<Connect><Stream>`.

---

## Codigos de Error

| HTTP | Descripcion |
|------|-------------|
| 400 | Request mal formado |
| 401 | Token invalido o ausente |
| 403 | Sin permisos para el recurso |
| 404 | Recurso no encontrado |
| 410 | Sesion finalizada |
| 422 | Datos de validacion incorrectos |
| 429 | Rate limit excedido |
| 500 | Error interno del servidor |
