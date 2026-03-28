# Cost Monitoring - AgenteDeVoz

Gap #15: Monitoreo de costos de APIs externas con alertas de presupuesto.

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/infrastructure/cost_monitor.py` | Monitor central con alertas |
| `src/infrastructure/api_cost_tracker.py` | Costos por llamada API |
| `src/infrastructure/budget_alerts.py` | Sistema de alertas multi-canal |

## Tarifas incluidas

| Proveedor | Servicio | Tarifa aproximada |
|-----------|---------|-------------------|
| Google | STT | $0.016/min |
| Deepgram | STT | $0.0125/min |
| Google | TTS | $4/1M chars |
| ElevenLabs | TTS | $0.30/1K chars |
| OpenAI | LLM (GPT-4o-mini) | $1.50/1M tokens input |
| Anthropic | LLM (Claude) | $3.00/1M tokens input |
| Twilio | Telefonia | $0.0085/min |

## Uso rapido

```python
from src.infrastructure.cost_monitor import CostMonitor, CostCategory, BudgetConfig
from src.infrastructure.api_cost_tracker import APICostTracker

budget = BudgetConfig(daily_limit_usd=100.0, monthly_limit_usd=2000.0)
monitor = CostMonitor(budget=budget)
tracker = APICostTracker()

# Registrar costo de una llamada STT (60 segundos)
cost = tracker.calculate_cost("google", "stt", 60.0)  # ~$0.016
tracker.record_api_call("google", "stt", 60.0, session_id="sess_123")
monitor.record_cost(CostCategory.STT, "google", cost, units=60, unit_type="seconds")

# Dashboard
dashboard = monitor.get_dashboard()
print(f"Gasto hoy: ${dashboard['daily']['total_usd']:.4f}")
print(f"% del presupuesto diario: {dashboard['daily']['pct_used']}%")
```

## Alertas

Umbrales por defecto: 50% (INFO), 75% (WARNING), 90% (CRITICAL), 100% (EMERGENCY).

Configurar en `config/monitoring/cost_alerts.yml`.

## Canales de notificacion

- `AlertChannel.LOG` — Logger Python (siempre activo)
- `AlertChannel.SLACK` — Webhook Slack
- `AlertChannel.EMAIL` — Correo electronico
- `AlertChannel.PAGERDUTY` — Solo para EMERGENCY
