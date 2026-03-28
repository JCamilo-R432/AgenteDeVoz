#!/usr/bin/env bash
# ============================================================
# health_monitor.sh - Monitoreo continuo de salud del sistema
# AgenteDeVoz - Fase 6
# Uso: bash scripts/health_monitor.sh [--interval 60] [--alert-email email]
# Ejecutar como daemon: nohup bash scripts/health_monitor.sh &
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuracion
INTERVAL="${MONITOR_INTERVAL:-60}"        # Segundos entre checks
BASE_URL="${BASE_URL:-http://localhost:8000}"
ALERT_EMAIL="${ALERTS_EMAIL:-}"
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"
LOG_FILE="/var/log/agentevoz/health_monitor.log"
MAX_FAILURES=3                             # Alertar despues de N fallos consecutivos
ERROR_RATE_THRESHOLD=5                     # % de errores para alertar
DISK_THRESHOLD=80                          # % de disco para alertar

# Estado
FAILURE_COUNT=0
LAST_ALERT_TIME=0
ALERT_COOLDOWN=1800  # 30 minutos entre alertas repetidas

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

log() {
  local msg="$1"
  echo "$(date '+%Y-%m-%d %H:%M:%S') $msg" | tee -a "$LOG_FILE" 2>/dev/null || echo "$(date) $msg"
}

send_alert() {
  local title="$1"; local body="$2"; local severity="${3:-warning}"
  local now; now=$(date +%s)

  # Cooldown: no enviar misma alerta repetidamente
  if [[ $((now - LAST_ALERT_TIME)) -lt $ALERT_COOLDOWN ]]; then
    log "ALERT COOLDOWN: $title (ignorada, ultima alerta hace $((now - LAST_ALERT_TIME))s)"
    return
  fi
  LAST_ALERT_TIME=$now

  log "ALERT [$severity]: $title - $body"

  # Email
  if [[ -n "$ALERT_EMAIL" ]] && command -v mail &>/dev/null; then
    echo "$body" | mail -s "[AGENTEVOZ-$severity] $title" "$ALERT_EMAIL" 2>/dev/null || true
  fi

  # Slack
  if [[ -n "$SLACK_WEBHOOK" ]]; then
    local color="warning"
    [[ "$severity" == "critical" ]] && color="danger"
    [[ "$severity" == "ok" ]] && color="good"
    curl -sf -X POST "$SLACK_WEBHOOK" \
      -H "Content-Type: application/json" \
      -d "{\"attachments\": [{\"color\": \"$color\", \"title\": \"$title\", \"text\": \"$body\"}]}" \
      &>/dev/null || true
  fi
}

check_api() {
  local response http_code
  http_code=$(curl -sf -o /tmp/agentevoz_health.json \
    -w "%{http_code}" \
    --connect-timeout 5 \
    --max-time 10 \
    "$BASE_URL/api/v1/health" 2>/dev/null || echo "000")

  if [[ "$http_code" == "200" ]]; then
    local status
    status=$(python -c "import json; d=json.load(open('/tmp/agentevoz_health.json')); print(d.get('status','?'))" 2>/dev/null || echo "?")
    echo "OK:$status"
  else
    echo "FAIL:HTTP_$http_code"
  fi
}

check_disk() {
  local usage
  usage=$(df "$PROJECT_ROOT" 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%' || echo "0")
  echo "$usage"
}

check_memory() {
  # Retorna uso de memoria en %
  if command -v free &>/dev/null; then
    free | awk '/Mem:/ {printf "%.0f", ($3/$2)*100}'
  else
    echo "0"
  fi
}

check_services() {
  local failed=()
  for svc in agentevoz postgresql redis nginx; do
    if ! systemctl is-active "$svc" &>/dev/null 2>&1; then
      failed+=("$svc")
    fi
  done
  echo "${failed[*]:-}"
}

log "============================================================"
log "AgenteDeVoz - Health Monitor iniciado"
log "Intervalo: ${INTERVAL}s | URL: $BASE_URL"
log "============================================================"

while true; do
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
  STATUS_LINE=""
  ISSUES=()

  # 1. Check API
  API_STATUS=$(check_api)
  if [[ "$API_STATUS" == OK:* ]]; then
    STATUS_LINE="API:OK"
    if [[ $FAILURE_COUNT -gt 0 ]]; then
      log "RECOVERED: API recuperada despues de $FAILURE_COUNT fallos"
      send_alert "AgenteDeVoz Recuperado" "El servicio esta respondiendo normalmente." "ok"
      FAILURE_COUNT=0
    fi
  else
    FAILURE_COUNT=$((FAILURE_COUNT + 1))
    STATUS_LINE="API:FAIL(${FAILURE_COUNT})"
    ISSUES+=("API no responde: $API_STATUS")
    log "FALLO #$FAILURE_COUNT: $API_STATUS"

    if [[ $FAILURE_COUNT -ge $MAX_FAILURES ]]; then
      send_alert \
        "AgenteDeVoz CAIDO" \
        "El servicio no ha respondido en $FAILURE_COUNT checks consecutivos. URL: $BASE_URL" \
        "critical"
    fi
  fi

  # 2. Check disco
  DISK_PCT=$(check_disk)
  if [[ "${DISK_PCT:-0}" -ge $DISK_THRESHOLD ]]; then
    ISSUES+=("Disco al ${DISK_PCT}%")
    if [[ "${DISK_PCT:-0}" -ge 90 ]]; then
      send_alert "Disco Critico" "Uso de disco: ${DISK_PCT}% - Limpiar logs urgente." "critical"
    else
      send_alert "Disco Alto" "Uso de disco: ${DISK_PCT}% - Revisar pronto." "warning"
    fi
  fi
  STATUS_LINE="$STATUS_LINE | DISK:${DISK_PCT:-?}%"

  # 3. Check memoria
  MEM_PCT=$(check_memory)
  if [[ "${MEM_PCT:-0}" -ge 85 ]]; then
    ISSUES+=("Memoria al ${MEM_PCT}%")
    send_alert "Memoria Alta" "Uso de memoria: ${MEM_PCT}%." "warning"
  fi
  STATUS_LINE="$STATUS_LINE | MEM:${MEM_PCT:-?}%"

  # 4. Check servicios del sistema (si aplica)
  FAILED_SVCS=$(check_services 2>/dev/null || echo "")
  if [[ -n "$FAILED_SVCS" ]]; then
    ISSUES+=("Servicios inactivos: $FAILED_SVCS")
    send_alert "Servicios Caidos" "Servicios no activos: $FAILED_SVCS" "critical"
  fi

  # Log de estado
  if [[ ${#ISSUES[@]} -eq 0 ]]; then
    log "OK | $STATUS_LINE"
  else
    log "ISSUES (${#ISSUES[@]}) | $STATUS_LINE | Problemas: ${ISSUES[*]}"
  fi

  sleep "$INTERVAL"
done
