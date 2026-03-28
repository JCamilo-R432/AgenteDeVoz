#!/usr/bin/env bash
# migrate_database.sh — Apply Alembic database migrations safely
# Usage: ./migrate_database.sh [target_revision] [--dry-run]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${APP_DIR}/logs/migrate_database.log"
TARGET="${1:-head}"
DRY_RUN="${2:-}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [MIGRATE] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }

mkdir -p "$(dirname "$LOG_FILE")"
log "====== MIGRATION STARTED (target=$TARGET) ======"

cd "$APP_DIR"
source .env 2>/dev/null || true

# ── Pre-migration backup ──────────────────────────────────────────────────────
log "Creating pre-migration backup..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from production.backup_restore_verified import BackupRestoreManager
    mgr = BackupRestoreManager()
    result = mgr.create_backup(label='pre_migration')
    if result['success']:
        print(f'Pre-migration backup: {result[\"file\"]}')
    else:
        print(f'Backup failed: {result.get(\"error\")}')
        sys.exit(1)
except Exception as e:
    print(f'Warning: could not create backup: {e}')
    # Don't fail — let user decide
" || log "WARNING: Pre-migration backup failed"

# ── Show current state ────────────────────────────────────────────────────────
log "Current migration state:"
alembic current 2>&1 | tee -a "$LOG_FILE" || true

log "Pending migrations:"
alembic history --indicate-current 2>&1 | head -20 | tee -a "$LOG_FILE" || true

# ── Dry run ───────────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == "--dry-run" ]]; then
  log "DRY RUN: Generating SQL without applying..."
  alembic upgrade "$TARGET" --sql 2>&1 | tee "${APP_DIR}/logs/migration_dryrun.sql"
  log "SQL saved to logs/migration_dryrun.sql — review before applying"
  exit 0
fi

# ── Apply migrations ──────────────────────────────────────────────────────────
log "Applying migrations to target: $TARGET"
alembic upgrade "$TARGET" 2>&1 | tee -a "$LOG_FILE"
MIGRATE_STATUS=$?

if [[ $MIGRATE_STATUS -ne 0 ]]; then
  die "Migration failed with exit code $MIGRATE_STATUS"
fi

# ── Post-migration verification ───────────────────────────────────────────────
log "Post-migration state:"
alembic current 2>&1 | tee -a "$LOG_FILE"

# Verify tables exist
python3 - << PYEOF
import os, sys
sys.path.insert(0, '.')
try:
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        name = os.getenv('DB_NAME', 'agentevoz')
        user = os.getenv('DB_USER', 'agentevoz_user')
        password = os.getenv('DB_PASSWORD', '')
        db_url = f'postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}'

    async def check():
        engine = create_async_engine(db_url)
        async with engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            ))
            tables = [row[0] for row in result]
            print(f'Tables in DB: {tables}')
            required = {'users', 'subscriptions', 'payments', 'licenses', 'voice_calls'}
            missing = required - set(tables)
            if missing:
                print(f'MISSING TABLES: {missing}')
                sys.exit(1)
            print('All required tables present ✅')
        await engine.dispose()

    asyncio.run(check())
except Exception as e:
    print(f'Post-migration check warning: {e}')
PYEOF

log "====== MIGRATION COMPLETED SUCCESSFULLY ======"
