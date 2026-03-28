# Load Balancer Setup - AgenteDeVoz

Gap #13: HAProxy load balancer con circuit breaker y health checks avanzados.

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/infrastructure/load_balancer.py` | LB con RR, least-conn, weighted, IP-hash |
| `src/infrastructure/haproxy_config.py` | Generador de haproxy.cfg |
| `src/infrastructure/health_check_advanced.py` | Circuit breaker pattern |

## Algoritmos soportados

| Algoritmo | Uso recomendado |
|-----------|-----------------|
| `round_robin` | Servidores homogeneos |
| `least_connections` | Llamadas largas (voz) |
| `weighted_round_robin` | Servidores con diferente capacidad |
| `ip_hash` | Sesiones pegajosas (WebSocket) |

## Uso rapido

```python
from src.infrastructure.load_balancer import LoadBalancer, Backend, LBAlgorithm

lb = LoadBalancer(algorithm=LBAlgorithm.LEAST_CONNECTIONS)
lb.add_backend(Backend("api1", "10.0.0.1", 8000, weight=2))
lb.add_backend(Backend("api2", "10.0.0.2", 8000, weight=1))

backend = lb.select_backend(client_ip="192.168.1.100")
# ... procesar peticion ...
lb.release_backend(backend.backend_id, success=True, response_time_ms=150)
```

## Circuit Breaker

```python
from src.infrastructure.health_check_advanced import CircuitBreaker, CircuitBreakerConfig

cb = CircuitBreaker("stt_api", CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout_s=30.0,
    success_threshold=2,
))

# Uso
try:
    result = cb.call(stt_client.transcribe, audio_data)
except RuntimeError:
    # Circuito abierto - usar fallback
    pass
```

## Instalar HAProxy

```bash
bash scripts/setup_haproxy.sh
```

Stats disponibles en: `http://localhost:8404/stats`
