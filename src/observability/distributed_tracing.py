"""
Distributed Tracing - AgenteDeVoz
Gap #23: Trazabilidad distribuida con Jaeger/Zipkin

Instrumenta la pipeline de voz completa:
STT -> NLP -> LLM -> TTS -> CRM
"""
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: float
    end_time: Optional[float] = None
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict] = field(default_factory=list)
    status: str = "ok"   # "ok" | "error"

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    def finish(self, status: str = "ok") -> None:
        self.end_time = time.time()
        self.status = status

    def set_tag(self, key: str, value: str) -> None:
        self.tags[key] = value

    def log_event(self, event: str, payload: Optional[Dict] = None) -> None:
        self.logs.append({
            "timestamp": time.time(),
            "event": event,
            "payload": payload or {},
        })

    def to_dict(self) -> Dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation_name,
            "service": self.service_name,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "tags": self.tags,
            "logs": self.logs,
        }


class DistributedTracing:
    """
    Sistema de trazabilidad distribuida para AgenteDeVoz.
    Compatible con el formato OpenTelemetry / Jaeger.
    """

    def __init__(self, service_name: str = "agente-de-voz", exporter_url: Optional[str] = None):
        self.service_name = service_name
        self.exporter_url = exporter_url
        self._active_traces: Dict[str, List[Span]] = {}
        self._completed_traces: List[List[Span]] = []
        self._max_completed = 500
        logger.info(
            "DistributedTracing inicializado (service=%s, exporter=%s)",
            service_name, exporter_url or "none"
        )

    def start_trace(self, operation_name: str, tags: Optional[Dict] = None) -> Span:
        """Inicia un nuevo trace raiz."""
        trace_id = uuid.uuid4().hex
        span = self._create_span(trace_id, operation_name, parent_span_id=None, tags=tags)
        self._active_traces[trace_id] = [span]
        logger.debug("Trace iniciado: %s -> %s", trace_id, operation_name)
        return span

    def start_child_span(
        self,
        parent_span: Span,
        operation_name: str,
        tags: Optional[Dict] = None,
    ) -> Span:
        """Crea un span hijo dentro de un trace existente."""
        span = self._create_span(
            parent_span.trace_id,
            operation_name,
            parent_span_id=parent_span.span_id,
            tags=tags,
        )
        if parent_span.trace_id in self._active_traces:
            self._active_traces[parent_span.trace_id].append(span)
        else:
            self._active_traces[parent_span.trace_id] = [span]
        return span

    def finish_span(self, span: Span, status: str = "ok") -> None:
        """Finaliza un span y lo exporta si es raiz."""
        span.finish(status)
        # Si todos los spans del trace estan terminados, exportar
        spans = self._active_traces.get(span.trace_id, [])
        if spans and all(s.end_time is not None for s in spans):
            self._export_trace(span.trace_id, spans)

    @contextmanager
    def trace(self, operation_name: str, parent_span: Optional[Span] = None, tags: Optional[Dict] = None):
        """Context manager para trazado automatico con finally-finish."""
        if parent_span:
            span = self.start_child_span(parent_span, operation_name, tags)
        else:
            span = self.start_trace(operation_name, tags)
        status = "ok"
        try:
            yield span
        except Exception as exc:
            status = "error"
            span.set_tag("error.message", str(exc))
            raise
        finally:
            self.finish_span(span, status)

    def _create_span(
        self,
        trace_id: str,
        operation_name: str,
        parent_span_id: Optional[str],
        tags: Optional[Dict] = None,
    ) -> Span:
        span = Span(
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service_name=self.service_name,
            start_time=time.time(),
            tags=dict(tags) if tags else {},
        )
        return span

    def _export_trace(self, trace_id: str, spans: List[Span]) -> None:
        """Exporta trace completado al backend (Jaeger / Zipkin / logs)."""
        self._completed_traces.append(list(spans))
        if len(self._completed_traces) > self._max_completed:
            self._completed_traces = self._completed_traces[-self._max_completed:]

        del self._active_traces[trace_id]

        total_ms = sum(s.duration_ms for s in spans if s.parent_span_id is None)
        errors = sum(1 for s in spans if s.status == "error")
        logger.info(
            "Trace exportado: %s | spans=%d | duracion=%.1fms | errores=%d",
            trace_id, len(spans), total_ms, errors
        )

        if self.exporter_url:
            self._send_to_backend(spans)

    def _send_to_backend(self, spans: List[Span]) -> None:
        """Envia spans al backend de trazabilidad (simulado)."""
        # En produccion usar opentelemetry-sdk:
        # from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        logger.debug("Spans enviados a backend: %s", self.exporter_url)

    def get_trace(self, trace_id: str) -> Optional[List[Dict]]:
        """Retorna spans de un trace (activo o completado)."""
        if trace_id in self._active_traces:
            return [s.to_dict() for s in self._active_traces[trace_id]]
        return None

    def get_stats(self) -> Dict:
        return {
            "active_traces": len(self._active_traces),
            "completed_traces": len(self._completed_traces),
            "service_name": self.service_name,
        }
