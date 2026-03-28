# Backup & Restore Procedure — AgenteDeVoz

## Overview

| Property | Value |
|----------|-------|
| Backup tool | `pg_dump` + gzip compression |
| Checksum | SHA-256 per backup file |
| Retention | 30 days (configurable) |
| Schedule | Daily at 02:00 UTC |
| Off-site | AWS S3 (optional) |
| RTO | 4 hours |
| RPO | 24 hours |

---

## Backup Schedule

| Job | Cron | Description |
|-----|------|-------------|
| Daily backup | `0 2 * * *` | Full `pg_dump` compressed backup |
| Cleanup | `0 3 * * 0` | Delete backups older than 30 days |
| Test restore | `0 4 * * 1` | Weekly verified restore to temp DB |

---

## Creating Backups

### Automatic (cron)
```bash
# Configured by setup_production.sh
# Runs daily: /scripts/backup_production.sh
```

### Manual
```bash
# Create a labeled backup
./scripts/backup_production.sh pre_deploy

# Or via Python
python -m production.backup_restore_verified backup --label manual
```

### Output
```
backups/
├── agentevoz_daily_20260323_020000.sql.gz
├── agentevoz_daily_20260323_020000.sql.gz.meta
├── agentevoz_pre_deploy_20260322_150000.sql.gz
└── agentevoz_pre_deploy_20260322_150000.sql.gz.meta
```

The `.meta` sidecar contains:
```json
{
  "file": "backups/agentevoz_daily_20260323_020000.sql.gz",
  "name": "agentevoz_daily_20260323_020000.sql.gz",
  "timestamp": "20260323_020000",
  "size_bytes": 2456321,
  "checksum_sha256": "a3f4b2c1...",
  "db_name": "agentevoz",
  "label": "daily"
}
```

---

## Verifying Backups

```bash
# Verify a specific backup
python -m production.backup_restore_verified verify \
  --file backups/agentevoz_daily_20260323_020000.sql.gz

# Verification checks:
# 1. File exists and is not empty
# 2. SHA-256 checksum matches metadata
# 3. gzip integrity (gunzip -t)
# 4. SQL header present (PostgreSQL dump marker)
```

---

## Status

```bash
python -m production.backup_restore_verified status
```

Output:
```json
{
  "backup_dir": "backups",
  "backup_count": 14,
  "total_size_mb": 42.5,
  "retention_days": 30,
  "s3_enabled": false,
  "latest_backup": "backups/agentevoz_daily_20260323_020000.sql.gz",
  "latest_backup_date": "2026-03-23T02:00:00"
}
```

---

## Restore Procedure

**See `config/backup/restore_procedure.md` for the full step-by-step runbook.**

Quick restore:
```bash
# Interactive (with confirmation prompt)
./scripts/restore_production.sh backups/agentevoz_daily_20260323_020000.sql.gz

# Automated (CI/DR use only)
./scripts/restore_production.sh backups/agentevoz_daily_20260323_020000.sql.gz --no-confirm
```

---

## Test Restore (Sandbox)

Weekly automated test that restores to a temporary database:

```bash
python -m production.backup_restore_verified test-restore
```

Output:
```json
{
  "success": true,
  "backup_file": "backups/agentevoz_daily_20260323_020000.sql.gz",
  "test_db": "agentevoz_restore_test",
  "user_row_count": 1247,
  "tested_at": "2026-03-23T04:00:00"
}
```

The test DB is automatically dropped after the test.

---

## S3 Off-Site Backup

Configure in `.env`:
```bash
BACKUP_S3_BUCKET=agentevoz-backups-prod
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
```

Backups are uploaded to `s3://agentevoz-backups-prod/agentevoz/backups/`.

Restore from S3:
```bash
aws s3 cp s3://agentevoz-backups-prod/agentevoz/backups/<filename>.sql.gz backups/
./scripts/restore_production.sh backups/<filename>.sql.gz
```

---

## Cleanup

```bash
# Delete backups older than retention_days (default: 30)
python -m production.backup_restore_verified cleanup
```

---

## Python API

```python
from production.backup_restore_verified import BackupRestoreManager

mgr = BackupRestoreManager(
    db_name="agentevoz",
    backup_dir="backups",
    retention_days=30,
)

# Create
result = mgr.create_backup(label="pre_deploy")

# Verify
ok = mgr.verify_backup(result["file"])

# Restore to production
mgr.restore_backup(result["file"])

# Test restore (sandboxed)
test = mgr.test_restore()

# Cleanup
deleted = mgr.cleanup_old_backups()
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `pg_dump not found` | Install: `apt-get install postgresql-client` |
| `Backup file empty` | Check DB connection, PGPASSWORD env var |
| `Checksum mismatch` | File corrupted — use another backup |
| `gzip integrity failed` | File truncated — use another backup |
| `Restore failed: role does not exist` | Create DB user first |
| `S3 upload failed` | Check AWS credentials and bucket permissions |
