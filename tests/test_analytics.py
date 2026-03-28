"""
Tests para Business Intelligence Analytics (Gap #30)
"""
import pytest
from src.analytics.business_intelligence import BusinessIntelligence, KPI, ReportType
from src.analytics.metrics_collector import MetricsCollector
from src.analytics.dashboard_analytics import DashboardAnalytics


class TestBusinessIntelligence:
    def setup_method(self):
        self.bi = BusinessIntelligence()

    def test_get_kpis_returns_all_kpis(self):
        kpis = self.bi.get_kpis()
        assert "fcr" in kpis
        assert "escalation_rate" in kpis
        assert "aht" in kpis
        assert "csat" in kpis
        assert "ticket_resolution" in kpis

    def test_kpi_has_required_fields(self):
        kpis = self.bi.get_kpis()
        fcr = kpis["fcr"]
        assert isinstance(fcr, KPI)
        assert fcr.name
        assert fcr.value >= 0
        assert fcr.target > 0
        assert fcr.status in ("green", "yellow", "red")
        assert fcr.trend in ("up", "down", "stable")

    def test_kpi_to_dict(self):
        kpis = self.bi.get_kpis()
        d = kpis["fcr"].to_dict()
        assert "achievement_pct" in d
        assert "value" in d
        assert "target" in d

    def test_user_segmentation(self):
        seg = self.bi.get_user_segmentation()
        assert "by_channel" in seg
        assert "by_intent" in seg
        assert "total_interactions" in seg

    def test_segmentation_percentages_sum(self):
        seg = self.bi.get_user_segmentation()
        total_pct = sum(v["percentage"] for v in seg["by_channel"].values())
        assert abs(total_pct - 100.0) < 1.0  # Tolerancia de 1%

    def test_trend_analysis_calls(self):
        trend = self.bi.get_trend_analysis("calls", days=7)
        assert "trend" in trend
        assert "average" in trend
        assert "data_points" in trend
        assert trend["trend"] in ("creciente", "decreciente", "estable")

    def test_generate_executive_report(self):
        report = self.bi.generate_report("executive")
        assert report["report_type"] == "executive"
        assert "kpis" in report
        assert "key_insights" in report

    def test_generate_operational_report(self):
        report = self.bi.generate_report("operational")
        assert "segmentation" in report

    def test_generate_technical_report(self):
        report = self.bi.generate_report("technical")
        assert "raw_data" in report

    def test_export_json(self):
        import json
        export = self.bi.export_report("json")
        data = json.loads(export)
        assert "kpis" in data

    def test_export_csv(self):
        export = self.bi.export_report("csv")
        assert "KPI,Valor" in export
        lines = export.strip().split("\n")
        assert len(lines) > 1


class TestMetricsCollector:
    def setup_method(self):
        self.collector = MetricsCollector()

    def test_record_and_get_latency(self):
        self.collector.record_latency("/health", 45.0)
        self.collector.record_latency("/health", 55.0)
        stats = self.collector.get_latency_stats()
        assert stats["count"] == 2
        assert stats["avg"] == 50.0

    def test_latency_percentiles(self):
        for i in range(100):
            self.collector.record_latency("/test", float(i + 1))
        stats = self.collector.get_latency_stats()
        assert stats["p50"] > 0
        assert stats["p95"] >= stats["p50"]
        assert stats["p99"] >= stats["p95"]

    def test_increment_counter(self):
        self.collector.increment("calls_today")
        self.collector.increment("calls_today", 5)
        counters = self.collector.get_counters()
        assert counters["calls_today"] == 6

    def test_uptime_positive(self):
        uptime = self.collector.get_uptime()
        assert uptime >= 0

    def test_get_snapshot(self):
        self.collector.record_latency("/test", 100.0)
        snapshot = self.collector.get_snapshot()
        assert "uptime_seconds" in snapshot
        assert "counters" in snapshot
        assert "latency" in snapshot
        assert "timestamp" in snapshot


class TestDashboardAnalytics:
    def setup_method(self):
        self.dashboard = DashboardAnalytics()

    def test_realtime_stats(self):
        stats = self.dashboard.get_realtime_stats()
        assert "active_calls" in stats
        assert "error_rate" in stats
        assert "updated_at" in stats

    def test_chart_data_calls(self):
        chart = self.dashboard.get_chart_data("calls_over_time", hours=12)
        assert chart["type"] == "line"
        assert "labels" in chart
        assert "datasets" in chart

    def test_chart_data_intent(self):
        chart = self.dashboard.get_chart_data("intent_distribution")
        assert chart["type"] == "pie"
        assert len(chart["labels"]) > 0

    def test_chart_data_channel(self):
        chart = self.dashboard.get_chart_data("channel_mix")
        assert chart["type"] == "donut"

    def test_invalid_chart_type(self):
        chart = self.dashboard.get_chart_data("nonexistent_chart")
        assert "error" in chart
