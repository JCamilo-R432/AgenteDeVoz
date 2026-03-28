"""Tests para DistributedTracing y JaegerClient (Gap #23)"""
import time
import pytest
from src.observability.distributed_tracing import DistributedTracing, Span
from src.observability.jaeger_client import JaegerClient, JaegerConfig


@pytest.fixture
def tracer():
    return DistributedTracing(service_name="test-service")


@pytest.fixture
def jaeger():
    config = JaegerConfig(
        collector_url="http://localhost:14268/api/traces",
        service_name="test-service",
        sample_rate=1.0,
    )
    return JaegerClient(config)


class TestDistributedTracing:
    def test_start_trace_returns_span(self, tracer):
        span = tracer.start_trace("test_op")
        assert isinstance(span, Span)
        tracer.finish_span(span)

    def test_trace_id_not_empty(self, tracer):
        span = tracer.start_trace("op")
        assert len(span.trace_id) > 0
        tracer.finish_span(span)

    def test_span_id_not_empty(self, tracer):
        span = tracer.start_trace("op")
        assert len(span.span_id) > 0
        tracer.finish_span(span)

    def test_root_span_no_parent(self, tracer):
        span = tracer.start_trace("op")
        assert span.parent_span_id is None
        tracer.finish_span(span)

    def test_child_span_has_parent(self, tracer):
        root = tracer.start_trace("root")
        child = tracer.start_child_span(root, "child")
        assert child.parent_span_id == root.span_id
        tracer.finish_span(child)
        tracer.finish_span(root)

    def test_child_same_trace_id(self, tracer):
        root = tracer.start_trace("root")
        child = tracer.start_child_span(root, "child")
        assert child.trace_id == root.trace_id
        tracer.finish_span(child)
        tracer.finish_span(root)

    def test_finish_span_sets_end_time(self, tracer):
        span = tracer.start_trace("op")
        tracer.finish_span(span)
        assert span.end_time is not None

    def test_duration_ms_positive(self, tracer):
        span = tracer.start_trace("op")
        time.sleep(0.01)
        tracer.finish_span(span)
        assert span.duration_ms > 0.0

    def test_set_tag(self, tracer):
        span = tracer.start_trace("op")
        span.set_tag("http.method", "POST")
        assert span.tags["http.method"] == "POST"
        tracer.finish_span(span)

    def test_log_event(self, tracer):
        span = tracer.start_trace("op")
        span.log_event("db.query", {"table": "users"})
        assert len(span.logs) == 1
        tracer.finish_span(span)

    def test_span_status_error(self, tracer):
        span = tracer.start_trace("op")
        tracer.finish_span(span, status="error")
        assert span.status == "error"

    def test_context_manager_success(self, tracer):
        with tracer.trace("ctx_op") as span:
            assert span.operation_name == "ctx_op"
        assert span.end_time is not None
        assert span.status == "ok"

    def test_context_manager_error(self, tracer):
        with pytest.raises(ValueError):
            with tracer.trace("failing_op") as span:
                raise ValueError("test error")
        assert span.status == "error"

    def test_stats_structure(self, tracer):
        stats = tracer.get_stats()
        assert "active_traces" in stats
        assert "completed_traces" in stats

    def test_to_dict(self, tracer):
        span = tracer.start_trace("op", tags={"env": "test"})
        tracer.finish_span(span)
        d = span.to_dict()
        assert "trace_id" in d
        assert "operation" in d
        assert "duration_ms" in d


class TestJaegerClient:
    def test_export_span_success(self, jaeger, tracer):
        span = tracer.start_trace("test_op")
        tracer.finish_span(span)
        result = jaeger.export_span(span)
        assert isinstance(result, bool)

    def test_flush_empty_buffer(self, jaeger):
        result = jaeger.flush()
        assert result is True

    def test_metrics_structure(self, jaeger):
        metrics = jaeger.get_metrics()
        assert "exported_spans" in metrics
        assert "failed_spans" in metrics
        assert "buffer_size" in metrics

    def test_export_spans_batch(self, jaeger, tracer):
        spans = []
        root = tracer.start_trace("batch_root")
        for i in range(3):
            child = tracer.start_child_span(root, f"child_{i}")
            tracer.finish_span(child)
            spans.append(child)
        tracer.finish_span(root)
        spans.append(root)
        result = jaeger.export_spans(spans)
        assert isinstance(result, bool)
