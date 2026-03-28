# Load Testing Results — AgenteDeVoz

## Overview

Load tests are performed using **Locust** against the production API.
This document tracks historical results and defines performance baselines.

**Test Framework:** Locust 2.x
**Location:** `testing/load_testing/`
**Reports:** `testing/reports/`

---

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| P50 latency | < 200ms | > 500ms |
| P95 latency | < 800ms | > 2,000ms |
| P99 latency | < 1,500ms | > 5,000ms |
| Error rate | < 1% | > 5% |
| Min RPS | > 40 | < 10 |
| Concurrent users | 100 | — |

---

## Test Scenarios

| Scenario | Users | Duration | Purpose |
|----------|-------|----------|---------|
| `smoke` | 5 | 1 min | CI sanity check |
| `baseline` | 50 | 5 min | Normal load baseline |
| `stress` | 200 | 10 min | Breaking point test |
| `spike` | 150 | 3 min | Sudden traffic spike |
| `soak` | 30 | 1 hour | Memory leak detection |
| `voice_heavy` | 80 | 5 min | Peak voice call load |
| `webhook_flood` | 20 | 2 min | Payment webhook stress |
| `pre_launch` | 100 | 10 min | Go-live readiness |

---

## Running Tests

### Quick smoke test (CI)
```bash
./scripts/run_load_test.sh smoke
```

### Full baseline
```bash
locust \
  -f testing/load_testing/locustfile.py \
  --host=https://agentevoz.com \
  --users=50 \
  --spawn-rate=5 \
  --run-time=300s \
  --headless \
  --csv=testing/reports/baseline \
  --html=testing/reports/baseline_report.html
```

### Pre-launch validation
```bash
./scripts/run_load_test.sh pre_launch
```

### Analyze results
```bash
python testing/load_testing/results_analyzer.py baseline
python testing/load_testing/results_analyzer.py stress --json
```

---

## Latest Baseline Results

*Update this section after each load test run.*

### Baseline (50 users, 5 min) — TEMPLATE

```
Scenario 'baseline': PASSED
  Requests : 15,240
  Failures : 12 (0.08%)
  RPS      : 50.8
  P95      : 612ms
  P99      : 987ms
```

**Endpoint breakdown:**

| Endpoint | P95 | P99 | Error% |
|----------|-----|-----|--------|
| GET /health | 8ms | 15ms | 0.0% |
| POST /api/v1/auth/login | 145ms | 230ms | 0.1% |
| GET /api/v1/users/me | 89ms | 156ms | 0.0% |
| POST /api/v1/voice/process | 1,240ms | 2,100ms | 0.5% |
| GET /api/v1/subscriptions/plans | 22ms | 45ms | 0.0% |

---

## Bottlenecks & Optimization History

| Date | Issue | Fix | Improvement |
|------|-------|-----|-------------|
| Template | `/voice/process` P99 > 3s | Added response caching | -40% latency |
| Template | DB connection pool exhausted | Increased pool to 20 | -30% errors |
| Template | Auth endpoint slow | Added Redis session cache | -60% latency |

---

## Capacity Planning

Based on baseline results:

| Metric | Current | 6 months | 12 months |
|--------|---------|----------|-----------|
| Registered users | — | 1,000 | 5,000 |
| Daily active users | — | 200 | 1,000 |
| Peak concurrent | — | 50 | 200 |
| Required RPS | — | 20 | 80 |
| Recommended servers | 1 | 2 | 4 |

---

## Regression Testing

Run before each release to catch performance regressions:

```bash
# Compare against baseline
pytest tests/test_load_testing.py -v

# Full pre-release check
./scripts/run_load_test.sh pre_launch
python testing/load_testing/results_analyzer.py pre_launch --json
```

A regression is flagged if:
- P95 increases by more than 20% vs. previous baseline
- Error rate increases by more than 0.5%
- RPS decreases by more than 10%

---

## Infrastructure Tuning

### PostgreSQL (`config/postgresql/primary.conf`)
```ini
max_connections = 100
shared_buffers = 256MB
work_mem = 16MB
maintenance_work_mem = 64MB
effective_cache_size = 1GB
```

### Uvicorn workers
```bash
uvicorn src.server:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
# Formula: (2 × CPU cores) + 1
```

### Nginx
```nginx
worker_processes auto;
worker_connections 1024;
keepalive_timeout 65;
```
