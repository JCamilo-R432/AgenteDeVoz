#!/usr/bin/env bash
# ============================================================
# run_coverage.sh - Genera reporte de cobertura de codigo
# Agente de Voz - Fase 5
# Uso: bash scripts/run_coverage.sh [--min 70]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="$PROJECT_ROOT/reports"
MIN_COVERAGE=70

while [[ $# -gt 0 ]]; do
  case $1 in
    --min) MIN_COVERAGE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

export PYTHONPATH="$PROJECT_ROOT/src"
export APP_ENV="test"
export LOG_LEVEL="WARNING"

mkdir -p "$REPORT_DIR/coverage_report"

echo "============================================================"
echo "  AgenteDeVoz - Reporte de Cobertura (min: ${MIN_COVERAGE}%)"
echo "============================================================"

python -m pytest \
  "$PROJECT_ROOT/tests/" \
  "$PROJECT_ROOT/src/tests/" \
  --cov="$PROJECT_ROOT/src" \
  --cov-report=html:"$REPORT_DIR/coverage_report" \
  --cov-report=term-missing \
  --cov-report=xml:"$REPORT_DIR/coverage.xml" \
  --cov-fail-under="$MIN_COVERAGE" \
  -q --no-header \
  --ignore="$PROJECT_ROOT/src/tests/test_api.py" \
  2>&1 || {
    echo ""
    echo "[WARN] Cobertura por debajo del minimo (${MIN_COVERAGE}%) o tests fallaron."
    echo "       Ver detalles arriba."
  }

echo ""
echo "============================================================"
echo "  Reporte HTML: $REPORT_DIR/coverage_report/index.html"
echo "  Reporte XML:  $REPORT_DIR/coverage.xml"
echo "============================================================"

# Intentar abrir en Windows
if command -v start &>/dev/null 2>&1; then
  echo "  Abriendo en navegador..."
  start "$REPORT_DIR/coverage_report/index.html" || true
fi
