from __future__ import annotations
from typing import Dict, List, Any
"""
Workflow Engine — motor de automatización de flujos de negocio.
Define WorkflowStep, WorkflowDefinition y WorkflowInstance.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable, Optional

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_INPUT = "waiting_input"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"


# Tipo para funciones de paso: recibe contexto, devuelve contexto actualizado
StepFn = Callable[[dict], Awaitable[dict]]


@dataclass
class WorkflowStep:
    id: str
    name: str
    description: str
    fn: StepFn
    requires_human_approval: bool = False
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 2


@dataclass
class StepResult:
    step_id: str
    status: StepStatus
    output: dict = field(default_factory=dict)
    error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None


@dataclass
class WorkflowInstance:
    instance_id: str
    workflow_id: str
    status: WorkflowStatus
    context: dict
    step_results: List[StepResult] = field(default_factory=list)
    current_step_index: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None

    @property
    def completed_steps(self) -> int:
        return sum(1 for r in self.step_results if r.status == StepStatus.COMPLETED)

    @property
    def current_step_name(self) -> Optional[str]:
        return self.context.get("_current_step_name")

    def to_summary(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "completed_steps": self.completed_steps,
            "total_steps": len(self.step_results) + (1 if self.status == WorkflowStatus.RUNNING else 0),
            "current_step": self.current_step_name,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class WorkflowDefinition:
    """Define un flujo de trabajo con sus pasos ordenados."""

    def __init__(self, workflow_id: str, name: str, description: str):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []

    def add_step(
        self,
        step_id: str,
        name: str,
        description: str,
        fn: StepFn,
        requires_human_approval: bool = False,
    ) -> "WorkflowDefinition":
        self.steps.append(WorkflowStep(
            id=step_id, name=name, description=description,
            fn=fn, requires_human_approval=requires_human_approval,
        ))
        return self  # fluent API


class WorkflowEngine:
    """Orquestador de workflows. Ejecuta pasos secuencialmente con manejo de errores."""

    def __init__(self):
        self._definitions: dict[str, WorkflowDefinition] = {}
        self._instances: dict[str, WorkflowInstance] = {}

    def register(self, definition: WorkflowDefinition) -> None:
        self._definitions[definition.workflow_id] = definition
        logger.info("Workflow registrado: %s (%d pasos)", definition.name, len(definition.steps))

    def get_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        return self._instances.get(instance_id)

    def list_instances(self, workflow_id: Optional[str] = None) -> List[dict]:
        instances = self._instances.values()
        if workflow_id:
            instances = [i for i in instances if i.workflow_id == workflow_id]
        return [i.to_summary() for i in instances]

    async def start(
        self,
        workflow_id: str,
        initial_context: dict,
    ) -> WorkflowInstance:
        definition = self._definitions.get(workflow_id)
        if not definition:
            raise ValueError(f"Workflow '{workflow_id}' no registrado")

        instance = WorkflowInstance(
            instance_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            context={**initial_context},
        )
        self._instances[instance.instance_id] = instance

        logger.info("Iniciando workflow %s (instancia %s)", workflow_id, instance.instance_id)
        await self._run(instance, definition)
        return instance

    async def _run(self, instance: WorkflowInstance, definition: WorkflowDefinition) -> None:
        for i, step in enumerate(definition.steps):
            if instance.status in (WorkflowStatus.CANCELLED, WorkflowStatus.FAILED):
                break

            instance.current_step_index = i
            instance.context["_current_step_name"] = step.name
            step_result = StepResult(step_id=step.id, status=StepStatus.IN_PROGRESS)

            if step.requires_human_approval:
                instance.status = WorkflowStatus.WAITING
                step_result.status = StepStatus.WAITING_INPUT
                instance.step_results.append(step_result)
                logger.info("Workflow %s esperando aprobación humana en paso '%s'", instance.instance_id, step.name)
                return  # pausa hasta que se reanude

            try:
                logger.info("Ejecutando paso '%s'", step.name)
                updated_context = await step.fn(instance.context)
                instance.context.update(updated_context or {})
                step_result.status = StepStatus.COMPLETED
                step_result.output = {k: v for k, v in (updated_context or {}).items() if not k.startswith("_")}
                step_result.completed_at = datetime.utcnow().isoformat()
            except Exception as exc:
                logger.error("Paso '%s' falló: %s", step.name, exc)
                step_result.status = StepStatus.FAILED
                step_result.error = str(exc)
                instance.status = WorkflowStatus.FAILED
                instance.error = f"Paso '{step.name}' falló: {exc}"
                instance.step_results.append(step_result)
                return

            instance.step_results.append(step_result)

        if instance.status == WorkflowStatus.RUNNING:
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = datetime.utcnow().isoformat()
            logger.info("Workflow %s completado exitosamente", instance.instance_id)

    async def resume(self, instance_id: str, approval_data: dict) -> Optional[WorkflowInstance]:
        """Reanuda un workflow que estaba esperando aprobación."""
        instance = self._instances.get(instance_id)
        if not instance or instance.status != WorkflowStatus.WAITING:
            return None

        definition = self._definitions.get(instance.workflow_id)
        if not definition:
            return None

        instance.context.update(approval_data)
        instance.status = WorkflowStatus.RUNNING

        # Reanudar desde el paso siguiente al último completado
        remaining_steps = definition.steps[instance.current_step_index + 1:]
        remaining_def = WorkflowDefinition(
            definition.workflow_id, definition.name, definition.description
        )
        remaining_def.steps = remaining_steps
        await self._run(instance, remaining_def)
        return instance

    def cancel(self, instance_id: str) -> bool:
        instance = self._instances.get(instance_id)
        if not instance:
            return False
        instance.status = WorkflowStatus.CANCELLED
        return True


# Singleton
workflow_engine = WorkflowEngine()
