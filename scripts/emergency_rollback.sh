#!/usr/bin/env bash
# ============================================================
# emergency_rollback.sh - Rollback de emergencia
# AgenteDeVoz - Fase 6
# Uso: bash scripts/emergency_rollback.sh [--level 1|2] [--dry-run]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
LOG_FILE="/var/log/agentevoz/rollback_$(date +%Y%m%d_%H%M%S).log"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

LEVEL=1
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --level) LEVEL="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) shift ;;
  esac
done

log() {
  echo -e "$1"
  echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE" 2>/dev/null || true
}

run_cmd() {
  local cmd="$1"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "  ${YELLOW}[DRY-RUN]${NC} $cmd"
  else
    log "  ${BLUE}[EXEC]${NC} $cmd"
    eval "$cmd"
  fi
}

echo "============================================================"
log "${RED}AgenteDeVoz - ROLLBACK DE EMERGENCIA${NC}"
log "Nivel: $LEVEL | Modo: $([ "$DRY_RUN" == "true" ] && echo "DRY-RUN" || echo "REAL")"
log "Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

if [[ "$DRY_RUN" == "false" ]]; then
  echo -e "${RED}ATENCION: Esto ejecutara un rollback real en produccion.${NC}"
  echo -e "${YELLOW}Nivel $LEVEL seleccionado.${NC}"
  echo ""
  read -r -p "Confirmar rollback Nivel $LEVEL? (escribir 'ROLLBACK' para confirmar): " CONFIRM
  if [[ "$CONFIRM" != "ROLLBACK" ]]; then
    echo "Rollback cancelado."
    exit 0
  fi
fi

# ============================================================
# NIVEL 1: Rollback de Aplicacion
# ============================================================
if [[ $LEVEL -ge 1 ]]; then
  log ""
  log "${YELLOW}=== NIVEL 1: Rollback de Aplicacion ===${NC}"

  # Verificar que hay una version anterior
  cd "$PROJECT_ROOT"
  CURRENT_TAG=$(git describe --tags --exact-match HEAD 2>/dev/null || git rev-parse --short HEAD)
  PREV_TAG=$(git tag --sort=-version:refname | grep -v "$CURRENT_TAG" | head -1)

  log "Version actual: $CURRENT_TAG"
  log "Version anterior disponible: ${PREV_TAG:-ninguna}"

  if [[ -z "${PREV_TAG:-}" ]]; then
    log "${RED}ERROR: No hay version anterior disponible para rollback${NC}"
    log "Verifique los tags de git: git tag --sort=-version:refname"
    exit 1
  fi

  # Detener servicio
  log "Deteniendo servicio agentevoz..."
  run_cmd "sudo systemctl stop agentevoz 2>/dev/null || true"
  sleep 2

  # Restaurar version anterior
  log "Restaurando version $PREV_TAG..."
  run_cmd "git checkout $PREV_TAG"

  # Reinstalar dependencias si hay cambios en requirements.txt
  log "Actualizando dependencias..."
  run_cmd "pip install -r requirements.txt -q"

  # Reiniciar servicio
  log "Reiniciando servicio..."
  run_cmd "sudo systemctl start agentevoz"
  sleep 5

  # Verificar
  log "Verificando salud del sistema..."
  if [[ "$DRY_RUN" == "false" ]]; then
    for i in 1 2 3; do
      if curl -sf "http://localhost:8000/api/v1/health" &>/dev/null; then
        log "${GREEN}Servicio respondiendo correctamente${NC}"
        break
      fi
      if [[ $i -eq 3 ]]; then
        log "${RED}CRITICO: Servicio no responde despues de rollback${NC}"
        log "Revisar logs: journalctl -u agentevoz --since '5 min ago'"
        exit 1
      fi
      log "Intento $i/3 - esperando..."
      sleep 10
    done
  fi

  log "${GREEN}Nivel 1 completado exitosamente${NC}"
fi

# ============================================================
# NIVEL 2: Rollback de Base de Datos
# ============================================================
if [[ $LEVEL -ge 2 ]]; then
  log ""
  log "${YELLOW}=== NIVEL 2: Rollback de Base de Datos ===${NC}"

  # Buscar backup mas reciente
  LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.dump 2>/dev/null | head -1 || echo "")

  if [[ -z "$LATEST_BACKUP" ]]; then
    log "${RED}ERROR: No se encontraron backups en $BACKUP_DIR${NC}"
    exit 1
  fi

  log "Backup a restaurar: $LATEST_BACKUP"
  BACKUP_DATE=$(stat -c %y "$LATEST_BACKUP" 2>/dev/null | cut -d' ' -f1 || echo "desconocida")
  log "Fecha del backup: $BACKUP_DATE"

  if [[ "$DRY_RUN" == "false" ]]; then
    echo ""
    echo -e "${RED}ADVERTENCIA: Esto reemplazara la base de datos con el backup de $BACKUP_DATE${NC}"
    echo -e "${RED}Se perderan todos los datos posteriores a esa fecha.${NC}"
    read -r -p "Confirmar restauracion de BD? (escribir 'RESTAURAR' para confirmar): " CONFIRM_DB
    if [[ "$CONFIRM_DB" != "RESTAURAR" ]]; then
      log "Restauracion de BD cancelada. El rollback de aplicacion (Nivel 1) ya fue aplicado."
      exit 0
    fi
  fi

  # Asegurar que la aplicacion esta detenida
  log "Asegurando que la aplicacion esta detenida..."
  run_cmd "sudo systemctl stop agentevoz 2>/dev/null || true"

  # Hacer backup de la BD actual (pre-rollback)
  DB_NAME="${DB_NAME:-agentevoz_production}"
  PRE_ROLLBACK_BACKUP="$BACKUP_DIR/pre_rollback_$(date +%Y%m%d_%H%M%S).dump"
  log "Haciendo backup de seguridad de BD actual: $PRE_ROLLBACK_BACKUP"
  run_cmd "pg_dump -U postgres -d $DB_NAME -F c -f '$PRE_ROLLBACK_BACKUP' 2>/dev/null || true"

  # Restaurar backup
  log "Restaurando backup de base de datos..."
  run_cmd "psql -U postgres -c 'DROP DATABASE IF EXISTS ${DB_NAME};'"
  run_cmd "psql -U postgres -c 'CREATE DATABASE ${DB_NAME};'"
  run_cmd "pg_restore -U postgres -d ${DB_NAME} --no-privileges '$LATEST_BACKUP'"

  # Reiniciar aplicacion
  log "Reiniciando aplicacion con BD restaurada..."
  run_cmd "sudo systemctl start agentevoz"
  sleep 5

  if [[ "$DRY_RUN" == "false" ]]; then
    if curl -sf "http://localhost:8000/api/v1/health" &>/dev/null; then
      log "${GREEN}Nivel 2 completado exitosamente${NC}"
    else
      log "${RED}CRITICO: Servicio no responde despues de rollback nivel 2${NC}"
      exit 1
    fi
  fi
fi

# ============================================================
# Resumen
# ============================================================
echo ""
echo "============================================================"
log "${BLUE}RESUMEN DEL ROLLBACK${NC}"
echo "============================================================"
log "Nivel ejecutado: $LEVEL"
log "Modo: $([ "$DRY_RUN" == "true" ] && echo "DRY-RUN (sin cambios reales)" || echo "REAL")"
log "Hora de fin: $(date '+%Y-%m-%d %H:%M:%S')"
log "Log completo: $LOG_FILE"
echo ""
if [[ "$DRY_RUN" == "false" ]]; then
  echo -e "${GREEN}ROLLBACK COMPLETADO${NC}"
  echo ""
  echo "PROXIMOS PASOS:"
  echo "1. Verificar metricas en los proximos 15 minutos"
  echo "2. Notificar al equipo del rollback"
  echo "3. Abrir incidente formal"
  echo "4. Investigar causa raiz del problema original"
  echo "5. Ver: operations/runbook_incidents.md"
else
  echo -e "${YELLOW}DRY-RUN COMPLETADO - Sin cambios aplicados${NC}"
  echo "Para ejecutar rollback real: bash scripts/emergency_rollback.sh --level $LEVEL"
fi
