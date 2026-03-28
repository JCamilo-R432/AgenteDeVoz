# Disaster Recovery — AgenteDeVoz

**Objetivo:** Restaurar el servicio en menos de 30 minutos tras una falla total.

---

## 1. Backup Schedule

| Tipo | Frecuencia | Retención | Ubicación |
|------|-----------|-----------|-----------|
| DB PostgreSQL | Diario 3 AM | 7 días | `/backups/agentevoz/db_*.sql.gz` |
| Archivos de config | Diario 3 AM | 7 días | `/backups/agentevoz/files_*.tar.gz` |

**Verificar que el cron está activo:**
```bash
crontab -l | grep backup
# Debe mostrar: 0 3 * * * /opt/AgenteDeVoz/backup.sh
```

---

## 2. Niveles de Incidente

| Nivel | Descripción | RTO |
|-------|-------------|-----|
| 1 — Proceso caído | PM2 reinicia automáticamente | < 1 min |
| 2 — Falla de app | Reinicio manual con PM2 | < 5 min |
| 3 — Corrupción de DB | Restore desde backup | < 30 min |
| 4 — VPS destruido | Re-provisionar + restore | < 2 horas |

---

## 3. Procedimiento de Recovery (Nivel 3 — DB)

### Paso 1: Detener el servicio
```bash
pm2 stop agentevoz-api
pm2 status  # verificar que está detenido
```

### Paso 2: Listar backups disponibles
```bash
python /opt/AgenteDeVoz/scripts/restore_backup.py --list
```
Salida esperada:
```
FILE                                             SIZE    DATE
db_agentevoz_2026-03-26_03-00-00.sql.gz        2.1MB  2026-03-26 03:00
db_agentevoz_2026-03-25_03-00-00.sql.gz        2.0MB  2026-03-25 03:00
...
```

### Paso 3: Restaurar el backup más reciente
```bash
# Opción A: automático (recomendado)
python /opt/AgenteDeVoz/scripts/restore_backup.py --restore-latest

# Opción B: dry-run primero (sin ejecutar)
python /opt/AgenteDeVoz/scripts/restore_backup.py --restore-latest --dry-run

# Opción C: fecha específica
python /opt/AgenteDeVoz/scripts/restore_backup.py --restore-date 2026-03-26

# Opción D: manual
gunzip -c /backups/agentevoz/db_agentevoz_YYYY-MM-DD_HH-MM-SS.sql.gz \
    | psql -U postgres agentevoz
```

### Paso 4: Restaurar archivos de configuración
```bash
# Listar archivos disponibles
ls -la /backups/agentevoz/files_*.tar.gz

# Restaurar (reemplaza archivos actuales)
tar -xzf /backups/agentevoz/files_YYYY-MM-DD_HH-MM-SS.tar.gz -C /
```

### Paso 5: Reiniciar el servicio
```bash
pm2 start agentevoz-api
pm2 status  # verificar que está running
```

### Paso 6: Verificar que todo funciona
```bash
# Health check
curl -sf http://localhost:8000/api/v1/health | python3 -m json.tool

# Test de DB
curl -sf http://localhost:8000/api/v1/health | grep '"database": "connected"'

# Test de endpoint de pedidos
curl -sf http://localhost:8000/api/v1/orders/ECO-2026-001001
```

---

## 4. Recovery Nivel 4 — VPS Destruido

### 4.1 Provisionar nuevo VPS (Namecheap)
```bash
# Instalar dependencias
apt update && apt install -y python3.11 python3.11-venv postgresql-client nginx certbot

# Instalar Node.js + PM2
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs
npm install -g pm2
```

### 4.2 Restaurar código
```bash
# Clonar repo
git clone https://github.com/JCamilo-R432/AgenteDeVoz.git /opt/AgenteDeVoz
cd /opt/AgenteDeVoz

# Instalar dependencias Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4.3 Restaurar configuración
```bash
# Desde el backup de archivos
tar -xzf /path/to/files_backup.tar.gz -C /

# O copiar .env desde tu máquina local
scp .env user@nuevo-vps:/opt/AgenteDeVoz/.env
```

### 4.4 Configurar PostgreSQL
```bash
sudo -u postgres psql -c "CREATE DATABASE agentevoz;"
sudo -u postgres psql -c "CREATE USER agentevoz_user WITH PASSWORD 'TU_PASSWORD';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE agentevoz TO agentevoz_user;"
```

### 4.5 Restaurar DB + ejecutar migrations
```bash
gunzip -c /path/to/db_backup.sql.gz | psql -U postgres agentevoz
# O migrations desde cero:
# alembic upgrade head
```

### 4.6 Iniciar servicio
```bash
cd /opt/AgenteDeVoz
source venv/bin/activate
pm2 start "uvicorn src.server:app --host 0.0.0.0 --port 8000" --name agentevoz-api
pm2 save
pm2 startup
```

### 4.7 Configurar Nginx + SSL
```bash
# Copiar config de nginx desde el repo
cp /opt/AgenteDeVoz/config/nginx.conf /etc/nginx/sites-available/agentevoz
ln -s /etc/nginx/sites-available/agentevoz /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# SSL con Let's Encrypt
certbot --nginx -d api.tudominio.com
```

---

## 5. Checklist de Verificación Post-Recovery

```bash
□ pm2 status     → agentevoz-api = online
□ curl /health   → {"status": "healthy"}
□ DB conectada   → "database": "connected"
□ SSL activo     → https:// responde
□ Cron backup    → crontab -l muestra 0 3 * * *
□ Logs limpios   → pm2 logs agentevoz-api (sin errores)
□ Test pedido    → GET /api/v1/orders/{order_number} responde
□ Test OTP       → POST /api/v1/auth/send-otp responde
```

---

## 6. Contactos de Emergencia

| Rol | Contacto |
|-----|----------|
| VPS Admin | Namecheap Support: support.namecheap.com |
| DB Admin | Tu email de admin |
| Twilio | console.twilio.com / help.twilio.com |
| SendGrid | app.sendgrid.com / support.sendgrid.com |

---

## 7. Configurar Backup (primera vez)

```bash
# Hacer ejecutable el script
chmod +x /opt/AgenteDeVoz/backup.sh

# Configurar variables de entorno
echo "DB_USER=postgres" >> /etc/environment
echo "DB_NAME=agentevoz" >> /etc/environment
echo "DB_PASSWORD=tu_password" >> /etc/environment
echo "BACKUP_DIR=/backups/agentevoz" >> /etc/environment
echo "APP_DIR=/opt/AgenteDeVoz" >> /etc/environment

# Agregar cron job (ejecuta a las 3:00 AM diario)
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/AgenteDeVoz/backup.sh >> /backups/agentevoz/cron.log 2>&1") | crontab -

# Test manual del backup
/opt/AgenteDeVoz/backup.sh

# Verificar que el backup se creó
ls -lh /backups/agentevoz/
```
