#!/bin/bash
# Security Audit Script - AgenteDeVoz
# Gap #8: Penetration Testing
# Ejecuta auditoria de seguridad completa

set -euo pipefail

REPORT_DIR="reports/security"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORT_DIR/audit_${TIMESTAMP}.json"

echo "=== AgenteDeVoz: Security Audit ==="
mkdir -p "$REPORT_DIR"

# 1. Analisis estatico con bandit
echo "[1/5] Analisis estatico (bandit)..."
if command -v bandit &>/dev/null; then
    bandit -r src/ -f json -o "$REPORT_DIR/bandit_${TIMESTAMP}.json" || true
    echo "  Reporte: $REPORT_DIR/bandit_${TIMESTAMP}.json"
else
    echo "  SKIP: bandit no instalado (pip install bandit)"
fi

# 2. Escaneo de vulnerabilidades CVE
echo "[2/5] Escaneo CVE (pip-audit)..."
if command -v pip-audit &>/dev/null; then
    pip-audit --format json -o "$REPORT_DIR/cve_${TIMESTAMP}.json" || true
    echo "  Reporte: $REPORT_DIR/cve_${TIMESTAMP}.json"
else
    echo "  SKIP: pip-audit no instalado (pip install pip-audit)"
fi

# 3. Verificar headers de seguridad
echo "[3/5] Verificando headers HTTP..."
TARGET="${TARGET_URL:-http://localhost:8000}"
if curl -s --max-time 5 "$TARGET/health" > /dev/null 2>&1; then
    curl -s -I "$TARGET/health" | grep -iE "(x-frame|x-content|strict-transport|content-security)" || true
else
    echo "  SKIP: Servicio no disponible en $TARGET"
fi

# 4. Verificar dependencias desactualizadas
echo "[4/5] Verificando dependencias..."
if command -v pip &>/dev/null; then
    pip list --outdated 2>/dev/null | head -20 || true
fi

# 5. Generar reporte Python
echo "[5/5] Generando reporte final..."
python3 -c "
from src.security.penetration_testing import PenetrationTestingFramework
from src.security.security_audit_tools import SecurityAuditTools
import json, os

ptf = PenetrationTestingFramework(target=os.environ.get('TARGET_URL', 'http://localhost:8000'))
tools = SecurityAuditTools()

report = ptf.generate_audit_report()
print(json.dumps(report, indent=2, default=str))
" > "$REPORT_FILE" 2>/dev/null || echo "  SKIP: Modulos no disponibles"

echo ""
echo "=== Auditoria completada ==="
echo "Reportes en: $REPORT_DIR/"
