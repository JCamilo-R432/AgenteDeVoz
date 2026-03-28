#!/usr/bin/env bash
# test_disaster_recovery.sh — Run DR test scenarios (non-destructive simulation)
# Schedule: monthly — 0 0 1 * * /app/scripts/test_disaster_recovery.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${APP_DIR}/logs/dr_test.log"
SCENARIO="${1:-all}"  # database_failure | server_failure | security_breach | all

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [DR-TEST] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }

mkdir -p "$(dirname "$LOG_FILE")"
log "====== DISASTER RECOVERY TEST STARTED (scenario=$SCENARIO) ======"

cd "$APP_DIR"
source .env 2>/dev/null || true

# ── Run DR test via Python module ─────────────────────────────────────────────
python3 - << PYEOF
import sys, json
sys.path.insert(0, '${APP_DIR}')
from production.disaster_recovery_plan import DisasterRecoveryPlan, DisasterType

plan = DisasterRecoveryPlan()
scenario = '${SCENARIO}'

if scenario == 'all':
    disaster_types = list(DisasterType)
else:
    mapping = {
        'database_failure': DisasterType.DATABASE_FAILURE,
        'server_failure': DisasterType.SERVER_FAILURE,
        'security_breach': DisasterType.SECURITY_BREACH,
        'data_corruption': DisasterType.DATA_CORRUPTION,
        'network_failure': DisasterType.NETWORK_FAILURE,
    }
    if scenario not in mapping:
        print(f"Unknown scenario: {scenario}")
        print(f"Available: {', '.join(mapping.keys())}, all")
        sys.exit(1)
    disaster_types = [mapping[scenario]]

all_passed = True
for dt in disaster_types:
    print(f"\n--- Testing: {dt.value} ---")
    result = plan.execute_dr_test(dt)
    status = "PASSED" if result['success'] else "FAILED"
    print(f"Result: {status}")
    print(f"  Steps completed: {result.get('steps_completed', 0)}/{result.get('total_steps', 0)}")
    print(f"  Total time: {result.get('total_duration_min', 0):.1f} min")
    if not result['success']:
        all_passed = False
        print(f"  Failed step: {result.get('failed_step', 'unknown')}")

print("\n" + "=" * 50)
overall = "PASSED" if all_passed else "FAILED"
print(f"DR Test Suite: {overall}")
sys.exit(0 if all_passed else 1)
PYEOF

RESULT=$?

# ── Generate DR document ──────────────────────────────────────────────────────
log "Generating updated DR document..."
python3 -c "
import sys
sys.path.insert(0, '${APP_DIR}')
from production.disaster_recovery_plan import DisasterRecoveryPlan
plan = DisasterRecoveryPlan()
doc = plan.generate_dr_document()
with open('docs/DISASTER_RECOVERY_PLAN.md', 'w') as f:
    f.write(doc)
print('DR document updated')
" 2>/dev/null || log "WARNING: Could not update DR document"

if [[ $RESULT -eq 0 ]]; then
  log "====== DR TEST PASSED ======"
else
  log "====== DR TEST FAILED — review logs and runbooks ======"
  exit 1
fi
