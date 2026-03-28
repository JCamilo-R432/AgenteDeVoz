#!/bin/bash
# Setup PostgreSQL Replication - AgenteDeVoz
# Gap #12: Database Replication
# Inicializa replicacion streaming entre primario y replica

set -euo pipefail

PRIMARY_HOST="${PRIMARY_HOST:-10.0.0.1}"
PRIMARY_PORT="${PRIMARY_PORT:-5432}"
REPLICA_DATA_DIR="${REPLICA_DATA_DIR:-/var/lib/postgresql/14/main}"
REPL_USER="${REPL_USER:-replicator}"
REPL_PASSWORD="${REPL_PASSWORD:-CHANGE_ME}"
SLOT_NAME="${SLOT_NAME:-slot_replica1}"

echo "=== AgenteDeVoz: Setup PostgreSQL Replication ==="
echo "Primary: $PRIMARY_HOST:$PRIMARY_PORT"
echo "Replica data dir: $REPLICA_DATA_DIR"

# 1. Crear usuario replicador en primario
echo "[1/5] Creando usuario replicador en primario..."
PGPASSWORD="$REPL_PASSWORD" psql -h "$PRIMARY_HOST" -p "$PRIMARY_PORT" -U postgres <<SQL
CREATE USER IF NOT EXISTS $REPL_USER WITH REPLICATION ENCRYPTED PASSWORD '$REPL_PASSWORD';
SELECT pg_create_physical_replication_slot('$SLOT_NAME') WHERE NOT EXISTS (
    SELECT 1 FROM pg_replication_slots WHERE slot_name = '$SLOT_NAME'
);
SQL

# 2. Detener servicio PostgreSQL en replica
echo "[2/5] Deteniendo PostgreSQL en replica..."
systemctl stop postgresql || true

# 3. Limpiar directorio de datos de replica
echo "[3/5] Limpiando directorio de datos de replica..."
rm -rf "${REPLICA_DATA_DIR:?}"/*

# 4. pg_basebackup para inicializar replica
echo "[4/5] Ejecutando pg_basebackup..."
PGPASSWORD="$REPL_PASSWORD" pg_basebackup \
    -h "$PRIMARY_HOST" \
    -p "$PRIMARY_PORT" \
    -U "$REPL_USER" \
    -D "$REPLICA_DATA_DIR" \
    -P --wal-method=stream \
    --slot="$SLOT_NAME" \
    -R \
    --checkpoint=fast

# 5. Iniciar PostgreSQL en replica
echo "[5/5] Iniciando replica..."
systemctl start postgresql

echo ""
echo "=== Replicacion configurada exitosamente ==="
echo "Verificar estado con:"
echo "  psql -h $PRIMARY_HOST -U postgres -c \"SELECT * FROM pg_stat_replication;\""
