# Agente de Voz - Atencion al Cliente

Sistema de agente de voz inteligente para atencion al cliente con STT/TTS, NLP,
integraciones externas (Twilio, WhatsApp, SendGrid, CRM) y dashboard de monitoreo.

## Objetivos

- Atender 70% de consultas sin intervencion humana
- Reducir tiempo de espera en 50%
- Disponibilidad 24/7
- Precision de reconocimiento > 95%

## Inicio rapido

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno
cp config/production.env.example config/production.env
# Editar con tus credenciales

# 3. Inicializar base de datos (opcional, requiere PostgreSQL)
bash scripts/setup_database.sh

# 4. Ejecutar demo de texto
cd AgenteDeVoz
set PYTHONPATH=src     # Windows
python src/main.py

# 5. Ejecutar servidor completo
uvicorn src.server:app --reload --port 8000
```

## Estructura del Proyecto

```
AgenteDeVoz/
├── fase_1_planificacion/      # Documentos de planificacion (8 docs)
├── fase_2_diseno/             # Documentos de diseno (9 docs)
├── config/
│   ├── production.env         # Variables de entorno produccion
│   └── staging.env            # Variables de entorno staging
├── docs/
│   ├── INTEGRATIONS.md        # Guia de integraciones externas
│   ├── DEPLOYMENT.md          # Guia de despliegue
│   ├── API_REFERENCE.md       # Referencia completa de la API
│   └── TROUBLESHOOTING.md     # Solucion de problemas
├── scripts/
│   ├── setup_database.sh      # Inicializa PostgreSQL
│   ├── deploy.sh              # Deploy con Docker Compose
│   ├── backup.sh              # Backup de DB y config
│   └── health_check.sh        # Verifica todos los servicios
├── src/
│   ├── server.py              # Servidor FastAPI principal
│   ├── main.py                # Demo de linea de comandos
│   ├── api/
│   │   ├── routes.py          # Endpoints REST
│   │   └── websocket.py       # WebSocket para audio/chat
│   ├── core/
│   │   ├── agent.py           # CustomerServiceAgent
│   │   └── conversation_manager.py
│   ├── speech/
│   │   ├── stt_engine.py      # Google STT + Whisper fallback
│   │   └── tts_engine.py      # Google TTS + pyttsx3 fallback
│   ├── nlp/
│   │   ├── intent_classifier.py   # Keywords + OpenAI/Anthropic
│   │   └── entity_extractor.py    # Regex + clasificacion
│   ├── business/
│   │   ├── faq_manager.py
│   │   ├── ticket_system.py
│   │   └── escalation_handler.py
│   ├── integrations/
│   │   ├── database.py
│   │   ├── database_schema.sql
│   │   ├── crm_connector.py       # HubSpot + circuit breaker
│   │   ├── twilio_voice.py
│   │   ├── whatsapp_api.py        # WhatsApp Business API
│   │   ├── sendgrid_email.py      # Emails HTML
│   │   └── redis_cache.py         # Cache + fallback en memoria
│   ├── dashboard/
│   │   ├── app.py             # Dashboard FastAPI + Jinja2
│   │   ├── templates/         # HTML (index, conversations, tickets, alerts)
│   │   └── static/            # CSS + JavaScript
│   ├── utils/
│   │   ├── logger.py
│   │   └── validators.py
│   ├── deploy/
│   │   ├── Dockerfile
│   │   ├── docker-compose.yml
│   │   ├── nginx.conf
│   │   └── systemd/agentevoz.service
│   └── tests/
│       ├── test_agent.py       # 20 tests del agente
│       ├── test_intents.py     # 25 tests de NLP
│       ├── test_stt.py         # 12 tests de STT/TTS
│       ├── test_integrations.py # 30 tests de integraciones
│       └── test_api.py         # 25 tests de API REST
├── requirements.txt
└── PROJECT_STATUS.md
```

## Stack Tecnologico

| Capa | Tecnologia |
|------|-----------|
| Web framework | FastAPI 0.115 |
| STT | Google Cloud Speech-to-Text / Whisper |
| TTS | Google Cloud Text-to-Speech / pyttsx3 |
| NLP | Keywords + OpenAI GPT-4o-mini / Claude Haiku |
| Base de datos | PostgreSQL 15 |
| Cache | Redis 7 |
| Telefonia | Twilio Voice + WebSocket |
| Mensajeria | WhatsApp Business API (Meta) |
| Email | SendGrid |
| CRM | HubSpot API |
| Deploy | Docker + Nginx + systemd |

## Intenciones soportadas

| Intencion | Ejemplo |
|-----------|---------|
| saludo | "Hola, buenos dias" |
| faq | "¿Cual es el horario de atencion?" |
| crear_ticket | "Tengo un problema con mi factura" |
| consultar_estado | "¿Cual es el estado de mi pedido?" |
| queja | "Estoy muy molesto con el servicio" |
| escalar_humano | "Quiero hablar con un agente" |
| despedida | "Gracias, hasta luego" |

## Endpoints principales

- `POST /api/v1/sessions/start` - Iniciar sesion
- `POST /api/v1/sessions/process` - Procesar input
- `POST /api/v1/tickets` - Crear ticket
- `GET  /api/v1/health` - Estado del sistema
- `GET  /dashboard` - Panel de monitoreo
- `WS   /ws/chat/{id}` - Chat en tiempo real

Ver [docs/API_REFERENCE.md](docs/API_REFERENCE.md) para la referencia completa.

## Tests

```bash
set PYTHONPATH=src
pytest src/tests/ -v --cov=src
```

## Documentacion

- [Guia de Integraciones](docs/INTEGRATIONS.md)
- [Guia de Despliegue](docs/DEPLOYMENT.md)
- [Referencia de API](docs/API_REFERENCE.md)
- [Solucion de Problemas](docs/TROUBLESHOOTING.md)

---

**Ultima Actualizacion:** 2026-03-22 | **Version:** 1.0.0
