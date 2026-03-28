"""
Tests para el A/B Testing Framework (Gap #29)
"""
import pytest
from src.ab_testing.ab_test_manager import ABTestManager, ExperimentStatus
from src.ab_testing.experiment_tracker import ExperimentTracker


class TestABTestManager:
    def setup_method(self):
        self.manager = ABTestManager()
        self.variants = [
            {"name": "control", "description": "Voz actual", "config": {"tts": "google"}, "traffic_percentage": 50.0},
            {"name": "variante_a", "description": "Voz nueva", "config": {"tts": "neural2"}, "traffic_percentage": 50.0},
        ]

    def test_create_experiment(self):
        exp_id = self.manager.create_experiment("test_tts", "Test TTS engines", self.variants)
        assert exp_id is not None
        assert len(exp_id) > 0

    def test_experiment_starts_as_draft(self):
        exp_id = self.manager.create_experiment("test_exp", "Desc", self.variants)
        experiments = self.manager.list_experiments()
        exp = next(e for e in experiments if e["id"] == exp_id)
        assert exp["status"] == ExperimentStatus.DRAFT.value

    def test_start_experiment(self):
        exp_id = self.manager.create_experiment("test_start", "Desc", self.variants)
        result = self.manager.start_experiment(exp_id)
        assert result is True
        experiments = self.manager.list_experiments()
        exp = next(e for e in experiments if e["id"] == exp_id)
        assert exp["status"] == ExperimentStatus.RUNNING.value

    def test_start_already_running_fails(self):
        exp_id = self.manager.create_experiment("test_double_start", "Desc", self.variants)
        self.manager.start_experiment(exp_id)
        result = self.manager.start_experiment(exp_id)
        assert result is False

    def test_assign_user_deterministic(self):
        exp_id = self.manager.create_experiment("test_assign", "Desc", self.variants)
        self.manager.start_experiment(exp_id)
        # Mismo usuario siempre recibe misma variante
        variant1 = self.manager.assign_user("user_123", exp_id)
        variant2 = self.manager.assign_user("user_123", exp_id)
        assert variant1 == variant2

    def test_assign_user_returns_valid_variant(self):
        exp_id = self.manager.create_experiment("test_assign2", "Desc", self.variants)
        self.manager.start_experiment(exp_id)
        variant = self.manager.assign_user("user_456", exp_id)
        assert variant in ["control", "variante_a"]

    def test_assign_user_to_stopped_experiment_returns_none(self):
        exp_id = self.manager.create_experiment("test_stopped", "Desc", self.variants)
        # No iniciar - status DRAFT
        result = self.manager.assign_user("user_789", exp_id)
        assert result is None

    def test_track_metric(self):
        exp_id = self.manager.create_experiment("test_metrics", "Desc", self.variants)
        self.manager.start_experiment(exp_id)
        # No debe lanzar excepcion
        self.manager.track_metric(exp_id, "control", "csat_score", 4.5)
        self.manager.track_metric(exp_id, "control", "csat_score", 4.7)

    def test_get_experiment_results(self):
        exp_id = self.manager.create_experiment("test_results", "Desc", self.variants)
        self.manager.start_experiment(exp_id)
        results = self.manager.get_experiment_results(exp_id)
        assert results is not None
        assert "variants" in results
        assert results["experiment_id"] == exp_id

    def test_get_results_nonexistent_experiment(self):
        result = self.manager.get_experiment_results("nonexistent")
        assert result is None

    def test_stop_experiment(self):
        exp_id = self.manager.create_experiment("test_stop", "Desc", self.variants)
        self.manager.start_experiment(exp_id)
        result = self.manager.stop_experiment(exp_id)
        assert result is True

    def test_stop_not_running_fails(self):
        exp_id = self.manager.create_experiment("test_stop2", "Desc", self.variants)
        result = self.manager.stop_experiment(exp_id)  # Draft, no running
        assert result is False

    def test_get_variant_config(self):
        exp_id = self.manager.create_experiment("test_config", "Desc", self.variants)
        self.manager.start_experiment(exp_id)
        config = self.manager.get_variant_config("user_999", exp_id)
        assert config is not None
        assert "variant" in config
        assert "config" in config

    def test_traffic_normalization(self):
        """Variantes con trafico que no suma 100% deben normalizarse."""
        variants_bad = [
            {"name": "a", "config": {}, "traffic_percentage": 30.0},
            {"name": "b", "config": {}, "traffic_percentage": 30.0},
        ]
        exp_id = self.manager.create_experiment("test_norm", "Desc", variants_bad)
        self.manager.start_experiment(exp_id)
        # Debe poder asignar usuarios sin error
        variant = self.manager.assign_user("user_001", exp_id)
        assert variant in ["a", "b"]

    def test_list_experiments(self):
        self.manager.create_experiment("exp1", "Desc1", self.variants)
        self.manager.create_experiment("exp2", "Desc2", self.variants)
        experiments = self.manager.list_experiments()
        names = [e["name"] for e in experiments]
        assert "exp1" in names
        assert "exp2" in names


class TestExperimentTracker:
    def setup_method(self):
        self.tracker = ExperimentTracker()

    def test_track_conversion(self):
        self.tracker.track_conversion("user1", "exp1", "control", "ticket_created")
        self.tracker.track_conversion("user2", "exp1", "control", "ticket_created")
        rate = self.tracker.get_conversion_rate("exp1", "control", "ticket_created", total_users=10)
        assert rate == 0.2

    def test_track_engagement(self):
        self.tracker.track_engagement("user1", "exp1", "variante_a", "call_duration", 120.0)
        self.tracker.track_engagement("user2", "exp1", "variante_a", "call_duration", 180.0)
        stats = self.tracker.get_engagement_stats("exp1", "variante_a", "call_duration")
        assert stats["count"] == 2
        assert stats["mean"] == 150.0

    def test_get_conversion_rate_no_users(self):
        rate = self.tracker.get_conversion_rate("exp_empty", "control", "default")
        assert rate == 0.0

    def test_get_experiment_summary(self):
        self.tracker.track_conversion("u1", "exp2", "control", "resolved")
        self.tracker.track_engagement("u1", "exp2", "control", "csat", 4.5)
        summary = self.tracker.get_experiment_summary("exp2")
        assert "experiment_id" in summary
        assert "variants" in summary

    def test_recent_events(self):
        self.tracker.track_conversion("u1", "exp3", "control", "conversion")
        events = self.tracker.get_recent_events(limit=10)
        assert len(events) >= 1
        assert events[-1]["type"] == "conversion"
