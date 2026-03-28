# SLA — Acuerdo de Nivel de Servicio
## Agente de Voz Inteligente

**Versión:** 1.0 | **Vigencia:** A partir de la firma del contrato

---

## 1. Definiciones

- **Uptime:** Porcentaje de tiempo en que el Servicio está disponible y funcional en un mes calendario.
- **Downtime:** Período en que el Servicio no está disponible para el Cliente, medido en minutos.
- **Incidente:** Degradación o interrupción del Servicio reportada o detectada.
- **Mantenimiento programado:** Ventana de mantenimiento notificada con al menos 24 horas de anticipación, no cuenta como downtime.
- **Tiempo de respuesta:** Tiempo desde que el Proveedor recibe la notificación hasta que confirma que está trabajando en el incidente.
- **Tiempo de resolución:** Tiempo desde la notificación hasta la restauración completa del Servicio.

---

## 2. Disponibilidad Garantizada

| Plan | Uptime garantizado | Downtime máx/mes |
|------|--------------------|------------------|
| Basic | 99,5% | ~3,6 horas |
| Pro | 99,7% | ~2,2 horas |
| Enterprise | 99,9% | ~44 minutos |

**Fórmula:** `Uptime% = (Minutos totales - Downtime) / Minutos totales × 100`

---

## 3. Tiempos de Respuesta y Resolución

### Severidad de Incidentes

| Nivel | Descripción | Ejemplo |
|-------|-------------|---------|
| **Crítico** | Servicio completamente no disponible | API no responde, DB caída |
| **Alto** | Funcionalidad principal degradada | OTP no se envía, pedidos no cargando |
| **Medio** | Funcionalidad secundaria afectada | Dashboard lento, logs incompletos |
| **Bajo** | Problema menor o consulta | Error cosmético, pregunta de configuración |

### SLAs por Severidad

| Nivel | Tiempo de Respuesta | Tiempo de Resolución |
|-------|---------------------|----------------------|
| Crítico | 1 hora hábil | 4 horas hábiles |
| Alto | 4 horas hábiles | 24 horas hábiles |
| Medio | 1 día hábil | 3 días hábiles |
| Bajo | 2 días hábiles | 7 días hábiles |

*Horas hábiles: Lunes a viernes, 8:00 AM – 6:00 PM, hora Colombia (UTC-5). Excluye festivos nacionales colombianos.*

---

## 4. Canales de Soporte y Escalación

```
Nivel 1: WhatsApp Business → Respuesta inicial
Nivel 2: Email soporte@[dominio] → Soporte técnico
Nivel 3: Videollamada urgente → Incidentes críticos
```

**Para incidentes críticos fuera de horario:** WhatsApp con mensaje "URGENTE: [descripción]"

---

## 5. Compensaciones por Incumplimiento

Si el Uptime mensual cae por debajo del garantizado:

| Uptime real | Crédito sobre mensualidad |
|-------------|--------------------------|
| 99,0% – 99,49% | 10% |
| 98,0% – 98,99% | 25% |
| 95,0% – 97,99% | 50% |
| < 95,0% | 100% (un mes gratis) |

**Condiciones para reclamar crédito:**
- El Cliente debe reportar el incidente durante o inmediatamente después del downtime
- La reclamación debe hacerse dentro de los 5 días hábiles siguientes al incidente
- Los créditos se aplican a la siguiente factura, no son reembolsables en efectivo

---

## 6. Exclusiones del SLA

El Proveedor **no** será responsable de downtime causado por:

- Mantenimiento programado (notificado con 24h de anticipación)
- Fuerza mayor (terremotos, inundaciones, guerras, pandemias)
- Fallas en el proveedor de internet del Cliente
- Ataques DDoS de gran escala (> 10 Gbps)
- Acciones del Cliente (configuraciones incorrectas, abuso de la API)
- Fallas en servicios de terceros fuera del control del Proveedor (Twilio, OpenAI, etc.)
- Expiración del certificado SSL por falta de configuración del Cliente

---

## 7. Monitoreo y Reportes

**7.1 Herramientas de monitoreo:**
- **UptimeRobot:** Verificación cada 5 minutos desde múltiples ubicaciones
- **Health Check endpoint:** `GET /api/v1/health` retorna estado de todos los servicios
- **Alertas automáticas:** El Proveedor recibe notificaciones de caída en < 5 minutos

**7.2 Reporte mensual de disponibilidad:**
El Proveedor enviará al Cliente un resumen mensual que incluye:
- % de uptime del mes
- Incidentes ocurridos y tiempos de resolución
- Tiempo de respuesta promedio de la API (ms)
- Cambios o mejoras realizadas

**7.3 Dashboard de estado (próximamente):**
El Cliente podrá consultar el estado en tiempo real en `status.[dominio-del-proveedor].com`

---

## 8. Proceso de Reporte de Incidentes

```
1. Cliente detecta problema
2. Cliente envía WhatsApp/Email con:
   - Descripción del problema
   - Hora de inicio (aproximada)
   - Screenshots/logs si los tiene
3. Proveedor confirma recepción (dentro del tiempo de respuesta)
4. Proveedor investiga y actualiza al Cliente cada hora
5. Proveedor resuelve y notifica cierre del incidente
6. Post-mortem: Para incidentes Críticos, el Proveedor envía análisis
   de causa raíz en 48 horas
```

---

## 9. Mantenimiento Programado

- **Notificación:** Con al menos 24 horas de anticipación
- **Ventana preferida:** 2:00 AM – 5:00 AM (hora Colombia)
- **Duración máxima:** 2 horas por evento
- **Frecuencia máxima:** 2 veces por mes
- **No cuenta** como downtime para el cálculo de uptime

---

*Este SLA forma parte integral del Contrato de Servicio. En caso de conflicto, prevalece el Contrato.*
