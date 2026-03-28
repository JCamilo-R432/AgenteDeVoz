# Production Readiness - AgenteDeVoz
**Version:** 1.0 | **Actualizado:** 2026-03-22

---

## Checklist de Production Readiness

### Codigo y Calidad

| Item | Estado | Evidencia |
|------|--------|-----------|
| Tests automatizados >= 150 | APROBADO | 200+ tests en 7 suites |
| Cobertura >= 70% | APROBADO | 78% (ver reports/coverage_report/) |
| 0 vulnerabilidades criticas | APROBADO | reports/security_report.md |
| Code review completado | [ ] | Completar antes de go-live |
| CHANGELOG actualizado | APROBADO | CHANGELOG.md |
| Deuda tecnica documentada | APROBADO | docs/QUALITY_METRICS.md |

### Infraestructura

| Item | Estado | Notas |
|------|--------|-------|
| Servidor provisionado | [ ] | Minimo: 4 vCPU, 8GB RAM, 100GB SSD |
| PostgreSQL 15 configurado | [ ] | Con backup automatico |
| Redis 7 configurado | [ ] | Con password |
| Nginx configurado | [ ] | HTTPS, rate limiting, security headers |
| SSL/TLS certificate | [ ] | Let's Encrypt o comercial |
| Firewall configurado | [ ] | Solo puertos 80, 443, 22 |
| Monitoreo activo | [ ] | Prometheus + Grafana |
| Alertas configuradas | [ ] | AlertManager + Pagerduty |
| Backup automatico | [ ] | Cron diario, retencion 30 dias |

### Configuracion

| Item | Estado | Notas |
|------|--------|-------|
| production_config.env completado | [ ] | Sin valores CAMBIAR_POR_* |
| Secrets en vault | [ ] | No en archivos versionados |
| .env fuera de git | APROBADO | .gitignore configurado |
| LOG_LEVEL=WARNING | [ ] | No DEBUG en produccion |
| APP_DEBUG=false | [ ] | Verificar en .env |

### Integraciones

| Integracion | Estado | Verificacion |
|-------------|--------|--------------|
| Twilio Voice | [ ] | Llamada de prueba completada |
| WhatsApp Business | [ ] | Plantillas aprobadas por Meta |
| SendGrid | [ ] | Dominio verificado (DKIM/SPF) |
| Google Cloud STT/TTS | [ ] | Credenciales de produccion |
| HubSpot CRM | [ ] | API key de produccion |
| Webhooks registrados | [ ] | Twilio + WhatsApp callbacks |

### Seguridad

| Item | Estado | Notas |
|------|--------|-------|
| Passwords cambiados | [ ] | Admin, DB, Redis |
| 2FA habilitado | [ ] | Para todos los admins |
| Rate limiting activo | [ ] | Nginx + Redis |
| CORS configurado | [ ] | Origenes especificos, no * |
| Security headers | [ ] | HSTS, X-Frame-Options, etc. |
| bandit sin issues altos | APROBADO | Ver reports/security_report.md |

### Operaciones

| Item | Estado | Notas |
|------|--------|-------|
| Runbooks escritos y revisados | APROBADO | operations/ |
| Equipo de on-call configurado | [ ] | Rotacion definida |
| Pagerduty configurado | [ ] | Escalacion automatica |
| Plan de rollback probado | [ ] | Ejecutar en staging antes |
| Backups restaurados y verificados | [ ] | Prueba de restauracion |
| Health monitor activo | [ ] | scripts/health_monitor.sh |

### Capacitacion

| Item | Estado | Notas |
|------|--------|-------|
| Agentes de soporte capacitados | [ ] | training/agent_training.md |
| Administradores capacitados | [ ] | training/admin_guide.md |
| DevOps capacitado en runbooks | [ ] | operations/ |
| Manual de usuario publicado | APROBADO | training/user_manual.md |

---

## Score de Production Readiness

Para calcular el score, marcar cada item completado:

```
Total items: ~50
Items completados: [X]
Score: [X/50 * 100]%

Minimo requerido para go-live: 90% (45/50 items)
Items criticos (sin excepcion): Seguridad, Integraciones, On-Call
```

---

## Items No-Negociables (Bloqueantes para Go-Live)

Los siguientes items DEBEN estar completados antes del lanzamiento:

1. [ ] 0 vulnerabilidades criticas de seguridad
2. [ ] Production.env sin valores CAMBIAR_POR_*
3. [ ] SSL/TLS funcionando en produccion
4. [ ] Backup automatico configurado y probado
5. [ ] Equipo de on-call con contactos actualizados
6. [ ] Plan de rollback probado en staging
7. [ ] Twilio webhook probado con llamada real
8. [ ] Smoke tests pasando en produccion

---

## Aprobacion Final

| Rol | Nombre | Aprobacion | Fecha |
|-----|--------|------------|-------|
| Tech Lead | | [ ] | |
| DevOps Lead | | [ ] | |
| QA Lead | | [ ] | |
| Product Owner | | [ ] | |
| Sponsor | | [ ] | |

**Go-Live aprobado:** [ ]
**Fecha aprobada para go-live:** ___________________
