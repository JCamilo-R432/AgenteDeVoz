#!/usr/bin/env bash
# ============================================================
# run_security_scan.sh - Ejecuta escaneo de seguridad
# Agente de Voz - Fase 5
# Uso: bash scripts/run_security_scan.sh [--full]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="$PROJECT_ROOT/reports"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

FULL=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --full) FULL=true; shift ;;
    *) shift ;;
  esac
done

export PYTHONPATH="$PROJECT_ROOT/src"
export APP_ENV="test"
export LOG_LEVEL="WARNING"

mkdir -p "$REPORT_DIR"

PASSED=0; FAILED=0; WARNINGS=0

echo "============================================================"
echo -e "  ${BLUE}AgenteDeVoz - Escaneo de Seguridad${NC}"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# 1. Tests de seguridad (pytest)
echo -e "${CYAN}[1/4] Tests de seguridad (pytest)...${NC}"
if python -m pytest "$PROJECT_ROOT/tests/security/" \
   -v --tb=short --no-header -q 2>&1; then
  echo -e "  ${GREEN}[OK]${NC} Tests de seguridad pasaron"
  PASSED=$((PASSED + 1))
else
  echo -e "  ${RED}[FALLO]${NC} Tests de seguridad fallaron"
  FAILED=$((FAILED + 1))
fi
echo ""

# 2. Bandit - analisis estatico de seguridad Python
echo -e "${CYAN}[2/4] Bandit (analisis estatico)...${NC}"
if command -v bandit &>/dev/null; then
  BANDIT_REPORT="$REPORT_DIR/bandit_report.txt"
  if bandit -r "$PROJECT_ROOT/src" \
     -x "$PROJECT_ROOT/src/tests" \
     --severity-level medium \
     -f txt -o "$BANDIT_REPORT" 2>&1; then
    echo -e "  ${GREEN}[OK]${NC} Sin vulnerabilidades criticas"
    PASSED=$((PASSED + 1))
  else
    ISSUES=$(grep -c "Issue:" "$BANDIT_REPORT" 2>/dev/null || echo "?")
    echo -e "  ${YELLOW}[WARN]${NC} $ISSUES issues encontrados - Ver $BANDIT_REPORT"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  echo -e "  ${YELLOW}[SKIP]${NC} Bandit no instalado (pip install bandit)"
  WARNINGS=$((WARNINGS + 1))
fi
echo ""

# 3. Safety - vulnerabilidades en dependencias
echo -e "${CYAN}[3/4] Safety (vulnerabilidades en dependencias)...${NC}"
if command -v safety &>/dev/null; then
  SAFETY_REPORT="$REPORT_DIR/safety_report.txt"
  if safety check \
     --output text 2>&1 | tee "$SAFETY_REPORT" | tail -5; then
    echo -e "  ${GREEN}[OK]${NC} Sin vulnerabilidades conocidas en dependencias"
    PASSED=$((PASSED + 1))
  else
    echo -e "  ${YELLOW}[WARN]${NC} Vulnerabilidades encontradas - Ver $SAFETY_REPORT"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  echo -e "  ${YELLOW}[SKIP]${NC} Safety no instalado (pip install safety)"
  WARNINGS=$((WARNINGS + 1))
fi
echo ""

# 4. Verificacion de secretos en codigo
echo -e "${CYAN}[4/4] Busqueda de secretos hardcodeados...${NC}"
SECRETS_FOUND=0

# Patrones de secretos comunes
PATTERNS=(
  "sk-[a-zA-Z0-9]{48}"
  "sk-ant-[a-zA-Z0-9]"
  "AKIA[A-Z0-9]{16}"
  "password\s*=\s*['\"][^'\"]{8,}"
  "secret_key\s*=\s*['\"][^'\"]{8,}"
)

for pattern in "${PATTERNS[@]}"; do
  if grep -rn --include="*.py" -E "$pattern" "$PROJECT_ROOT/src" \
     --exclude-dir="__pycache__" 2>/dev/null | \
     grep -v "test\|example\|placeholder\|CAMBIAR" | head -5; then
    SECRETS_FOUND=$((SECRETS_FOUND + 1))
  fi
done

if [[ $SECRETS_FOUND -eq 0 ]]; then
  echo -e "  ${GREEN}[OK]${NC} Sin secretos hardcodeados detectados"
  PASSED=$((PASSED + 1))
else
  echo -e "  ${RED}[FALLO]${NC} Posibles secretos encontrados ($SECRETS_FOUND patrones)"
  FAILED=$((FAILED + 1))
fi
echo ""

# Resumen
echo "============================================================"
echo -e "  ${BLUE}RESUMEN DE SEGURIDAD${NC}"
echo "============================================================"
echo -e "  Pasaron:   ${GREEN}$PASSED${NC}"
echo -e "  Warnings:  ${YELLOW}$WARNINGS${NC}"
echo -e "  Fallaron:  ${RED}$FAILED${NC}"
echo ""
echo "  Reportes en: $REPORT_DIR/"
echo ""

if [[ $FAILED -eq 0 ]]; then
  if [[ $WARNINGS -gt 0 ]]; then
    echo -e "  ${YELLOW}SEGURIDAD: OK con $WARNINGS advertencias${NC}"
  else
    echo -e "  ${GREEN}SEGURIDAD: APROBADO${NC}"
  fi
  exit 0
else
  echo -e "  ${RED}SEGURIDAD: $FAILED CHECKS FALLARON${NC}"
  exit 1
fi
