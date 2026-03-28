#!/usr/bin/env bash
# ============================================================
# backup.sh - Backup de PostgreSQL y archivos de configuracion
# Uso: bash scripts/backup.sh [--quick] [--dest /ruta]
# Cron recomendado: 0 3 * * * /opt/agentevoz/scripts/backup.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/agentevoz}"
RETENTION_DAYS=7
QUICK=false
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# Parsear argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --quick) QUICK=true; shift ;;
    --dest)  BACKUP_DIR="$2"; shift 2 ;;
    *) echo "Opcion desconocida: $1"; exit 1 ;;
  esac
done

# Cargar env
ENV_FILE="$PROJECT_ROOT/config/production.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-agentevoz}"
DB_USER="${DB_USER:-agentevoz}"
DB_PASS="${DB_PASSWORD:-}"

mkdir -p "$BACKUP_DIR"

echo "============================================================"
echo "  AgenteDeVoz - Backup ($TIMESTAMP)"
echo "  Destino: $BACKUP_DIR"
echo "============================================================"

# ── Backup de PostgreSQL ───────────────────────────────────────────────────

echo "[1/3] Dump de PostgreSQL..."
export PGPASSWORD="$DB_PASS"
DUMP_FILE="$BACKUP_DIR/db_${DB_NAME}_${TIMESTAMP}.sql.gz"

if [[ "$QUICK" == "true" ]]; then
  # Solo tablas criticas en backup rapido
  pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --table=tickets --table=conversations --table=users \
    --no-owner --no-acl | gzip > "$DUMP_FILE"
  echo "[OK] Dump rapido -> $DUMP_FILE"
else
  pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --no-owner --no-acl --format=plain | gzip > "$DUMP_FILE"
  echo "[OK] Dump completo -> $DUMP_FILE"
fi
unset PGPASSWORD

# ── Backup de configuracion ───────────────────────────────────────────────

echo "[2/3] Backup de configuracion..."
CONF_FILE="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"
tar -czf "$CONF_FILE" \
  -C "$PROJECT_ROOT" \
  config/ \
  --exclude="*.env" \
  --exclude="*.key" \
  2>/dev/null || echo "[WARN] Algunos archivos no pudieron incluirse."
echo "[OK] Config -> $CONF_FILE"

# ── Limpieza de backups antiguos ──────────────────────────────────────────

echo "[3/3] Limpiando backups mayores de ${RETENTION_DAYS} dias..."
find "$BACKUP_DIR" -name "*.gz" -mtime "+${RETENTION_DAYS}" -delete
REMAINING=$(find "$BACKUP_DIR" -name "*.gz" | wc -l)
echo "[OK] $REMAINING archivo(s) de backup retenidos."

# Resumen de tamaño
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
echo ""
echo "============================================================"
echo "  Backup completado: $BACKUP_DIR ($TOTAL_SIZE total)"
echo "============================================================"
