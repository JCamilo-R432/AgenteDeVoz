# Guia de Despliegue - AgenteDeVoz

## Requisitos del Sistema

### Hardware recomendado (produccion)

| Componente | Minimo | Recomendado |
|------------|--------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disco | 20 GB SSD | 50 GB SSD |
| Red | 10 Mbps | 100 Mbps |

### Software requerido

- Ubuntu 22.04 LTS (o similar)
- Docker 24.x + Docker Compose 2.x
- Python 3.11+ (si despliegue directo sin Docker)
- PostgreSQL 15 (o via Docker)
- Redis 7 (o via Docker)
- Nginx 1.25+
- Certificado SSL (Let's Encrypt recomendado)

---

## Opcion 1: Docker Compose (Recomendado)

### Paso 1: Clonar y configurar

```bash
git clone https://github.com/tuempresa/agentevoz.git
cd agentevoz

# Copiar y editar variables de entorno
cp config/production.env.example config/production.env
nano config/production.env
# Editar TODAS las variables marcadas con CAMBIAR_POR_...
```

### Paso 2: Configurar credenciales de Google Cloud

```bash
# Copiar el archivo JSON de credenciales de Google
cp /ruta/google-credentials.json config/google-credentials.json
chmod 600 config/google-credentials.json
```

### Paso 3: Configurar SSL

```bash
# Instalar certbot
sudo apt install certbot

# Obtener certificado (requiere que el dominio apunte al servidor)
sudo certbot certonly --standalone -d agentevoz.tuempresa.com

# Copiar certificados
sudo cp /etc/letsencrypt/live/agentevoz.tuempresa.com/fullchain.pem \
    src/deploy/certs/
sudo cp /etc/letsencrypt/live/agentevoz.tuempresa.com/privkey.pem \
    src/deploy/certs/
```

### Paso 4: Inicializar base de datos

```bash
bash scripts/setup_database.sh --env prod
```

### Paso 5: Desplegar

```bash
bash scripts/deploy.sh --env prod
```

### Paso 6: Verificar

```bash
# Health check completo
bash scripts/health_check.sh

# Ver logs
docker logs agentevoz_app -f

# Estado de contenedores
docker ps
```

---

## Opcion 2: Despliegue directo (systemd)

### Paso 1: Crear usuario y directorio

```bash
sudo useradd -r -s /bin/false agentevoz
sudo mkdir -p /opt/agentevoz /var/log/agentevoz
sudo chown agentevoz:agentevoz /opt/agentevoz /var/log/agentevoz
```

### Paso 2: Instalar dependencias del sistema

```bash
sudo apt update && sudo apt install -y \
    python3.11 python3.11-venv python3.11-dev \
    portaudio19-dev libportaudio2 \
    ffmpeg postgresql-client
```

### Paso 3: Configurar entorno Python

```bash
cd /opt/agentevoz
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### Paso 4: Instalar servicio systemd

```bash
sudo cp src/deploy/systemd/agentevoz.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable agentevoz
sudo systemctl start agentevoz
```

### Paso 5: Configurar Nginx

```bash
sudo cp src/deploy/nginx.conf /etc/nginx/nginx.conf
sudo nginx -t
sudo systemctl reload nginx
```

---

## Configuracion de Twilio

1. En Twilio Console, ir a Phone Numbers > Manage > Active numbers
2. Seleccionar tu numero
3. En "Voice Configuration":
   - Webhook URL: `https://agentevoz.tuempresa.com/api/v1/webhooks/twilio/voice`
   - HTTP Method: POST
   - Status Callback: `https://agentevoz.tuempresa.com/api/v1/webhooks/twilio/status`
4. Guardar cambios

---

## Variables de Entorno Obligatorias

Las siguientes variables deben configurarse antes del primer arranque:

```
APP_SECRET_KEY          - Clave secreta de la app (32+ chars)
DB_PASSWORD             - Password de PostgreSQL
REDIS_PASSWORD          - Password de Redis
JWT_SECRET_KEY          - Secreto para tokens JWT (64+ chars)
TWILIO_ACCOUNT_SID      - SID de cuenta Twilio
TWILIO_AUTH_TOKEN       - Token de autenticacion Twilio
WHATSAPP_VERIFY_TOKEN   - Token de verificacion webhook Meta
SENDGRID_API_KEY        - API key de SendGrid
GOOGLE_APPLICATION_CREDENTIALS - Ruta al JSON de Google Cloud
```

---

## Renovacion de SSL

Configurar cron para renovacion automatica:

```bash
# Agregar a crontab del sistema
echo "0 3 1 * * certbot renew --quiet && systemctl reload nginx" | sudo tee -a /etc/crontab
```

---

## Backups

```bash
# Manual
bash scripts/backup.sh

# Cron diario a las 3am
echo "0 3 * * * /opt/agentevoz/scripts/backup.sh" | sudo crontab -u agentevoz -
```

---

## Rollback

```bash
# Volver a la version anterior de Docker
docker tag agentevoz:latest agentevoz:rollback-$(date +%Y%m%d)
docker tag agentevoz:1.0.0 agentevoz:latest

# Reiniciar con la version anterior
cd src/deploy
docker-compose restart app
```

---

## Monitoreo

- Dashboard: `https://agentevoz.tuempresa.com/dashboard`
- API Docs: `https://agentevoz.tuempresa.com/api/docs`
- Health: `https://agentevoz.tuempresa.com/api/v1/health`
- Logs: `docker logs agentevoz_app -f`
