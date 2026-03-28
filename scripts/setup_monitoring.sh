#!/usr/bin/env bash
# =============================================================================
# AgenteDeVoz — Setup de Monitoreo
# =============================================================================
# Configura:
#   1. Variables de entorno para alertas
#   2. Cron de health-check local cada 5 minutos
#   3. Instrucciones para UptimeRobot
#
# Uso:
#   chmod +x scripts/setup_monitoring.sh
#   sudo ./scripts/setup_monitoring.sh
# =============================================================================

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/AgenteDeVoz}"
LOG_DIR="${LOG_DIR:-/var/log/agentevoz}"
API_BASE="${API_BASE:-http://localhost:8000}"
ALERT_EMAIL="${ALERT_EMAIL:-}"        # e.g. admin@tuempresa.com
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"    # e.g. https://hooks.slack.com/...

# ── Colores ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Verificaciones ────────────────────────────────────────────────────────────
[[ -d "$APP_DIR" ]] || error "APP_DIR no encontrado: $APP_DIR"
command -v curl >/dev/null || error "curl no instalado"

# ── Directorio de logs ────────────────────────────────────────────────────────
info "Creando directorio de logs: $LOG_DIR"
mkdir -p "$LOG_DIR"
chmod 755 "$LOG_DIR"

# ── Script de health-check local ──────────────────────────────────────────────
HEALTHCHECK_SCRIPT="$APP_DIR/scripts/healthcheck_cron.sh"

info "Creando script de health-check: $HEALTHCHECK_SCRIPT"
cat > "$HEALTHCHECK_SCRIPT" <<HCSCRIPT
#!/usr/bin/env bash
# Cron health-check — ejecuta cada 5 minutos
API_BASE="${API_BASE}"
LOG_FILE="${LOG_DIR}/healthcheck.log"
ALERT_EMAIL="${ALERT_EMAIL}"
MAX_LOG_LINES=10000

rotate_log() {
    local lines
    lines=\$(wc -l < "\$LOG_FILE" 2>/dev/null || echo 0)
    if [[ \$lines -gt \$MAX_LOG_LINES ]]; then
        tail -n 5000 "\$LOG_FILE" > "\${LOG_FILE}.tmp" && mv "\${LOG_FILE}.tmp" "\$LOG_FILE"
    fi
}

check_health() {
    local ts
    ts=\$(date '+%Y-%m-%dT%H:%M:%SZ')
    local response
    response=\$(curl -sf --max-time 10 "\$API_BASE/api/v1/monitoring/health" 2>&1)
    local exit_code=\$?

    if [[ \$exit_code -ne 0 ]]; then
        echo "\$ts CRITICAL: health check failed (curl exit=\$exit_code)" >> "\$LOG_FILE"
        if [[ -n "\$ALERT_EMAIL" ]]; then
            echo "AgenteDeVoz health check FAILED at \$ts. curl exit=\$exit_code" \\
                | mail -s "CRITICAL: AgenteDeVoz DOWN" "\$ALERT_EMAIL" 2>/dev/null || true
        fi
        return 1
    fi

    local status
    status=\$(echo "\$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "parse_error")

    echo "\$ts OK: status=\$status" >> "\$LOG_FILE"
    rotate_log
}

check_health
HCSCRIPT

chmod +x "$HEALTHCHECK_SCRIPT"
info "Health-check script creado."

# ── Cron job (cada 5 minutos) ─────────────────────────────────────────────────
CRON_LINE="*/5 * * * * $HEALTHCHECK_SCRIPT >> $LOG_DIR/healthcheck_cron.log 2>&1"

if crontab -l 2>/dev/null | grep -q "healthcheck_cron"; then
    warn "Cron de health-check ya existe — omitiendo."
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    info "Cron de health-check agregado: cada 5 minutos."
fi

# ── Variables de entorno de alertas ───────────────────────────────────────────
ENV_FILE="$APP_DIR/.env"

add_env_if_missing() {
    local key="$1" val="$2"
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        warn "$key ya está en .env — omitiendo."
    else
        echo "${key}=${val}" >> "$ENV_FILE"
        info "Agregado a .env: $key"
    fi
}

if [[ -f "$ENV_FILE" ]]; then
    [[ -n "$ALERT_EMAIL" ]] && add_env_if_missing "ALERT_EMAIL_TO" "$ALERT_EMAIL"
    [[ -n "$SLACK_WEBHOOK" ]] && add_env_if_missing "ALERT_SLACK_WEBHOOK" "$SLACK_WEBHOOK"
    add_env_if_missing "JSON_LOGS" "true"
    add_env_if_missing "LOG_LEVEL" "INFO"
    add_env_if_missing "APP_ENV" "production"
    info "Variables de entorno de alertas actualizadas."
else
    warn ".env no encontrado en $APP_DIR — crea las siguientes variables manualmente:"
    echo "  ALERT_EMAIL_TO=$ALERT_EMAIL"
    echo "  ALERT_SLACK_WEBHOOK=$SLACK_WEBHOOK"
    echo "  JSON_LOGS=true"
    echo "  LOG_LEVEL=INFO"
    echo "  APP_ENV=production"
fi

# ── Test del health endpoint ───────────────────────────────────────────────────
info "Probando health endpoint..."
if curl -sf --max-time 5 "$API_BASE/api/v1/monitoring/health" > /dev/null 2>&1; then
    info "Health endpoint responde correctamente."
else
    warn "Health endpoint no responde en $API_BASE — verifica que el servidor esté corriendo."
fi

# ── Instrucciones UptimeRobot ─────────────────────────────────────────────────
echo ""
echo "========================================================"
echo "  CONFIGURACIÓN UPTIMEROBOT"
echo "========================================================"
echo "  1. Ir a https://uptimerobot.com (plan gratuito disponible)"
echo "  2. Add New Monitor:"
echo "     Type: HTTP(s)"
echo "     Friendly Name: AgenteDeVoz API"
echo "     URL: https://tu-dominio.com/api/v1/monitoring/health"
echo "     Monitoring Interval: 5 minutes"
echo "     Alert Contacts: tu email"
echo ""
echo "  3. Add New Monitor (full health):"
echo "     URL: https://tu-dominio.com/api/v1/monitoring/health/full"
echo "     Keyword: \"healthy\""
echo "     Keyword Type: keyword exists"
echo ""
echo "  4. Opcional — Prometheus/Grafana:"
echo "     Metrics endpoint: https://tu-dominio.com/api/v1/monitoring/metrics"
echo "========================================================"
echo ""

info "Setup de monitoreo completado."
info "Logs en: $LOG_DIR"
info "Script cron: $HEALTHCHECK_SCRIPT"
