# Chaos Engineering Guide - AgenteDeVoz
**Version:** 1.0 | **Actualizado:** 2026-03-22

---

## Introduccion

El Chaos Engineering es la practica de experimentar con un sistema para descubrir debilidades antes de que se manifiesten como fallos en produccion. En AgenteDeVoz, esto significa probar que los fallbacks, circuit breakers y mecanismos de recuperacion funcionan correctamente.

**Principio de Chaos Monkey:** "Si puede sobrevivir un ataque controlado en staging, puede sobrevivir un fallo inesperado en produccion."

---

## Cuándo Ejecutar Tests de Caos

| Evento | Tests Recomendados |
|--------|-------------------|
| Antes de cada release mayor | Suite completa (todos los escenarios) |
| Despues de cambios en integraciones | Escenario especifico del servicio modificado |
| Mensualmente en staging | Suite completa + reporte |
| Antes del go-live | Suite completa obligatoria |
| Despues de un incidente P0 | Escenario relacionado con el incidente |

---

## Escenarios de Fallo Implementados

### Escenario 1: Latencia en Base de Datos

```python
from src.chaos.failure_scenarios import FailureScenarios

# Simula: disco lento, conexiones agotadas, lock contention
scenario = FailureScenarios.database_latency()
# Configuracion: 800ms latencia, 70% probabilidad, 30s duracion
```

**Verifica que:**
- Las queries se ejecutan con timeout correcto (< 5s)
- El pool de conexiones no se agota
- Las respuestas del agente siguen llegando (con posible degradacion)
- Las alertas de latencia se disparan en Prometheus

**Resultado esperado:** Sistema degradado pero funcional. Respuestas mas lentas pero sin errores 5xx.

---

### Escenario 2: Redis No Disponible

```python
scenario = FailureScenarios.redis_unavailable()
# Configuracion: error 100% probabilidad, 15s duracion
```

**Verifica que:**
- El fallback in-memory de `redis_cache.py` se activa automaticamente
- El rate limiting sigue funcionando (con datos menos precisos en multi-proceso)
- Las sesiones activas no se pierden (si hay sesiones en memoria)
- Las metricas de cache miss aumentan en el dashboard

**Resultado esperado:** Sistema completamente funcional usando fallback in-memory.

---

### Escenario 3: Timeout en Twilio

```python
scenario = FailureScenarios.twilio_timeout()
# Configuracion: timeout 5s, 50% probabilidad, 20s duracion
```

**Verifica que:**
- El TwiML generator retorna respuesta de error graceful
- Las llamadas activas no se cortan abruptamente
- Se activan alertas de webhook failures
- El WebhookRetryManager reintenta los callbacks fallidos

**Resultado esperado:** Algunas llamadas con error, pero recuperacion automatica.

---

### Escenario 4: Google STT Intermitente

```python
scenario = FailureScenarios.google_stt_intermittent()
# Configuracion: fallo 30% probabilidad, 25s duracion
```

**Verifica que:**
- El fallback a Whisper se activa para los requests fallidos
- La precision del STT se degrada pero el sistema sigue funcionando
- Las metricas de fallback aumentan en el dashboard
- El agente responde razonablemente con transcripciones de menor calidad

**Resultado esperado:** Sistema funcional con Whisper como fallback.

---

### Escenario 5: API LLM Degradada

```python
scenario = FailureScenarios.llm_api_degraded()
# Configuracion: 2s latencia, 60% probabilidad, 30s duracion
```

**Verifica que:**
- El timeout del LLM se activa correctamente (< 5s)
- El fallback a clasificacion por keywords funciona
- Los circuit breakers en `crm_connector.py` se activan si la latencia es muy alta
- El costo en `cost_optimizer.py` no se dispara con reintentos

**Resultado esperado:** Clasificacion de intenciones menos precisa pero funcional.

---

## Procedimiento de Ejecucion

### Pre-requisitos

```bash
# 1. Confirmar que estas en staging
echo "APP_ENV=${APP_ENV:-staging}"  # Debe decir "staging"

# 2. Informar al equipo
# Enviar mensaje en Slack: "Iniciando chaos tests en staging. ETA: 15 minutos."

# 3. Verificar que el sistema esta saludable ANTES de inyectar fallos
bash scripts/health_check.sh

# 4. Abrir Grafana para monitorear en tiempo real
# http://staging-grafana:3000/d/agentevoz-ops-v1
```

### Ejecucion

```bash
# Opcion 1: Escenario unico
bash scripts/run_chaos_tests.sh --scenario redis_unavailable

# Opcion 2: Suite completa
bash scripts/run_chaos_tests.sh --all

# Opcion 3: Suite completa con reporte
bash scripts/run_chaos_tests.sh --all --report

# Opcion 4: Ver que se ejecutaria sin ejecutar
bash scripts/run_chaos_tests.sh --all --dry-run
```

### Post-ejecucion

```bash
# 1. Verificar que el sistema se recupero completamente
bash scripts/health_check.sh

# 2. Revisar el reporte generado
cat reports/chaos_report_TIMESTAMP.json | python3 -m json.tool

# 3. Notificar al equipo con resultados
# "Chaos tests completados. Score de resiliencia: XX/100. [detalles]"

# 4. Si hubo fallos inesperados: abrir issue en GitHub/Jira
```

---

## Interpretacion de Resultados

### Score de Resiliencia

| Score | Estado | Interpretacion |
|-------|--------|----------------|
| 90-100 | RESILIENTE | Sistema altamente resiliente. Continuar con periodicidad mensual. |
| 75-89 | ACEPTABLE | Sistema funcional bajo fallos. Revisar los escenarios que fallaron. |
| 60-74 | FRAGIL | Problemas de resiliencia detectados. Priorizar mejoras antes del go-live. |
| < 60 | CRITICO | Sistema no esta listo para produccion. Bloqueante para go-live. |

### Fallo en un Escenario

Si un escenario falla (resilience_score < 70):

1. **Identificar el servicio afectado** en el reporte
2. **Verificar el circuit breaker** del servicio en el codigo
3. **Revisar los timeouts** configurados en `src/config/settings.py`
4. **Agregar o mejorar el fallback** si no existe
5. **Re-ejecutar el escenario** para verificar la correccion
6. **Documentar la mejora** en el CHANGELOG

---

## Mejores Practicas

### DO (Hacer)

- Siempre ejecutar en **staging**, nunca en produccion sin aprobacion
- **Informar al equipo** antes de ejecutar tests (puede generar alertas falsas)
- **Monitorear en Grafana** durante la ejecucion
- **Documentar los resultados** en el registro de mantenimiento
- Comenzar con **probabilidades bajas** (10-30%) y aumentar gradualmente
- Ejecutar los tests de forma **repetible** para comparar resultados

### DON'T (No hacer)

- NO ejecutar en produccion sin coordinacion del equipo completo
- NO ignorar resultados de resilience_score < 70
- NO ejecutar durante ventanas de alto trafico
- NO olvidar verificar que el sistema se recupero despues del test
- NO ejecutar si el sistema ya esta degradado (agravar problemas existentes)

---

## Agregar Nuevos Escenarios

Para agregar un nuevo escenario de fallo:

```python
# En src/chaos/failure_scenarios.py

@staticmethod
def nuevo_servicio_fallo() -> ChaosExperiment:
    """Descripcion clara del escenario y que verifica."""
    return ChaosExperiment(
        name="nuevo_servicio_fallo",
        description="Descripcion del fallo simulado",
        service="nombre_servicio",
        failure_type="latency",  # o "error", "timeout", "partial"
        probability=0.5,         # 50% de las llamadas fallan
        duration_seconds=30,     # 30 segundos de duracion
        kwargs={"latency_ms": 500},
    )
```

Luego agregar al metodo `all_scenarios()` y escribir el test correspondiente en `tests/test_chaos.py`.

---

## Historial de Chaos Tests

| Fecha | Entorno | Score | Vulnerabilidades | Accion |
|-------|---------|-------|-----------------|--------|
| 2026-03-22 | staging | [Pendiente] | [Pendiente] | Primer run pre-produccion |

---

**Responsable:** DevOps Lead + Tech Lead
**Frecuencia:** Mensual en staging, obligatorio antes de cada release mayor
**Proxima ejecucion:** Primera semana post go-live
