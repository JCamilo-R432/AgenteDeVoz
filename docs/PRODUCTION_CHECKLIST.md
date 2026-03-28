# Production Checklist — AgenteDeVoz

Use this checklist before every production deployment and during initial setup.
Mark each item ✅ when verified.

---

## Pre-Launch Checklist

### Infrastructure
- [ ] Server provisioned (Ubuntu 22.04 LTS, min 4 vCPU / 8 GB RAM)
- [ ] PostgreSQL 15+ installed and running
- [ ] Redis 7+ installed and running
- [ ] Nginx installed and configured
- [ ] Domain DNS records pointing to server IP (A record + www)
- [ ] Firewall configured (ports 80, 443, 22 only)

### SSL / HTTPS
- [ ] Let's Encrypt certificate obtained (`./scripts/configure_ssl.sh`)
- [ ] Auto-renewal cron configured
- [ ] `certbot renew --dry-run` passes
- [ ] HTTPS redirect working (HTTP → HTTPS)
- [ ] HSTS header present (`Strict-Transport-Security`)
- [ ] TLS 1.2+ only (TLS 1.0/1.1 disabled)
- [ ] SSL Labs grade: A or A+

### Environment Variables
- [ ] `SECRET_KEY` — strong random string (min 64 chars)
- [ ] `JWT_SECRET` — strong random string (min 64 chars)
- [ ] `DB_PASSWORD` — strong unique password
- [ ] `VAULT_MASTER_PASSWORD` — set and stored securely
- [ ] `VAULT_SALT` — set (not default value)
- [ ] `OPENAI_API_KEY` — valid and tested
- [ ] `STRIPE_SECRET_KEY` — production key (not test)
- [ ] `STRIPE_WEBHOOK_SECRET` — set for webhook validation
- [ ] `DOMAIN` — set to production domain
- [ ] `SSL_EMAIL` — admin contact email

### Secrets Vault
- [ ] Vault initialized (`./scripts/setup_vault.sh`)
- [ ] All API keys imported to vault
- [ ] Vault file permissions: 0600
- [ ] `python -m production.secrets_vault status` shows `encrypted: true`

### Database
- [ ] Schema deployed (`alembic upgrade head`)
- [ ] Migrations verified (`alembic current` shows expected revision)
- [ ] Admin user created (`python scripts/create_admin.py`)
- [ ] Database connection pool configured
- [ ] Indexes verified on high-traffic tables

### Backups
- [ ] Backup directory created with correct permissions
- [ ] Daily backup cron configured
- [ ] First manual backup created and verified
- [ ] `python -m production.backup_restore_verified status` shows backups
- [ ] S3 off-site backup configured (if applicable)
- [ ] Test restore completed successfully

### API Keys
- [ ] All required API keys validated (`python -m production.api_keys_manager`)
- [ ] No keys expiring within 7 days
- [ ] Twilio phone number configured
- [ ] SendGrid sender domain verified
- [ ] Stripe products and prices created

### Application
- [ ] `requirements.txt` dependencies installed
- [ ] `uvicorn` running behind nginx
- [ ] Health endpoint responding: `GET /health` → 200
- [ ] API docs accessible: `/docs`
- [ ] SaaS routes mounted (check health response for `"saas": true`)
- [ ] Rate limiting active
- [ ] Middleware stack: Auth → RateLimit → Subscription → Audit

### Load Testing
- [ ] Smoke test passed (5 users, 1 min)
- [ ] Baseline test passed (50 users, 5 min, P95 < 800ms)
- [ ] No memory leaks after soak test

### Monitoring
- [ ] Health check cron (`*/5 * * * *`)
- [ ] Log rotation configured
- [ ] Error alerting configured
- [ ] Uptime monitoring active

### Security
- [ ] No debug mode in production (`DEBUG=false`)
- [ ] CORS restricted to known origins
- [ ] SQL injection protection (ORM, parameterized queries)
- [ ] Security headers: `X-Frame-Options`, `X-Content-Type-Options`, `CSP`
- [ ] Rate limiting: 60 req/min for API, 5 req/min for auth
- [ ] Dependency audit: `pip-audit requirements.txt`

---

## Pre-Deployment Checklist (Each Release)

- [ ] All tests passing: `pytest tests/ -v`
- [ ] Integration tests passing: `pytest testing/integration_e2e/ -v`
- [ ] No new critical security vulnerabilities
- [ ] Database migrations reviewed
- [ ] Pre-migration backup created (`./scripts/backup_production.sh pre_deploy`)
- [ ] Rollback plan documented
- [ ] Deployment window communicated to stakeholders

---

## Post-Deployment Verification

- [ ] Health check passing
- [ ] Key flows working (register, login, voice call, subscription)
- [ ] No spike in error rates
- [ ] Database row counts sane
- [ ] Monitoring alerts not triggered
- [ ] Run smoke test: `pytest testing/integration_e2e/ -k smoke -v`

---

## Contacts

| Role | Name | Contact |
|------|------|---------|
| On-Call Engineer | TBD | See PagerDuty |
| Tech Lead | TBD | Slack #tech-lead |
| DBA | TBD | Slack #database |
| CTO | TBD | Phone (emergency only) |

See `docs/DISASTER_RECOVERY_PLAN.md` for full escalation procedures.
