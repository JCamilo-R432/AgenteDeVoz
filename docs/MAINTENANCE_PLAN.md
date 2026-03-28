# Plan de Mantenimiento - AgenteDeVoz
**Version:** 1.0 | **Actualizado:** 2026-03-22

---

## Principios del Plan

1. **Mantenimiento preventivo > correctivo:** Mejor actuar antes de que falle
2. **Automatizar todo lo posible:** Reducir errores humanos y carga operativa
3. **Comunicar siempre:** El equipo y stakeholders deben saber que mantenimientos hay
4. **Documentar cambios:** Cada mantenimiento queda registrado

---

## Calendario de Mantenimiento

### Diario (Automatico)

| Hora | Tarea | Script | Tiempo |
|------|-------|--------|--------|
| 02:00 AM | Backup de base de datos | `scripts/backup.sh` | ~10 min |
| 02:30 AM | Limpieza de logs viejos (> 30 dias) | Cron | ~2 min |
| Cada 5 min | Health check | `scripts/health_monitor.sh` | Continuo |
| Cada hora | Metricas exportadas a Prometheus | Automatico | Continuo |

```bash
# Cron para mantenimiento diario
# /etc/cron.d/agentevoz-daily
0 2 * * * agentevoz /opt/agentevoz/scripts/backup.sh >> /var/log/agentevoz/backup.log 2>&1
30 2 * * * agentevoz find /var/log/agentevoz -name "*.log" -mtime +30 -delete
```

### Semanal (Martes a las 2 AM)

| Tarea | Responsable | Duracion | Impacto |
|-------|-------------|----------|---------|
| VACUUM de base de datos | Automatico (cron) | ~15 min | Sin impacto |
| Revision de dependencias con outdated | DevOps | Manual | Sin impacto |
| Revision de logs de seguridad | DevOps | Manual | Sin impacto |
| Verificacion de certificado SSL | Automatico | ~1 min | Sin impacto |
| Backup de configuracion | Automatico | ~2 min | Sin impacto |

```bash
# Cron semanal
# /etc/cron.d/agentevoz-weekly
0 2 * * 2 postgres psql -U agentevoz_user -d agentevoz_production -c "VACUUM ANALYZE;" >> /var/log/agentevoz/vacuum.log 2>&1
```

### Mensual (Primer domingo del mes, 2 AM)

| Tarea | Responsable | Duracion | Requiere Downtime |
|-------|-------------|----------|-------------------|
| Actualizacion de parches de seguridad del OS | DevOps | ~30 min | Posible (reboot) |
| Actualizacion de dependencias Python (patch) | DevOps | ~15 min | Reload |
| Rotacion de credenciales Redis | DevOps | ~5 min | Reload |
| Prueba de backup (restauracion en entorno test) | DevOps | ~30 min | No |
| Revision y actualizacion de runbooks | Ops Lead | Manual | No |
| Revision de reglas de alertas | DevOps | Manual | No |

**Ventana de mantenimiento mensual:** Primer domingo 2 AM - 6 AM (Colombia)
**Aviso requerido:** 48 horas antes

### Trimestral (Primer domingo del trimestre)

| Tarea | Responsable | Duracion | Requiere Downtime |
|-------|-------------|----------|-------------------|
| Actualizacion de versiones mayores Python/FastAPI | DevOps + Dev | ~2 horas | Si (ventana) |
| Rotacion de JWT secret + App secret | DevOps | ~10 min | Reload |
| Prueba de disaster recovery | DevOps | ~1 hora | No (staging) |
| Auditoria de usuarios admin | Admin | ~30 min | No |
| Revision de SLOs y ajuste de umbrales | Tech Lead | Manual | No |
| Actualizacion de documentacion | Todos | Manual | No |

**Ventana de mantenimiento trimestral:** Primer domingo del trimestre 2 AM - 8 AM
**Aviso requerido:** 1 semana antes

### Anual

| Tarea | Responsable | Notas |
|-------|-------------|-------|
| Auditoria de seguridad externa | Security | Pentesting |
| Revision de arquitectura | Tech Lead | Evaluar mejoras |
| Capacitacion de refresco del equipo | Ops Lead | Nuevos miembros |
| Revision del plan de DR | Tech Lead | Actualizar si hay cambios |
| Renovacion de contratos de soporte | PO + Legal | Twilio, Google, etc. |

---

## Procedimiento de Mantenimiento Con Downtime

Seguir cuando el mantenimiento requiere interrumpir el servicio:

```bash
# 1. Notificar (con >= 48h de anticipacion para mensual, 1 semana para trimestral)
# Ver: launch/communication_plan.md para templates

# 2. Activar pagina de mantenimiento en Nginx
# Descomentar en nginx.conf: return 503;
sudo nginx -t && sudo systemctl reload nginx

# 3. Esperar que las sesiones activas terminen (o terminarlas si urgente)
curl -H "Authorization: Bearer ${ADMIN_TOKEN}" https://[dominio]/api/v1/sessions | \
  python -c "import sys,json; sessions=json.load(sys.stdin); print(f'Sesiones activas: {len(sessions)}')"

# 4. Hacer backup antes del mantenimiento
bash scripts/backup.sh

# 5. Ejecutar mantenimiento
[TAREAS DE MANTENIMIENTO]

# 6. Verificar que todo funciona
bash scripts/post_deploy_verify.sh

# 7. Desactivar pagina de mantenimiento
# Comentar el return 503 en nginx.conf
sudo nginx -t && sudo systemctl reload nginx

# 8. Comunicar fin del mantenimiento
```

---

## Mantenimiento de Dependencias

### Politica de Actualizaciones

| Tipo | Frecuencia | Proceso |
|------|-----------|---------|
| Patch (1.2.3 → 1.2.4) | Mensual o segun CVE | Actualizar + tests + deploy |
| Minor (1.2.x → 1.3.0) | Trimestral | Revision + tests completos + deploy planificado |
| Major (1.x → 2.0) | Segun necesidad | Evaluacion completa + planificacion dedicada |
| CVE critico | Inmediato (< 48h) | Proceso de hotfix urgente |

### Monitoreo de CVEs

```bash
# Verificacion semanal automatica
safety check --output json > /tmp/safety_report.json 2>/dev/null
VULNS=$(python -c "import json; d=json.load(open('/tmp/safety_report.json')); print(len(d.get('vulnerabilities', [])))")
if [[ $VULNS -gt 0 ]]; then
  echo "ATENCION: $VULNS vulnerabilidades encontradas en dependencias"
fi
```

---

## Plan de Capacidad

### Indicadores de Necesidad de Escalar

| Indicador | Umbral | Accion |
|-----------|--------|--------|
| CPU promedio > 70% por 1 semana | Evaluar escalar verticalmente | Tech Lead + DevOps |
| RAM > 80% promedio | Evaluar escalar verticalmente | Tech Lead + DevOps |
| Llamadas concurrentes cerca de 50 | Evaluar escalar horizontalmente | Tech Lead |
| Latencia P95 aumentando semana a semana | Optimizar o escalar | Tech Lead |
| Storage > 70% | Limpiar o ampliar disco | DevOps |

### Escalado Planificado

Si el crecimiento es predecible (ej: campaña de marketing):
1. Revisar capacidad actual vs carga esperada
2. Escalar recursos 24h antes del evento
3. Monitoreo intensivo durante el evento
4. Reducir recursos post-evento si aplica

---

## Registro de Mantenimientos

| Fecha | Tipo | Descripcion | Responsable | Incidencias |
|-------|------|-------------|-------------|-------------|
| 2026-03-22 | Inicial | Setup produccion | DevOps | Ninguna |
| [Fecha] | [Tipo] | [Descripcion] | [Nombre] | [Si/No] |

---

**Responsable del plan:** DevOps Lead
**Revision del plan:** Trimestral
**Proxima revision:** [Fecha go-live + 90 dias]
