"""
Tests para Webhook Retry Manager con backoff exponencial (Gap #39)
"""
import time
import pytest
from src.compliance.webhook_retry import WebhookRetryManager, WebhookStatus


class TestWebhookRetryManager:
    def setup_method(self):
        self.manager = WebhookRetryManager()

    def test_send_webhook_returns_id(self):
        webhook_id = self.manager.send_webhook(
            "http://test.example.com/webhook",
            {"event": "ticket.created", "ticket_id": "TKT-001"},
        )
        assert webhook_id is not None
        assert len(webhook_id) > 0

    def test_webhook_id_is_unique(self):
        id1 = self.manager.send_webhook("http://test.com/wh1", {"event": "a"})
        id2 = self.manager.send_webhook("http://test.com/wh2", {"event": "b"})
        assert id1 != id2

    def test_get_webhook_status_after_send(self):
        webhook_id = self.manager.send_webhook("http://test.com/wh", {"event": "test"})
        status = self.manager.get_webhook_status(webhook_id)
        assert status is not None
        assert "id" in status
        assert "status" in status
        assert "url" in status

    def test_get_nonexistent_webhook_status(self):
        result = self.manager.get_webhook_status("nonexistent_id")
        assert result is None

    def test_webhook_status_after_simulated_delivery(self):
        """En modo simulado (sin requests), el webhook debe entregarse exitosamente."""
        webhook_id = self.manager.send_webhook("http://test.com/sim", {"test": True})
        status = self.manager.get_webhook_status(webhook_id)
        # Modo simulado: debe estar DELIVERED
        assert status["status"] == WebhookStatus.DELIVERED.value

    def test_calculate_retry_delay_exponential(self):
        """El delay debe crecer exponencialmente."""
        delay_1 = self.manager._calculate_retry_delay(1)
        delay_2 = self.manager._calculate_retry_delay(2)
        delay_3 = self.manager._calculate_retry_delay(3)
        # Con jitter, el delay 2 debe ser significativamente mayor que delay 1
        assert delay_2 > delay_1 * 1.5
        assert delay_3 > delay_2 * 1.5

    def test_calculate_retry_delay_has_jitter(self):
        """El delay debe incluir jitter (no siempre el mismo valor)."""
        delays = [self.manager._calculate_retry_delay(2) for _ in range(20)]
        # Con jitter, no todos los delays deben ser iguales
        unique_delays = len(set(delays))
        assert unique_delays > 1

    def test_calculate_retry_delay_minimum_one_second(self):
        """El delay minimo debe ser >= 1 segundo."""
        for attempt in range(1, 6):
            delay = self.manager._calculate_retry_delay(attempt)
            assert delay >= 1.0

    def test_dlq_after_max_attempts(self):
        """Un webhook que falla max_attempts veces debe ir a DLQ."""
        from src.compliance.webhook_retry import WebhookRecord
        record = WebhookRecord("test_dlq", "http://fail.com", {}, "evt1")
        record.attempt = record.max_attempts  # Ya alcanzo el maximo
        self.manager._webhooks["test_dlq"] = record
        self.manager._move_to_dlq(record)
        assert "test_dlq" in self.manager._dead_letter_queue
        assert record.status == WebhookStatus.DEAD

    def test_get_dlq_webhooks(self):
        from src.compliance.webhook_retry import WebhookRecord
        record = WebhookRecord("dlq_id", "http://dead.com", {}, "evt2")
        self.manager._webhooks["dlq_id"] = record
        self.manager._dead_letter_queue.append("dlq_id")
        record.status = WebhookStatus.DEAD
        dlq = self.manager.get_dlq_webhooks()
        dlq_ids = [w["id"] for w in dlq]
        assert "dlq_id" in dlq_ids

    def test_retry_dead_letter_nonexistent(self):
        result = self.manager.retry_dead_letter("nonexistent_dlq")
        assert result is False

    def test_cleanup_old_webhooks(self):
        """Limpiar webhooks entregados mas antiguos que max_age_hours."""
        from datetime import datetime, timedelta
        from src.compliance.webhook_retry import WebhookRecord

        record = WebhookRecord("old_wh", "http://test.com", {}, "evt3")
        record.status = WebhookStatus.DELIVERED
        record.delivered_at = datetime.utcnow() - timedelta(hours=25)
        self.manager._webhooks["old_wh"] = record

        removed = self.manager.cleanup_old_webhooks(max_age_hours=24)
        assert removed >= 1
        assert "old_wh" not in self.manager._webhooks

    def test_cleanup_keeps_recent_webhooks(self):
        """No eliminar webhooks entregados recientemente."""
        from src.compliance.webhook_retry import WebhookRecord
        from datetime import datetime

        record = WebhookRecord("new_wh", "http://test.com", {}, "evt4")
        record.status = WebhookStatus.DELIVERED
        record.delivered_at = datetime.utcnow()
        self.manager._webhooks["new_wh"] = record

        removed = self.manager.cleanup_old_webhooks(max_age_hours=24)
        assert "new_wh" in self.manager._webhooks

    def test_process_retry_queue_empty(self):
        processed = self.manager.process_retry_queue()
        assert processed == 0

    def test_get_stats(self):
        self.manager.send_webhook("http://test.com/s1", {"e": "1"})
        stats = self.manager.get_stats()
        assert "total_webhooks" in stats
        assert "by_status" in stats
        assert "dlq_size" in stats
        assert "delivery_rate" in stats
        assert stats["total_webhooks"] >= 1

    def test_custom_event_id(self):
        custom_id = "evt_custom_123"
        webhook_id = self.manager.send_webhook(
            "http://test.com/custom",
            {"data": "test"},
            event_id=custom_id,
        )
        status = self.manager.get_webhook_status(webhook_id)
        assert status["event_id"] == custom_id
