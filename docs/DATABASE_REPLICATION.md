# Database Replication - AgenteDeVoz

Gap #12: Replicacion PostgreSQL primary/replica con failover de lectura.

## Topologia

```
[App Writes] -> [PostgreSQL PRIMARY :5432]
                        |
                  WAL Streaming
                        |
              [PostgreSQL REPLICA1 :5432]  <- [App Reads]
              [PostgreSQL REPLICA2 :5432]  <- [App Reads]
```

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/infrastructure/database_replication.py` | Pool de nodos, distribucion lecturas |
| `src/infrastructure/postgresql_replication.py` | Generador de configuracion |
| `src/infrastructure/replication_monitor.py` | Monitor de lag y alertas |

## Configuracion rapida

```bash
# 1. Configurar primary
PRIMARY_HOST=10.0.0.1 REPL_PASSWORD=secret bash scripts/setup_replication.sh

# 2. Verificar replicacion
psql -h 10.0.0.1 -U postgres -c "SELECT * FROM pg_stat_replication;"
```

## Uso en codigo

```python
from src.infrastructure.database_replication import (
    DatabaseReplicationManager, DatabaseNode, ReplicationRole, ReplicationStatus
)

mgr = DatabaseReplicationManager(max_replica_lag_s=10.0)
mgr.register_node(DatabaseNode("primary", "10.0.0.1", 5432, "agentevoz", ReplicationRole.PRIMARY))
mgr.register_node(DatabaseNode("replica1", "10.0.0.2", 5432, "agentevoz", ReplicationRole.REPLICA))

# Obtener nodo para escritura
write_conn = mgr.get_write_node()  # -> PRIMARY

# Obtener nodo para lectura (prefiere replica)
read_conn = mgr.get_read_node(prefer_replica=True)  # -> REPLICA si lag OK
```

## Archivos de configuracion

- `config/postgresql/primary.conf` — postgresql.conf para primario
- `config/postgresql/replica.conf` — postgresql.conf para replica
- `config/postgresql/replication.sql` — SQL de setup y monitoreo

## Alertas de lag

El `ReplicationMonitor` alerta cuando:
- Lag > 30 segundos (configurable)
- Lag > 50 MB de bytes pendientes
- Estado de replica no es `streaming`
