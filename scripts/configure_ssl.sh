#!/usr/bin/env bash
# configure_ssl.sh — Obtain and configure Let's Encrypt SSL certificate
set -euo pipefail

log() { echo "[SSL] $(date '+%H:%M:%S') $*"; }
die() { log "ERROR: $*"; exit 1; }

DOMAIN="${DOMAIN:-}"
SSL_EMAIL="${SSL_EMAIL:-}"
SSL_STAGING="${SSL_STAGING:-false}"

[[ -z "$DOMAIN" ]]    && die "DOMAIN env var not set"
[[ -z "$SSL_EMAIL" ]] && die "SSL_EMAIL env var not set"

log "Configuring SSL for domain: $DOMAIN"
log "Contact email: $SSL_EMAIL"
log "Staging mode: $SSL_STAGING"

# ── Check certbot ─────────────────────────────────────────────────────────────
if ! command -v certbot &>/dev/null; then
  log "Installing certbot..."
  apt-get update -qq
  apt-get install -y -qq certbot python3-certbot-nginx
fi
log "Certbot version: $(certbot --version 2>&1)"

# ── Check if cert already exists ─────────────────────────────────────────────
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
if [[ -d "$CERT_DIR" ]]; then
  log "Certificate already exists at $CERT_DIR"
  log "Checking expiry..."
  DAYS=$(openssl x509 -in "${CERT_DIR}/cert.pem" -noout -enddate 2>/dev/null | \
    awk -F= '{print $2}' | \
    python3 -c "import sys,datetime; d=datetime.datetime.strptime(input().strip(),'%b %d %H:%M:%S %Y %Z'); print((d-datetime.datetime.now()).days)")
  log "Certificate expires in $DAYS days"
  if (( DAYS > 30 )); then
    log "Certificate valid — no action needed"
    exit 0
  fi
  log "Certificate needs renewal (${DAYS} days remaining)"
fi

# ── Obtain / renew certificate ────────────────────────────────────────────────
CERTBOT_ARGS=(
  "--nginx"
  "-d" "${DOMAIN}"
  "-d" "www.${DOMAIN}"
  "--non-interactive"
  "--agree-tos"
  "-m" "${SSL_EMAIL}"
  "--redirect"
)

[[ "$SSL_STAGING" == "true" ]] && CERTBOT_ARGS+=("--staging") && log "WARNING: Using staging environment"

log "Running certbot..."
certbot "${CERTBOT_ARGS[@]}"
log "Certificate obtained successfully"

# ── Configure auto-renewal cron ───────────────────────────────────────────────
CRON_JOB="0 3 * * * certbot renew --quiet && systemctl reload nginx 2>&1 | logger -t certbot"
if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
  (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
  log "Auto-renewal cron configured"
else
  log "Auto-renewal cron already present"
fi

# ── Verify certificate ────────────────────────────────────────────────────────
log "Verifying certificate..."
openssl x509 -in "${CERT_DIR}/cert.pem" -noout -subject -dates
log "SSL configuration complete for $DOMAIN"

# ── Test renewal (dry-run) ────────────────────────────────────────────────────
log "Running renewal dry-run test..."
if certbot renew --dry-run 2>&1 | grep -q "No renewals were attempted\|Congratulations"; then
  log "Dry-run renewal: OK"
else
  log "WARNING: Dry-run renewal had issues — check certbot logs"
fi
