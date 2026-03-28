#!/usr/bin/env bash
# ============================================================
# setup_database.sh - Crea y migra la base de datos PostgreSQL
# Uso: bash scripts/setup_database.sh [--env staging|prod]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SCHEMA_FILE="$PROJECT_ROOT/src/integrations/database_schema.sql"
ENV_FILE="$PROJECT_ROOT/config/production.env"
ENV="prod"

# Parsear argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --env) ENV="$2"; shift 2 ;;
    *) echo "Opcion desconocida: $1"; exit 1 ;;
  esac
done

if [[ "$ENV" == "staging" ]]; then
  ENV_FILE="$PROJECT_ROOT/config/staging.env"
fi

echo "============================================================"
echo "  AgenteDeVoz - Setup de Base de Datos ($ENV)"
echo "============================================================"

# Cargar variables de entorno
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
  echo "[OK] Variables cargadas desde $ENV_FILE"
else
  echo "[ERROR] Archivo de entorno no encontrado: $ENV_FILE"
  exit 1
fi

# Valores por defecto
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-agentevoz}"
DB_USER="${DB_USER:-agentevoz}"
DB_PASS="${DB_PASSWORD:-}"

if [[ -z "$DB_PASS" ]]; then
  echo "[ERROR] DB_PASSWORD no configurado."
  exit 1
fi

export PGPASSWORD="$DB_PASS"

echo ""
echo "Host: $DB_HOST:$DB_PORT"
echo "Base: $DB_NAME"
echo "Usuario: $DB_USER"
echo ""

# ── Verificar conexión ─────────────────────────────────────────────────────

echo "[1/4] Verificando conexion a PostgreSQL..."
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -t 10; then
  echo "[ERROR] No se puede conectar a PostgreSQL."
  exit 1
fi
echo "[OK] Conexion exitosa."

# ── Crear base de datos si no existe ──────────────────────────────────────

echo "[2/4] Creando base de datos '$DB_NAME' (si no existe)..."
RESULT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null || echo "0")

if echo "$RESULT" | grep -q "1"; then
  echo "[OK] Base de datos ya existe."
else
  psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -c \
    "CREATE DATABASE $DB_NAME ENCODING 'UTF8' LC_COLLATE 'es_CO.UTF-8' LC_CTYPE 'es_CO.UTF-8' TEMPLATE template0;"
  echo "[OK] Base de datos '$DB_NAME' creada."
fi

# Asegurar permisos del usuario
psql -h "$DB_HOST" -p "$DB_PORT" -U postgres -c \
  "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null || true

# ── Ejecutar schema ────────────────────────────────────────────────────────

echo "[3/4] Ejecutando schema SQL..."
if [[ ! -f "$SCHEMA_FILE" ]]; then
  echo "[ERROR] No se encontro el schema: $SCHEMA_FILE"
  exit 1
fi

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_FILE"
echo "[OK] Schema aplicado correctamente."

# ── Verificar tablas ───────────────────────────────────────────────────────

echo "[4/4] Verificando tablas creadas..."
TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tc \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" | tr -d ' ')

echo "[OK] $TABLE_COUNT tabla(s) encontrada(s) en el schema public."

echo ""
echo "============================================================"
echo "  Setup completado exitosamente."
echo "============================================================"

unset PGPASSWORD
