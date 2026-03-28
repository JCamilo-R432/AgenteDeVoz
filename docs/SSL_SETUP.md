# SSL Setup Guide — AgenteDeVoz

## Overview

AgenteDeVoz uses Let's Encrypt certificates managed by Certbot with automatic renewal.
Self-signed certificates are available for local development.

---

## Prerequisites

- Ubuntu 22.04+ server
- Nginx installed
- Domain DNS pointing to server IP
- Port 80/443 open in firewall
- `DOMAIN` and `SSL_EMAIL` env vars set

---

## Quick Setup

```bash
export DOMAIN="agentevoz.com"
export SSL_EMAIL="admin@agentevoz.com"

./scripts/configure_ssl.sh
```

This script:
1. Installs Certbot if needed
2. Obtains certificate for `agentevoz.com` + `www.agentevoz.com`
3. Configures nginx with HTTPS redirect
4. Sets up auto-renewal cron (`0 3 * * *`)
5. Runs a dry-run renewal test

---

## Manual Steps

### 1. Install Certbot

```bash
# Ubuntu/Debian
apt-get install certbot python3-certbot-nginx

# Or via snap
snap install --classic certbot
```

### 2. Obtain Certificate

```bash
certbot --nginx \
  -d agentevoz.com \
  -d www.agentevoz.com \
  --non-interactive \
  --agree-tos \
  -m admin@agentevoz.com \
  --redirect
```

### 3. Verify

```bash
# Check expiry
openssl x509 -in /etc/letsencrypt/live/agentevoz.com/cert.pem -noout -enddate

# Or using the manager
python -c "
from production.ssl_certificate_manager import SSLCertificateManager
mgr = SSLCertificateManager('agentevoz.com', 'admin@agentevoz.com')
mgr.print_status()
"
```

---

## Auto-Renewal

Certbot adds a systemd timer automatically. Verify with:

```bash
systemctl status certbot.timer
systemctl list-timers | grep certbot
```

Manual renewal test:
```bash
certbot renew --dry-run
```

---

## Development: Self-Signed Certificate

```bash
python -c "
from production.ssl_certificate_manager import SSLCertificateManager
mgr = SSLCertificateManager('localhost', 'dev@localhost')
mgr.generate_self_signed('config/ssl')
"
# Creates: config/ssl/selfsigned.key + config/ssl/selfsigned.crt
```

Nginx dev config snippet:
```nginx
ssl_certificate     /path/to/config/ssl/selfsigned.crt;
ssl_certificate_key /path/to/config/ssl/selfsigned.key;
```

---

## Monitoring Expiry

The certificate renewal daemon checks daily and sends alerts:

```bash
# Manual check
python config/ssl/certificate_renewal.py

# Status via Python
python -c "
from production.ssl_certificate_manager import SSLCertificateManager
mgr = SSLCertificateManager('agentevoz.com', 'admin@agentevoz.com')
print(mgr.check_expiration())
"
```

Alert thresholds (configured in `config/production/ssl_config.json`):
- 30 days: Email warning
- 14 days: Email warning
- 7 days: Critical email + force renewal
- 3 days: Emergency renewal + escalation
- 1 day: Page on-call

---

## Nginx Configuration Reference

```nginx
server {
    listen 443 ssl http2;
    server_name agentevoz.com www.agentevoz.com;

    ssl_certificate     /etc/letsencrypt/live/agentevoz.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/agentevoz.com/privkey.pem;

    # Strong TLS settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # HSTS (2 years)
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name agentevoz.com www.agentevoz.com;
    return 301 https://$host$request_uri;
}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `certbot: command not found` | Install certbot: `apt-get install certbot` |
| `Challenge failed` | Check DNS, port 80 open, nginx running |
| `Too many certificates` | Use `--staging` flag for testing |
| Rate limit hit | Wait 1 week or use staging environment |
| Certificate not renewing | Check `journalctl -u certbot` |
| nginx not loading new cert | `systemctl reload nginx` |
| `openssl: command not found` | `apt-get install openssl` |

---

## Staging Environment

To test without hitting Let's Encrypt rate limits:

```bash
export SSL_STAGING=true
./scripts/configure_ssl.sh
```

Note: Staging certificates are not trusted by browsers. Remove `SSL_STAGING` for production.
