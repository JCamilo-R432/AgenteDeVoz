# Secrets Management — AgenteDeVoz

## Overview

AgenteDeVoz uses a layered secrets management approach:

1. **Local encrypted vault** (`production/secrets_vault.py`) — AES-256 encrypted JSON file
2. **Environment variables** — fallback for CI/CD and containerized deployments
3. **HashiCorp Vault** — optional for enterprise deployments (configured via `config/production/vault_config.json`)

---

## Architecture

```
Application code
      │
      ▼
SecretsVault.get_secret("KEY")
      │
      ├─── Encrypted vault file ──── AES-256 (Fernet)
      │    production/secrets.vault  ◄── PBKDF2-HMAC-SHA256 (480k iterations)
      │
      └─── Environment fallback ──── os.getenv("KEY")
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install cryptography
```

### 2. Set master password

```bash
export VAULT_MASTER_PASSWORD="$(openssl rand -base64 48)"
export VAULT_SALT="$(openssl rand -base64 32)"

# Add to .env (never commit to git)
echo "VAULT_MASTER_PASSWORD=${VAULT_MASTER_PASSWORD}" >> .env
echo "VAULT_SALT=${VAULT_SALT}" >> .env
```

### 3. Initialize vault

```bash
# Import all secrets from current environment
./scripts/setup_vault.sh

# Or manually
python -m production.secrets_vault set OPENAI_API_KEY "sk-..."
python -m production.secrets_vault set STRIPE_SECRET_KEY "sk_live_..."
```

### 4. Verify vault

```bash
python -m production.secrets_vault status
# → {"encrypted": true, "secret_count": 12, "mode": "production"}

python -m production.secrets_vault list
# → Shows all keys with metadata (no values)
```

---

## CLI Reference

```bash
# Status
python -m production.secrets_vault status

# Store a secret
python -m production.secrets_vault set <KEY> <VALUE>

# Retrieve a secret
python -m production.secrets_vault get <KEY>

# Delete a secret
python -m production.secrets_vault delete <KEY>

# List all keys (no values shown)
python -m production.secrets_vault list

# Import multiple secrets from environment
python -m production.secrets_vault import-env OPENAI_API_KEY STRIPE_SECRET_KEY TWILIO_AUTH_TOKEN
```

---

## Python API

```python
from production.secrets_vault import SecretsVault

vault = SecretsVault()  # Uses VAULT_MASTER_PASSWORD env var

# Store
vault.save_secret("OPENAI_API_KEY", "sk-...", description="OpenAI production key")

# Retrieve (with env fallback)
api_key = vault.get_secret("OPENAI_API_KEY")

# Rotate
vault.rotate_secret("OPENAI_API_KEY", "sk-new-...")

# List metadata
secrets = vault.list_secrets()
for s in secrets:
    print(f"{s['key']} — v{s['version']} — updated {s['updated_at']}")
```

---

## Security Properties

| Property | Value |
|----------|-------|
| Encryption | AES-256-GCM (via Fernet) |
| Key Derivation | PBKDF2-HMAC-SHA256 |
| KDF Iterations | 480,000 |
| Key Length | 32 bytes |
| Salt | SHA-256 of `VAULT_SALT` env var |
| File Permissions | 0600 (owner read/write only) |
| Audit Logging | Every READ, WRITE, ROTATE, DELETE |

---

## Required Secrets

| Key | Description | Rotation |
|-----|-------------|----------|
| `OPENAI_API_KEY` | OpenAI GPT API | 90 days |
| `ANTHROPIC_API_KEY` | Anthropic Claude API | 90 days |
| `STRIPE_SECRET_KEY` | Stripe payments | 180 days |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook validation | On rotation |
| `TWILIO_ACCOUNT_SID` | Twilio (SMS/Voice) | 180 days |
| `TWILIO_AUTH_TOKEN` | Twilio auth | 90 days |
| `SENDGRID_API_KEY` | SendGrid email | 90 days |
| `DB_PASSWORD` | PostgreSQL password | 90 days |
| `SECRET_KEY` | App secret key | 180 days |
| `JWT_SECRET` | JWT signing key | 180 days |
| `VAULT_MASTER_PASSWORD` | Vault master key | 365 days |

---

## Key Rotation Procedure

```bash
# 1. Generate new key value
NEW_KEY="sk-new-$(openssl rand -hex 24)"

# 2. Rotate in vault
python -m production.secrets_vault set OPENAI_API_KEY "$NEW_KEY"

# 3. Update in provider (OpenAI, Stripe, etc.)

# 4. Verify new key works
python -m production.api_keys_manager --validate

# 5. Revoke old key in provider dashboard
```

---

## Vault File Format

```json
{
  "_vault_version": "1.0",
  "_saved_at": "2026-03-23T02:00:00",
  "_encrypted": true,
  "secrets": {
    "OPENAI_API_KEY": {
      "value": "<fernet-encrypted-base64>",
      "description": "OpenAI production key",
      "created_at": "2026-01-01T00:00:00",
      "updated_at": "2026-03-23T02:00:00",
      "rotated_at": null,
      "version": 1
    }
  }
}
```

---

## Development Mode

When `VAULT_MASTER_PASSWORD` is not set, the vault runs in development mode
(plaintext storage). **Never use development mode in production.**

```bash
# Check current mode
python -m production.secrets_vault status
# → {"mode": "development", "encrypted": false}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `cryptography library not installed` | `pip install cryptography` |
| `Could not decrypt — wrong master password` | Check `VAULT_MASTER_PASSWORD` env var |
| `Vault file does not exist` | Run `./scripts/setup_vault.sh` |
| `Vault not encrypted` | Set `VAULT_MASTER_PASSWORD` env var |
| Audit log flooded | Check `VAULT_AUDIT` log level in logging config |
