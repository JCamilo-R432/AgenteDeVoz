#!/usr/bin/env bash
# =============================================================================
# run_chaos_tests.sh - Ejecutar suite de tests de caos en AgenteDeVoz
# =============================================================================
# USO:
#   bash scripts/run_chaos_tests.sh [--scenario NOMBRE] [--all] [--report]
#
# OPCIONES:
#   --scenario NOMBRE  Ejecutar escenario especifico
#   --all              Ejecutar todos los escenarios
#   --report           Generar reporte en archivo
#   --dry-run          Mostrar que se ejecutaria sin ejecutar
#
# ADVERTENCIA: Solo ejecutar en entorno de STAGING.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${PROJECT_DIR}/reports/chaos_${TIMESTAMP}.log"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Valores por defecto
SCENARIO=""
RUN_ALL=false
GENERATE_REPORT=false
DRY_RUN=false

# Parsear argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        --scenario) SCENARIO="$2"; shift 2 ;;
        --all) RUN_ALL=true; shift ;;
        --report) GENERATE_REPORT=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Argumento desconocido: $1"; exit 1 ;;
    esac
done

log() { echo -e "[$(date +'%H:%M:%S')] $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}  CHAOS ENGINEERING TESTS - AgenteDeVoz${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# Verificacion de entorno
check_environment() {
    log "Verificando entorno..."

    # Solo permitir en staging
    if [[ "${APP_ENV:-}" == "production" ]]; then
        log_error "PROHIBIDO ejecutar chaos tests en PRODUCCION"
        log_error "Configurar APP_ENV=staging"
        exit 1
    fi

    log_ok "Entorno: ${APP_ENV:-staging}"

    # Verificar que Python y dependencias esten disponibles
    if ! command -v python3 &>/dev/null; then
        log_error "Python3 no encontrado"
        exit 1
    fi
    log_ok "Python: $(python3 --version)"
}

run_chaos_test() {
    local scenario="$1"
    log "Ejecutando escenario: ${scenario}"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "[DRY-RUN] Se ejecutaria: python3 -m pytest tests/test_chaos.py -k '${scenario}' -v"
        return 0
    fi

    python3 -m pytest tests/test_chaos.py -v --no-header 2>&1
}

run_all_scenarios() {
    log "Ejecutando TODOS los escenarios de caos..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "[DRY-RUN] Se ejecutaria suite completa de chaos tests"
        return 0
    fi

    # Ejecutar tests de chaos
    python3 -m pytest tests/test_chaos.py -v --no-header 2>&1

    # Ejecutar test de resiliencia completo
    python3 -c "
from src.chaos.resilience_tests import ResilienceTests
import json

tester = ResilienceTests()
report = tester.run_all()
print(json.dumps(report, indent=2))
" 2>&1
}

generate_report() {
    local report_file="${PROJECT_DIR}/reports/chaos_report_${TIMESTAMP}.json"
    mkdir -p "${PROJECT_DIR}/reports"

    log "Generando reporte en: ${report_file}"
    python3 -c "
import json
from src.chaos.resilience_tests import ResilienceTests

tester = ResilienceTests()
report = tester.run_all()
with open('${report_file}', 'w') as f:
    json.dump(report, f, indent=2)
print(f'Reporte guardado: ${report_file}')
print(f'Score de resiliencia: {report[\"overall_score\"]}/100')
print(f'Estado: {report[\"overall_status\"]}')
" 2>&1
}

# Ejecucion principal
check_environment

if [[ -n "$SCENARIO" ]]; then
    run_chaos_test "$SCENARIO"
elif [[ "$RUN_ALL" == "true" ]]; then
    run_all_scenarios
    if [[ "$GENERATE_REPORT" == "true" ]]; then
        generate_report
    fi
else
    echo "USO: bash scripts/run_chaos_tests.sh [--scenario NOMBRE | --all] [--report]"
    echo ""
    echo "Escenarios disponibles:"
    echo "  database_latency   - Latencia en PostgreSQL"
    echo "  redis_unavailable  - Redis caido (verifica fallback)"
    echo "  twilio_timeout     - Timeout en API de Twilio"
    echo "  google_stt         - Fallos en Google STT"
    echo "  llm_api_degraded   - LLM lento (verifica keywords fallback)"
    echo ""
    echo "Ejemplos:"
    echo "  bash scripts/run_chaos_tests.sh --all"
    echo "  bash scripts/run_chaos_tests.sh --scenario redis_unavailable"
    echo "  bash scripts/run_chaos_tests.sh --all --report"
    exit 1
fi

echo ""
log_ok "Chaos tests completados."
