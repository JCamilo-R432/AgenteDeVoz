#!/usr/bin/env bash
# ============================================================
# run_all_tests.sh - Ejecuta toda la bateria de tests
# Agente de Voz - Fase 5
# Uso: bash scripts/run_all_tests.sh [--fast] [--coverage]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colores
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

# Opciones
FAST=false
COVERAGE=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --fast)     FAST=true;     shift ;;
    --coverage) COVERAGE=true; shift ;;
    *) shift ;;
  esac
done

# Configuracion
export PYTHONPATH="$PROJECT_ROOT/src"
export DATABASE_URL="${DATABASE_URL:-postgresql://test:test@localhost:5432/agentevoz_test}"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export LOG_LEVEL="WARNING"
export APP_ENV="test"

TOTAL=0; PASSED=0; FAILED=0
REPORT_DIR="$PROJECT_ROOT/reports"
mkdir -p "$REPORT_DIR"

echo "============================================================"
echo -e "  ${BLUE}AgenteDeVoz - Bateria Completa de Tests${NC}"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

run_suite() {
  local name="$1"
  local path="$2"
  local extra_args="${3:-}"

  TOTAL=$((TOTAL + 1))
  echo -e "${YELLOW}[$(printf '%d/%d' $TOTAL 7)] $name...${NC}"

  if python -m pytest "$path" -v --tb=short $extra_args \
     --no-header -q 2>&1 | tail -5; then
    echo -e "  ${GREEN}[PASO]${NC} $name"
    PASSED=$((PASSED + 1))
    return 0
  else
    echo -e "  ${RED}[FALLO]${NC} $name"
    FAILED=$((FAILED + 1))
    return 1
  fi
}

# 1. Tests existentes en src/tests/
run_suite "Tests heredados (src/tests/)" "$PROJECT_ROOT/src/tests/" || true

# 2. Tests unitarios
run_suite "Tests Unitarios" "$PROJECT_ROOT/tests/unit/" || true

# 3. Tests de integracion (omitir db_required si no hay DB)
if [[ "$FAST" == "true" ]]; then
  run_suite "Tests de Integracion (sin DB)" \
    "$PROJECT_ROOT/tests/integration/" "-m 'not db_required'" || true
else
  run_suite "Tests de Integracion" "$PROJECT_ROOT/tests/integration/" || true
fi

# 4. Tests E2E
run_suite "Tests End-to-End" "$PROJECT_ROOT/tests/e2e/" || true

# 5. Tests de carga (omitir en modo rapido)
if [[ "$FAST" != "true" ]]; then
  run_suite "Tests de Carga" "$PROJECT_ROOT/tests/load/" "-m 'not slow'" || true
else
  echo -e "${YELLOW}[SKIP] Tests de carga (modo --fast)${NC}"
fi

# 6. Tests de seguridad
run_suite "Tests de Seguridad" "$PROJECT_ROOT/tests/security/" || true

# 7. Cobertura
TOTAL=$((TOTAL + 1))
echo -e "${YELLOW}[$(printf '%d/%d' $TOTAL 7)] Cobertura de codigo...${NC}"
if [[ "$COVERAGE" == "true" ]]; then
  if python -m pytest "$PROJECT_ROOT/tests/" "$PROJECT_ROOT/src/tests/" \
     --cov="$PROJECT_ROOT/src" \
     --cov-report=html:"$REPORT_DIR/coverage_report" \
     --cov-report=term-missing \
     --cov-report=xml:"$REPORT_DIR/coverage.xml" \
     -q --no-header 2>&1 | tail -10; then
    echo -e "  ${GREEN}[PASO]${NC} Cobertura generada en $REPORT_DIR/coverage_report/"
    PASSED=$((PASSED + 1))
  else
    echo -e "  ${RED}[FALLO]${NC} Error generando cobertura"
    FAILED=$((FAILED + 1))
  fi
else
  echo -e "  ${YELLOW}[SKIP]${NC} Pasar --coverage para generar reporte"
  TOTAL=$((TOTAL - 1))
fi

# Resumen
echo ""
echo "============================================================"
echo -e "  ${BLUE}RESUMEN DE TESTS${NC}"
echo "============================================================"
echo "  Suites ejecutadas: $TOTAL"
echo -e "  Pasaron:  ${GREEN}$PASSED${NC}"
echo -e "  Fallaron: ${RED}$FAILED${NC}"
echo ""

if [[ "$COVERAGE" == "true" ]] && [[ -f "$REPORT_DIR/coverage_report/index.html" ]]; then
  echo "  Reporte: $REPORT_DIR/coverage_report/index.html"
fi

if [[ $FAILED -eq 0 ]]; then
  echo -e "  ${GREEN}TODOS LOS TESTS PASARON${NC}"
  exit 0
else
  echo -e "  ${RED}$FAILED SUITE(S) FALLARON${NC}"
  exit 1
fi
