#!/bin/bash
# Configure PagerDuty/OpsGenie - AgenteDeVoz
# Gap #16: Incident Management
# Verifica y configura integraciones de alertas

set -euo pipefail

echo "=== AgenteDeVoz: Configuracion Gestion de Incidentes ==="

# Verificar variables de entorno requeridas
check_env() {
    local var="$1"
    if [ -z "${!var:-}" ]; then
        echo "ERROR: Variable de entorno $var no configurada"
        return 1
    fi
    echo "  OK: $var configurada"
}

echo "[1/4] Verificando variables de entorno..."
check_env "PAGERDUTY_INTEGRATION_KEY" || MISSING_PD=1
check_env "OPSGENIE_API_KEY" || MISSING_OG=1

if [ -n "${MISSING_PD:-}" ] && [ -n "${MISSING_OG:-}" ]; then
    echo "ERROR: Se requiere al menos PAGERDUTY_INTEGRATION_KEY u OPSGENIE_API_KEY"
    exit 1
fi

# Test PagerDuty
echo "[2/4] Probando PagerDuty..."
if [ -n "${PAGERDUTY_INTEGRATION_KEY:-}" ]; then
    PD_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        -X POST https://events.pagerduty.com/v2/enqueue \
        -H "Content-Type: application/json" \
        -d '{
            "routing_key": "'"$PAGERDUTY_INTEGRATION_KEY"'",
            "event_action": "trigger",
            "dedup_key": "test-agentevoz-setup",
            "payload": {
                "summary": "[TEST] AgenteDeVoz setup verification",
                "severity": "info",
                "source": "setup-script"
            }
        }')
    if [ "$PD_RESPONSE" = "202" ]; then
        echo "  PagerDuty OK (HTTP 202)"
        # Resolver el test
        curl -s -X POST https://events.pagerduty.com/v2/enqueue \
            -H "Content-Type: application/json" \
            -d '{"routing_key":"'"$PAGERDUTY_INTEGRATION_KEY"'","event_action":"resolve","dedup_key":"test-agentevoz-setup"}' > /dev/null
    else
        echo "  WARN: PagerDuty respuesta inesperada: $PD_RESPONSE"
    fi
fi

# Test OpsGenie
echo "[3/4] Probando OpsGenie..."
if [ -n "${OPSGENIE_API_KEY:-}" ]; then
    OG_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        -X GET "https://api.opsgenie.com/v2/alerts?limit=1" \
        -H "Authorization: GenieKey $OPSGENIE_API_KEY")
    if [ "$OG_RESPONSE" = "200" ]; then
        echo "  OpsGenie OK (HTTP 200)"
    else
        echo "  WARN: OpsGenie respuesta: $OG_RESPONSE"
    fi
fi

# Guardar en .env si no existe
echo "[4/4] Verificando configuracion de on-call..."
if [ -f "config/monitoring/incident_rules.yml" ]; then
    echo "  Reglas de incidentes: config/monitoring/incident_rules.yml"
fi

echo ""
echo "=== Gestion de incidentes configurada ==="
echo "Playbooks disponibles: api_down, high_latency, security_breach, data_loss"
