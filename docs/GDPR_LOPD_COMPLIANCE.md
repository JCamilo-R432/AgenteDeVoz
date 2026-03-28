# GDPR/LOPD Compliance - AgenteDeVoz

Gap #9: Cumplimiento GDPR (UE), LOPD-GDD (Espana) y Ley 1581/2012 (Colombia).

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/compliance/gdpr_compliance.py` | Derechos ARCO+, notificacion brechas, DPIA |
| `src/compliance/lopd_compliance.py` | Autoridades ES/CO, transferencias internacionales |
| `src/compliance/consent_manager.py` | Gestion de consentimientos por proposito |
| `src/compliance/data_export.py` | Exportacion JSON/CSV/ZIP (Art. 20) |
| `src/compliance/data_deletion.py` | Borrado/anonimizacion (Art. 17) |

## Derechos del interesado implementados

| Derecho | Articulo GDPR | Plazo |
|---------|--------------|-------|
| Acceso | Art. 15 | 30 dias |
| Rectificacion | Art. 16 | 30 dias |
| Supresion | Art. 17 | 30 dias |
| Portabilidad | Art. 20 | 30 dias |
| Oposicion | Art. 21 | Inmediato |
| Registro actividades | Art. 30 | Continuo |
| Notificacion brecha | Art. 33-34 | 72 horas |
| DPIA | Art. 35 | Pre-tratamiento |

## Uso rapido

```python
from src.compliance.gdpr_compliance import GDPRComplianceManager, DSRType

gdpr = GDPRComplianceManager()

# Solicitud de acceso
dsr = gdpr.submit_dsr("user123", DSRType.ACCESS, "Quiero ver mis datos")
gdpr.handle_access_request(dsr.dsr_id, user_data)

# Notificar brecha de datos
breach = gdpr.report_data_breach(
    description="Acceso no autorizado a grabaciones",
    affected_users=150,
    data_categories=["voice_recordings"],
    source="security_scan",
)
# Deadline automatico: 72 horas para notificar autoridad
```

## Propositos de consentimiento

- `voice_service` — Contrato (obligatorio)
- `analytics` — Interes legitimo (TTL 365d)
- `marketing` — Consentimiento (TTL 365d)
- `voice_biometrics` — Consentimiento (TTL 180d, dato sensible)
- `recording_training` — Consentimiento (TTL 365d)
