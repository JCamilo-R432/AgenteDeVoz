"""
Tests para Chaos Engineering (Gap #34)
"""
import pytest
from src.chaos.chaos_monkey import ChaosMonkey, ChaosExperiment, FailureType
from src.chaos.failure_scenarios import FailureScenarios
from src.chaos.resilience_tests import ResilienceTests


class TestChaosMonkey:
    def setup_method(self):
        self.monkey = ChaosMonkey(environment="staging")

    def teardown_method(self):
        self.monkey.disable()

    def test_initialization(self):
        assert not self.monkey._enabled
        assert self.monkey._environment == "staging"

    def test_enable_disable(self):
        self.monkey.enable()
        assert self.monkey._enabled is True
        self.monkey.disable()
        assert self.monkey._enabled is False

    def test_inject_failure_latency(self):
        self.monkey.inject_failure("database", "latency", 0.5, latency_ms=100)
        assert "database" in self.monkey._injected_failures

    def test_inject_failure_invalid_type_raises(self):
        with pytest.raises(ValueError):
            self.monkey.inject_failure("database", "invalid_type")

    def test_inject_failure_invalid_probability_raises(self):
        with pytest.raises(ValueError):
            self.monkey.inject_failure("database", "latency", probability=1.5)

    def test_should_fail_when_disabled(self):
        self.monkey.inject_failure("database", "latency", 1.0)
        # No habilitado -> no debe fallar
        assert self.monkey.should_fail("database") is False

    def test_should_fail_with_zero_probability(self):
        self.monkey.inject_failure("redis", "error", 0.0)
        self.monkey.enable()
        # Probabilidad 0 -> nunca falla
        for _ in range(20):
            assert self.monkey.should_fail("redis") is False

    def test_should_fail_with_full_probability(self):
        self.monkey.inject_failure("twilio", "error", 1.0)
        self.monkey.enable()
        # Probabilidad 1.0 -> siempre falla
        for _ in range(5):
            assert self.monkey.should_fail("twilio") is True

    def test_apply_failure_latency(self):
        import time
        self.monkey.inject_failure("test_service", "latency", 1.0, latency_ms=50)
        start = time.time()
        self.monkey.apply_failure("test_service")
        elapsed = (time.time() - start) * 1000
        assert elapsed >= 40  # Al menos 40ms (tolerancia)

    def test_apply_failure_error_raises(self):
        self.monkey.inject_failure("test_err", "error", 1.0, error_msg="Test error")
        with pytest.raises(Exception, match="Test error"):
            self.monkey.apply_failure("test_err")

    def test_apply_failure_timeout_raises(self):
        self.monkey.inject_failure("test_timeout", "timeout", 1.0, timeout_ms=50)
        with pytest.raises(TimeoutError):
            self.monkey.apply_failure("test_timeout")

    def test_run_experiment_basic(self):
        scenario = ChaosExperiment(
            name="test_basic",
            description="Test basico",
            service="test_svc",
            failure_type="latency",
            probability=0.5,
            duration_seconds=1.0,  # Corto para el test
            kwargs={"latency_ms": 10},
        )
        result = self.monkey.run_experiment(scenario, lambda: True)
        assert result.experiment_name == "test_basic"
        assert result.total_calls > 0
        assert 0 <= result.resilience_score <= 100

    def test_run_experiment_all_pass(self):
        scenario = ChaosExperiment(
            name="test_all_pass",
            description="Sin fallos",
            service="no_fail_svc",
            failure_type="latency",
            probability=0.0,  # Sin inyeccion
            duration_seconds=0.5,
            kwargs={"latency_ms": 1},
        )
        result = self.monkey.run_experiment(scenario, lambda: True)
        assert result.failed_calls == 0

    def test_generate_resilience_report_empty(self):
        report = self.monkey.generate_resilience_report([])
        assert "error" in report

    def test_generate_resilience_report_with_results(self):
        from src.chaos.chaos_monkey import ExperimentResult
        results = [
            ExperimentResult(
                experiment_name="test1",
                success=True,
                total_calls=100,
                failed_calls=5,
                avg_latency_ms=200.0,
                max_latency_ms=500.0,
                errors=[],
                resilience_score=95.0,
            )
        ]
        report = self.monkey.generate_resilience_report(results)
        assert "overall_score" in report
        assert "overall_status" in report
        assert report["overall_score"] == 95.0

    def test_disable_clears_failures(self):
        self.monkey.inject_failure("db", "error", 1.0)
        self.monkey.enable()
        self.monkey.disable()
        assert len(self.monkey._injected_failures) == 0


class TestFailureScenarios:
    def test_all_scenarios_are_valid(self):
        scenarios = FailureScenarios.all_scenarios()
        assert len(scenarios) == 5
        for s in scenarios:
            assert s.name
            assert s.service
            assert s.failure_type in [f.value for f in FailureType]
            assert 0.0 <= s.probability <= 1.0
            assert s.duration_seconds > 0

    def test_database_latency_scenario(self):
        s = FailureScenarios.database_latency()
        assert s.service == "database"
        assert s.failure_type == "latency"
        assert s.kwargs.get("latency_ms", 0) > 0

    def test_redis_unavailable_scenario(self):
        s = FailureScenarios.redis_unavailable()
        assert s.probability == 1.0
        assert s.failure_type == "error"


class TestResilienceTests:
    def test_run_single_valid_scenario(self):
        tester = ResilienceTests()
        report = tester.run_single("redis_unavailable")
        assert "overall_score" in report
        assert "experiments_run" in report

    def test_run_single_invalid_scenario(self):
        tester = ResilienceTests()
        report = tester.run_single("nonexistent_scenario")
        assert "error" in report

    def test_get_last_report_no_results(self):
        tester = ResilienceTests()
        report = tester.get_last_report()
        assert "error" in report
