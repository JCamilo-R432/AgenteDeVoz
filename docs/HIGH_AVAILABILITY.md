# High Availability - AgenteDeVoz

Gap #11: Configuracion de alta disponibilidad con failover automatico.

## Arquitectura

```
[Cliente] -> [HAProxy LB] -> [API Node 1 (PRIMARY)]
                          -> [API Node 2 (SECONDARY)]
                          -> [API Node 3 (STANDBY/backup)]
```

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/infrastructure/high_availability.py` | Gestor de nodos y failover |
| `src/infrastructure/failover_manager.py` | Estrategias y hooks de failover |
| `src/infrastructure/health_checks.py` | Health checks TCP/HTTP/disco |

## Uso rapido

```python
from src.infrastructure.high_availability import (
    HighAvailabilityManager, Node, NodeRole, HAConfig
)

config = HAConfig(
    heartbeat_timeout_s=15.0,
    max_failures_before_failover=3,
    failover_cooldown_s=60.0,
)
ha = HighAvailabilityManager(config=config)

ha.register_node(Node("api1", "10.0.0.1", 8000, NodeRole.PRIMARY))
ha.register_node(Node("api2", "10.0.0.2", 8000, NodeRole.SECONDARY))

# Registrar heartbeats periodicamente
ha.record_heartbeat("api1", response_time_ms=45.0)

# Ciclo de health check (ejecutar cada N segundos)
results = ha.run_health_check_cycle()
status = ha.get_cluster_status()
```

## SLO

- Disponibilidad objetivo: >= 99.9% (8.7h downtime/ano)
- Tiempo maximo de failover: < 30 segundos
- Cooldown entre failovers: 60 segundos

## Scripts

```bash
bash scripts/test_failover.sh          # Test controlado de failover
bash scripts/backup_and_restore.sh     # Backup y restauracion
```
