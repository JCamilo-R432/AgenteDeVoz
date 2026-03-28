#!/usr/bin/env bash
# restore_production.sh — Restore from a production backup with safety checks
# Usage: ./restore_production.sh [backup_file] [--no-confirm]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${APP_DIR}/logs/restore_production.log"
BACKUP_FILE="${1:-}"
NO_CONFIRM="${2:-}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }
warn() { log "WARNING: $*"; }

mkdir -p "$(dirname "$LOG_FILE")"
log "====== RESTORE STARTED ======"

cd "$APP_DIR"
source .env 2>/dev/null || true

# ── Find backup file ──────────────────────────────────────────────────────────
if [[ -z "$BACKUP_FILE" ]]; then
  log "No backup file specified — using latest backup"
  BACKUP_FILE=$(ls -t backups/*.sql.gz 2>/dev/null | head -1)
  [[ -z "$BACKUP_FILE" ]] && die "No backup files found in backups/"
fi

log "Target backup: $BACKUP_FILE"

if [[ ! -f "$BACKUP_FILE" ]]; then
  die "Backup file not found: $BACKUP_FILE"
fi

# ── Confirmation ──────────────────────────────────────────────────────────────
if [[ "$NO_CONFIRM" != "--no-confirm" ]]; then
  echo ""
  echo "⚠️  WARNING: This will overwrite the production database!"
  echo "   Database: ${DB_NAME:-agentevoz}"
  echo "   Backup:   $BACKUP_FILE"
  echo ""
  read -r -p "Type 'RESTORE' to confirm: " CONFIRM
  [[ "$CONFIRM" != "RESTORE" ]] && die "Restore cancelled by user"
fi

# ── Step 1: Create a pre-restore backup ────────────────────────────────────────
log "Creating pre-restore snapshot..."
python3 -c "
import sys
sys.path.insert(0, '${APP_DIR}')
from production.backup_restore_verified import BackupRestoreManager
mgr = BackupRestoreManager()
result = mgr.create_backup(label='pre_restore')
print('Pre-restore backup:', result.get('file', 'N/A'))
" || warn "Could not create pre-restore backup — proceeding anyway"

# ── Step 2: Verify backup integrity ───────────────────────────────────────────
log "Verifying backup integrity..."
python3 -c "
import sys
sys.path.insert(0, '${APP_DIR}')
from production.backup_restore_verified import BackupRestoreManager
mgr = BackupRestoreManager()
ok = mgr.verify_backup('${BACKUP_FILE}')
if not ok:
    print('VERIFICATION FAILED')
    sys.exit(1)
print('Verification OK')
" || die "Backup verification failed — restore aborted"

# ── Step 3: Stop application ───────────────────────────────────────────────────
log "Stopping application..."
systemctl stop agentevoz 2>/dev/null && log "Service stopped" || warn "Could not stop service"

# ── Step 4: Restore ────────────────────────────────────────────────────────────
log "Restoring backup..."
python3 -c "
import sys
sys.path.insert(0, '${APP_DIR}')
from production.backup_restore_verified import BackupRestoreManager
mgr = BackupRestoreManager()
ok = mgr.restore_backup('${BACKUP_FILE}')
sys.exit(0 if ok else 1)
" || die "Restore failed"
log "Restore completed ✅"

# ── Step 5: Run migrations ────────────────────────────────────────────────────
log "Applying migrations..."
alembic upgrade head && log "Migrations OK" || warn "Migration step had issues"

# ── Step 6: Restart application ───────────────────────────────────────────────
log "Restarting application..."
systemctl start agentevoz && log "Service started" || die "Failed to start service"

# ── Step 7: Health check ──────────────────────────────────────────────────────
sleep 5
DOMAIN="${DOMAIN:-localhost}"
PORT="${APP_PORT:-8000}"
if curl -sf "http://${DOMAIN}:${PORT}/health" > /dev/null; then
  log "Health check passed ✅"
else
  die "Health check failed after restore — manual intervention required"
fi

log "====== RESTORE COMPLETED SUCCESSFULLY ======"
