# Incident Management - AgenteDeVoz

Gap #16: Gestion de incidentes con PagerDuty/OpsGenie y playbooks de respuesta.

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/operations/incident_manager.py` | Ciclo de vida completo de incidentes |
| `src/operations/pagerduty_integration.py` | PagerDuty Events API v2 |
| `src/operations/opsgenie_integration.py` | OpsGenie Alert API v2 |
| `src/operations/incident_response.py` | Playbooks de respuesta |
| `src/operations/on_call_scheduler.py` | Rotaciones y escalado on-call |

## Severidades y SLOs

| Severidad | Descripcion | Ack SLO | Resolucion SLO |
|-----------|-------------|---------|----------------|
| SEV1 | Servicio caido | 5 min | 1 hora |
| SEV2 | Degradacion significativa | 15 min | 4 horas |
| SEV3 | Impacto parcial | 60 min | 24 horas |
| SEV4 | Impacto minimo | 24 horas | 7 dias |

## Uso rapido

```python
from src.operations.incident_manager import IncidentManager, IncidentSeverity
from src.operations.pagerduty_integration import PagerDutyIntegration, PagerDutyConfig

pd = PagerDutyIntegration(PagerDutyConfig(
    integration_key=os.environ["PAGERDUTY_INTEGRATION_KEY"]
))
manager = IncidentManager()
manager.register_notifier(pd)

# Crear incidente
inc = manager.create_incident(
    title="API Gateway no responde",
    description="Health checks fallando en todos los nodos",
    severity=IncidentSeverity.SEV1,
    service="api-gateway",
)

# Reconocer
manager.acknowledge(inc.incident_id, engineer="eng1@team.com")

# Actualizar con progreso
manager.add_update(inc.incident_id, "eng1@team.com", "Identificado: OOM en pod api-2")

# Resolver
manager.resolve(inc.incident_id, "eng1@team.com", "Aumentado limite memoria K8s")
```

## Playbooks disponibles

- `api_down` — Reinicio de pods, modo mantenimiento, notificacion
- `high_latency` — Escalado, verificacion dependencias
- `security_breach` — Aislamiento, forense, GDPR notification
- `data_loss` — Stop writes, restauracion backup, Art. 34

## Configurar alertas

```bash
export PAGERDUTY_INTEGRATION_KEY="your-key"
export OPSGENIE_API_KEY="your-key"
bash scripts/configure_pagerduty.sh
```
