#!/usr/bin/env bash
# setup_jaeger.sh - Levanta Jaeger para distributed tracing

set -euo pipefail

JAEGER_VERSION="${JAEGER_VERSION:-1.53.0}"
JAEGER_UI_PORT="${JAEGER_UI_PORT:-16686}"
JAEGER_COLLECTOR_PORT="${JAEGER_COLLECTOR_PORT:-14268}"
NAMESPACE="${K8S_NAMESPACE:-monitoring}"

echo "=== Setup Jaeger Distributed Tracing ==="
echo "Version: $JAEGER_VERSION"

# -- Docker Compose (desarrollo local) --
if command -v docker &>/dev/null && [[ "${USE_DOCKER:-true}" == "true" ]]; then
    echo "[1/2] Levantando Jaeger con Docker..."
    docker run -d \
        --name jaeger \
        --restart unless-stopped \
        -p 5775:5775/udp \
        -p 6831:6831/udp \
        -p 6832:6832/udp \
        -p 5778:5778 \
        -p ${JAEGER_UI_PORT}:16686 \
        -p ${JAEGER_COLLECTOR_PORT}:14268 \
        -p 14250:14250 \
        -p 9411:9411 \
        -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
        jaegertracing/all-in-one:${JAEGER_VERSION} \
        2>/dev/null || echo "Jaeger ya estaba corriendo"

    echo "  Jaeger UI: http://localhost:${JAEGER_UI_PORT}"
    echo "  Collector: http://localhost:${JAEGER_COLLECTOR_PORT}/api/traces"

# -- Kubernetes --
elif command -v kubectl &>/dev/null; then
    echo "[1/2] Instalando Jaeger Operator en Kubernetes..."
    kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

    # Instalar cert-manager (requerido por Jaeger Operator)
    kubectl apply -f \
        "https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml" \
        --server-side || true

    echo "Esperando cert-manager..."
    kubectl wait --namespace cert-manager \
        --for=condition=ready pod \
        --selector=app=cert-manager \
        --timeout=120s || echo "Timeout esperando cert-manager"

    # Instalar Jaeger Operator
    kubectl apply -f \
        "https://github.com/jaegertracing/jaeger-operator/releases/download/v${JAEGER_VERSION}/jaeger-operator.yaml" \
        --namespace "${NAMESPACE}" || true

    # Crear instancia Jaeger all-in-one
    cat <<EOF | kubectl apply -f -
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: agentevoz-jaeger
  namespace: ${NAMESPACE}
spec:
  strategy: allInOne
  allInOne:
    image: jaegertracing/all-in-one:${JAEGER_VERSION}
  storage:
    type: memory
    options:
      memory:
        max-traces: 100000
  ingress:
    enabled: true
    hosts:
      - jaeger.agentevoz.internal
EOF
    echo "  Jaeger Operator instalado en namespace ${NAMESPACE}"
fi

echo "[2/2] Configurando AgenteDeVoz para usar Jaeger..."
if [[ -f ".env" ]]; then
    grep -q "JAEGER_COLLECTOR_URL" .env || \
        echo "JAEGER_COLLECTOR_URL=http://localhost:${JAEGER_COLLECTOR_PORT}/api/traces" >> .env
    echo "  Variable JAEGER_COLLECTOR_URL configurada en .env"
fi

echo ""
echo "=== Jaeger listo ==="
echo "UI: http://localhost:${JAEGER_UI_PORT}"
echo "Servicio: agentevoz (filtrar en UI por service name)"
