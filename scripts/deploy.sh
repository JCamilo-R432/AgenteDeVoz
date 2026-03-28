#!/usr/bin/env bash
# ============================================================
# deploy.sh - Despliega la aplicacion con Docker Compose
# Uso: bash scripts/deploy.sh [--env staging|prod] [--no-build]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/src/deploy/docker-compose.yml"
ENV="prod"
BUILD=true
TAG="1.0.0"

# Parsear argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --env)      ENV="$2";    shift 2 ;;
    --no-build) BUILD=false; shift ;;
    --tag)      TAG="$2";    shift 2 ;;
    *) echo "Opcion desconocida: $1"; exit 1 ;;
  esac
done

ENV_FILE="$PROJECT_ROOT/config/${ENV}.env"

echo "============================================================"
echo "  AgenteDeVoz - Deploy ($ENV) v$TAG"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# Verificar prereqs
for cmd in docker docker-compose git; do
  command -v "$cmd" &>/dev/null || { echo "[ERROR] $cmd no encontrado."; exit 1; }
done

# Cargar env
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
  echo "[OK] Entorno cargado: $ENV_FILE"
else
  echo "[WARN] $ENV_FILE no encontrado. Usando variables del sistema."
fi

# ── Pre-checks ─────────────────────────────────────────────────────────────

echo ""
echo "[1/6] Verificando estado de Git..."
if [[ -d "$PROJECT_ROOT/.git" ]]; then
  COMMIT=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD)
  BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)
  echo "[OK] Branch: $BRANCH | Commit: $COMMIT"
  if git -C "$PROJECT_ROOT" status --porcelain | grep -q .; then
    echo "[WARN] Hay cambios sin commitear. Continuando de todas formas."
  fi
fi

# ── Build ──────────────────────────────────────────────────────────────────

if [[ "$BUILD" == "true" ]]; then
  echo ""
  echo "[2/6] Construyendo imagen Docker..."
  cd "$PROJECT_ROOT"
  docker build -f src/deploy/Dockerfile -t "agentevoz:$TAG" -t "agentevoz:latest" .
  echo "[OK] Imagen construida: agentevoz:$TAG"
else
  echo "[2/6] Omitiendo build (--no-build)."
fi

# ── Backup pre-deploy ──────────────────────────────────────────────────────

echo ""
echo "[3/6] Backup pre-deploy..."
if [[ -f "$SCRIPT_DIR/backup.sh" ]]; then
  bash "$SCRIPT_DIR/backup.sh" --quick 2>/dev/null || echo "[WARN] Backup rapido falló. Continuando."
else
  echo "[WARN] backup.sh no encontrado. Omitiendo backup."
fi

# ── Deploy ─────────────────────────────────────────────────────────────────

echo ""
echo "[4/6] Iniciando servicios..."
cd "$PROJECT_ROOT/src/deploy"
docker-compose -f "$COMPOSE_FILE" \
  --project-name agentevoz \
  --env-file "$ENV_FILE" \
  up -d --remove-orphans

echo "[OK] Servicios iniciados."

# ── Esperar health checks ──────────────────────────────────────────────────

echo ""
echo "[5/6] Esperando health checks (max 60s)..."
MAX_WAIT=60
ELAPSED=0
until docker inspect --format='{{.State.Health.Status}}' agentevoz_app 2>/dev/null | grep -q "healthy"; do
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    echo "[ERROR] La app no respondio en ${MAX_WAIT}s."
    docker logs agentevoz_app --tail 30
    exit 1
  fi
  sleep 3
  ELAPSED=$((ELAPSED + 3))
  echo "  Esperando... ${ELAPSED}s"
done
echo "[OK] App saludable."

# ── Smoke test ─────────────────────────────────────────────────────────────

echo ""
echo "[6/6] Smoke test..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/ping)
if [[ "$HTTP_CODE" == "200" ]]; then
  echo "[OK] API respondiendo (HTTP $HTTP_CODE)."
else
  echo "[ERROR] API no responde correctamente (HTTP $HTTP_CODE)."
  exit 1
fi

echo ""
echo "============================================================"
echo "  Deploy completado exitosamente."
echo "  URL: https://agentevoz.tuempresa.com"
echo "  Dashboard: https://agentevoz.tuempresa.com/dashboard"
echo "  Commit: $COMMIT (${BRANCH})"
echo "============================================================"
