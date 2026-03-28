#!/usr/bin/env bash
# ============================================================
# pre_deploy_check.sh - Verificaciones antes de desplegar
# AgenteDeVoz - Fase 6
# Uso: bash scripts/pre_deploy_check.sh [--strict]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

STRICT=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --strict) STRICT=true; shift ;;
    *) shift ;;
  esac
done

export PYTHONPATH="$PROJECT_ROOT/src"
export APP_ENV="${APP_ENV:-test}"

PASSED=0; FAILED=0; WARNINGS=0

check_pass() { echo -e "  ${GREEN}[OK]${NC} $1"; PASSED=$((PASSED + 1)); }
check_fail() { echo -e "  ${RED}[FALLO]${NC} $1"; FAILED=$((FAILED + 1)); }
check_warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; WARNINGS=$((WARNINGS + 1)); }

echo "============================================================"
echo -e "  ${BLUE}AgenteDeVoz - Verificacion Pre-Despliegue${NC}"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# 1. Tests unitarios
echo -e "${YELLOW}[1/8] Tests unitarios...${NC}"
if python -m pytest "$PROJECT_ROOT/tests/unit/" \
   -q --tb=no --no-header 2>&1 | tail -3; then
  check_pass "Tests unitarios pasando"
else
  check_fail "Tests unitarios FALLANDO"
fi
echo ""

# 2. Tests de seguridad
echo -e "${YELLOW}[2/8] Tests de seguridad...${NC}"
if python -m pytest "$PROJECT_ROOT/tests/security/" \
   -q --tb=no --no-header 2>&1 | tail -3; then
  check_pass "Tests de seguridad pasando"
else
  check_fail "Tests de seguridad FALLANDO"
fi
echo ""

# 3. Cobertura de codigo
echo -e "${YELLOW}[3/8] Cobertura de codigo (minimo 70%)...${NC}"
COVERAGE_OUTPUT=$(python -m pytest \
  "$PROJECT_ROOT/tests/" "$PROJECT_ROOT/src/tests/" \
  --cov="$PROJECT_ROOT/src" \
  --cov-report=term \
  --ignore="$PROJECT_ROOT/src/tests/test_api.py" \
  -q --no-header \
  -m "not db_required and not slow" 2>&1)

COVERAGE_PCT=$(echo "$COVERAGE_OUTPUT" | grep "TOTAL" | awk '{print $NF}' | tr -d '%' || echo "0")
if [[ "${COVERAGE_PCT:-0}" -ge 70 ]]; then
  check_pass "Cobertura: ${COVERAGE_PCT}% (>= 70%)"
else
  check_fail "Cobertura: ${COVERAGE_PCT}% (< 70%)"
fi
echo ""

# 4. Analisis de seguridad con bandit
echo -e "${YELLOW}[4/8] Analisis estatico (bandit)...${NC}"
if command -v bandit &>/dev/null; then
  BANDIT_OUTPUT=$(bandit -r "$PROJECT_ROOT/src" \
    -x "$PROJECT_ROOT/src/tests" \
    --severity-level high \
    -q 2>&1)
  HIGH_ISSUES=$(echo "$BANDIT_OUTPUT" | grep -c "Severity: High" || true)
  if [[ "$HIGH_ISSUES" -eq 0 ]]; then
    check_pass "Bandit: Sin issues de severidad alta"
  else
    check_fail "Bandit: $HIGH_ISSUES issues de severidad alta"
  fi
else
  check_warn "Bandit no instalado (pip install bandit)"
fi
echo ""

# 5. Vulnerabilidades en dependencias
echo -e "${YELLOW}[5/8] Vulnerabilidades en dependencias (safety)...${NC}"
if command -v safety &>/dev/null; then
  if safety check -q 2>&1 | grep -q "No known security vulnerabilities found"; then
    check_pass "Safety: Sin vulnerabilidades conocidas"
  else
    VULN_COUNT=$(safety check 2>&1 | grep -c "vulnerability" || echo "?")
    if [[ "$STRICT" == "true" ]]; then
      check_fail "Safety: Vulnerabilidades encontradas ($VULN_COUNT)"
    else
      check_warn "Safety: Posibles vulnerabilidades (revisar antes de deploy)"
    fi
  fi
else
  check_warn "Safety no instalado (pip install safety)"
fi
echo ""

# 6. Variables de entorno criticas
echo -e "${YELLOW}[6/8] Variables de entorno criticas...${NC}"
ENV_FILE=""
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  ENV_FILE="$PROJECT_ROOT/.env"
elif [[ -f "$PROJECT_ROOT/config/production.env" ]]; then
  ENV_FILE="$PROJECT_ROOT/config/production.env"
fi

if [[ -n "$ENV_FILE" ]]; then
  # Verificar que no haya valores CAMBIAR_POR_ en produccion
  if grep -q "CAMBIAR_POR_" "$ENV_FILE" 2>/dev/null; then
    UNFILLED=$(grep -c "CAMBIAR_POR_" "$ENV_FILE")
    check_fail "Config: $UNFILLED variables sin configurar (CAMBIAR_POR_*)"
  else
    check_pass "Config: Todas las variables configuradas"
  fi
else
  check_warn "Config: No se encontro archivo .env (buscar en sistema)"
fi
echo ""

# 7. Conexion a base de datos
echo -e "${YELLOW}[7/8] Conexion a base de datos...${NC}"
if command -v pg_isready &>/dev/null; then
  DB_HOST="${DB_HOST:-localhost}"
  DB_PORT="${DB_PORT:-5432}"
  if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
    check_pass "PostgreSQL disponible en $DB_HOST:$DB_PORT"
  else
    if [[ "$APP_ENV" == "production" ]]; then
      check_fail "PostgreSQL no disponible (REQUERIDO en produccion)"
    else
      check_warn "PostgreSQL no disponible (aceptable en test)"
    fi
  fi
else
  check_warn "pg_isready no disponible (no se pudo verificar PostgreSQL)"
fi
echo ""

# 8. Espacio en disco
echo -e "${YELLOW}[8/8] Espacio en disco...${NC}"
DISK_USAGE=$(df "$PROJECT_ROOT" 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')
if [[ -n "$DISK_USAGE" ]]; then
  if [[ "$DISK_USAGE" -lt 80 ]]; then
    check_pass "Disco: ${DISK_USAGE}% usado (< 80%)"
  elif [[ "$DISK_USAGE" -lt 90 ]]; then
    check_warn "Disco: ${DISK_USAGE}% usado (precaucion)"
  else
    check_fail "Disco: ${DISK_USAGE}% usado (CRITICO)"
  fi
else
  check_warn "No se pudo verificar espacio en disco"
fi
echo ""

# Resumen
echo "============================================================"
echo -e "  ${BLUE}RESUMEN${NC}"
echo "============================================================"
echo -e "  Pasaron:   ${GREEN}$PASSED${NC}"
echo -e "  Warnings:  ${YELLOW}$WARNINGS${NC}"
echo -e "  Fallaron:  ${RED}$FAILED${NC}"
echo ""

if [[ $FAILED -eq 0 ]]; then
  if [[ $WARNINGS -gt 0 ]]; then
    echo -e "  ${YELLOW}LISTO PARA DEPLOY (con $WARNINGS advertencias)${NC}"
    echo "  Revisa los warnings antes de proceder a produccion."
  else
    echo -e "  ${GREEN}LISTO PARA DEPLOY${NC}"
  fi
  exit 0
else
  echo -e "  ${RED}NO LISTO PARA DEPLOY ($FAILED checks fallaron)${NC}"
  echo "  Corrige los errores antes de continuar."
  exit 1
fi
