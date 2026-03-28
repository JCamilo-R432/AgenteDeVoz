"""
Incident Response - AgenteDeVoz
Gap #16: Playbooks de respuesta a incidentes

Define procedimientos automatizados y manuales por tipo de incidente.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlaybookStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlaybookStep:
    step_id: str
    title: str
    description: str
    automated: bool = False
    action: Optional[Callable] = None
    timeout_s: int = 300
    required: bool = True
    status: PlaybookStatus = PlaybookStatus.PENDING
    completed_at: Optional[str] = None
    result: Optional[str] = None


@dataclass
class PlaybookRun:
    run_id: str
    playbook_name: str
    incident_id: str
    started_at: str
    steps: List[PlaybookStep] = field(default_factory=list)
    status: PlaybookStatus = PlaybookStatus.IN_PROGRESS
    completed_at: Optional[str] = None

    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == PlaybookStatus.COMPLETED)

    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == PlaybookStatus.FAILED)


class IncidentResponsePlaybook:
    """
    Define y ejecuta playbooks de respuesta a incidentes.
    Mezcla pasos automatizados con verificaciones manuales.
    """

    # Playbooks predefinidos por tipo de incidente
    PLAYBOOK_TEMPLATES: Dict[str, List[Dict]] = {
        "api_down": [
            {"id": "1", "title": "Verificar estado del servicio", "description": "Revisar logs y health checks", "automated": False},
            {"id": "2", "title": "Reiniciar pods K8s", "description": "kubectl rollout restart deployment/agentevoz", "automated": True},
            {"id": "3", "title": "Verificar base de datos", "description": "Confirmar conectividad PostgreSQL", "automated": False},
            {"id": "4", "title": "Activar modo mantenimiento", "description": "Actualizar pagina de estado", "automated": False},
            {"id": "5", "title": "Notificar stakeholders", "description": "Email a equipo y clientes afectados", "automated": False},
        ],
        "high_latency": [
            {"id": "1", "title": "Revisar metricas de latencia", "description": "Grafana dashboard latency", "automated": False},
            {"id": "2", "title": "Verificar rate limiting", "description": "Revisar logs de rate limiter", "automated": True},
            {"id": "3", "title": "Escalar instancias", "description": "HPA manual: kubectl scale", "automated": True},
            {"id": "4", "title": "Verificar dependencias externas", "description": "STT/TTS API response times", "automated": False},
        ],
        "security_breach": [
            {"id": "1", "title": "AISLAR sistema afectado", "description": "Desconectar de red si es necesario", "automated": False, "required": True},
            {"id": "2", "title": "Preservar evidencia", "description": "Capturar logs antes de reiniciar", "automated": False, "required": True},
            {"id": "3", "title": "Notificar DPO", "description": "GDPR: notificar dentro de 72h si hay datos personales", "automated": False, "required": True},
            {"id": "4", "title": "Cambiar credenciales", "description": "Rotar API keys, passwords, tokens", "automated": False},
            {"id": "5", "title": "Analisis forense", "description": "Revisar logs de acceso y anomalias", "automated": False},
        ],
        "data_loss": [
            {"id": "1", "title": "Detener escrituras", "description": "Poner BD en modo read-only", "automated": False, "required": True},
            {"id": "2", "title": "Evaluar alcance", "description": "Determinar tablas y registros afectados", "automated": False},
            {"id": "3", "title": "Restaurar desde backup", "description": "pg_restore desde ultimo backup verificado", "automated": False, "required": True},
            {"id": "4", "title": "Verificar integridad", "description": "Validar checksums de datos restaurados", "automated": False},
            {"id": "5", "title": "Notificar usuarios afectados", "description": "GDPR Art. 34 si aplica", "automated": False},
        ],
    }

    def __init__(self):
        self._runs: Dict[str, PlaybookRun] = {}
        self._run_counter = 0
        logger.info("IncidentResponsePlaybook inicializado (%d plantillas)", len(self.PLAYBOOK_TEMPLATES))

    def start_playbook(self, incident_id: str, playbook_name: str) -> Optional[PlaybookRun]:
        template = self.PLAYBOOK_TEMPLATES.get(playbook_name)
        if not template:
            logger.error("Playbook no encontrado: %s", playbook_name)
            return None

        self._run_counter += 1
        run_id = f"RUN-{self._run_counter:04d}"
        steps = [
            PlaybookStep(
                step_id=s["id"],
                title=s["title"],
                description=s["description"],
                automated=s.get("automated", False),
                required=s.get("required", True),
            )
            for s in template
        ]
        run = PlaybookRun(
            run_id=run_id,
            playbook_name=playbook_name,
            incident_id=incident_id,
            started_at=datetime.now().isoformat(),
            steps=steps,
        )
        self._runs[run_id] = run
        logger.info("Playbook iniciado: %s (incidente=%s)", run_id, incident_id)
        return run

    def complete_step(
        self, run_id: str, step_id: str, result: str = "OK", failed: bool = False
    ) -> bool:
        run = self._runs.get(run_id)
        if not run:
            return False
        for step in run.steps:
            if step.step_id == step_id:
                step.status = PlaybookStatus.FAILED if failed else PlaybookStatus.COMPLETED
                step.completed_at = datetime.now().isoformat()
                step.result = result

                # Verificar si el playbook esta completo
                if all(s.status in (PlaybookStatus.COMPLETED, PlaybookStatus.SKIPPED)
                       for s in run.steps):
                    run.status = PlaybookStatus.COMPLETED
                    run.completed_at = datetime.now().isoformat()
                    logger.info("Playbook completado: %s", run_id)
                return True
        return False

    def skip_step(self, run_id: str, step_id: str, reason: str = "") -> bool:
        run = self._runs.get(run_id)
        if not run:
            return False
        for step in run.steps:
            if step.step_id == step_id:
                if step.required:
                    logger.warning("Intentando saltar paso requerido: %s/%s", run_id, step_id)
                    return False
                step.status = PlaybookStatus.SKIPPED
                step.result = reason
                return True
        return False

    def get_run(self, run_id: str) -> Optional[PlaybookRun]:
        return self._runs.get(run_id)

    def get_runs_for_incident(self, incident_id: str) -> List[PlaybookRun]:
        return [r for r in self._runs.values() if r.incident_id == incident_id]

    def get_available_playbooks(self) -> List[str]:
        return list(self.PLAYBOOK_TEMPLATES.keys())
