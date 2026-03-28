# Disaster Recovery Plan — AgenteDeVoz

**Version:** 1.0
**Last Updated:** 2026-03-23
**Next Review:** 2026-06-23
**Test Frequency:** Quarterly

---

## Recovery Objectives

| Disaster Type | RTO | RPO | Priority |
|---------------|-----|-----|----------|
| Database Failure | 4h | 24h | P1 |
| Server Failure | 2h | 1h | P1 |
| Security Breach | 8h | 4h | P1 |
| Data Corruption | 6h | 24h | P2 |
| Network Failure | 1h | 0h | P2 |
| Payment Provider Outage | 30min | 0h | P2 |
| AI Provider Outage | 15min | 0h | P3 |

---

## Emergency Contacts

| Role | Contact | Available |
|------|---------|-----------|
| On-Call Engineer | See PagerDuty | 24/7 |
| Tech Lead | Slack @techlead | Business hours |
| DBA | Slack @dba-team | On-call rotation |
| CTO | Phone (emergency) | Critical only |
| DevOps | Slack #devops | 24/7 |

---

## Runbook: Database Failure

**Trigger:** PostgreSQL unreachable, connection errors, data loss detected
**RTO:** 4 hours | **RPO:** 24 hours

### Steps

1. **Alert** — PagerDuty auto-alerts on-call engineer
2. **Assess** — Check PostgreSQL status: `systemctl status postgresql`
3. **Attempt restart** — `systemctl restart postgresql`
4. **Check logs** — `journalctl -u postgresql -n 100`
5. **Attempt DB repair** — `pg_resetwal` if WAL corruption
6. **Identify latest valid backup** — `python -m production.backup_restore_verified status`
7. **Execute restore** — `./scripts/restore_production.sh <backup_file>`
8. **Verify** — Count rows in critical tables
9. **Restore service** — `systemctl start agentevoz`

**Estimated time:** 45 minutes

---

## Runbook: Server Failure

**Trigger:** Server unreachable, hardware failure, OS crash
**RTO:** 2 hours | **RPO:** 1 hour

### Steps

1. **Alert** — Monitoring triggers P1 alert
2. **Assess** — Check server console (cloud provider dashboard)
3. **Attempt reboot** — Cloud console restart
4. **Provision replacement** — Launch new instance from AMI/snapshot
5. **Restore application** — Deploy from git: `./scripts/setup_production.sh`
6. **Restore database** — `./scripts/restore_production.sh`
7. **Update DNS** — Point domain to new server IP
8. **Verify SSL** — Check certificate valid on new server
9. **Health check** — `curl -f https://agentevoz.com/health`

**Estimated time:** 60 minutes

---

## Runbook: Security Breach

**Trigger:** Unauthorized access, credential leak, suspicious activity detected
**RTO:** 8 hours | **RPO:** 4 hours

### Steps

1. **ISOLATE** — Block all external traffic immediately
2. **Preserve evidence** — Snapshot server, copy logs
3. **Rotate all credentials** — All API keys, DB password, JWT secret
4. **Revoke all active sessions** — Flush token denylist
5. **Audit access logs** — Identify breach vector and scope
6. **Patch vulnerability** — Fix identified security gap
7. **Restore from clean backup** — Pre-breach backup if data compromised
8. **Enable enhanced monitoring** — Increase log verbosity
9. **Legal notification** — GDPR 72h notification if personal data involved
10. **Post-incident report** — Root cause analysis within 48h

**Estimated time:** 240 minutes
**Legal deadline:** 72 hours (GDPR Article 33)

---

## Runbook: Data Corruption

**Trigger:** Inconsistent data, application errors, failed data integrity checks
**RTO:** 6 hours | **RPO:** 24 hours

### Steps

1. **Stop writes** — Set application to read-only or maintenance mode
2. **Identify scope** — Determine which tables/records are affected
3. **Create snapshot** — Backup current (corrupted) state for analysis
4. **Find clean backup** — Last backup before corruption occurred
5. **Restore data** — `./scripts/restore_production.sh <pre_corruption_backup>`
6. **Replay transactions** — Apply any post-backup transactions from logs if possible
7. **Verify integrity** — Run data consistency checks
8. **Resume operations** — Remove read-only mode

**Estimated time:** 120 minutes

---

## DR Test Schedule

| Test | Frequency | Next Date | Responsible |
|------|-----------|-----------|-------------|
| Backup restore drill | Monthly | 2026-04-23 | On-call team |
| Full DR simulation | Quarterly | 2026-06-23 | Tech lead |
| Tabletop exercise | Semi-annual | 2026-09-23 | All team |
| Plan review | Annual | 2027-03-23 | CTO |

### Running a DR Test

```bash
# Simulate database failure recovery (non-destructive)
./scripts/test_disaster_recovery.sh database_failure

# Run all scenarios
./scripts/test_disaster_recovery.sh all
```

---

## Communication Templates

### Internal Alert
```
🚨 [INCIDENT P{level}] AgenteDeVoz {component} failure
Time: {timestamp}
Impact: {impact_description}
On-call: {engineer_name}
Status: Investigating
Updates: Every 15 min in #incidents
```

### Customer Communication
```
We are currently experiencing technical difficulties with our service.
Our team is actively working to resolve the issue.
Expected resolution: {eta}
We apologize for any inconvenience.
```

---

## Recovery Validation Checklist

After any recovery event, verify:

- [ ] Health endpoint responding: `GET /health` → 200
- [ ] User login working
- [ ] Voice call processing working
- [ ] Payment processing working
- [ ] All API integrations responding
- [ ] No data loss beyond RPO
- [ ] SSL certificate valid
- [ ] Monitoring re-enabled
- [ ] Incident post-mortem scheduled

---

## Backup Locations

| Location | Type | Retention | Access |
|----------|------|-----------|--------|
| `/app/backups/` | Local pg_dump | 30 days | SSH |
| S3 bucket | Off-site pg_dump | 90 days | AWS CLI |
| PostgreSQL WAL | Continuous | 7 days | PITR |

---

## Key Commands Quick Reference

```bash
# Create emergency backup
./scripts/backup_production.sh emergency

# Restore from backup
./scripts/restore_production.sh backups/<file>.sql.gz

# Rotate all secrets
./scripts/setup_vault.sh

# Check service health
curl -f https://agentevoz.com/health | python3 -m json.tool

# View recent logs
journalctl -u agentevoz -n 100 --no-pager

# Check SSL expiry
python -c "from production.ssl_certificate_manager import SSLCertificateManager; SSLCertificateManager('agentevoz.com','').print_status()"

# Validate all API keys
python -m production.api_keys_manager --validate
```
