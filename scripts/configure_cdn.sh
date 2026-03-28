#!/usr/bin/env bash
# configure_cdn.sh - Configura Cloudflare CDN para AgenteDeVoz

set -euo pipefail

CF_API_TOKEN="${CF_API_TOKEN:-}"
CF_ZONE_ID="${CF_ZONE_ID:-}"
BASE_DOMAIN="${BASE_DOMAIN:-api.agentevoz.com}"
RULES_FILE="${RULES_FILE:-config/cdn/cloudflare_rules.json}"

echo "=== Configuracion CDN Cloudflare ==="

if [[ -z "$CF_API_TOKEN" || -z "$CF_ZONE_ID" ]]; then
    echo "ERROR: Configura CF_API_TOKEN y CF_ZONE_ID"
    echo "  export CF_API_TOKEN=tu_token"
    echo "  export CF_ZONE_ID=tu_zone_id"
    exit 1
fi

CF_HEADERS=(
    -H "Authorization: Bearer ${CF_API_TOKEN}"
    -H "Content-Type: application/json"
)

echo "[1/4] Verificando zona Cloudflare..."
ZONE_STATUS=$(curl -sf \
    "${CF_HEADERS[@]}" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['status'])" 2>/dev/null || echo "unknown")
echo "  Zona status: $ZONE_STATUS"

echo "[2/4] Aplicando configuracion de seguridad..."
# Habilitar HTTPS siempre
curl -sf -X PATCH \
    "${CF_HEADERS[@]}" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/settings/always_use_https" \
    -d '{"value":"on"}' > /dev/null && echo "  Always HTTPS: ON"

# TLS 1.2 minimo
curl -sf -X PATCH \
    "${CF_HEADERS[@]}" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/settings/min_tls_version" \
    -d '{"value":"1.2"}' > /dev/null && echo "  TLS min: 1.2"

# HTTP/3 (QUIC)
curl -sf -X PATCH \
    "${CF_HEADERS[@]}" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/settings/http3" \
    -d '{"value":"on"}' > /dev/null && echo "  HTTP/3: ON"

echo "[3/4] Configurando Page Rules para cache de audio..."
curl -sf -X POST \
    "${CF_HEADERS[@]}" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/pagerules" \
    -d "{
  \"targets\": [{\"target\": \"url\", \"constraint\": {\"operator\": \"matches\", \"value\": \"https://${BASE_DOMAIN}/audio/*\"}}],
  \"actions\": [{\"id\": \"cache_level\", \"value\": \"cache_everything\"}, {\"id\": \"edge_cache_ttl\", \"value\": 3600}],
  \"status\": \"active\"
}" > /dev/null && echo "  Page Rule audio cache: OK"

echo "[4/4] Purgando cache existente..."
curl -sf -X POST \
    "${CF_HEADERS[@]}" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/purge_cache" \
    -d '{"purge_everything":true}' > /dev/null && echo "  Cache purgado"

echo ""
echo "=== CDN Cloudflare configurado ==="
echo "Zona: ${CF_ZONE_ID}"
echo "Dominio: ${BASE_DOMAIN}"
