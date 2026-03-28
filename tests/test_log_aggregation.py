"""Tests para LogAggregator y ElasticsearchClient (Gap #24)"""
import pytest
from src.observability.log_aggregation import LogAggregator, LogLevel, LogEntry
from src.observability.elasticsearch_client import ElasticsearchClient


@pytest.fixture
def agg():
    return LogAggregator(service_name="test-service", backend="stdout", min_level=LogLevel.DEBUG)


@pytest.fixture
def es():
    return ElasticsearchClient(host="localhost", port=9200, index_prefix="test")


class TestLogAggregator:
    def test_log_info(self, agg):
        agg.info("mensaje de prueba")
        assert len(agg._buffer) == 1

    def test_log_warning(self, agg):
        agg.warning("advertencia")
        assert any(e.level == LogLevel.WARNING for e in agg._buffer)

    def test_log_error(self, agg):
        agg.error("error critico")
        assert any(e.level == LogLevel.ERROR for e in agg._buffer)

    def test_log_debug(self, agg):
        agg.debug("debug info")
        assert any(e.level == LogLevel.DEBUG for e in agg._buffer)

    def test_log_with_session_id(self, agg):
        agg.info("mensaje", session_id="sess_001")
        entry = agg._buffer[-1]
        assert entry.session_id == "sess_001"

    def test_log_with_trace_id(self, agg):
        agg.info("mensaje", trace_id="trace_abc")
        entry = agg._buffer[-1]
        assert entry.trace_id == "trace_abc"

    def test_level_filter_drops_debug(self):
        filtered_agg = LogAggregator(
            service_name="svc", backend="stdout", min_level=LogLevel.INFO
        )
        filtered_agg.debug("should be dropped")
        assert len(filtered_agg._buffer) == 0

    def test_flush_returns_count(self, agg):
        agg.info("a")
        agg.info("b")
        count = agg.flush()
        assert count == 2

    def test_flush_clears_buffer(self, agg):
        agg.info("a")
        agg.flush()
        assert len(agg._buffer) == 0

    def test_flush_empty_returns_zero(self, agg):
        count = agg.flush()
        assert count == 0

    def test_auto_flush_on_batch_size(self):
        small_agg = LogAggregator(
            service_name="svc", backend="stdout", batch_size=3, min_level=LogLevel.DEBUG
        )
        for i in range(4):
            small_agg.info(f"msg {i}")
        # Despues del 4to mensaje, el batch_size=3 ya causo flush
        assert small_agg._sent_count >= 3

    def test_get_stats_structure(self, agg):
        stats = agg.get_stats()
        assert "service" in stats
        assert "backend" in stats
        assert "sent_total" in stats

    def test_search_by_level(self, agg):
        agg.error("error aqui")
        agg.info("info aqui")
        results = agg.search(level=LogLevel.ERROR)
        assert all(e["level"] == "ERROR" for e in results)

    def test_search_by_session_id(self, agg):
        agg.info("msg 1", session_id="sess_x")
        agg.info("msg 2", session_id="sess_y")
        results = agg.search(session_id="sess_x")
        assert all(e["session_id"] == "sess_x" for e in results)

    def test_log_entry_to_json(self):
        entry = LogEntry(level=LogLevel.INFO, message="test", service="svc")
        json_str = entry.to_json()
        assert "test" in json_str
        assert "INFO" in json_str


class TestElasticsearchClient:
    def test_index_document(self, es):
        result = es.index_document("logs", {"message": "test", "level": "INFO"})
        assert result is True

    def test_bulk_index(self, es):
        docs = [{"message": f"msg {i}"} for i in range(5)]
        count = es.bulk_index("logs", docs)
        assert count == 5

    def test_search_returns_dict(self, es):
        result = es.search("logs", query={"match_all": {}})
        assert "hits" in result
        assert "took" in result

    def test_search_logs_filter(self, es):
        results = es.search_logs(level="ERROR", size=10)
        assert isinstance(results, list)

    def test_create_index(self, es):
        result = es.create_index("custom-index")
        assert result is True

    def test_delete_old_logs(self, es):
        deleted = es.delete_old_logs("logs", older_than_days=30)
        assert deleted >= 0

    def test_get_index_stats(self, es):
        stats = es.get_index_stats("logs")
        assert "index" in stats
        assert "doc_count" in stats
