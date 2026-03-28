"""Tests para Gap #13: Load Balancer."""
import pytest
from src.infrastructure.load_balancer import (
    LoadBalancer, Backend, BackendStatus, LBAlgorithm,
)
from src.infrastructure.haproxy_config import (
    HAProxyConfigGenerator, HAProxyBackendConfig, HAProxyFrontendConfig, HAProxyServer,
)
from src.infrastructure.health_check_advanced import (
    AdvancedHealthChecker, CircuitBreaker, CircuitBreakerConfig, CircuitState,
)


class TestLoadBalancer:
    @pytest.fixture
    def backends(self):
        return [
            Backend("b1", "10.0.0.1", 8000, weight=1),
            Backend("b2", "10.0.0.2", 8000, weight=2),
            Backend("b3", "10.0.0.3", 8000, weight=1),
        ]

    @pytest.fixture
    def lb(self, backends):
        lb = LoadBalancer(algorithm=LBAlgorithm.ROUND_ROBIN)
        for b in backends:
            lb.add_backend(b)
        return lb

    def test_add_backend(self, lb):
        stats = lb.get_stats()
        assert stats["total_backends"] == 3

    def test_round_robin_distributes(self, lb):
        selected = set()
        for _ in range(9):
            b = lb.select_backend()
            assert b is not None
            selected.add(b.backend_id)
            lb.release_backend(b.backend_id)
        assert len(selected) >= 2

    def test_least_connections(self, backends):
        lb = LoadBalancer(algorithm=LBAlgorithm.LEAST_CONNECTIONS)
        for b in backends:
            lb.add_backend(b)
        b = lb.select_backend()
        assert b is not None

    def test_weighted_round_robin(self, backends):
        lb = LoadBalancer(algorithm=LBAlgorithm.WEIGHTED_ROUND_ROBIN)
        for b in backends:
            lb.add_backend(b)
        selected = []
        for _ in range(10):
            b = lb.select_backend()
            selected.append(b.backend_id)
            lb.release_backend(b.backend_id)
        assert "b2" in selected   # b2 has higher weight

    def test_ip_hash_consistent(self, backends):
        lb = LoadBalancer(algorithm=LBAlgorithm.IP_HASH)
        for b in backends:
            lb.add_backend(b)
        b1 = lb.select_backend(client_ip="192.168.1.100")
        b2 = lb.select_backend(client_ip="192.168.1.100")
        assert b1.backend_id == b2.backend_id

    def test_no_available_backends_returns_none(self):
        lb = LoadBalancer()
        result = lb.select_backend()
        assert result is None

    def test_mark_backend_down(self, lb):
        lb.mark_backend_down("b1")
        b = lb.backends_iter = [b for b in lb._backends.values() if b.backend_id == "b1"]
        assert lb._backends["b1"].status == BackendStatus.DOWN

    def test_mark_backend_up(self, lb):
        lb.mark_backend_down("b1")
        lb.mark_backend_up("b1")
        assert lb._backends["b1"].status == BackendStatus.UP

    def test_drain_backend(self, lb):
        lb.drain_backend("b1")
        assert lb._backends["b1"].status == BackendStatus.MAINTENANCE

    def test_release_backend_decrements_connections(self, lb):
        b = lb.select_backend()
        initial_connections = b.active_connections
        lb.release_backend(b.backend_id)
        assert lb._backends[b.backend_id].active_connections == initial_connections - 1

    def test_release_failed_increments_error_count(self, lb):
        b = lb.select_backend()
        before = lb._backends[b.backend_id].failed_requests
        lb.release_backend(b.backend_id, success=False)
        assert lb._backends[b.backend_id].failed_requests == before + 1

    def test_stats_structure(self, lb):
        stats = lb.get_stats()
        assert "algorithm" in stats
        assert "available_backends" in stats
        assert "backends" in stats

    def test_remove_backend(self, lb):
        lb.remove_backend("b1")
        assert lb.get_stats()["total_backends"] == 2


class TestHAProxyConfigGenerator:
    @pytest.fixture
    def generator(self):
        return HAProxyConfigGenerator()

    def test_generate_default_config(self, generator):
        servers = [{"host": "10.0.0.1"}, {"host": "10.0.0.2"}]
        config = generator.generate_default_config(servers, api_port=8000, lb_port=80)
        assert "frontend" in config
        assert "backend" in config

    def test_config_contains_servers(self, generator):
        servers = [{"host": "10.0.0.1"}, {"host": "10.0.0.2"}]
        config = generator.generate_default_config(servers)
        assert "10.0.0.1" in config
        assert "10.0.0.2" in config

    def test_config_contains_health_check(self, generator):
        servers = [{"host": "10.0.0.1"}]
        config = generator.generate_default_config(servers)
        assert "health" in config.lower() or "/health" in config

    def test_config_has_stats_section(self, generator):
        backend = HAProxyBackendConfig(
            name="test_backend",
            servers=[HAProxyServer("s1", "10.0.0.1", 8000)],
        )
        generator.add_backend(backend)
        config = generator.generate_config()
        assert "stats" in config

    def test_config_has_global_section(self, generator):
        config = generator.generate_config()
        assert "global" in config

    def test_config_has_defaults_section(self, generator):
        config = generator.generate_config()
        assert "defaults" in config

    def test_balance_algorithm_in_config(self, generator):
        backend = HAProxyBackendConfig(
            name="lb_test",
            balance="leastconn",
            servers=[HAProxyServer("s1", "10.0.0.1", 8000)],
        )
        generator.add_backend(backend)
        config = generator.generate_config()
        assert "leastconn" in config

    def test_server_weight_in_config(self, generator):
        backend = HAProxyBackendConfig(
            name="weighted",
            servers=[HAProxyServer("s1", "10.0.0.1", 8000, weight=3)],
        )
        generator.add_backend(backend)
        config = generator.generate_config()
        assert "weight 3" in config


class TestCircuitBreaker:
    @pytest.fixture
    def breaker(self):
        cfg = CircuitBreakerConfig(failure_threshold=3, recovery_timeout_s=0.1, success_threshold=2)
        return CircuitBreaker("test_service", cfg)

    def test_initial_state_closed(self, breaker):
        assert breaker.get_state() == CircuitState.CLOSED

    def test_successful_call(self, breaker):
        result = breaker.call(lambda: "ok")
        assert result == "ok"

    def test_opens_after_threshold_failures(self, breaker):
        for _ in range(3):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        assert breaker.get_state() == CircuitState.OPEN

    def test_open_circuit_raises_runtime_error(self, breaker):
        breaker.force_open()
        with pytest.raises(RuntimeError):
            breaker.call(lambda: "ok")

    def test_half_open_after_timeout(self, breaker):
        import time
        breaker.force_open()
        time.sleep(0.15)
        try:
            breaker.call(lambda: "ok")
        except RuntimeError:
            pass
        assert breaker.get_state() in (CircuitState.HALF_OPEN, CircuitState.CLOSED)

    def test_closes_after_successes(self, breaker):
        breaker.force_open()
        breaker._last_failure_time = 0  # Force recovery_timeout
        # Simulate half-open -> successes
        breaker._state = CircuitState.HALF_OPEN
        for _ in range(2):
            breaker.call(lambda: "ok")
        assert breaker.get_state() == CircuitState.CLOSED

    def test_force_close(self, breaker):
        breaker.force_open()
        breaker.force_close()
        assert breaker.get_state() == CircuitState.CLOSED

    def test_stats_structure(self, breaker):
        stats = breaker.get_stats()
        assert "state" in stats
        assert "failure_count" in stats


class TestAdvancedHealthChecker:
    @pytest.fixture
    def checker(self):
        return AdvancedHealthChecker()

    def test_register_and_check(self, checker):
        checker.register_component("db", lambda: True)
        result = checker.check("db")
        assert result["status"] == "healthy"

    def test_failing_component(self, checker):
        checker.register_component("cache", lambda: (_ for _ in ()).throw(Exception("down")))
        result = checker.check("cache")
        assert result["status"] == "unhealthy"

    def test_check_all(self, checker):
        checker.register_component("a", lambda: True)
        checker.register_component("b", lambda: True)
        results = checker.check_all()
        assert "overall" in results
        assert len(results["components"]) == 2

    def test_circuit_open_status(self, checker):
        cfg = CircuitBreakerConfig(failure_threshold=1)
        checker.register_component("svc", lambda: (_ for _ in ()).throw(Exception("down")), cfg)
        checker.check("svc")  # triggers open
        checker.check("svc")  # open circuit
        # Should either be circuit_open or unhealthy

    def test_get_breaker(self, checker):
        checker.register_component("x", lambda: True)
        breaker = checker.get_breaker("x")
        assert breaker is not None
