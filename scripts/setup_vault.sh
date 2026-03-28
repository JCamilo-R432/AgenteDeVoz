#!/usr/bin/env bash
# setup_vault.sh — Initialize and populate the AgenteDeVoz secrets vault
set -euo pipefail

log() { echo "[VAULT] $(date '+%H:%M:%S') $*"; }
die() { log "ERROR: $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
VAULT_PATH="${VAULT_PATH:-${APP_DIR}/production/secrets.vault}"

[[ -z "${VAULT_MASTER_PASSWORD:-}" ]] && die "VAULT_MASTER_PASSWORD not set"

log "Initializing secrets vault at: $VAULT_PATH"

# ── Ensure vault directory exists ─────────────────────────────────────────────
mkdir -p "$(dirname "$VAULT_PATH")"

# ── Import secrets from environment ───────────────────────────────────────────
log "Importing secrets from environment variables..."

cd "$APP_DIR"
source .env 2>/dev/null || true

KEYS_TO_IMPORT=(
  "OPENAI_API_KEY"
  "ANTHROPIC_API_KEY"
  "GOOGLE_CLOUD_KEY"
  "TWILIO_ACCOUNT_SID"
  "TWILIO_AUTH_TOKEN"
  "SENDGRID_API_KEY"
  "STRIPE_SECRET_KEY"
  "STRIPE_PUBLISHABLE_KEY"
  "STRIPE_WEBHOOK_SECRET"
  "MERCADOPAGO_ACCESS_TOKEN"
  "PAYPAL_CLIENT_ID"
  "PAYPAL_CLIENT_SECRET"
  "DB_PASSWORD"
  "SECRET_KEY"
  "JWT_SECRET"
  "WHATSAPP_ACCESS_TOKEN"
)

python3 - << PYEOF
import sys
sys.path.insert(0, '${APP_DIR}')
from production.secrets_vault import SecretsVault

vault = SecretsVault(
    master_password='${VAULT_MASTER_PASSWORD}',
    vault_path='${VAULT_PATH}'
)

keys = $(printf '"%s",' "${KEYS_TO_IMPORT[@]}" | sed 's/,$//' | python3 -c "import sys; print('[' + sys.stdin.read() + ']')")
imported = vault.import_from_env(keys)
print(f"[VAULT] Imported {imported}/{len(keys)} secrets")
status = vault.status()
print(f"[VAULT] Status: {status}")
PYEOF

# ── Verify vault ──────────────────────────────────────────────────────────────
log "Verifying vault integrity..."
python3 - << PYEOF
import sys
sys.path.insert(0, '${APP_DIR}')
from production.secrets_vault import SecretsVault

vault = SecretsVault(
    master_password='${VAULT_MASTER_PASSWORD}',
    vault_path='${VAULT_PATH}'
)

if vault.is_production_ready():
    print("[VAULT] Vault is production-ready ✅")
    sys.exit(0)
else:
    print("[VAULT] Vault NOT production-ready ❌")
    sys.exit(1)
PYEOF

# ── Set file permissions ──────────────────────────────────────────────────────
chmod 600 "$VAULT_PATH"
log "Vault permissions set to 0600"
log "Vault setup complete"
log ""
log "Vault contents (keys only):"
python3 -c "
import sys; sys.path.insert(0, '${APP_DIR}')
from production.secrets_vault import SecretsVault
v = SecretsVault(master_password='${VAULT_MASTER_PASSWORD}', vault_path='${VAULT_PATH}')
for s in v.list_secrets():
    print(f\"  {s['key']:40s} v{s['version']} updated={s['updated_at']}\")
"
