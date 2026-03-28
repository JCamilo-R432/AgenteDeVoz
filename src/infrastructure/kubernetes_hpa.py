"""
Kubernetes HPA - AgenteDeVoz
Gap #25: Gestion del Horizontal Pod Autoscaler de Kubernetes

Genera manifiestos HPA y gestiona escalado via kubectl.
"""
import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HPAConfig:
    name: str
    namespace: str
    deployment: str
    min_replicas: int
    max_replicas: int
    cpu_target_percent: int = 70
    memory_target_percent: Optional[int] = None
    custom_metrics: Optional[List[Dict]] = None


class KubernetesHPA:
    """
    Gestor de Horizontal Pod Autoscaler para Kubernetes.
    Genera manifiestos YAML y ejecuta comandos kubectl.
    """

    API_VERSION = "autoscaling/v2"

    def __init__(self, kubeconfig: Optional[str] = None, dry_run: bool = False):
        self.kubeconfig = kubeconfig
        self.dry_run = dry_run
        self._kubectl_available = self._check_kubectl()
        logger.info(
            "KubernetesHPA inicializado (kubectl=%s, dry_run=%s)",
            self._kubectl_available, dry_run
        )

    def _check_kubectl(self) -> bool:
        try:
            result = subprocess.run(
                ["kubectl", "version", "--client", "--output=json"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def generate_manifest(self, config: HPAConfig) -> Dict:
        """Genera el manifiesto YAML del HPA en formato dict."""
        metrics = [
            {
                "type": "Resource",
                "resource": {
                    "name": "cpu",
                    "target": {
                        "type": "Utilization",
                        "averageUtilization": config.cpu_target_percent,
                    },
                },
            }
        ]

        if config.memory_target_percent:
            metrics.append({
                "type": "Resource",
                "resource": {
                    "name": "memory",
                    "target": {
                        "type": "Utilization",
                        "averageUtilization": config.memory_target_percent,
                    },
                },
            })

        if config.custom_metrics:
            metrics.extend(config.custom_metrics)

        return {
            "apiVersion": self.API_VERSION,
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": config.name,
                "namespace": config.namespace,
                "labels": {"app": config.deployment, "managed-by": "agentevoz"},
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": config.deployment,
                },
                "minReplicas": config.min_replicas,
                "maxReplicas": config.max_replicas,
                "metrics": metrics,
                "behavior": {
                    "scaleUp": {
                        "stabilizationWindowSeconds": 60,
                        "policies": [
                            {"type": "Pods", "value": 2, "periodSeconds": 60}
                        ],
                    },
                    "scaleDown": {
                        "stabilizationWindowSeconds": 300,
                        "policies": [
                            {"type": "Pods", "value": 1, "periodSeconds": 120}
                        ],
                    },
                },
            },
        }

    def apply_hpa(self, config: HPAConfig) -> bool:
        """Aplica el HPA en el cluster usando kubectl apply."""
        if not self._kubectl_available:
            logger.warning("kubectl no disponible - solo modo simulacion")
            logger.info("HPA simulado aplicado: %s/%s", config.namespace, config.name)
            return True

        manifest = self.generate_manifest(config)
        manifest_json = json.dumps(manifest)

        cmd = ["kubectl", "apply", "-f", "-", "-n", config.namespace]
        if self.dry_run:
            cmd.append("--dry-run=client")
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])

        try:
            result = subprocess.run(
                cmd,
                input=manifest_json,
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                logger.info("HPA aplicado: %s/%s", config.namespace, config.name)
                return True
            logger.error("Error aplicando HPA: %s", result.stderr)
            return False
        except subprocess.TimeoutExpired:
            logger.error("Timeout aplicando HPA")
            return False

    def get_hpa_status(self, name: str, namespace: str = "default") -> Optional[Dict]:
        """Obtiene el estado actual del HPA."""
        if not self._kubectl_available:
            return {
                "name": name,
                "namespace": namespace,
                "current_replicas": 1,
                "desired_replicas": 1,
                "status": "simulated",
            }
        try:
            result = subprocess.run(
                ["kubectl", "get", "hpa", name, "-n", namespace, "-o", "json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            return None
        except Exception as exc:
            logger.error("Error obteniendo HPA status: %s", exc)
            return None

    def scale_deployment(self, deployment: str, replicas: int, namespace: str = "default") -> bool:
        """Escala un deployment manualmente (bypass HPA)."""
        if not self._kubectl_available:
            logger.info("Scale simulado: %s -> %d replicas", deployment, replicas)
            return True
        try:
            result = subprocess.run(
                ["kubectl", "scale", "deployment", deployment,
                 f"--replicas={replicas}", "-n", namespace],
                capture_output=True, text=True, timeout=15
            )
            return result.returncode == 0
        except Exception as exc:
            logger.error("Error escalando deployment: %s", exc)
            return False
