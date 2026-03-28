"""
Tests: Load Testing Infrastructure (scenarios, analyzer)
"""
import csv
import json
import os
import pytest
from pathlib import Path


ROOT = Path(__file__).parent.parent


class TestLocustfileExists:
    def test_locustfile_exists(self):
        assert (ROOT / "testing" / "load_testing" / "locustfile.py").exists()

    def test_scenarios_py_exists(self):
        assert (ROOT / "testing" / "load_testing" / "scenarios.py").exists()

    def test_results_analyzer_exists(self):
        assert (ROOT / "testing" / "load_testing" / "results_analyzer.py").exists()


class TestLocustfileContent:
    @pytest.fixture
    def locust_content(self):
        return (ROOT / "testing" / "load_testing" / "locustfile.py").read_text()

    def test_has_http_user(self, locust_content):
        assert "HttpUser" in locust_content

    def test_has_task_decorator(self, locust_content):
        assert "@task" in locust_content

    def test_has_between_wait(self, locust_content):
        assert "between" in locust_content

    def test_has_standard_user(self, locust_content):
        assert "StandardUser" in locust_content

    def test_has_power_user(self, locust_content):
        assert "PowerUser" in locust_content

    def test_has_on_start(self, locust_content):
        assert "on_start" in locust_content

    def test_has_auth_task(self, locust_content):
        assert "auth/login" in locust_content or "/login" in locust_content

    def test_has_voice_task(self, locust_content):
        assert "voice" in locust_content

    def test_has_health_check(self, locust_content):
        assert "/health" in locust_content


class TestScenarios:
    def test_scenarios_importable(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS, get_scenario
        assert SCENARIOS is not None

    def test_minimum_scenarios(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS
        assert len(SCENARIOS) >= 4

    def test_required_scenarios_exist(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS
        required = ["smoke", "baseline", "stress"]
        for name in required:
            assert name in SCENARIOS, f"Missing scenario: {name}"

    def test_scenario_has_users(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS
        for name, s in SCENARIOS.items():
            assert s.users > 0, f"{name}: users must be > 0"

    def test_scenario_has_duration(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS
        for name, s in SCENARIOS.items():
            assert s.duration_seconds > 0, f"{name}: duration must be > 0"

    def test_scenario_has_spawn_rate(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS
        for name, s in SCENARIOS.items():
            assert s.spawn_rate > 0, f"{name}: spawn_rate must be > 0"

    def test_scenario_has_success_criteria(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS
        for name, s in SCENARIOS.items():
            assert s.success_criteria, f"{name}: success_criteria must be defined"

    def test_scenario_has_max_failure_rate(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS
        for name, s in SCENARIOS.items():
            assert "max_failure_rate_pct" in s.success_criteria

    def test_smoke_is_quick(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import SCENARIOS
        smoke = SCENARIOS["smoke"]
        assert smoke.users <= 20
        assert smoke.duration_seconds <= 120

    def test_get_scenario_returns_correct(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import get_scenario
        s = get_scenario("baseline")
        assert s is not None
        assert s.name == "baseline"

    def test_get_scenario_unknown_returns_none(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import get_scenario
        s = get_scenario("nonexistent_scenario_xyz")
        assert s is None

    def test_to_locust_args(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.scenarios import get_scenario
        s = get_scenario("smoke")
        args = s.to_locust_args()
        assert "locust" in args
        assert "--users" in args
        assert "--run-time" in args
        assert "--headless" in args


class TestResultsAnalyzer:
    def test_analyzer_importable(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.results_analyzer import ResultsAnalyzer
        assert ResultsAnalyzer is not None

    def test_analyzer_raises_on_missing_file(self, tmp_path):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.results_analyzer import ResultsAnalyzer
        analyzer = ResultsAnalyzer(reports_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            analyzer.analyze("nonexistent")

    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create a minimal Locust stats CSV."""
        headers = [
            "Type", "Name", "Request Count", "Failure Count",
            "Median Response Time", "Average Response Time (ms)",
            "Min Response Time", "Max Response Time", "Average Content Size",
            "Requests/s", "Failures/s", "50%", "66%", "75%", "80%",
            "90%", "95%", "98%", "99%", "99.9%", "99.99%", "100%",
            "Average (ms)"
        ]
        rows = [
            ["GET", "/health", "1000", "5", "50", "65", "10", "500",
             "200", "16.7", "0.1", "50", "70", "80", "90", "150", "200",
             "300", "400", "450", "480", "500", "65"],
            ["", "Aggregated", "1000", "5", "50", "65", "10", "500",
             "200", "16.7", "0.1", "50", "70", "80", "90", "150", "200",
             "300", "400", "450", "480", "500", "65"],
        ]
        stats_file = tmp_path / "test_stats.csv"
        with open(stats_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return tmp_path

    def test_analyze_passes_criteria(self, sample_csv):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.results_analyzer import ResultsAnalyzer
        analyzer = ResultsAnalyzer(reports_dir=str(sample_csv))
        result = analyzer.analyze("test", {"max_failure_rate_pct": 5.0, "max_p95_ms": 500})
        assert result.total_requests == 1000
        assert result.total_failures == 5

    def test_analyze_detects_failure_rate_violation(self, sample_csv):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.results_analyzer import ResultsAnalyzer
        analyzer = ResultsAnalyzer(reports_dir=str(sample_csv))
        result = analyzer.analyze("test", {"max_failure_rate_pct": 0.1})  # 0.5% actual > 0.1%
        assert not result.passed or result.failure_rate_pct <= 0.1

    def test_analyze_result_has_required_fields(self, sample_csv):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.results_analyzer import ResultsAnalyzer
        analyzer = ResultsAnalyzer(reports_dir=str(sample_csv))
        result = analyzer.analyze("test")
        assert hasattr(result, "passed")
        assert hasattr(result, "total_requests")
        assert hasattr(result, "failure_rate_pct")
        assert hasattr(result, "avg_rps")
        assert hasattr(result, "p95_ms")
        assert hasattr(result, "violations")

    def test_save_json(self, sample_csv, tmp_path):
        import sys
        sys.path.insert(0, str(ROOT))
        from testing.load_testing.results_analyzer import ResultsAnalyzer
        analyzer = ResultsAnalyzer(reports_dir=str(sample_csv))
        result = analyzer.analyze("test")
        out = str(tmp_path / "result.json")
        analyzer.save_json(result, out)
        assert Path(out).exists()
        data = json.loads(Path(out).read_text())
        assert "passed" in data
        assert "total_requests" in data
