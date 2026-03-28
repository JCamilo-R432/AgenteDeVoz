"""
Health & Metrics endpoints.
GET /health        — liveness
GET /health/ready  — readiness
GET /health/full   — informe completo
GET /metrics       — Prometheus text format
"""
from fastapi import APIRouter, Response
from monitoring.health_checks import health_checker
from monitoring.metrics import registry

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness():
    """Liveness probe — el proceso responde."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    """Readiness probe — el sistema puede aceptar tráfico."""
    ready = await health_checker.is_ready()
    if not ready:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Service not ready")
    return {"status": "ready"}


@router.get("/health/full")
async def full_health():
    """Informe completo de salud de todos los componentes."""
    report = await health_checker.run_all()
    status_code = 200 if report.status == "healthy" else (503 if report.status == "unhealthy" else 207)
    return Response(
        content=__import__("json").dumps(report.to_dict()),
        status_code=status_code,
        media_type="application/json",
    )


@router.get("/metrics")
async def prometheus_metrics():
    """Expone métricas en formato Prometheus text."""
    return Response(
        content=registry.to_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
