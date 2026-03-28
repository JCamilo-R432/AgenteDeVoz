# Guia de Testing - AgenteDeVoz
**Fase 5 | Actualizado:** 2026-03-22

---

## Indice

1. [Estructura de Tests](#estructura)
2. [Configuracion del Entorno](#configuracion)
3. [Ejecutar Tests](#ejecutar)
4. [Tests por Categoria](#categorias)
5. [Cobertura de Codigo](#cobertura)
6. [Tests de Carga](#carga)
7. [Tests de Seguridad](#seguridad)
8. [CI/CD](#cicd)
9. [Escribir Nuevos Tests](#nuevos)
10. [Troubleshooting](#troubleshooting)

---

## 1. Estructura de Tests {#estructura}

```
tests/
├── conftest.py                  # Fixtures globales y configuracion
├── unit/                        # Tests unitarios (rapidos, sin dependencias)
│   ├── test_tts.py             # Motor TTS
│   ├── test_faq.py             # FAQ Manager
│   ├── test_tickets.py         # Sistema de tickets
│   └── test_validators.py      # Validadores de entrada
├── integration/                 # Tests con servicios (mockeados)
│   ├── test_database.py        # PostgreSQL (real o mock)
│   ├── test_redis.py           # Redis cache
│   ├── test_whatsapp.py        # WhatsApp Business API
│   ├── test_sendgrid.py        # SendGrid email
│   └── test_twilio.py          # Twilio Voice
├── e2e/                         # Tests de flujos completos
│   ├── test_conversation_flow.py  # Flujo de conversacion
│   ├── test_ticket_lifecycle.py   # Ciclo de vida de tickets
│   └── test_escalation_flow.py    # Escalamiento a humano
├── load/                        # Tests de carga y rendimiento
│   ├── test_concurrency.py     # Sesiones concurrentes
│   └── test_stress.py          # Stress tests
└── security/                    # Tests de seguridad
    ├── test_injection.py        # SQL/XSS/Command injection
    ├── test_auth.py             # JWT y autenticacion
    └── test_data_protection.py  # Proteccion de datos

src/tests/                       # Tests heredados (integrados)
├── test_integrations.py         # Redis, WhatsApp, SendGrid
└── test_api.py                  # Endpoints REST
```

---

## 2. Configuracion del Entorno {#configuracion}

### Instalacion de dependencias de test

```bash
pip install pytest pytest-cov pytest-asyncio
pip install passlib[bcrypt]
# Opcional para escaneo de seguridad:
pip install bandit safety
```

### Variables de entorno

Los tests usan `config/test.env` automaticamente via `conftest.py`.
No se requiere configuracion adicional para tests unitarios.

Para tests de integracion con DB real:
```bash
# Crear base de datos de test
bash scripts/setup_database.sh test

# O manualmente:
createdb agentevoz_test
export DATABASE_URL=postgresql://test:test@localhost:5432/agentevoz_test
```

---

## 3. Ejecutar Tests {#ejecutar}

### Todos los tests (recomendado)

```bash
bash scripts/run_all_tests.sh
```

### Modo rapido (sin DB real, sin tests lentos)

```bash
bash scripts/run_all_tests.sh --fast
```

### Con reporte de cobertura

```bash
bash scripts/run_all_tests.sh --coverage
# O directamente:
bash scripts/run_coverage.sh
```

### Suite especifica

```bash
# Solo unitarios
python -m pytest tests/unit/ -v

# Solo integracion
python -m pytest tests/integration/ -v

# Solo E2E
python -m pytest tests/e2e/ -v

# Solo seguridad
python -m pytest tests/security/ -v

# Solo carga
python -m pytest tests/load/ -v
```

### Por marcador

```bash
# Tests rapidos (unit + integration sin DB)
python -m pytest -m "unit" -v
python -m pytest -m "not db_required and not slow" -v

# Solo tests que requieren DB
python -m pytest -m "db_required" -v
```

### Test especifico

```bash
python -m pytest tests/unit/test_faq.py::TestFAQManager::test_answer_horario -v
```

---

## 4. Tests por Categoria {#categorias}

### Unit Tests (tests/unit/)

Sin dependencias externas. Usan mocks para DB y servicios externos.

**test_tts.py** — 12 tests
- Inicializacion del motor TTS
- Sintesis de texto (valido, vacio, largo, None)
- Cache de audio
- Integracion con pipeline de voz

**test_faq.py** — 15 tests
- Respuestas para intents conocidos
- Manejo de preguntas desconocidas
- Sensibilidad a mayusculas/minusculas
- Adicion dinamica de FAQs
- Conteo de consultas

**test_tickets.py** — 20 tests
- Creacion de tickets con/sin DB
- Verificacion de estado
- Creacion de quejas
- Deteccion de prioridad (URGENTE/ALTA)
- Unicidad de numeros de ticket

**test_validators.py** — 35 tests
- Validacion de telefonos (Colombia: 300-399, fijo Bogota 601)
- Validacion de emails (RFC basico)
- Validacion de ticket IDs
- Sanitizacion de inputs (XSS, SQL, longitud)
- Validacion de intents
- Validacion de fechas

### Integration Tests (tests/integration/)

Usan servicios reales o simulados segun disponibilidad.

**test_database.py** — 9 tests
- `TestDatabaseMocked`: siempre corre (4 tests)
- `TestDatabaseIntegration`: requiere `@db_required` skip si no hay DB (5 tests)

**test_redis.py** — 20 tests
- Usa puerto 6380 (incorrecto) para forzar modo in-memory
- Todas las operaciones funcionan en fallback
- Rate limiting, TTL, sesiones, patrones

**test_whatsapp.py** — 22 tests
- Modo simulado (no consume API real)
- Normalizacion de telefonos
- Verificacion de webhook
- Parseo de mensajes entrantes

**test_sendgrid.py** — 20 tests
- Modo simulado (no envia emails reales)
- Verificacion de contenido HTML
- Templates built-in

**test_twilio.py** — 15 tests
- Generacion de TwiML
- XML valido
- Transferencia de llamada
- Cierre de llamada

### E2E Tests (tests/e2e/)

Flujos completos sin mocks de logica de negocio.

**test_conversation_flow.py** — 18 tests
- Flujo saludo → FAQ → despedida
- Transiciones de estado correctas
- Multi-turno (4+ intercambios)
- Fallback counter
- Retention de session_id

**test_ticket_lifecycle.py** — 15 tests
- Crear ticket → consultar estado
- Queja → ticket automatico
- Prioridad URGENTE detectada
- Ticket sin DB (modo graceful)
- Ordenamiento por SLA

**test_escalation_flow.py** — 15 tests
- Solicitud explicita de humano
- Frustracion detectada
- 3 fallbacks → sugerencia de escalamiento
- Reset de contador de fallbacks
- Business hours check

### Load Tests (tests/load/)

Rendimiento y concurrencia.

**test_concurrency.py**
- 10 sesiones simultaneas (ThreadPoolExecutor)
- 5 sesiones FAQ concurrentes
- Independencia de sesiones
- Thread safety de ConversationManager
- Sesion 10 turnos < 10s

**test_stress.py**
- 200 intent classifications
- 200 entity extractions
- 500 validaciones
- 300 FAQ queries
- 1000 sanitize_input calls
- 500 Redis operations
- 100 tickets sin DB

### Security Tests (tests/security/)

OWASP Top 10 mitigaciones.

**test_injection.py** — 32+ tests
- 9 payloads SQL injection
- 8 payloads XSS
- 7 payloads command injection
- Limites de longitud

**test_auth.py** — 21 tests
- JWT: generacion, validacion, expirado, secreto incorrecto
- Ataque alg=none bloqueado
- Endpoints protegidos
- Credenciales incorrectas rechazadas
- Rate limiting de in-memory

**test_data_protection.py** — 15 tests
- API keys no en repr
- Passwords hasheados (bcrypt)
- Variables sensibles configuradas
- Sin secretos hardcodeados
- production.env tiene placeholders

---

## 5. Cobertura de Codigo {#cobertura}

### Generar reporte

```bash
# Reporte completo (HTML + XML + terminal)
bash scripts/run_coverage.sh

# Con umbral personalizado
bash scripts/run_coverage.sh --min 80

# Solo terminal
python -m pytest tests/ src/tests/ \
  --cov=src \
  --cov-report=term-missing \
  -q
```

### Ver reporte HTML

```
reports/coverage_report/index.html
```

### Configuracion (.coveragerc)

- Minimo: 70% (configurable)
- Excluidos: tests/, migrations/, venv/
- Excluye lineas: `pragma: no cover`, `raise NotImplementedError`, etc.

### Agregar exclusiones

```python
def metodo_debug():  # pragma: no cover
    print("solo para debug")
```

---

## 6. Tests de Carga {#carga}

```bash
# Estandar (sin tests lentos)
bash scripts/run_load_test.sh

# Solo tests rapidos
bash scripts/run_load_test.sh --light

# Todos los tests
bash scripts/run_load_test.sh --full
```

Ver resultados en: `reports/performance_report.md`

---

## 7. Tests de Seguridad {#seguridad}

```bash
# Suite completa (pytest + bandit + safety + secretos)
bash scripts/run_security_scan.sh

# Solo tests pytest
python -m pytest tests/security/ -v
```

Requiere instalacion opcional:
```bash
pip install bandit safety
```

Ver resultados en: `reports/security_report.md`

---

## 8. CI/CD {#cicd}

GitHub Actions ejecuta automaticamente en cada push/PR:

1. **Lint** (flake8)
2. **Type check** (mypy)
3. **Unit tests** (sin servicios externos)
4. **Integration tests** (con servicios de GitHub Actions)
5. **Security scan** (bandit)
6. **Coverage report** (artefacto)

Ver: `.github/workflows/ci.yml`

---

## 9. Escribir Nuevos Tests {#nuevos}

### Estructura de un test unitario

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

class TestMiModulo:
    """Tests para MiModulo."""

    def test_inicializacion(self):
        """El modulo se inicializa correctamente."""
        from mi_modulo import MiClase
        obj = MiClase()
        assert obj is not None

    def test_metodo_principal(self):
        """El metodo principal retorna el resultado esperado."""
        from mi_modulo import MiClase
        obj = MiClase()
        resultado = obj.metodo("input")
        assert isinstance(resultado, str)
        assert len(resultado) > 0
```

### Usar fixtures de conftest.py

```python
def test_con_agent(self, agent_fixture):
    """Usa el agente del conftest."""
    response = agent_fixture.process_input("hola", "test-session-001")
    assert response is not None

def test_sin_llm(self, agent_fixture, no_llm):
    """Fuerza modo keyword (determinista)."""
    # no_llm monkeypatcha las API keys a vacio
    response = agent_fixture.process_input("crear ticket", "test-001")
    assert "ticket" in response.lower()
```

### Marcadores disponibles

```python
@pytest.mark.unit
def test_rapido():
    pass

@pytest.mark.integration
def test_con_servicio():
    pass

@pytest.mark.slow
def test_lento():
    pass

@pytest.mark.db_required
def test_necesita_db():
    pass
```

### Skip condicional para servicios

```python
def _redis_available():
    import redis
    try:
        r = redis.Redis(host='localhost', port=6379)
        r.ping()
        return True
    except Exception:
        return False

@pytest.mark.skipif(not _redis_available(), reason="Redis no disponible")
def test_con_redis_real():
    pass
```

---

## 10. Troubleshooting {#troubleshooting}

### Error: `ModuleNotFoundError: No module named 'business'`

```bash
export PYTHONPATH=/ruta/al/proyecto/src
# O en Windows:
set PYTHONPATH=C:\ruta\al\proyecto\src
```

### Error: `FAILED tests/... - Failed: DID NOT RAISE`

El test espera una excepcion pero no se lanzó. Revisar la logica del modulo bajo test.

### Tests de DB fallan

Los tests con `@db_required` necesitan PostgreSQL corriendo:
```bash
# Verificar si PostgreSQL esta disponible
pg_isready -h localhost -p 5432
# Crear DB de test
createdb agentevoz_test
```

### Tests lentos en CI

Usar `--fast` para omitir tests lentos y tests que requieren DB:
```bash
bash scripts/run_all_tests.sh --fast
```

### Cobertura por debajo del 70%

Ver el reporte HTML para identificar lineas no cubiertas:
```
reports/coverage_report/index.html
```
Agregar tests para los modulos con menor cobertura o marcar codigo con `# pragma: no cover` si es codigo auxiliar.

### Warning: `PytestUnknownMarkWarning`

Los marcadores deben estar definidos en `pytest.ini`. Si aparece este warning, agregar el marcador a la seccion `[markers]`.
