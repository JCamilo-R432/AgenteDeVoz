#!/usr/bin/env bash
# ============================================================
# init_database.sh — Inicializa la base de datos de AgenteDeVoz
#
# Aplica las migraciones de Alembic y siembra datos básicos.
# Uso:
#   bash scripts/init_database.sh              # aplica migraciones + seed
#   bash scripts/init_database.sh --seed-only  # solo datos básicos
#   bash scripts/init_database.sh --migrate-only # solo migraciones
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

SEED_ONLY=false
MIGRATE_ONLY=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --seed-only)    SEED_ONLY=true;    shift ;;
    --migrate-only) MIGRATE_ONLY=true; shift ;;
    *) shift ;;
  esac
done

echo "============================================================"
echo -e "  ${GREEN}AgenteDeVoz — Inicialización de Base de Datos${NC}"
echo "============================================================"
echo ""

# ── Verificar conexión ────────────────────────────────────────────────────────
if [[ -z "${DATABASE_URL:-}" ]]; then
  if [[ -f "$PROJECT_ROOT/.env" ]]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | grep DATABASE_URL | xargs)
  fi
fi

DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/agentevoz}"
echo "Base de datos: $DATABASE_URL"
echo ""

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src"

# ── Migraciones Alembic ───────────────────────────────────────────────────────
if [[ "$SEED_ONLY" == "false" ]]; then
  echo -e "${YELLOW}Aplicando migraciones...${NC}"
  python -m alembic -c migrations/alembic.ini upgrade head
  echo -e "  ${GREEN}[OK]${NC} Migraciones aplicadas"
  echo ""
fi

# ── Datos de seed ─────────────────────────────────────────────────────────────
if [[ "$MIGRATE_ONLY" == "false" ]]; then
  echo -e "${YELLOW}Insertando datos básicos...${NC}"

  python - <<'PYTHON'
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agentevoz")

try:
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    conn.autocommit = False
    cur = conn.cursor()

    # ── Planes de suscripción ──────────────────────────────────────────────────
    cur.execute("""
        INSERT INTO subscription_plans (id, name, price_monthly, max_calls, max_agents, features)
        VALUES
            ('plan_free',    'Free',       0.00,   100,  1, '{"basic_tts": true}'),
            ('plan_starter', 'Starter',   29.00,  1000,  3, '{"basic_tts": true, "analytics": true}'),
            ('plan_pro',     'Pro',        79.00,  5000,  10,'{"elevenlabs_tts": true, "analytics": true, "crm": true}'),
            ('plan_enterprise','Enterprise',299.00,99999,50, '{"elevenlabs_tts": true, "analytics": true, "crm": true, "sla": true}')
        ON CONFLICT (id) DO NOTHING
    """)

    # ── Usuario admin de demo ──────────────────────────────────────────────────
    import hashlib, secrets
    demo_password_hash = "$2b$12$" + secrets.token_hex(22)  # placeholder, cambiar en producción
    cur.execute("""
        INSERT INTO users (email, hashed_password, name, phone, is_active, is_admin)
        VALUES ('admin@agentevoz.com', %s, 'Admin Demo', '+573001234567', true, true)
        ON CONFLICT (email) DO NOTHING
    """, (demo_password_hash,))

    # ── Cliente de prueba ──────────────────────────────────────────────────────
    cur.execute("""
        INSERT INTO users (email, hashed_password, name, phone, is_active)
        VALUES ('cliente@ejemplo.com', %s, 'Carlos Rodríguez', '+573009876543', true)
        ON CONFLICT (email) DO NOTHING
    """, (demo_password_hash,))

    conn.commit()
    cur.close()
    conn.close()
    print("  [OK] Datos básicos insertados")

except psycopg2.errors.UndefinedTable as e:
    print(f"  [AVISO] Tabla no existe aún: {e}")
    print("         Ejecuta primero: alembic upgrade head")
except Exception as e:
    print(f"  [ERROR] {e}")
    sys.exit(1)
PYTHON

  echo ""
fi

echo "============================================================"
echo -e "  ${GREEN}Base de datos inicializada correctamente${NC}"
echo "============================================================"
echo ""
echo "Próximos pasos:"
echo "  1. Verifica la conexión: psql \$DATABASE_URL -c '\dt'"
echo "  2. Inicia el servidor:   uvicorn src.server:app --reload"
echo "  3. API docs en:          http://localhost:8000/api/docs"
