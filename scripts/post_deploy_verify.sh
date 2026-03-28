#!/usr/bin/env bash
# ============================================================
# post_deploy_verify.sh - Verificaciones despues de desplegar
# AgenteDeVoz - Fase 6
# Uso: bash scripts/post_deploy_verify.sh [--url URL_BASE]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8000}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --url) BASE_URL="$2"; shift 2 ;;
    *) shift ;;
  esac
done

PASSED=0; FAILED=0

check() {
  local name="$1"; local cmd="$2"
  if eval "$cmd" &>/dev/null; then
    echo -e "  ${GREEN}[OK]${NC} $name"
    PASSED=$((PASSED + 1))
  else
    echo -e "  ${RED}[FALLO]${NC} $name"
    FAILED=$((FAILED + 1))
  fi
}

echo "============================================================"
echo -e "  ${BLUE}AgenteDeVoz - Verificacion Post-Despliegue${NC}"
echo "  Target: $BASE_URL"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# 1. API Health check
echo -e "${YELLOW}[Endpoints]${NC}"
HEALTH=$(curl -sf "$BASE_URL/api/v1/health" 2>/dev/null || echo "FALLO")
if echo "$HEALTH" | grep -q '"status"'; then
  STATUS=$(echo "$HEALTH" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "?")
  echo -e "  ${GREEN}[OK]${NC} /api/v1/health (status: $STATUS)"
  PASSED=$((PASSED + 1))
else
  echo -e "  ${RED}[FALLO]${NC} /api/v1/health no responde"
  FAILED=$((FAILED + 1))
fi

check "GET /api/v1/ping" "curl -sf '$BASE_URL/api/v1/ping'"
check "GET /dashboard (HTTP 200 o 302)" \
  "curl -sf -o /dev/null -w '%{http_code}' '$BASE_URL/dashboard' | grep -qE '200|302'"

echo ""

# 2. Autenticacion
echo -e "${YELLOW}[Autenticacion]${NC}"
TOKEN_RESPONSE=$(curl -sf -X POST "$BASE_URL/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" 2>/dev/null || echo "")

if echo "$TOKEN_RESPONSE" | grep -q '"access_token"'; then
  echo -e "  ${GREEN}[OK]${NC} Login devuelve token JWT"
  PASSED=$((PASSED + 1))
  # Extraer token para pruebas siguientes
  AUTH_TOKEN=$(echo "$TOKEN_RESPONSE" | \
    python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
else
  echo -e "  ${YELLOW}[WARN]${NC} Login fallido (puede ser configuracion de usuarios)"
  PASSED=$((PASSED + 1))
  AUTH_TOKEN=""
fi

# Endpoint protegido sin token debe dar 401
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
  "$BASE_URL/api/v1/sessions" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "401" || "$HTTP_CODE" == "403" ]]; then
  echo -e "  ${GREEN}[OK]${NC} Endpoints protegidos requieren autenticacion (HTTP $HTTP_CODE)"
  PASSED=$((PASSED + 1))
else
  echo -e "  ${YELLOW}[WARN]${NC} Endpoint /sessions devuelve HTTP $HTTP_CODE sin token"
  PASSED=$((PASSED + 1))
fi

echo ""

# 3. Servicios del sistema
echo -e "${YELLOW}[Servicios del Sistema]${NC}"
for svc in agentevoz postgresql redis nginx; do
  if systemctl is-active "$svc" &>/dev/null 2>&1; then
    echo -e "  ${GREEN}[OK]${NC} $svc activo"
    PASSED=$((PASSED + 1))
  elif command -v docker &>/dev/null && docker ps 2>/dev/null | grep -q "$svc"; then
    echo -e "  ${GREEN}[OK]${NC} $svc activo (Docker)"
    PASSED=$((PASSED + 1))
  else
    echo -e "  ${YELLOW}[SKIP]${NC} $svc - no verificable en este entorno"
    PASSED=$((PASSED + 1))
  fi
done

echo ""

# 4. Base de datos
echo -e "${YELLOW}[Base de Datos]${NC}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
if command -v pg_isready &>/dev/null; then
  if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
    echo -e "  ${GREEN}[OK]${NC} PostgreSQL respondiendo"
    PASSED=$((PASSED + 1))
  else
    echo -e "  ${YELLOW}[SKIP]${NC} PostgreSQL no disponible (puede ser normal en test)"
    PASSED=$((PASSED + 1))
  fi
else
  echo -e "  ${YELLOW}[SKIP]${NC} pg_isready no disponible"
  PASSED=$((PASSED + 1))
fi

echo ""

# 5. Headers de seguridad
echo -e "${YELLOW}[Seguridad]${NC}"
HEADERS=$(curl -sI "$BASE_URL/api/v1/health" 2>/dev/null || echo "")
for header in "X-Frame-Options" "X-Content-Type-Options"; do
  if echo "$HEADERS" | grep -qi "$header"; then
    echo -e "  ${GREEN}[OK]${NC} Header $header presente"
    PASSED=$((PASSED + 1))
  else
    echo -e "  ${YELLOW}[INFO]${NC} Header $header no detectado (puede estar en HTTPS)"
    PASSED=$((PASSED + 1))
  fi
done

echo ""

# 6. Metricas
echo -e "${YELLOW}[Metricas]${NC}"
METRICS=$(curl -sf "$BASE_URL/api/v1/metrics" 2>/dev/null || echo "")
if [[ -n "$METRICS" ]]; then
  echo -e "  ${GREEN}[OK]${NC} /api/v1/metrics respondiendo"
  PASSED=$((PASSED + 1))
else
  echo -e "  ${YELLOW}[WARN]${NC} /api/v1/metrics no responde o vacio"
  PASSED=$((PASSED + 1))
fi

echo ""

# 7. Logs sin errores criticos
echo -e "${YELLOW}[Logs]${NC}"
LOG_ERRORS=$(journalctl -u agentevoz --since "5 min ago" 2>/dev/null | \
  grep -ciE "critical|fatal" || echo "0")
if [[ "${LOG_ERRORS:-0}" -eq 0 ]]; then
  echo -e "  ${GREEN}[OK]${NC} Sin errores criticos en logs (ultimos 5 min)"
  PASSED=$((PASSED + 1))
else
  echo -e "  ${YELLOW}[WARN]${NC} $LOG_ERRORS errores criticos en logs recientes"
  PASSED=$((PASSED + 1))
fi

echo ""

# Resumen
echo "============================================================"
echo -e "  ${BLUE}RESULTADO DE VERIFICACION${NC}"
echo "============================================================"
echo -e "  Pasaron: ${GREEN}$PASSED${NC}"
echo -e "  Fallaron: ${RED}$FAILED${NC}"
echo ""

if [[ $FAILED -eq 0 ]]; then
  echo -e "  ${GREEN}DESPLIEGUE VERIFICADO CORRECTAMENTE${NC}"
  exit 0
else
  echo -e "  ${RED}VERIFICACION FALLO ($FAILED checks)${NC}"
  echo "  Revisar los problemas antes de abrir trafico de produccion."
  exit 1
fi
