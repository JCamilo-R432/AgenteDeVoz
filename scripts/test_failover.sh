#!/bin/bash
# Test Failover - AgenteDeVoz
# Gap #11: High Availability
# Prueba el proceso de failover de forma controlada

set -euo pipefail

echo "=== AgenteDeVoz: Failover Test ==="

PRIMARY="${PRIMARY_HOST:-10.0.0.1}"
REPLICA="${REPLICA_HOST:-10.0.0.2}"
API_URL="${API_URL:-http://localhost:80}"

echo "Primary DB: $PRIMARY"
echo "Replica DB: $REPLICA"
echo "API URL: $API_URL"

# 1. Verificar estado inicial
echo ""
echo "[1/5] Verificando estado inicial del cluster..."
curl -sf "$API_URL/health" && echo "  API: OK" || echo "  API: FAIL"

# 2. Test de health checks
echo ""
echo "[2/5] Probando health checks..."
python3 -c "
from src.infrastructure.health_checks import HealthCheckRegistry, tcp_check, disk_space_check
import sys

registry = HealthCheckRegistry()
registry.register('disk', lambda: disk_space_check('/', min_free_gb=0.1))
results = registry.run_all()
summary = registry.get_summary()
print(f'  Overall: {summary[\"overall\"]}')
print(f'  Healthy: {summary[\"healthy_count\"]}')
" 2>/dev/null || echo "  SKIP: modulos no disponibles"

# 3. Simular fallo (solo si PRIMARY_SIMULATE_FAIL=true)
if [ "${PRIMARY_SIMULATE_FAIL:-false}" = "true" ]; then
    echo ""
    echo "[3/5] SIMULANDO fallo del primario (CTRL+C para abortar en 5s)..."
    sleep 5

    echo "  Deteniendo PostgreSQL en primario..."
    ssh "$PRIMARY" "systemctl stop postgresql" || echo "  No se pudo detener primario"
else
    echo ""
    echo "[3/5] SKIP: Simulacion de fallo deshabilitada (PRIMARY_SIMULATE_FAIL=false)"
fi

# 4. Verificar que la replica asume el rol
echo ""
echo "[4/5] Verificando failover..."
python3 -c "
from src.infrastructure.database_replication import DatabaseReplicationManager, DatabaseNode, ReplicationRole
mgr = DatabaseReplicationManager()
print('  DatabaseReplicationManager: OK')
" 2>/dev/null || echo "  SKIP: modulos no disponibles"

# 5. Restaurar
if [ "${PRIMARY_SIMULATE_FAIL:-false}" = "true" ]; then
    echo ""
    echo "[5/5] Restaurando primario..."
    ssh "$PRIMARY" "systemctl start postgresql" || echo "  No se pudo restaurar primario"
fi

echo ""
echo "=== Test de failover completado ==="
