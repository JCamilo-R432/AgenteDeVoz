#!/usr/bin/env bash
# run_contract_tests.sh - Ejecuta pruebas de contrato de integraciones

set -euo pipefail

REPORT_DIR="${REPORT_DIR:-reports/contracts}"
FAIL_FAST="${FAIL_FAST:-false}"

echo "=== Contract Tests - AgenteDeVoz ==="
mkdir -p "$REPORT_DIR"

echo "[1/3] Ejecutando pruebas de contrato (pytest)..."
PYTEST_ARGS=(
    "tests/test_contract_tests.py"
    "-v"
    "--tb=short"
    "--junit-xml=${REPORT_DIR}/contract_results.xml"
)

if [[ "$FAIL_FAST" == "true" ]]; then
    PYTEST_ARGS+=("-x")
fi

python -m pytest "${PYTEST_ARGS[@]}"
EXIT_CODE=$?

echo "[2/3] Generando reporte de contratos..."
python3 - <<'PYEOF'
import json, sys, os
from src.api.contract_tests import ContractTests

ct = ContractTests()
all_results = ct.run_all()
summary = ct.get_summary()

report = {
    "summary": summary,
    "suites": {}
}
for suite, results in all_results.items():
    report["suites"][suite] = [
        {
            "interaction": r.interaction,
            "passed": r.passed,
            "duration_ms": round(r.duration_ms, 2),
            "request_errors": r.request_errors,
            "response_errors": r.response_errors,
        }
        for r in results
    ]

report_path = os.path.join(os.environ.get("REPORT_DIR", "reports/contracts"), "contract_report.json")
os.makedirs(os.path.dirname(report_path), exist_ok=True)
with open(report_path, "w") as f:
    json.dump(report, f, indent=2)

print(f"Reporte generado: {report_path}")
print(f"Total: {summary['total_interactions']} | Pasaron: {summary['passed']} | Fallaron: {summary['failed']}")
print(f"Tasa de exito: {summary['pass_rate_percent']}%")

if summary["failed"] > 0:
    sys.exit(1)
PYEOF
REPORT_EXIT=$?

echo "[3/3] Resultados finales..."
if [[ $EXIT_CODE -eq 0 && $REPORT_EXIT -eq 0 ]]; then
    echo "TODOS LOS CONTRATOS PASARON"
    echo "Reporte: ${REPORT_DIR}/contract_report.json"
    exit 0
else
    echo "CONTRATOS FALLIDOS - Revisar ${REPORT_DIR}/contract_report.json"
    exit 1
fi
