# Cumplimiento Normativo por Industria - AgenteDeVoz
**Version:** 1.0 | **Actualizado:** 2026-03-22

---

## Introduccion

AgenteDeVoz opera en el sector de telecomunicaciones/atencion al cliente en Colombia. Este documento describe los marcos normativos relevantes y como el sistema los cumple, con codigo de referencia para implementaciones especificas.

---

## 1. Ley 1581 de 2012 - Proteccion de Datos Personales (Colombia)

**Autoridad regulatoria:** Superintendencia de Industria y Comercio (SIC)
**Sitio:** www.sic.gov.co

### Requisitos Principales

| Articulo | Requisito | Implementacion |
|----------|-----------|----------------|
| Art. 4 | Principios del tratamiento (finalidad, libertad, veracidad) | Politica de Privacidad + consentimiento inicial |
| Art. 8 | Derechos del titular (acceso, rectificacion, supresion) | Endpoint /api/v1/data-subject-requests |
| Art. 17 | Obligaciones del responsable | DPO designado, registro de tratamiento |
| Art. 25 | Transferencias internacionales | DPAs con Google, OpenAI, Twilio |

### Implementacion en Codigo

```python
# src/compliance/gdpr_colombia.py
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ColombiaPrivacyCompliance:
    """
    Cumplimiento con Ley 1581/2012 y Decreto 1377/2013.
    Gestiona derechos de titulares de datos personales.
    """

    DATA_RETENTION_POLICIES = {
        "voice_recordings": timedelta(seconds=0),    # Solo durante la llamada
        "transcripts": timedelta(days=90),
        "support_tickets": timedelta(days=365 * 5),  # 5 anos (Estatuto Consumidor)
        "billing_data": timedelta(days=365 * 10),    # 10 anos (obligacion fiscal)
        "system_logs": timedelta(days=90),
        "marketing_consent": None,  # Hasta revocacion
    }

    def __init__(self, db_connection=None):
        self._db = db_connection
        self._requests_log: List[Dict] = []

    def handle_data_subject_request(
        self,
        request_type: str,
        titular_id: str,
        verification_data: Dict,
    ) -> Dict:
        """
        Maneja una solicitud de derechos del titular.

        Args:
            request_type: "access", "rectification", "deletion", "revoke_consent"
            titular_id: Identificador del titular (numero de telefono o documento)
            verification_data: Datos para verificar identidad del titular

        Returns:
            Resultado de la solicitud con referencia para seguimiento
        """
        request_id = hashlib.sha256(
            f"{titular_id}:{request_type}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]

        # Registrar la solicitud
        entry = {
            "request_id": request_id,
            "type": request_type,
            "titular_id": titular_id,
            "received_at": datetime.utcnow().isoformat(),
            "status": "received",
            "deadline": (datetime.utcnow() + timedelta(days=15)).isoformat(),
        }
        self._requests_log.append(entry)

        logger.info(f"Solicitud de derechos del titular recibida: {request_type} | ID: {request_id}")

        if request_type == "deletion":
            return self._process_deletion_request(titular_id, request_id)
        elif request_type == "access":
            return self._process_access_request(titular_id, request_id)
        elif request_type == "revoke_consent":
            return self._process_consent_revocation(titular_id, request_id)

        return {"request_id": request_id, "status": "received", "deadline_days": 15}

    def _process_deletion_request(self, titular_id: str, request_id: str) -> Dict:
        """
        Procesa solicitud de supresion de datos (derecho al olvido).
        Solo anonimiza datos que no tienen obligacion legal de retention.
        """
        # En produccion: ejecutar en DB
        # UPDATE conversations SET phone_number = 'DELETED', session_data = NULL
        # WHERE customer_phone = titular_id AND created_at < NOW() - INTERVAL '5 years'
        # Datos con obligacion legal (tickets, facturacion) se anonomizan, no eliminan
        logger.info(f"Procesando supresion de datos para titular: {titular_id[:4]}****")
        return {
            "request_id": request_id,
            "status": "processing",
            "message": "Los datos seran anonimizados en 15 dias habiles. "
                       "Datos con obligacion legal de retencion seran anonimizados, no eliminados.",
            "deadline": (datetime.utcnow() + timedelta(days=15)).isoformat(),
        }

    def _process_access_request(self, titular_id: str, request_id: str) -> Dict:
        """Procesa solicitud de acceso a datos propios."""
        return {
            "request_id": request_id,
            "status": "processing",
            "message": "Reporte de datos personales enviado al email registrado en 10 dias habiles.",
        }

    def _process_consent_revocation(self, titular_id: str, request_id: str) -> Dict:
        """Procesa revocacion de consentimiento para tratamiento."""
        return {
            "request_id": request_id,
            "status": "completed",
            "message": "Consentimiento revocado. Solo se mantendran datos con base legal distinta al consentimiento.",
        }

    def check_retention_compliance(self, data_category: str, created_at: datetime) -> bool:
        """Verifica si un dato debe ser eliminado segun la politica de retencion."""
        retention = self.DATA_RETENTION_POLICIES.get(data_category)
        if retention is None:
            return True  # Sin limite (ej: marketing hasta revocacion)
        if retention.total_seconds() == 0:
            return False  # Eliminar inmediatamente
        return datetime.utcnow() < created_at + retention
```

---

## 2. PCI-DSS - Seguridad de Datos de Tarjetas de Pago

**Nota:** AgenteDeVoz **NO procesa** datos de tarjetas de credito/debito directamente. Si en el futuro se agrega funcionalidad de pagos, se debe:

1. Usar un Payment Service Provider (PSP) certificado PCI-DSS (ej: Wompi, PayU, Stripe)
2. Nunca almacenar datos de tarjeta en nuestra infraestructura
3. Usar tokenizacion para referencias de pago

### Medidas Actuales Alineadas con PCI-DSS

```python
# Medidas de seguridad alineadas con PCI-DSS (relevantes aunque no procesemos tarjetas)

class PCIDSSAlignedSecurity:
    """
    Controles de seguridad alineados con PCI-DSS.
    Aplicables a cualquier sistema que maneje datos sensibles.
    """

    # PCI-DSS Req 6.4: Desarrollar software de forma segura
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    # PCI-DSS Req 8: Identificar y autenticar acceso a componentes
    PASSWORD_POLICY = {
        "min_length": 12,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_numbers": True,
        "require_special": True,
        "max_age_days": 90,
        "history_count": 12,  # No repetir ultimas 12 contrasenas
        "lockout_attempts": 6,
        "lockout_duration_minutes": 30,
    }

    # PCI-DSS Req 10: Rastrear y monitorear accesos
    AUDIT_LOG_REQUIREMENTS = {
        "log_user_access": True,
        "log_failed_attempts": True,
        "log_admin_actions": True,
        "log_data_access": True,
        "retention_days": 365,
    }
```

---

## 3. GDPR - Reglamento General de Proteccion de Datos (UE)

**Aplicabilidad:** Si el sistema atiende a ciudadanos de la Union Europea o residentes en paises del EEE.
**Autoridad:** Agencia Espanola de Proteccion de Datos (si hay usuarios en Espana)

```python
class GDPRCompliance:
    """
    Controles de cumplimiento GDPR para usuarios de la UE.
    Activa controles adicionales sobre la base de Ley 1581.
    """

    LAWFUL_BASIS = {
        "service_provision": "Art. 6(1)(b) - Ejecucion del contrato",
        "legal_obligation": "Art. 6(1)(c) - Obligacion legal",
        "legitimate_interest": "Art. 6(1)(f) - Interes legitimo",
        "consent": "Art. 6(1)(a) - Consentimiento",
    }

    # GDPR Art. 17 - Derecho al olvido (mas estricto que Ley 1581)
    EU_DELETION_DEADLINE_DAYS = 30  # vs 15 dias Colombia

    # GDPR Art. 33 - Notificacion de brechas de seguridad
    BREACH_NOTIFICATION_HOURS = 72  # A la autoridad supervisora

    # GDPR Art. 25 - Privacidad desde el diseno
    PRIVACY_BY_DESIGN_CONTROLS = [
        "Minimizacion de datos: solo recopilar lo estrictamente necesario",
        "Seudonimizacion de logs: reemplazar IDs reales con hashes",
        "Cifrado en reposo para todos los datos personales",
        "Acceso con menos privilegios necesarios",
        "Evaluacion de impacto (DPIA) antes de nuevos tratamientos de alto riesgo",
    ]

    def assess_breach(self, incident: dict) -> dict:
        """Evalua si un incidente constituye brecha notificable segun GDPR."""
        is_notifiable = (
            incident.get("personal_data_exposed", False)
            and incident.get("affected_users", 0) > 0
            and incident.get("risk_level") in ("high", "critical")
        )

        return {
            "is_notifiable_to_authority": is_notifiable,
            "notification_deadline": "72 horas desde conocimiento del incidente",
            "notify_affected_individuals": incident.get("risk_level") == "critical",
            "documentation_required": True,
            "next_steps": [
                "Documentar el incidente en el registro de brechas",
                "Evaluar impacto sobre derechos y libertades de los afectados",
                "Notificar a la autoridad supervisora si es notificable",
                "Notificar a los afectados si hay riesgo alto para sus derechos",
            ],
        }
```

---

## 4. ISO 27001 - Gestion de Seguridad de la Informacion

**Estado:** Alineacion parcial. Certificacion formal recomendada para contratos enterprise.

### Controles Implementados (Anexo A)

| Control ISO 27001 | Descripcion | Estado |
|-------------------|-------------|--------|
| A.9.4.1 Restriccion de acceso | RBAC con 5 roles | Implementado |
| A.9.4.2 Procedimientos de login | JWT + rate limiting | Implementado |
| A.10.1.1 Politica de cifrado | TLS 1.3 + AES-256 | Implementado |
| A.12.4 Logging y monitoreo | Prometheus + Loki | Implementado |
| A.12.6.1 Gestion de vulnerabilidades | bandit + safety en CI | Implementado |
| A.14.2.1 SDLC seguro | GitHub Actions + code review | Implementado |
| A.16.1 Gestion de incidentes | Runbook de incidentes | Documentado |
| A.17.1 Continuidad del negocio | Plan de rollback 3 niveles | Documentado |
| A.18.1.4 Privacidad | Ley 1581 + Politica de Privacidad | Implementado |

### Roadmap hacia Certificacion

```
Fase 1 (Q1 2026): Alineacion tecnica - COMPLETADO
  - Implementar controles tecnicos del Anexo A
  - Documentar politicas de seguridad

Fase 2 (Q2 2026): Sistema de Gestion
  - Establecer SGSI formal
  - Definir alcance y objetivos de seguridad
  - Auditorias internas

Fase 3 (Q3 2026): Auditoria de Certificacion
  - Auditoria externa por organismo acreditado
  - Cierre de no conformidades
  - Certificacion ISO 27001

Costo estimado: $15,000 - $30,000 USD (auditoria + implementacion)
```

---

## 5. CRC - Comision de Regulacion de Comunicaciones (Colombia)

**Aplicabilidad:** Si el servicio opera sobre redes de telecomunicaciones en Colombia.

### Requisitos Relevantes

| Norma CRC | Requisito | Implementacion |
|-----------|-----------|----------------|
| Res. 5050/2016 | Calidad del servicio al usuario | SLA 99.0%, tiempos de respuesta documentados |
| Res. 4225/2013 | Mecanismos de atencion al usuario | Sistema de tickets + escalacion |
| Res. 3066/2011 | Regimen de proteccion al usuario | Runbook de quejas y reclamos |

```python
class CRCCompliance:
    """
    Cumplimiento con regulacion CRC de Colombia.
    """

    # Tiempos maximos de atencion segun CRC
    MAX_RESPONSE_TIMES = {
        "complaints": timedelta(days=15),       # Quejas: 15 dias habiles
        "claims": timedelta(days=15),           # Reclamaciones: 15 dias habiles
        "petitions": timedelta(days=15),        # Peticiones: 15 dias habiles
        "urgent_interruption": timedelta(hours=8),  # Interrupciones urgentes: 8 horas
    }

    def is_within_crc_deadline(self, ticket_type: str, created_at: datetime) -> bool:
        """Verifica si un ticket esta dentro del plazo CRC."""
        max_time = self.MAX_RESPONSE_TIMES.get(ticket_type)
        if not max_time:
            return True
        return datetime.utcnow() < created_at + max_time
```

---

## 6. Checklist de Cumplimiento Normativo

### Antes del Go-Live

- [ ] Politica de Privacidad revisada por abogado especializado en datos Colombia
- [ ] Terminos de Servicio revisados por abogado
- [ ] DPAs firmados con: Google Cloud, OpenAI, Anthropic, Twilio, Meta, SendGrid, HubSpot
- [ ] DPO designado y registrado ante la SIC
- [ ] Registro de actividades de tratamiento (RAT) completado
- [ ] Consentimiento inicial grabado o documentado para cada usuario
- [ ] Proceso de derechos del titular (ARCO) operativo y probado
- [ ] Politica de retencion de datos implementada en base de datos
- [ ] Plan de respuesta a brechas documentado y probado
- [ ] Notificacion a SIC si tratamiento requiere registro previo

### Trimestral

- [ ] Revision del RAT (Registro de Actividades de Tratamiento)
- [ ] Verificar vigencia de DPAs con proveedores
- [ ] Auditoria de accesos a datos personales
- [ ] Revision de solicitudes ARCO recibidas y tiempos de respuesta
- [ ] Actualizacion de la politica de privacidad si hay nuevos tratamientos

---

## 7. Contactos de Autoridades Regulatorias

| Autoridad | Area | Contacto |
|-----------|------|----------|
| SIC - Delegatura para la Proteccion de Datos | Datos personales | www.sic.gov.co |
| CRC - Comision de Regulacion de Comunicaciones | Telecomunicaciones | www.crcom.gov.co |
| MinTIC - Ministerio de TIC | Politicas digitales | www.mintic.gov.co |
| SFC - Superintendencia Financiera | Si aplica servicios financieros | www.superfinanciera.gov.co |

---

**Nota Legal:** Este documento es de referencia tecnica. Para decisiones legales, consultar con abogado especializado en derecho digital y regulacion de telecomunicaciones en Colombia.

**Proxima revision:** Trimestral (junio 2026)
**Responsable:** Tech Lead + Asesor Legal
