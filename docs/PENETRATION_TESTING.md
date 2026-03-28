# Penetration Testing - AgenteDeVoz

Gap #8: Framework de pruebas de penetracion y auditoria de seguridad.

## Modulos

| Archivo | Descripcion |
|---------|-------------|
| `src/security/penetration_testing.py` | Framework principal con OWASP Top 10 |
| `src/security/vulnerability_scanner.py` | Escaneo CVE con pip-audit |
| `src/security/security_audit_tools.py` | Verificacion TLS, auth, cifrado |
| `src/security/third_party_audit.py` | Auditorias de terceros |

## Uso rapido

```python
from src.security.penetration_testing import PenetrationTestingFramework, VulnerabilitySeverity

ptf = PenetrationTestingFramework(target="http://localhost:8000")

# Escaneo automatizado (requiere herramientas externas)
results = ptf.run_automated_scan(skip_external=True)

# Registrar vulnerabilidad manual
ptf.register_manual_vulnerability(
    title="SQL Injection en login",
    severity=VulnerabilitySeverity.HIGH,
    cwe="CWE-89",
    owasp_category="A03:2021",
    description="Input sin sanitizar en query de autenticacion",
    affected_component="POST /api/auth/login",
    cvss_score=8.5,
)

report = ptf.generate_audit_report()
print(f"Total vulnerabilidades: {report['total_vulnerabilities']}")
print(f"Risk score: {report['risk_score']}")
```

## Ejecutar auditoria completa

```bash
bash scripts/run_security_audit.sh
```

## Herramientas externas requeridas (produccion)

- `bandit` — Analisis estatico Python: `pip install bandit`
- `pip-audit` — CVE scanning: `pip install pip-audit`
- `safety` — Seguridad de dependencias: `pip install safety`
- `nikto` — Scanner web: `apt install nikto`

## Categorias OWASP Top 10 cubiertas

A01:2021 Broken Access Control, A02 Cryptographic Failures, A03 Injection,
A04 Insecure Design, A05 Security Misconfiguration, A06 Vulnerable Components,
A07 Authentication Failures, A08 Integrity Failures, A09 Logging Failures,
A10 SSRF.
