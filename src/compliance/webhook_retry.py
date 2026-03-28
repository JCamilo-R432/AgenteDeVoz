"""
Webhook Retry Manager - AgenteDeVoz
Gap #39: Reintentos con backoff exponencial y dead letter queue

Implementa el patron de reintentos robusto para webhooks salientes:
- Backoff exponencial: delay = 2^attempt * 60 segundos
- Jitter del ±25% para evitar thundering herd
- Dead Letter Queue (DLQ) para webhooks que superan max reintentos
- Limpieza automatica de webhooks antiguos
"""
import hashlib
import json
import logging
import random
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

try:
    import requests as req_lib
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebhookStatus(Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"  # En DLQ, requiere intervencion manual


class WebhookRecord:
    def __init__(self, webhook_id: str, url: str, payload: Dict, event_id: str):
        self.id = webhook_id
        self.url = url
        self.payload = payload
        self.event_id = event_id
        self.status = WebhookStatus.PENDING
        self.attempt = 0
        self.max_attempts = 5
        self.created_at = datetime.utcnow()
        self.last_attempt_at: Optional[datetime] = None
        self.next_retry_at: Optional[datetime] = None
        self.delivered_at: Optional[datetime] = None
        self.errors: List[Dict] = []

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "url": self.url,
            "event_id": self.event_id,
            "status": self.status.value,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at.isoformat(),
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "errors": self.errors[-5:],  # Ultimos 5 errores
        }


class WebhookRetryManager:
    """
    Gestor de webhooks con reintentos exponenciales y DLQ.

    Estrategia de reintentos:
    - Intento 1: inmediato
    - Intento 2: 2^1 * 60s = 2 min (±25% jitter) = 1.5-2.5 min
    - Intento 3: 2^2 * 60s = 4 min (±25% jitter) = 3-5 min
    - Intento 4: 2^3 * 60s = 8 min (±25% jitter) = 6-10 min
    - Intento 5: 2^4 * 60s = 16 min (±25% jitter) = 12-20 min
    - Despues de 5 intentos: -> Dead Letter Queue
    """

    BASE_RETRY_SECONDS = 60
    JITTER_FACTOR = 0.25  # ±25%

    def __init__(self, redis_client=None):
        self._webhooks: Dict[str, WebhookRecord] = {}
        self._dead_letter_queue: List[str] = []  # webhook_ids en DLQ
        self._redis = redis_client
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
        headers: Optional[Dict] = None,
        timeout_seconds: int = 30,
    ) -> str:
        """
        Envia un webhook con reintentos automaticos.

        Args:
            url: URL destino del webhook
            payload: Datos a enviar (se serializa a JSON)
            event_id: ID unico del evento (para idempotencia)
            headers: Headers HTTP adicionales
            timeout_seconds: Timeout por intento

        Returns:
            webhook_id para rastrear el estado
        """
        webhook_id = str(uuid.uuid4())[:16]
        if not event_id:
            event_id = hashlib.md5(f"{url}:{json.dumps(payload, default=str)}".encode()).hexdigest()[:16]

        record = WebhookRecord(webhook_id, url, payload, event_id)

        with self._lock:
            self._webhooks[webhook_id] = record

        # Intentar envio inmediato
        success = self._attempt_delivery(record, headers=headers, timeout=timeout_seconds)
        if not success and record.attempt < record.max_attempts:
            self._schedule_retry(record)

        return webhook_id

    def _attempt_delivery(
        self,
        record: WebhookRecord,
        headers: Optional[Dict] = None,
        timeout: int = 30,
    ) -> bool:
        """Intenta entregar el webhook. Retorna True si exitoso."""
        record.attempt += 1
        record.last_attempt_at = datetime.utcnow()
        record.status = WebhookStatus.RETRYING if record.attempt > 1 else WebhookStatus.PENDING

        default_headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": record.id,
            "X-Event-ID": record.event_id,
            "X-Attempt": str(record.attempt),
        }
        if headers:
            default_headers.update(headers)

        try:
            if not REQUESTS_AVAILABLE:
                # Modo simulado para testing
                logger.info(f"[SIMULADO] Webhook enviado: {record.url} (intento {record.attempt})")
                record.status = WebhookStatus.DELIVERED
                record.delivered_at = datetime.utcnow()
                return True

            response = req_lib.post(
                record.url,
                json=record.payload,
                headers=default_headers,
                timeout=timeout,
            )

            if response.status_code in (200, 201, 202, 204):
                record.status = WebhookStatus.DELIVERED
                record.delivered_at = datetime.utcnow()
                logger.info(f"Webhook {record.id} entregado exitosamente (intento {record.attempt})")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                record.errors.append({"attempt": record.attempt, "error": error_msg, "ts": datetime.utcnow().isoformat()})
                logger.warning(f"Webhook {record.id} falló: {error_msg}")
                return False

        except Exception as e:
            error_msg = str(e)
            record.errors.append({"attempt": record.attempt, "error": error_msg, "ts": datetime.utcnow().isoformat()})
            logger.warning(f"Webhook {record.id} error (intento {record.attempt}): {error_msg}")
            return False

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calcula el delay de reintento con backoff exponencial y jitter.

        Formula: 2^attempt * BASE_RETRY_SECONDS * (1 ± JITTER_FACTOR)
        """
        base_delay = (2 ** attempt) * self.BASE_RETRY_SECONDS
        jitter = base_delay * self.JITTER_FACTOR
        delay = base_delay + random.uniform(-jitter, jitter)
        return max(delay, 1.0)  # Minimo 1 segundo

    def _schedule_retry(self, record: WebhookRecord) -> None:
        """Programa el siguiente reintento."""
        if record.attempt >= record.max_attempts:
            self._move_to_dlq(record)
            return

        delay = self._calculate_retry_delay(record.attempt)
        record.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
        record.status = WebhookStatus.RETRYING
        logger.info(
            f"Webhook {record.id} programado para reintento "
            f"#{record.attempt + 1} en {delay:.0f}s"
        )

    def _move_to_dlq(self, record: WebhookRecord) -> None:
        """Mueve el webhook a la Dead Letter Queue."""
        record.status = WebhookStatus.DEAD
        with self._lock:
            if record.id not in self._dead_letter_queue:
                self._dead_letter_queue.append(record.id)
        logger.error(
            f"Webhook {record.id} movido a DLQ despues de {record.attempt} intentos. "
            f"URL: {record.url}"
        )

    def process_retry_queue(self) -> int:
        """
        Procesa todos los webhooks pendientes de reintento.
        Llamar periodicamente (ej: cada minuto via cron).

        Returns:
            Numero de webhooks procesados
        """
        now = datetime.utcnow()
        processed = 0

        with self._lock:
            pending = [
                record for record in self._webhooks.values()
                if record.status == WebhookStatus.RETRYING
                and record.next_retry_at
                and record.next_retry_at <= now
            ]

        for record in pending:
            success = self._attempt_delivery(record)
            if not success:
                self._schedule_retry(record)
            processed += 1

        if processed > 0:
            logger.info(f"Cola de reintentos procesada: {processed} webhooks")
        return processed

    def retry_dead_letter(self, webhook_id: str) -> bool:
        """
        Reintenta manualmente un webhook en la Dead Letter Queue.

        Args:
            webhook_id: ID del webhook a reintentar

        Returns:
            True si se entrego exitosamente
        """
        record = self._webhooks.get(webhook_id)
        if not record or record.status != WebhookStatus.DEAD:
            logger.warning(f"Webhook {webhook_id} no encontrado en DLQ")
            return False

        logger.info(f"Reintentando webhook desde DLQ: {webhook_id}")
        record.attempt = record.max_attempts - 1  # Un intento mas
        record.status = WebhookStatus.RETRYING

        success = self._attempt_delivery(record)
        if success and webhook_id in self._dead_letter_queue:
            self._dead_letter_queue.remove(webhook_id)
        return success

    def get_webhook_status(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Retorna el estado actual de un webhook."""
        record = self._webhooks.get(webhook_id)
        if not record:
            return None
        return record.to_dict()

    def get_dlq_webhooks(self) -> List[Dict]:
        """Retorna todos los webhooks en la Dead Letter Queue."""
        return [
            self._webhooks[wid].to_dict()
            for wid in self._dead_letter_queue
            if wid in self._webhooks
        ]

    def cleanup_old_webhooks(self, max_age_hours: int = 24) -> int:
        """
        Elimina webhooks antiguos ya entregados.

        Args:
            max_age_hours: Edad maxima en horas para webhooks entregados

        Returns:
            Numero de webhooks eliminados
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_delete = []

        with self._lock:
            for webhook_id, record in self._webhooks.items():
                if (
                    record.status == WebhookStatus.DELIVERED
                    and record.delivered_at
                    and record.delivered_at < cutoff
                ):
                    to_delete.append(webhook_id)

            for webhook_id in to_delete:
                del self._webhooks[webhook_id]

        logger.info(f"Limpieza de webhooks: {len(to_delete)} registros eliminados")
        return len(to_delete)

    def get_stats(self) -> Dict[str, Any]:
        """Estadisticas del gestor de webhooks."""
        all_records = list(self._webhooks.values())
        by_status = {}
        for status in WebhookStatus:
            by_status[status.value] = len([r for r in all_records if r.status == status])

        return {
            "total_webhooks": len(all_records),
            "by_status": by_status,
            "dlq_size": len(self._dead_letter_queue),
            "delivery_rate": (
                round(by_status.get("delivered", 0) / len(all_records) * 100, 1)
                if all_records else 0
            ),
        }
