#!/usr/bin/env bash
# setup_elasticsearch.sh - Instala Elasticsearch + Kibana para log aggregation

set -euo pipefail

ES_VERSION="${ES_VERSION:-8.12.0}"
ES_PORT="${ES_PORT:-9200}"
KIBANA_PORT="${KIBANA_PORT:-5601}"
ES_PASSWORD="${ES_PASSWORD:-changeme_secure_password}"

echo "=== Setup Elasticsearch + Kibana (ELK) ==="
echo "Version: $ES_VERSION"

# -- Docker Compose --
if command -v docker-compose &>/dev/null || command -v docker &>/dev/null; then
    echo "[1/3] Creando docker-compose para ELK..."
    cat > /tmp/elk-compose.yml <<EOF
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:${ES_VERSION}
    container_name: agentevoz-es
    environment:
      - discovery.type=single-node
      - ELASTIC_PASSWORD=${ES_PASSWORD}
      - xpack.security.enabled=true
      - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
    ports:
      - "${ES_PORT}:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:9200/_cluster/health | grep -q '\"status\":\"green\\|yellow\"'"]
      interval: 30s
      timeout: 10s
      retries: 5

  kibana:
    image: docker.elastic.co/kibana/kibana:${ES_VERSION}
    container_name: agentevoz-kibana
    environment:
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - ELASTICSEARCH_USERNAME=kibana_system
      - ELASTICSEARCH_PASSWORD=${ES_PASSWORD}
    ports:
      - "${KIBANA_PORT}:5601"
    depends_on:
      elasticsearch:
        condition: service_healthy

volumes:
  es_data:
EOF
    docker-compose -f /tmp/elk-compose.yml up -d
    echo "  Elasticsearch: http://localhost:${ES_PORT}"
    echo "  Kibana: http://localhost:${KIBANA_PORT}"
fi

echo "[2/3] Esperando que Elasticsearch este listo..."
MAX_WAIT=60
ELAPSED=0
until curl -sf "http://localhost:${ES_PORT}/_cluster/health" \
    -u "elastic:${ES_PASSWORD}" > /dev/null 2>&1; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [[ $ELAPSED -ge $MAX_WAIT ]]; then
        echo "Timeout esperando Elasticsearch"
        break
    fi
done

echo "[3/3] Creando indices para AgenteDeVoz..."
curl -sf -X PUT "http://localhost:${ES_PORT}/agentevoz-logs" \
    -u "elastic:${ES_PASSWORD}" \
    -H "Content-Type: application/json" \
    -d '{
  "settings": {"number_of_shards": 1, "number_of_replicas": 0},
  "mappings": {
    "properties": {
      "timestamp":   {"type": "date", "format": "epoch_second"},
      "level":       {"type": "keyword"},
      "service":     {"type": "keyword"},
      "session_id":  {"type": "keyword"},
      "trace_id":    {"type": "keyword"},
      "message":     {"type": "text"}
    }
  }
}' && echo "  Indice agentevoz-logs creado" || echo "  Indice ya existe"

# Configurar .env
if [[ -f ".env" ]]; then
    grep -q "ELASTICSEARCH_URL" .env || \
        echo "ELASTICSEARCH_URL=http://localhost:${ES_PORT}" >> .env
    echo "  Variable ELASTICSEARCH_URL configurada"
fi

echo ""
echo "=== ELK Stack listo ==="
echo "Elasticsearch: http://localhost:${ES_PORT} (usuario: elastic / ${ES_PASSWORD})"
echo "Kibana: http://localhost:${KIBANA_PORT}"
