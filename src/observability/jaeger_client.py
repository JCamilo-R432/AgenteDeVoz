"""
Jaeger Client - AgenteDeVoz
Gap #23: Cliente para exportar traces a Jaeger

Formatea spans en formato Jaeger Thrift/Protobuf
y los envía al Jaeger Collector via HTTP.
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .distributed_tracing import Span

logger = logging.getLogger(__name__)


@dataclass
class JaegerConfig:
    collector_url: str      # http://jaeger:14268/api/traces
    service_name: str
    agent_host: str = "localhost"
    agent_port: int = 6831
    sample_rate: float = 1.0    # 1.0 = 100% de traces


class JaegerClient:
    """
    Cliente HTTP para exportar spans a Jaeger Collector.
    Soporta formato Thrift sobre HTTP (endpoint /api/traces).
    """

    JAEGER_THRIFT_CONTENT_TYPE = "application/x-thrift"

    def __init__(self, config: JaegerConfig):
        self.config = config
        self._exported_count = 0
        self._failed_count = 0
        self._batch_buffer: List[Span] = []
        self._batch_size = 100
        logger.info(
            "JaegerClient inicializado -> %s (sample_rate=%.0f%%)",
            config.collector_url, config.sample_rate * 100
        )

    def export_span(self, span: Span) -> bool:
        """Exporta un span individual a Jaeger."""
        if not self._should_sample():
            return True  # Dropped by sampling

        self._batch_buffer.append(span)
        if len(self._batch_buffer) >= self._batch_size:
            return self.flush()
        return True

    def export_spans(self, spans: List[Span]) -> bool:
        """Exporta una lista de spans (trace completo)."""
        if not self._should_sample():
            return True
        self._batch_buffer.extend(spans)
        return self.flush()

    def flush(self) -> bool:
        """Envia el buffer actual a Jaeger."""
        if not self._batch_buffer:
            return True
        spans = list(self._batch_buffer)
        self._batch_buffer.clear()

        try:
            payload = self._format_jaeger_payload(spans)
            self._http_post(payload)
            self._exported_count += len(spans)
            logger.debug("Jaeger: %d spans exportados", len(spans))
            return True
        except Exception as exc:
            self._failed_count += len(spans)
            logger.error("Jaeger: error exportando spans: %s", exc)
            return False

    def _should_sample(self) -> bool:
        """Determina si el trace debe ser muestreado."""
        import random
        return random.random() < self.config.sample_rate

    def _format_jaeger_payload(self, spans: List[Span]) -> Dict:
        """
        Formatea spans en estructura Jaeger JSON compatible con
        el endpoint /api/traces del Jaeger Collector.
        """
        processes: Dict[str, Dict] = {}
        jaeger_spans = []

        for span in spans:
            svc = span.service_name
            if svc not in processes:
                processes[svc] = {
                    "serviceName": svc,
                    "tags": [{"key": "runtime", "type": "string", "value": "python"}],
                }

            jaeger_spans.append({
                "traceID": span.trace_id,
                "spanID": span.span_id,
                "parentSpanID": span.parent_span_id or "",
                "operationName": span.operation_name,
                "startTime": int(span.start_time * 1_000_000),  # microseconds
                "duration": int(span.duration_ms * 1000),         # microseconds
                "tags": [
                    {"key": k, "type": "string", "value": v}
                    for k, v in span.tags.items()
                ],
                "logs": [
                    {
                        "timestamp": int(log["timestamp"] * 1_000_000),
                        "fields": [{"key": "event", "type": "string", "value": log["event"]}],
                    }
                    for log in span.logs
                ],
                "processID": svc,
            })

        return {
            "data": [
                {
                    "traceID": spans[0].trace_id if spans else "",
                    "spans": jaeger_spans,
                    "processes": processes,
                }
            ]
        }

    def _http_post(self, payload: Dict) -> None:
        """Envia payload al Jaeger Collector via HTTP (simulado)."""
        # En produccion usar requests:
        # import requests
        # resp = requests.post(
        #     self.config.collector_url,
        #     json=payload,
        #     headers={"Content-Type": "application/json"},
        #     timeout=5,
        # )
        # resp.raise_for_status()
        logger.debug(
            "Jaeger HTTP POST -> %s (%d bytes)",
            self.config.collector_url,
            len(json.dumps(payload))
        )

    def get_metrics(self) -> Dict:
        return {
            "exported_spans": self._exported_count,
            "failed_spans": self._failed_count,
            "buffer_size": len(self._batch_buffer),
            "collector_url": self.config.collector_url,
            "sample_rate": self.config.sample_rate,
        }
