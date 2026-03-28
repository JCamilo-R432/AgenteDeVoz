from __future__ import annotations
from typing import Dict, List, Optional, Any
"""
Workflow endpoints — iniciar, consultar y aprobar flujos de negocio.
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from workflows.workflow_engine import workflow_engine
import workflows.return_workflow  # noqa: F401  — registra workflows al importar

router = APIRouter(tags=["workflows"])


class StartWorkflowRequest(BaseModel):
    workflow_id: str
    context: dict = {}


class ResumeRequest(BaseModel):
    approval_data: dict = {}


@router.get("/")
async def list_workflows():
    """Lista workflows disponibles."""
    return {
        "workflows": [
            {"id": wf_id, "name": wf.name, "steps": len(wf.steps)}
            for wf_id, wf in workflow_engine._definitions.items()
        ]
    }


@router.post("/start")
async def start_workflow(req: StartWorkflowRequest):
    """Inicia un workflow con el contexto proporcionado."""
    try:
        instance = await workflow_engine.start(req.workflow_id, req.context)
        return instance.to_summary()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/instances")
async def list_instances(workflow_id: Optional[str] = None):
    """Lista todas las instancias (opcionalmente filtradas por workflow)."""
    return {"instances": workflow_engine.list_instances(workflow_id)}


@router.get("/instances/{instance_id}")
async def get_instance(instance_id: str):
    """Consulta el estado de una instancia."""
    inst = workflow_engine.get_instance(instance_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Instancia no encontrada")
    return inst.to_summary()


@router.post("/instances/{instance_id}/resume")
async def resume_instance(instance_id: str, req: ResumeRequest):
    """Aprueba y reanuda un workflow pausado esperando aprobación humana."""
    inst = await workflow_engine.resume(instance_id, req.approval_data)
    if not inst:
        raise HTTPException(status_code=404, detail="Instancia no encontrada o no está esperando aprobación")
    return inst.to_summary()


@router.post("/instances/{instance_id}/cancel")
async def cancel_instance(instance_id: str):
    """Cancela una instancia activa."""
    success = workflow_engine.cancel(instance_id)
    if not success:
        raise HTTPException(status_code=404, detail="Instancia no encontrada")
    return {"status": "cancelled", "instance_id": instance_id}
