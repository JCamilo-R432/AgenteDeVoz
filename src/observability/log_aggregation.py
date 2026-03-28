"""
Log Aggregation - AgenteDeVoz
Gap #24: Agregacion centralizada de logs (ELK / Loki)

Estructura logs en formato JSON compatible con
Elasticsearch y Loki (Grafana).
"""
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    level: LogLevel
    message: str
    service: str
    timestamp: float = field(default_factory=time.time)
    log_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    extra: Dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "log_id": self.log_id,
            "timestamp": self.timestamp,
            "level": self.level.value,
            "service": self.service,
            "message": self.message,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            **self.extra,
        })

    def to_dict(self) -> Dict:
        return json.loads(self.to_json())


class LogAggregator:
    """
    Agregador de logs estructurados con soporte para:
    - Elasticsearch (ELK Stack)
    - Loki (Grafana)
    - Envio por lotes con buffer
    """

    def __init__(
        self,
        service_name: str,
        backend: str = "elasticsearch",   # "elasticsearch" | "loki" | "stdout"
        backend_url: Optional[str] = None,
        batch_size: int = 50,
        min_level: LogLevel = LogLevel.INFO,
    ):
        self.service_name = service_name
        self.backend = backend
        self.backend_url = backend_url
        self.batch_size = batch_size
        self.min_level = min_level
        self._buffer: List[LogEntry] = []
        self._sent_count = 0
        self._dropped_count = 0

        logger.info(
            "LogAggregator inicializado (service=%s, backend=%s, min_level=%s)",
            service_name, backend, min_level.value
        )

    # ------------------------------------------------------------------
    # API de logging
    # ------------------------------------------------------------------

    def log(
        self,
        level: LogLevel,
        message: str,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        **extra,
    ) -> None:
        """Registra un evento de log."""
        if not self._passes_level_filter(level):
            self._dropped_count += 1
            return

        entry = LogEntry(
            level=level,
            message=message,
            service=self.service_name,
            session_id=session_id,
            trace_id=trace_id,
            extra=extra,
        )
        self._buffer.append(entry)

        if self.backend == "stdout":
            print(entry.to_json())

        if len(self._buffer) >= self.batch_size:
            self.flush()

    def info(self, message: str, **kwargs) -> None:
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self.log(LogLevel.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        self.log(LogLevel.DEBUG, message, **kwargs)

    # ------------------------------------------------------------------
    # Flush y envio
    # ------------------------------------------------------------------

    def flush(self) -> int:
        """Envia el buffer al backend. Retorna cantidad enviada."""
        if not self._buffer:
            return 0
        batch = list(self._buffer)
        self._buffer.clear()

        if self.backend == "elasticsearch":
            self._send_to_elasticsearch(batch)
        elif self.backend == "loki":
            self._send_to_loki(batch)
        # stdout ya fue manejado en log()

        self._sent_count += len(batch)
        logger.debug("LogAggregator: %d logs enviados a %s", len(batch), self.backend)
        return len(batch)

    def _send_to_elasticsearch(self, entries: List[LogEntry]) -> None:
        """Envia logs al API Bulk de Elasticsearch."""
        if not self.backend_url:
            return
        # Formato NDJSON para Bulk API
        lines = []
        for entry in entries:
            lines.append(json.dumps({"index": {"_index": f"agentevoz-{self.service_name}"}}))
            lines.append(entry.to_json())
        # En produccion: requests.post(f"{self.backend_url}/_bulk", data="\n".join(lines))
        logger.debug("ES bulk: %d documentos -> %s", len(entries), self.backend_url)

    def _send_to_loki(self, entries: List[LogEntry]) -> None:
        """Envia logs al endpoint Loki Push API."""
        if not self.backend_url:
            return
        streams = []
        for entry in entries:
            streams.append({
                "stream": {
                    "service": entry.service,
                    "level": entry.level.value,
                },
                "values": [
                    [str(int(entry.timestamp * 1e9)), entry.message]
                ],
            })
        payload = {"streams": streams}
        # En produccion: requests.post(f"{self.backend_url}/loki/api/v1/push", json=payload)
        logger.debug("Loki push: %d streams -> %s", len(streams), self.backend_url)

    def _passes_level_filter(self, level: LogLevel) -> bool:
        order = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]
        return order.index(level) >= order.index(self.min_level)

    # ------------------------------------------------------------------
    # Query local (para testing)
    # ------------------------------------------------------------------

    def search(
        self,
        level: Optional[LogLevel] = None,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Busca en el buffer local (no en el backend remoto)."""
        results = list(self._buffer)
        if level:
            results = [e for e in results if e.level == level]
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        return [e.to_dict() for e in results[-limit:]]

    def get_stats(self) -> Dict:
        return {
            "service": self.service_name,
            "backend": self.backend,
            "buffer_size": len(self._buffer),
            "sent_total": self._sent_count,
            "dropped_total": self._dropped_count,
        }
