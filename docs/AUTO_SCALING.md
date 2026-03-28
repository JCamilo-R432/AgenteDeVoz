# Auto-Scaling (Gap #25)

## Descripcion
Escalado horizontal automatico basado en CPU, memoria, latencia y conexiones.
Integracion con Kubernetes HPA (Horizontal Pod Autoscaler).

## Umbrales de escalado
| Metrica | Scale Up | Scale Down |
|---------|----------|------------|
| CPU % | >= 70% | < 30% |
| Memoria % | >= 80% | < 50% |
| Latencia avg | >= 2000ms | < 500ms |
| Conexiones | >= 50/replica | - |

## Cooldowns
- Scale up: 60 segundos entre eventos
- Scale down: 300 segundos entre eventos

## Uso
```python
from src.infrastructure.auto_scaler import AutoScaler, ScalingMetrics

scaler = AutoScaler(
    deployment_name="agentevoz",
    namespace="production",
    min_replicas=2,
    max_replicas=20,
)

metrics = ScalingMetrics(
    cpu_percent=75.0,
    memory_percent=60.0,
    active_connections=120,
    avg_response_ms=800.0,
    queue_depth=5,
)

decision = scaler.evaluate(metrics)
if decision.direction != ScaleDirection.NONE:
    scaler.apply_decision(decision)
    k8s_hpa.scale_deployment("agentevoz", decision.target_replicas)
```

## Kubernetes HPA
Manifiesto en `config/kubernetes/hpa.yaml`.
```bash
kubectl apply -f config/kubernetes/hpa.yaml
kubectl get hpa -n production
```

## Limites de replicas
- Minimo: 2 replicas (alta disponibilidad)
- Maximo: 20 replicas
- Surge maximo: +2 replicas por evento de scale-up
- Reduccion maxima: -1 replica por evento de scale-down
