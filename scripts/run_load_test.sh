#!/usr/bin/env bash
# ============================================================
# run_load_test.sh - Ejecuta tests de carga y rendimiento
# Agente de Voz - Fase 5 + Gap #2 (Locust)
# Uso: bash scripts/run_load_test.sh [scenario|--light|--full]
#      bash scripts/run_load_test.sh smoke
#      bash scripts/run_load_test.sh baseline --host https://agentevoz.com
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="$PROJECT_ROOT/testing/reports"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

LIGHT=false
FULL=false
SCENARIO=""
HOST="${TEST_HOST:-http://localhost:8000}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --light)  LIGHT=true; shift ;;
    --full)   FULL=true;  shift ;;
    --host)   HOST="$2"; shift 2 ;;
    smoke|baseline|stress|spike|soak|voice_heavy|webhook_flood|pre_launch)
              SCENARIO="$1"; shift ;;
    *) shift ;;
  esac
done

# ── Locust scenario mode ──────────────────────────────────────────────────────
if [[ -n "$SCENARIO" ]]; then
  echo "Running Locust scenario: $SCENARIO (host=$HOST)"
  mkdir -p "$REPORT_DIR"

  LOCUST_ARGS=$(python3 -c "
import sys; sys.path.insert(0, '$PROJECT_ROOT')
from testing.load_testing.scenarios import get_scenario
s = get_scenario('$SCENARIO')
if not s:
    print('Unknown scenario')
    sys.exit(1)
print(' '.join(s.to_locust_args()))
" 2>&1)

  if [[ $? -ne 0 ]]; then
    echo "Error getting scenario args: $LOCUST_ARGS"
    exit 1
  fi

  # Replace default host with specified host
  eval "$LOCUST_ARGS --host $HOST"
  EXIT_CODE=$?

  if [[ $EXIT_CODE -eq 0 ]]; then
    echo "Analyzing results..."
    python3 testing/load_testing/results_analyzer.py "$SCENARIO" 2>/dev/null || true
  fi
  exit $EXIT_CODE
fi

export PYTHONPATH="$PROJECT_ROOT/src"
export APP_ENV="test"
export LOG_LEVEL="WARNING"

mkdir -p "$REPORT_DIR"

echo "============================================================"
echo -e "  ${BLUE}AgenteDeVoz - Tests de Carga${NC}"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

PASSED=0; FAILED=0

run_load_suite() {
  local name="$1"
  local args="${2:-}"
  echo -e "${YELLOW}Ejecutando: $name${NC}"

  if python -m pytest "$PROJECT_ROOT/tests/load/" \
     $args -v --tb=short --no-header -q 2>&1; then
    echo -e "  ${GREEN}[PASO]${NC} $name"
    PASSED=$((PASSED + 1))
  else
    echo -e "  ${RED}[FALLO]${NC} $name"
    FAILED=$((FAILED + 1))
  fi
  echo ""
}

if [[ "$LIGHT" == "true" ]]; then
  echo -e "${YELLOW}Modo ligero: solo tests rapidos${NC}"
  run_load_suite "Concurrencia (sin slow)" "-m 'not slow'"
elif [[ "$FULL" == "true" ]]; then
  echo -e "${YELLOW}Modo completo: todos los tests de carga${NC}"
  run_load_suite "Concurrencia completa" ""
  run_load_suite "Stress tests" ""
else
  run_load_suite "Tests de carga estandar" "-m 'not slow'"
fi

echo "============================================================"
echo -e "  ${BLUE}RESUMEN${NC}"
echo "============================================================"
echo -e "  Pasaron: ${GREEN}$PASSED${NC}"
echo -e "  Fallaron: ${RED}$FAILED${NC}"
echo ""

if [[ $FAILED -eq 0 ]]; then
  echo -e "  ${GREEN}TESTS DE CARGA: OK${NC}"
  exit 0
else
  echo -e "  ${RED}TESTS DE CARGA: $FAILED FALLARON${NC}"
  exit 1
fi
