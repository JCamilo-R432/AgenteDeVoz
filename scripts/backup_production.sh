#!/usr/bin/env bash
# backup_production.sh — Create a verified production backup
# Runs daily via cron: 0 2 * * * /app/scripts/backup_production.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${APP_DIR}/logs/backup_production.log"
LABEL="${1:-daily}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }

mkdir -p "$(dirname "$LOG_FILE")"
log "====== BACKUP STARTED (label=$LABEL) ======"

cd "$APP_DIR"
source .env 2>/dev/null || true

# ── Create backup ─────────────────────────────────────────────────────────────
log "Creating database backup..."
RESULT=$(python3 -c "
import sys, json
sys.path.insert(0, '${APP_DIR}')
from production.backup_restore_verified import BackupRestoreManager
mgr = BackupRestoreManager()
result = mgr.create_backup(label='${LABEL}')
print(json.dumps(result))
")

SUCCESS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success','false'))")
BACKUP_FILE=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file',''))")

if [[ "$SUCCESS" != "True" && "$SUCCESS" != "true" ]]; then
  die "Backup creation failed: $RESULT"
fi

log "Backup created: $BACKUP_FILE"

# ── Verify backup ─────────────────────────────────────────────────────────────
log "Verifying backup integrity..."
python3 -c "
import sys
sys.path.insert(0, '${APP_DIR}')
from production.backup_restore_verified import BackupRestoreManager
mgr = BackupRestoreManager()
ok = mgr.verify_backup('${BACKUP_FILE}')
sys.exit(0 if ok else 1)
" || die "Backup verification FAILED for $BACKUP_FILE"
log "Backup verified ✅"

# ── Status report ─────────────────────────────────────────────────────────────
log "Backup status:"
python3 -c "
import sys, json
sys.path.insert(0, '${APP_DIR}')
from production.backup_restore_verified import BackupRestoreManager
mgr = BackupRestoreManager()
status = mgr.get_status()
for k, v in status.items():
    print(f'  {k}: {v}')
"

log "====== BACKUP COMPLETED ======"
exit 0
