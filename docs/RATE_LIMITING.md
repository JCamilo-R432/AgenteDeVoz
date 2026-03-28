# Rate Limiting - AgenteDeVoz

Gap #14: Rate limiting multicapa con proteccion DDoS.

## Capas de proteccion

1. **DDoS Protection** — Deteccion de floods globales y por IP
2. **IP Rate Limiter** — Limites por IP con auto-bloqueo
3. **User Rate Limiter** — Quotas por plan (Free/Pro/Enterprise)
4. **Rate Limiter** — Token bucket / sliding window por clave arbitraria

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/infrastructure/rate_limiter.py` | Token bucket + sliding window |
| `src/infrastructure/ip_rate_limiting.py` | Rate limiting por IP con listas |
| `src/infrastructure/user_rate_limiting.py` | Quotas por plan de servicio |
| `src/infrastructure/ddos_protection.py` | Deteccion y mitigacion DDoS |

## Quotas por plan

| Plan | RPM | RPD | RPM | Llamadas concurrentes |
|------|-----|-----|-----|----------------------|
| FREE | 10 | 1,000 | 10,000/mes | 2 |
| PRO | 60 | 10,000 | 300,000/mes | 10 |
| ENTERPRISE | 300 | 100,000 | 3M/mes | 50 |
| INTERNAL | 10,000 | ilimitado | ilimitado | 1,000 |

## Uso rapido

```python
from src.infrastructure.rate_limiter import RateLimiter, RateLimitConfig
from src.infrastructure.ip_rate_limiting import IPRateLimiter
from src.infrastructure.user_rate_limiting import UserRateLimiter, ServicePlan

# Rate limiter por IP
ip_rl = IPRateLimiter()
result = ip_rl.is_allowed("192.168.1.100")
if not result["allowed"]:
    return 429, {"retry_after": result["retry_after_s"]}

# Rate limiter por usuario
user_rl = UserRateLimiter()
user_rl.register_user("user123", ServicePlan.PRO)
decision = user_rl.check_and_record("user123")
if not decision["allowed"]:
    return 429, {"reason": decision["reason"]}
```

## Redis (produccion)

Ver `config/rate_limiting/redis_rate_limit.lua` para implementacion
distribuida con Redis compatible con multiples instancias.
