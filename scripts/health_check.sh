#!/usr/bin/env bash
# ============================================================
# health_check.sh - Verifica estado de todos los servicios
# Uso: bash scripts/health_check.sh [--alert-email admin@empresa.com]
# Cron recomendado: */5 * * * * /opt/agentevoz/scripts/health_check.sh
# ============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APP_URL="${APP_URL:-http://localhost:8000}"
ALERT_EMAIL=""
EXIT_CODE=0
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Parsear argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --alert-email) ALERT_EMAIL="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Cargar env
ENV_FILE="$PROJECT_ROOT/config/production.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

# Colores (desactivar si no es TTY)
if [[ -t 1 ]]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; NC=''
fi

FAILED_CHECKS=()

# ── Función de check ───────────────────────────────────────────────────────

check() {
  local name="$1"
  local cmd="$2"
  local expected="${3:-0}"

  if eval "$cmd" &>/dev/null; then
    echo -e "  ${GREEN}[OK]${NC}   $name"
  else
    echo -e "  ${RED}[FAIL]${NC} $name"
    FAILED_CHECKS+=("$name")
    EXIT_CODE=1
  fi
}

echo "============================================================"
echo "  AgenteDeVoz - Health Check ($TIMESTAMP)"
echo "============================================================"
echo ""

# ── API REST ───────────────────────────────────────────────────────────────

echo "API REST:"
check "Ping endpoint" \
  "curl -sf --max-time 5 $APP_URL/api/v1/ping"
check "Health endpoint" \
  "curl -sf --max-time 10 $APP_URL/api/v1/health | grep -q '\"status\":\"ok\"'"
check "Tiempo respuesta < 2s" \
  "[ \$(curl -so /dev/null -w '%{time_total}' --max-time 5 $APP_URL/api/v1/ping | awk '{print int(\$0 < 2)}') -eq 1 ]"

# ── Docker containers ─────────────────────────────────────────────────────

echo ""
echo "Docker Containers:"
if command -v docker &>/dev/null; then
  check "agentevoz_app corriendo" \
    "docker ps --filter name=agentevoz_app --filter status=running -q | grep -q ."
  check "agentevoz_postgres corriendo" \
    "docker ps --filter name=agentevoz_postgres --filter status=running -q | grep -q ."
  check "agentevoz_redis corriendo" \
    "docker ps --filter name=agentevoz_redis --filter status=running -q | grep -q ."
  check "agentevoz_nginx corriendo" \
    "docker ps --filter name=agentevoz_nginx --filter status=running -q | grep -q ."
else
  echo "  ${YELLOW}[SKIP]${NC} Docker no disponible en este host."
fi

# ── PostgreSQL ─────────────────────────────────────────────────────────────

echo ""
echo "PostgreSQL:"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-agentevoz}"
DB_NAME="${DB_NAME:-agentevoz}"

if command -v pg_isready &>/dev/null; then
  check "pg_isready" \
    "pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t 5"
else
  check "TCP porta postgres" \
    "nc -z -w 3 $DB_HOST $DB_PORT"
fi

# ── Redis ──────────────────────────────────────────────────────────────────

echo ""
echo "Redis:"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

if command -v redis-cli &>/dev/null; then
  check "Redis PING" \
    "redis-cli -h $REDIS_HOST -p $REDIS_PORT ping | grep -qi pong"
else
  check "TCP porta redis" \
    "nc -z -w 3 $REDIS_HOST $REDIS_PORT"
fi

# ── Disco ──────────────────────────────────────────────────────────────────

echo ""
echo "Recursos del sistema:"
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
check "Disco < 85%" "[ $DISK_USAGE -lt 85 ]"

MEM_AVAIL=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo "999")
check "Memoria disponible > 200MB" "[ $MEM_AVAIL -gt 200 ]"

# ── Logs recientes ─────────────────────────────────────────────────────────

echo ""
echo "Logs (ultimos 5 min):"
LOG_FILE="${LOG_DIR:-/var/log/agentevoz}/app.log"
if [[ -f "$LOG_FILE" ]]; then
  ERROR_COUNT=$(tail -100 "$LOG_FILE" 2>/dev/null | grep -c "ERROR" || echo "0")
  check "Errores en log < 10" "[ $ERROR_COUNT -lt 10 ]"
  if [[ "$ERROR_COUNT" -gt 0 ]]; then
    echo "  ${YELLOW}[INFO]${NC} $ERROR_COUNT error(es) en log reciente."
  fi
else
  echo "  ${YELLOW}[SKIP]${NC} Log no encontrado: $LOG_FILE"
fi

# ── Resumen ────────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
if [[ $EXIT_CODE -eq 0 ]]; then
  echo -e "  ${GREEN}RESULTADO: TODOS LOS CHECKS PASARON${NC}"
else
  echo -e "  ${RED}RESULTADO: ${#FAILED_CHECKS[@]} CHECK(S) FALLARON${NC}"
  for f in "${FAILED_CHECKS[@]}"; do
    echo -e "  ${RED}  - $f${NC}"
  done

  # Enviar alerta por email si se configuró
  if [[ -n "$ALERT_EMAIL" ]] && command -v mail &>/dev/null; then
    echo "Enviando alerta a $ALERT_EMAIL..."
    BODY="Health check fallido en AgenteDeVoz ($TIMESTAMP):\n"
    for f in "${FAILED_CHECKS[@]}"; do
      BODY+="  - $f\n"
    done
    echo -e "$BODY" | mail -s "[ALERTA] AgenteDeVoz Health Check FALLO" "$ALERT_EMAIL" || true
  fi
fi
echo "============================================================"
exit $EXIT_CODE
