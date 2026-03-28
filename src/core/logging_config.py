from __future__ import annotations
from typing import Dict, List, Any
"""
Structured JSON logging for AgenteDeVoz.
Replaces plain-text logging with JSON lines suitable for log aggregation
(Papertrail, Logtail, Datadog, etc.).

Usage:
    from core.logging_config import configure_logging, get_logger

    configure_logging()               # call once at startup
    logger = get_logger("my_module")  # use everywhere
    logger.info("Order created", extra={"order_id": "ECO-001", "tenant_id": "t1"})
"""


import json
import logging
import os
import sys
import time
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emits one JSON object per log line."""

    SERVICE = os.getenv("SERVICE_NAME", "agentevoz-api")
    ENV = os.getenv("APP_ENV", "production")

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service": self.SERVICE,
            "env": self.ENV,
        }

        # Attach extra fields (tenant_id, request_id, etc.)
        for key, val in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            ):
                payload[key] = val

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(
    level: Optional[str] = None,
    json_logs: Optional[bool] = None,
) -> None:
    """
    Configure root logger once at application startup.

    Args:
        level: Log level string (DEBUG/INFO/WARNING/ERROR). Defaults to
               LOG_LEVEL env var, then INFO.
        json_logs: Emit JSON lines. Defaults to JSON_LOGS env var or True
                   when APP_ENV == production.
    """
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    if json_logs is None:
        json_logs = os.getenv("JSON_LOGS", "").lower() not in ("0", "false", "no")
        if os.getenv("APP_ENV", "production") == "development":
            json_logs = False

    root = logging.getLogger()
    if root.handlers:
        # Already configured — avoid adding duplicate handlers
        root.setLevel(log_level)
        return

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root.addHandler(handler)
    root.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (always a child of the root logger)."""
    return logging.getLogger(name)
