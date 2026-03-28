# SLA y SLO - AgenteDeVoz
**Version:** 1.0 | **Actualizado:** 2026-03-22
**Vigencia:** A partir de la fecha de go-live

---

## Definiciones

- **SLA (Service Level Agreement):** Acuerdo formal entre el proveedor del servicio y el cliente, con consecuencias comerciales si no se cumple.
- **SLO (Service Level Objective):** Objetivo interno de rendimiento del equipo tecnico, mas estricto que el SLA.
- **SLI (Service Level Indicator):** Metrica especifica que se mide para evaluar el cumplimiento.
- **Error Budget:** Tiempo permitido de fallo dentro del SLO (Ej: 99.5% uptime = 0.5% budget = ~3.6h/mes).

---

## SLOs por Categoria

### Disponibilidad

| Metrica | SLO | SLA Externo | Error Budget Mensual |
|---------|-----|-------------|---------------------|
| Uptime del servicio | 99.5% | 99.0% | ~3.6 horas/mes |
| Uptime del dashboard | 99.0% | 98.0% | ~7.3 horas/mes |
| Disponibilidad de webhooks | 99.5% | 99.0% | ~3.6 horas/mes |

**Medicion:** Prometheus `up{job="agentevoz_app"}`, Uptime Kuma

### Latencia (Performance)

| Percentil | SLO | SLA Externo | Medicion |
|-----------|-----|-------------|----------|
| P50 (mediana) | < 500ms | < 1s | Prometheus histogram |
| P95 | < 2s | < 3s | Prometheus histogram |
| P99 | < 5s | < 8s | Prometheus histogram |

**Nota:** Latencia incluye STT + NLP + TTS cuando aplica (llamada completa E2E puede ser mayor).

### Error Rate

| Metrica | SLO | SLA | Medicion |
|---------|-----|-----|----------|
| Tasa de errores 5xx | < 0.5% | < 1% | Prometheus |
| Tasa de errores 4xx (no auth) | < 2% | < 5% | Prometheus |
| Precision STT | > 95% | > 90% | Muestreo manual |
| Precision NLP (intenciones) | > 90% | > 85% | Dashboard |

### Tiempo de Respuesta a Incidentes

| Severidad | SLO Respuesta | SLO Resolucion | SLA Resolucion |
|-----------|--------------|----------------|----------------|
| P0 - Critico | 5 min | 60 min | 4 horas |
| P1 - Alto | 15 min | 4 horas | 24 horas |
| P2 - Medio | 1 hora | 24 horas | 72 horas |
| P3 - Bajo | 4 horas | 72 horas | 7 dias |

---

## SLOs de Negocio

| Metrica | SLO (Objetivo) | Medicion |
|---------|---------------|----------|
| FCR (First Contact Resolution) | >= 70% | Dashboard diario |
| Tasa de escalacion a humano | <= 25% | Dashboard diario |
| AHT (Average Handle Time) | < 5 min | Dashboard diario |
| CSAT (Customer Satisfaction) | >= 4.5/5 | Encuesta post-llamada |
| Tiempo de respuesta ticket urgente | < 15 min | Sistema de tickets |
| Tiempo de respuesta ticket alto | < 1 hora | Sistema de tickets |

---

## Calculo del Error Budget

### Uptime 99.5% (SLO)

```
Periodo     | Tiempo total  | Downtime permitido
------------|---------------|-------------------
Por dia     | 24 horas      | 7.2 minutos
Por semana  | 168 horas     | 50.4 minutos
Por mes     | 730 horas     | 3.65 horas
Por ano     | 8,760 horas   | 43.8 horas
```

### Latencia P95 < 2s (SLO)

```
Objetivo: 95% de requests < 2 segundos
Quema de budget: Cada vez que P95 > 2s por >= 10 minutos
Alerta: Cuando se ha quemado > 50% del budget mensual
```

---

## Exclusiones del SLA

Los siguientes escenarios NO cuentan para el calculo del SLA:

1. **Mantenimiento programado:** Anunciado con >= 48h de anticipacion
2. **Fuerza mayor:** Desastres naturales, cortes de energia masivos
3. **Servicios externos:** Caidas de Google Cloud, Twilio, OpenAI (fuera de nuestro control)
4. **Ataques DDoS:** Si superan las capacidades de mitigacion configuradas
5. **Acciones del cliente:** Configuraciones incorrectas por parte del cliente

---

## Penalidades SLA (Si aplica)

| Incumplimiento | Penalidad |
|----------------|-----------|
| Uptime < 99.0% (mensual) | [Credito de servicio: X%] |
| Uptime < 98.0% (mensual) | [Credito de servicio: Y%] |
| Tiempo de resolucion P0 > 4h | [Credito de servicio: Z%] |

*Las penalidades especificas se definen en el contrato comercial.*

---

## Monitoreo y Reporte de SLOs

### Herramientas

- **Prometheus:** Metricas de latencia, error rate, uptime tecnico
- **Grafana:** Dashboard de SLOs en tiempo real
- **Uptime Kuma:** Uptime externo (desde fuera de la red interna)

### Reportes

| Reporte | Frecuencia | Audiencia | Canal |
|---------|-----------|-----------|-------|
| SLO Dashboard | Tiempo real | Equipo tecnico | Grafana |
| Reporte semanal | Semanal | Stakeholders | Email |
| Reporte mensual | Mensual | Alta direccion | Email + Reunion |
| Reporte de incidente | Post-incidente | Stakeholders | Email |

### Alertas de Error Budget

```
Budget quemado al 50% → Alerta WARNING en Slack
Budget quemado al 80% → Alerta CRITICA + reunion de equipo
Budget agotado → Freeze de cambios + foco en estabilidad
```

---

## Revision de SLOs

Los SLOs se revisan:

- **Mensualmente:** Ajustar umbrales basados en datos reales del mes anterior
- **Trimestralmente:** Revision formal con stakeholders
- **Post-incidente P0:** Si el incidente revela que el SLO no es representativo

**Proximo review:** [Fecha go-live + 30 dias]
**Responsable:** Tech Lead + Product Owner
