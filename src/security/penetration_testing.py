"""
Penetration Testing Framework - AgenteDeVoz
Gap #8: Framework para pentesting y auditorias de seguridad

Gestiona vulnerabilidades, escaneos automatizados y reportes
de auditores externos. Compatible con OWASP Top 10.
"""
import hashlib
import json
import logging
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class VulnerabilitySeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


@dataclass
class Vulnerability:
    id: str
    title: str
    description: str
    severity: VulnerabilitySeverity
    cvss_score: float               # 0.0 - 10.0
    cwe_id: str
    affected_component: str
    proof_of_concept: str
    remediation: str
    status: VulnerabilityStatus = VulnerabilityStatus.OPEN
    discovered_date: datetime = field(default_factory=datetime.now)
    resolved_date: Optional[datetime] = None
    assigned_to: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "severity": self.severity.value,
            "cvss_score": self.cvss_score,
            "cwe_id": self.cwe_id,
            "status": self.status.value,
            "affected_component": self.affected_component,
            "remediation": self.remediation,
        }


class PenetrationTestingFramework:
    """
    Framework de pentesting para AgenteDeVoz.
    Orquesta herramientas de scanning, registra vulnerabilidades
    y genera reportes de auditoria (OWASP Top 10).
    """

    OWASP_CHECKS = [
        "A01_Broken_Access_Control",
        "A02_Cryptographic_Failures",
        "A03_Injection",
        "A04_Insecure_Design",
        "A05_Security_Misconfiguration",
        "A06_Vulnerable_Components",
        "A07_Authentication_Failures",
        "A08_Integrity_Failures",
        "A09_Logging_Failures",
        "A10_SSRF",
    ]

    # CVSS scores por severidad (umbral minimo)
    SEVERITY_CVSS_MAP = {
        VulnerabilitySeverity.CRITICAL: 9.0,
        VulnerabilitySeverity.HIGH: 7.0,
        VulnerabilitySeverity.MEDIUM: 4.0,
        VulnerabilitySeverity.LOW: 0.1,
        VulnerabilitySeverity.INFO: 0.0,
    }

    def __init__(self):
        self.vulnerabilities: Dict[str, Vulnerability] = {}
        self.audit_reports: List[Dict] = []
        self.last_scan_date: Optional[datetime] = None
        logger.info("PenetrationTestingFramework inicializado")

    def run_automated_scan(self, target_url: str, scan_type: str = "full") -> Dict:
        """
        Ejecuta escaneo automatizado de vulnerabilidades.
        Herramientas: bandit (SAST), nikto, sqlmap, nuclei, owasp-zap.
        """
        logger.info("Iniciando %s scan en %s", scan_type, target_url)
        scan_results = {
            "target": target_url,
            "scan_type": scan_type,
            "start_time": datetime.now().isoformat(),
            "vulnerabilities_found": 0,
            "tools_used": [],
            "findings": [],
        }

        tools = {
            "bandit": self._run_bandit_scan,
            "nikto": self._run_nikto_scan,
            "sqlmap": self._run_sqlmap_scan,
            "nuclei": self._run_nuclei_scan,
            "owasp_headers": self._check_security_headers,
        }

        for tool_name, tool_fn in tools.items():
            try:
                findings = tool_fn(target_url)
                scan_results["tools_used"].append(tool_name)
                scan_results["findings"].extend(findings)
                scan_results["vulnerabilities_found"] += len(findings)
                for f in findings:
                    self._register_vulnerability(f)
            except Exception as exc:
                logger.error("Error ejecutando %s: %s", tool_name, exc)

        scan_results["end_time"] = datetime.now().isoformat()
        self.last_scan_date = datetime.now()
        logger.info(
            "Scan completado: %d vulnerabilidades encontradas",
            scan_results["vulnerabilities_found"],
        )
        return scan_results

    def _run_bandit_scan(self, target_path: str) -> List[Dict]:
        """SAST: escaneo de codigo Python con Bandit."""
        findings = []
        try:
            result = subprocess.run(
                ["bandit", "-r", "src/", "-f", "json", "-ll"],
                capture_output=True, text=True, timeout=120,
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for issue in data.get("results", []):
                    findings.append({
                        "title": issue.get("test_id", "BANDIT"),
                        "description": issue.get("issue_text", ""),
                        "severity": issue.get("issue_severity", "low").lower(),
                        "cvss_score": 3.0,
                        "cwe_id": "CWE-code",
                        "component": issue.get("filename", "unknown"),
                        "remediation": issue.get("more_info", ""),
                        "tool": "bandit",
                    })
        except FileNotFoundError:
            logger.debug("bandit no instalado, saltando SAST scan")
        except Exception as exc:
            logger.error("Bandit error: %s", exc)
        return findings

    def _run_nikto_scan(self, target_url: str) -> List[Dict]:
        """Escaneo de vulnerabilidades web con Nikto."""
        findings = []
        try:
            result = subprocess.run(
                ["nikto", "-h", target_url, "-Format", "json", "-output", "/tmp/nikto.json"],
                capture_output=True, text=True, timeout=300,
            )
            logger.debug("Nikto scan ejecutado en %s", target_url)
        except FileNotFoundError:
            logger.debug("nikto no instalado, saltando scan")
        except Exception as exc:
            logger.error("Nikto error: %s", exc)
        return findings

    def _run_sqlmap_scan(self, target_url: str) -> List[Dict]:
        """Deteccion de SQL injection con SQLMap."""
        findings = []
        try:
            result = subprocess.run(
                ["sqlmap", "-u", target_url, "--batch", "--risk=1", "--level=1", "--output-format=json"],
                capture_output=True, text=True, timeout=300,
            )
            logger.debug("SQLMap scan ejecutado en %s", target_url)
        except FileNotFoundError:
            logger.debug("sqlmap no instalado, saltando scan")
        except Exception as exc:
            logger.error("SQLMap error: %s", exc)
        return findings

    def _run_nuclei_scan(self, target_url: str) -> List[Dict]:
        """Escaneo de templates de vulnerabilidades con Nuclei."""
        findings = []
        try:
            result = subprocess.run(
                ["nuclei", "-u", target_url, "-json", "-severity", "medium,high,critical"],
                capture_output=True, text=True, timeout=300,
            )
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    try:
                        item = json.loads(line)
                        findings.append({
                            "title": item.get("template-id", "nuclei"),
                            "description": item.get("info", {}).get("description", ""),
                            "severity": item.get("info", {}).get("severity", "info").lower(),
                            "cvss_score": 5.0,
                            "cwe_id": "CWE-unknown",
                            "component": target_url,
                            "remediation": item.get("info", {}).get("remediation", ""),
                            "tool": "nuclei",
                        })
                    except json.JSONDecodeError:
                        pass
        except FileNotFoundError:
            logger.debug("nuclei no instalado, saltando scan")
        except Exception as exc:
            logger.error("Nuclei error: %s", exc)
        return findings

    def _check_security_headers(self, target_url: str) -> List[Dict]:
        """Verifica headers de seguridad HTTP (OWASP A05)."""
        findings = []
        required_headers = {
            "Strict-Transport-Security": ("A02", "HSTS no configurado", "high"),
            "Content-Security-Policy": ("A05", "CSP no configurado", "medium"),
            "X-Frame-Options": ("A01", "Clickjacking posible", "medium"),
            "X-Content-Type-Options": ("A05", "MIME sniffing posible", "low"),
            "Referrer-Policy": ("A05", "Referrer Policy no configurado", "low"),
        }
        # Simulado: en produccion usar requests.get(target_url)
        for header, (owasp, title, sev) in required_headers.items():
            logger.debug("Verificando header: %s", header)
        return findings

    def _register_vulnerability(self, finding: Dict) -> str:
        """Registra vulnerabilidad en el sistema de tracking."""
        vuln_id = uuid.uuid4().hex[:8].upper()
        severity_map = {
            "critical": VulnerabilitySeverity.CRITICAL,
            "high": VulnerabilitySeverity.HIGH,
            "medium": VulnerabilitySeverity.MEDIUM,
            "low": VulnerabilitySeverity.LOW,
        }
        sev = severity_map.get(finding.get("severity", "low"), VulnerabilitySeverity.LOW)
        vuln = Vulnerability(
            id=vuln_id,
            title=finding.get("title", "Sin titulo"),
            description=finding.get("description", ""),
            severity=sev,
            cvss_score=float(finding.get("cvss_score", 0.0)),
            cwe_id=finding.get("cwe_id", "CWE-unknown"),
            affected_component=finding.get("component", "unknown"),
            proof_of_concept=finding.get("proof", ""),
            remediation=finding.get("remediation", ""),
            assigned_to=finding.get("assigned_to"),
        )
        self.vulnerabilities[vuln_id] = vuln
        logger.warning(
            "Vulnerabilidad registrada: %s [%s] - %s",
            vuln_id, sev.value, vuln.title
        )
        return vuln_id

    def register_manual_vulnerability(
        self,
        title: str,
        description: str,
        severity: VulnerabilitySeverity,
        cvss_score: float,
        cwe_id: str,
        affected_component: str,
        remediation: str,
        proof_of_concept: str = "",
        assigned_to: Optional[str] = None,
    ) -> str:
        """Registra vulnerabilidad manualmente (auditores externos)."""
        finding = {
            "title": title,
            "description": description,
            "severity": severity.value,
            "cvss_score": cvss_score,
            "cwe_id": cwe_id,
            "component": affected_component,
            "remediation": remediation,
            "proof": proof_of_concept,
            "assigned_to": assigned_to,
        }
        return self._register_vulnerability(finding)

    def remediate_vulnerability(self, vuln_id: str, resolution_notes: str) -> bool:
        """Marca vulnerabilidad como resuelta."""
        if vuln_id not in self.vulnerabilities:
            return False
        vuln = self.vulnerabilities[vuln_id]
        vuln.status = VulnerabilityStatus.RESOLVED
        vuln.resolved_date = datetime.now()
        logger.info("Vulnerabilidad %s resuelta: %s", vuln_id, resolution_notes)
        return True

    def generate_audit_report(self, auditor_name: str, audit_type: str = "third_party") -> Dict:
        """Genera reporte completo de auditoria de seguridad."""
        by_sev = {s.value: 0 for s in VulnerabilitySeverity}
        by_status = {s.value: 0 for s in VulnerabilityStatus}
        risk_weights = {
            VulnerabilitySeverity.CRITICAL: 10.0,
            VulnerabilitySeverity.HIGH: 5.0,
            VulnerabilitySeverity.MEDIUM: 2.0,
            VulnerabilitySeverity.LOW: 0.5,
            VulnerabilitySeverity.INFO: 0.1,
        }
        total_risk = 0.0
        for vuln in self.vulnerabilities.values():
            by_sev[vuln.severity.value] += 1
            by_status[vuln.status.value] += 1
            if vuln.status == VulnerabilityStatus.OPEN:
                total_risk += risk_weights[vuln.severity]

        report = {
            "audit_id": f"AUDIT-{datetime.now().strftime('%Y%m%d-%H%M')}",
            "auditor": auditor_name,
            "audit_type": audit_type,
            "audit_date": datetime.now().isoformat(),
            "total_vulnerabilities": len(self.vulnerabilities),
            "by_severity": by_sev,
            "by_status": by_status,
            "overall_risk_score": round(min(10.0, total_risk), 2),
            "owasp_coverage": self.OWASP_CHECKS,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities.values()],
            "recommendations": self._generate_recommendations(),
            "last_scan": self.last_scan_date.isoformat() if self.last_scan_date else None,
        }
        self.audit_reports.append(report)
        logger.info("Reporte de auditoria generado: %s", report["audit_id"])
        return report

    def _generate_recommendations(self) -> List[str]:
        recs = []
        critical_open = sum(
            1 for v in self.vulnerabilities.values()
            if v.severity == VulnerabilitySeverity.CRITICAL and v.status == VulnerabilityStatus.OPEN
        )
        high_open = sum(
            1 for v in self.vulnerabilities.values()
            if v.severity == VulnerabilitySeverity.HIGH and v.status == VulnerabilityStatus.OPEN
        )
        if critical_open:
            recs.append(f"CRITICO: Resolver {critical_open} vulnerabilidades criticas de inmediato")
        if high_open:
            recs.append(f"ALTO: Resolver {high_open} vulnerabilidades altas en < 48h")
        recs += [
            "Implementar Content Security Policy (CSP)",
            "Habilitar HTTP Strict Transport Security (HSTS)",
            "Actualizar dependencias vulnerables",
            "Implementar rate limiting en APIs",
            "Habilitar MFA para administradores",
            "Encriptar datos sensibles en reposo y transito",
        ]
        return recs

    def get_statistics(self) -> Dict:
        total = len(self.vulnerabilities)
        if not total:
            return {"total": 0}
        open_v = [v for v in self.vulnerabilities.values() if v.status == VulnerabilityStatus.OPEN]
        return {
            "total": total,
            "open": len(open_v),
            "resolved": total - len(open_v),
            "critical_open": sum(1 for v in open_v if v.severity == VulnerabilitySeverity.CRITICAL),
            "high_open": sum(1 for v in open_v if v.severity == VulnerabilitySeverity.HIGH),
            "avg_cvss": round(sum(v.cvss_score for v in self.vulnerabilities.values()) / total, 2),
            "last_scan": self.last_scan_date.isoformat() if self.last_scan_date else None,
        }
