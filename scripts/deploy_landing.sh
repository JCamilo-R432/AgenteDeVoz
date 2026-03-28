#!/usr/bin/env bash
# deploy_landing.sh — Deploy AgenteDeVoz landing page to a VPS with nginx
# Usage: bash scripts/deploy_landing.sh [--domain agentevoz.com] [--app-dir /var/www/agentevoz]
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────
DOMAIN="${DOMAIN:-agentevoz.com}"
APP_DIR="${APP_DIR:-/var/www/agentevoz}"
APP_USER="${APP_USER:-agentevoz}"
FASTAPI_PORT="${FASTAPI_PORT:-8000}"
NGINX_CONF="/etc/nginx/sites-available/agentevoz"
CERT_EMAIL="${CERT_EMAIL:-admin@${DOMAIN}}"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

# ── Parse args ────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --domain)   DOMAIN="$2";  shift 2 ;;
    --app-dir)  APP_DIR="$2"; shift 2 ;;
    --port)     FASTAPI_PORT="$2"; shift 2 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

# ── Pre-flight ────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root (sudo bash scripts/deploy_landing.sh)"
command -v nginx  >/dev/null || die "nginx not installed (apt install nginx)"
command -v python3 >/dev/null || die "python3 not found"

log "Deploying AgenteDeVoz landing to ${DOMAIN} → ${APP_DIR}"

# ── Create app user / dir ─────────────────────────────────────────
if ! id "${APP_USER}" &>/dev/null; then
  useradd --system --no-create-home --shell /bin/false "${APP_USER}"
  log "Created system user: ${APP_USER}"
fi

mkdir -p "${APP_DIR}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# ── Sync files ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
log "Syncing files from ${SCRIPT_DIR} → ${APP_DIR}"

rsync -a --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='node_modules' \
  "${SCRIPT_DIR}/" "${APP_DIR}/"

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# ── Python virtual env ────────────────────────────────────────────
VENV="${APP_DIR}/.venv"
if [[ ! -d "${VENV}" ]]; then
  log "Creating Python venv at ${VENV}"
  python3 -m venv "${VENV}"
fi

"${VENV}/bin/pip" install --quiet --upgrade pip
if [[ -f "${APP_DIR}/requirements.txt" ]]; then
  "${VENV}/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"
fi

# ── nginx configuration ───────────────────────────────────────────
log "Writing nginx config → ${NGINX_CONF}"

cat > "${NGINX_CONF}" <<NGINX
# AgenteDeVoz nginx config — generated $(date)
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options    "nosniff"  always;
    add_header X-Frame-Options           "SAMEORIGIN" always;
    add_header Referrer-Policy           "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy        "microphone=(self)" always;

    # Static assets — served by nginx directly (fast + cache)
    location /css/ {
        root  ${APP_DIR}/public;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    location /js/ {
        root  ${APP_DIR}/public;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    location /images/ {
        root  ${APP_DIR}/public;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    location /favicon.ico {
        root  ${APP_DIR}/public;
        log_not_found off;
    }

    # WebSocket (voice streaming)
    location /api/v1/voice/ws/ {
        proxy_pass         http://127.0.0.1:${FASTAPI_PORT};
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host       \$host;
        proxy_read_timeout 300s;
    }

    # Everything else → FastAPI
    location / {
        proxy_pass         http://127.0.0.1:${FASTAPI_PORT};
        proxy_set_header   Host             \$host;
        proxy_set_header   X-Real-IP        \$remote_addr;
        proxy_set_header   X-Forwarded-For  \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_read_timeout 60s;
        proxy_buffering    off;
    }
}
NGINX

# Enable site
ln -sf "${NGINX_CONF}" "/etc/nginx/sites-enabled/agentevoz"
nginx -t || die "nginx config test failed"

# ── systemd service ───────────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/agentevoz-web.service"
log "Writing systemd service → ${SERVICE_FILE}"

cat > "${SERVICE_FILE}" <<SYSTEMD
[Unit]
Description=AgenteDeVoz Web (FastAPI + Landing)
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment="PYTHONPATH=${APP_DIR}/src"
EnvironmentFile=-${APP_DIR}/config/production.env
ExecStart=${VENV}/bin/uvicorn src.server:app --host 127.0.0.1 --port ${FASTAPI_PORT} --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=agentevoz-web

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
systemctl enable  agentevoz-web
systemctl restart agentevoz-web
systemctl reload  nginx

log "Service status:"
systemctl status agentevoz-web --no-pager -l || true

# ── SSL certificate (Let's Encrypt) ───────────────────────────────
if command -v certbot >/dev/null; then
  if [[ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
    log "Requesting Let's Encrypt certificate for ${DOMAIN}"
    certbot --nginx -d "${DOMAIN}" -d "www.${DOMAIN}" \
      --email "${CERT_EMAIL}" --agree-tos --non-interactive || \
      log "certbot failed — check DNS and try: certbot --nginx -d ${DOMAIN}"
  else
    log "SSL certificate already exists for ${DOMAIN}"
  fi
else
  log "certbot not found — install with: apt install certbot python3-certbot-nginx"
fi

log "──────────────────────────────────────────"
log "Deploy complete!"
log "  Landing : https://${DOMAIN}/"
log "  Agent   : https://${DOMAIN}/agent"
log "  Logs    : journalctl -u agentevoz-web -f"
log "──────────────────────────────────────────"
