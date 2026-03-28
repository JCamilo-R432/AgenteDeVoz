#!/usr/bin/env bash
# setup_production.sh — Full production environment setup for AgenteDeVoz
# Run as root or with sudo on a fresh Ubuntu 22.04+ server.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="/var/log/agentevoz_setup.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }

log "======================================================"
log "  AgenteDeVoz Production Setup"
log "======================================================"
log "App dir: $APP_DIR"

# ── 1. System dependencies ──────────────────────────────────────────────────
log "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  python3.11 python3.11-venv python3.11-dev \
  postgresql-client \
  nginx \
  redis-server \
  certbot python3-certbot-nginx \
  curl wget git \
  build-essential libpq-dev \
  awscli \
  jq

# ── 2. Python environment ────────────────────────────────────────────────────
log "Setting up Python virtual environment..."
cd "$APP_DIR"
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
log "Python environment ready"

# ── 3. Environment variables ─────────────────────────────────────────────────
if [[ ! -f "$APP_DIR/.env" ]]; then
  if [[ -f "$APP_DIR/config/production.env" ]]; then
    cp "$APP_DIR/config/production.env" "$APP_DIR/.env"
    log "Copied production.env to .env"
  else
    die ".env file not found. Copy config/production.env and fill in secrets."
  fi
fi
log ".env file present"

# ── 4. Directories ────────────────────────────────────────────────────────────
log "Creating required directories..."
mkdir -p "$APP_DIR"/{backups,logs,static,uploads}
mkdir -p "$APP_DIR"/config/{ssl,backup}
chmod 750 "$APP_DIR/backups" "$APP_DIR/logs"

# ── 5. Database migrations ────────────────────────────────────────────────────
log "Running database migrations..."
cd "$APP_DIR"
source .env 2>/dev/null || true
if command -v alembic &>/dev/null; then
  alembic upgrade head && log "Migrations applied" || log "WARNING: migrations failed — check DB connection"
else
  log "WARNING: alembic not found in PATH — run manually: alembic upgrade head"
fi

# ── 6. SSL Certificate ────────────────────────────────────────────────────────
DOMAIN="${DOMAIN:-}"
SSL_EMAIL="${SSL_EMAIL:-}"
if [[ -n "$DOMAIN" && -n "$SSL_EMAIL" ]]; then
  log "Configuring SSL for $DOMAIN..."
  bash "$SCRIPT_DIR/configure_ssl.sh" || log "WARNING: SSL setup had errors — check configure_ssl.sh"
else
  log "DOMAIN or SSL_EMAIL not set — skipping SSL setup"
fi

# ── 7. Nginx ──────────────────────────────────────────────────────────────────
log "Configuring nginx..."
if [[ -f "$APP_DIR/config/nginx/agentevoz.conf" ]]; then
  cp "$APP_DIR/config/nginx/agentevoz.conf" /etc/nginx/sites-available/agentevoz
  ln -sf /etc/nginx/sites-available/agentevoz /etc/nginx/sites-enabled/agentevoz
  nginx -t && systemctl reload nginx
  log "Nginx configured"
else
  log "WARNING: nginx config not found at config/nginx/agentevoz.conf"
fi

# ── 8. Systemd service ────────────────────────────────────────────────────────
log "Setting up systemd service..."
cat > /etc/systemd/system/agentevoz.service << EOF
[Unit]
Description=AgenteDeVoz Voice AI API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/uvicorn src.server:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable agentevoz
log "Systemd service configured"

# ── 9. Secrets vault ─────────────────────────────────────────────────────────
if [[ -n "${VAULT_MASTER_PASSWORD:-}" ]]; then
  log "Initializing secrets vault..."
  bash "$SCRIPT_DIR/setup_vault.sh" || log "WARNING: vault setup had errors"
fi

# ── 10. Cron jobs ─────────────────────────────────────────────────────────────
log "Setting up cron jobs..."
(crontab -l 2>/dev/null; cat << 'CRON'
# AgenteDeVoz automated tasks
0 2 * * *  /bin/bash /app/scripts/backup_production.sh >> /var/log/agentevoz_backup.log 2>&1
0 3 * * *  certbot renew --quiet && systemctl reload nginx
0 3 * * 0  python /app/config/backup/backup_schedule.py cleanup
0 4 * * 1  python /app/config/backup/backup_schedule.py test-restore
*/5 * * * * /bin/bash /app/scripts/health_check.sh || systemctl restart agentevoz
CRON
) | sort -u | crontab -
log "Cron jobs configured"

# ── Done ──────────────────────────────────────────────────────────────────────
log "======================================================"
log "  Production setup complete!"
log "======================================================"
log "Next steps:"
log "  1. Review and update .env with all required secrets"
log "  2. Start service: systemctl start agentevoz"
log "  3. Run smoke test: curl -f https://${DOMAIN:-localhost}/health"
log "  4. Validate API keys: python -m production.api_keys_manager --validate"
