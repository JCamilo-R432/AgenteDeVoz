# Restore Procedure — AgenteDeVoz

## Overview
This document describes the step-by-step procedure to restore the AgenteDeVoz database
from a backup. Follow this exactly during a disaster recovery event.

**RTO Target:** 4 hours
**RPO Target:** 24 hours (daily backups) or 1 hour (WAL streaming)

---

## Prerequisites

- Access to the backup files (local `backups/` dir or S3)
- PostgreSQL client tools (`psql`, `gunzip`)
- Environment variables: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- Application stopped to prevent data inconsistency during restore

---

## Step 1: Stop the Application

```bash
# Kubernetes
kubectl scale deployment agentevoz --replicas=0 -n production

# Docker
docker-compose stop app

# Systemd
systemctl stop agentevoz
```

---

## Step 2: Identify the Target Backup

```bash
# List local backups
ls -lht backups/*.sql.gz | head -20

# Check backup metadata
cat backups/<backup_file>.meta

# Or using the manager
python -m production.backup_restore_verified status
```

---

## Step 3: Verify Backup Integrity

```bash
# Verify checksum + gzip integrity + SQL header
python -m production.backup_restore_verified verify --file backups/<backup_file>.sql.gz

# Or manually
gunzip -t backups/<backup_file>.sql.gz && echo "gzip OK"
```

If verification fails, try the previous backup.

---

## Step 4: Create a Snapshot of Current DB (Defensive)

```bash
# Before overwriting, create a snapshot of current state
python -m production.backup_restore_verified backup --label pre_restore

# Verify it was created
ls -la backups/agentevoz_pre_restore_*.sql.gz
```

---

## Step 5: Drop and Recreate Target Database

> **WARNING:** This is destructive. Double-check DB name before proceeding.

```bash
export PGPASSWORD="${DB_PASSWORD}"

# Terminate active connections
psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}';"

# Drop and recreate
psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} postgres \
  -c "DROP DATABASE IF EXISTS \"${DB_NAME}\";"
psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} postgres \
  -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\";"
```

---

## Step 6: Restore the Backup

```bash
# Option A: Using the manager (recommended)
python -m production.backup_restore_verified restore \
  --file backups/<backup_file>.sql.gz

# Option B: Manual
gunzip -c backups/<backup_file>.sql.gz | \
  psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} ${DB_NAME}
```

---

## Step 7: Verify the Restore

```bash
# Check row counts
psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} ${DB_NAME} \
  -c "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM subscriptions; SELECT COUNT(*) FROM payments;"

# Check latest records
psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} ${DB_NAME} \
  -c "SELECT email, created_at FROM users ORDER BY created_at DESC LIMIT 5;"
```

---

## Step 8: Run Post-Restore Migrations

```bash
# Apply any pending migrations
cd /app && alembic upgrade head

# Verify migration state
alembic current
```

---

## Step 9: Restart the Application

```bash
# Kubernetes
kubectl scale deployment agentevoz --replicas=3 -n production

# Docker
docker-compose up -d app

# Systemd
systemctl start agentevoz
```

---

## Step 10: Smoke Test

```bash
# Health check
curl -f https://agentevoz.com/health

# Quick functional test
python testing/integration_e2e/test_full_flow.py -k "test_health"
```

---

## Rollback

If the restore causes issues and you need to revert:

```bash
# The pre-restore snapshot from Step 4 can be used
python -m production.backup_restore_verified restore \
  --file backups/agentevoz_pre_restore_<timestamp>.sql.gz
```

---

## Contact Escalation

| Time Without Recovery | Action |
|----------------------|--------|
| 0-30 min | On-call engineer handles |
| 30-60 min | Escalate to Tech Lead |
| 60-120 min | Escalate to CTO |
| 120+ min | Invoke full DR team |

See `docs/DISASTER_RECOVERY_PLAN.md` for contact information.
