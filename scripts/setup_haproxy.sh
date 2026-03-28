#!/bin/bash
# Setup HAProxy - AgenteDeVoz
# Gap #13: Load Balancer
# Instala y configura HAProxy 2.8

set -euo pipefail

HAPROXY_CFG="/etc/haproxy/haproxy.cfg"
CERT_DIR="/etc/haproxy/certs"

echo "=== AgenteDeVoz: Setup HAProxy ==="

# Instalar HAProxy
echo "[1/5] Instalando HAProxy..."
apt-get update -qq && apt-get install -y haproxy=2.8.*

# Copiar configuracion
echo "[2/5] Copiando configuracion..."
cp "$(dirname "$0")/../config/haproxy/haproxy.cfg" "$HAPROXY_CFG"

# Crear directorio de certificados
echo "[3/5] Configurando TLS..."
mkdir -p "$CERT_DIR"
if [ ! -f "$CERT_DIR/agentevoz.pem" ]; then
    echo "ADVERTENCIA: Certificado TLS no encontrado. Generando self-signed para dev..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /tmp/agentevoz.key \
        -out /tmp/agentevoz.crt \
        -subj "/C=CO/O=AgenteDeVoz/CN=agentevoz.local" 2>/dev/null
    cat /tmp/agentevoz.crt /tmp/agentevoz.key > "$CERT_DIR/agentevoz.pem"
    chmod 600 "$CERT_DIR/agentevoz.pem"
fi

# Crear paginas de error
echo "[4/5] Creando paginas de error..."
mkdir -p /etc/haproxy/errors
for code in 400 403 408 500 502 503 504; do
    echo "HTTP/1.0 $code
Content-Type: text/html

<html><body><h1>$code - AgenteDeVoz Error</h1></body></html>" > "/etc/haproxy/errors/${code}.http"
done

# Validar y arrancar
echo "[5/5] Validando configuracion y arrancando HAProxy..."
haproxy -c -f "$HAPROXY_CFG" && echo "Configuracion valida"
systemctl enable haproxy
systemctl restart haproxy

echo ""
echo "=== HAProxy configurado ==="
echo "Stats:  http://localhost:8404/stats"
echo "HTTP:   http://localhost:80"
echo "HTTPS:  https://localhost:443"
