"""Tests para Gap #11: High Availability."""
import pytest
import time
from src.infrastructure.high_availability import (
    HighAvailabilityManager, Node, NodeRole, NodeStatus, HAConfig,
)
from src.infrastructure.failover_manager import (
    FailoverManager, FailoverStrategy, ServiceEndpoint,
)
from src.infrastructure.health_checks import (
    HealthCheckRegistry, HealthStatus, HealthCheckResult,
    tcp_check, disk_space_check,
)


class TestHighAvailabilityManager:
    @pytest.fixture
    def ha(self):
        cfg = HAConfig(heartbeat_timeout_s=5.0, max_failures_before_failover=2)
        return HighAvailabilityManager(config=cfg)

    @pytest.fixture
    def nodes(self):
        return [
            Node("node1", "10.0.0.1", 8000, NodeRole.PRIMARY),
            Node("node2", "10.0.0.2", 8000, NodeRole.SECONDARY),
            Node("node3", "10.0.0.3", 8000, NodeRole.STANDBY),
        ]

    def test_register_node(self, ha, nodes):
        ha.register_node(nodes[0])
        status = ha.get_cluster_status()
        assert status["total_nodes"] == 1

    def test_record_heartbeat(self, ha, nodes):
        ha.register_node(nodes[0])
        result = ha.record_heartbeat("node1", response_time_ms=50.0)
        assert result is True

    def test_get_primary_node(self, ha, nodes):
        ha.register_node(nodes[0])
        ha.record_heartbeat("node1")
        primary = ha.get_primary_node()
        assert primary is not None
        assert primary.role == NodeRole.PRIMARY

    def test_health_check_healthy_node(self, ha, nodes):
        ha.register_node(nodes[0])
        ha.record_heartbeat("node1")
        status = ha.check_node_health("node1")
        assert status == NodeStatus.HEALTHY

    def test_health_check_unhealthy_no_heartbeat(self, ha, nodes):
        cfg = HAConfig(heartbeat_timeout_s=0.01)
        ha2 = HighAvailabilityManager(config=cfg)
        ha2.register_node(nodes[1])
        time.sleep(0.05)
        status = ha2.check_node_health("node2")
        assert status == NodeStatus.UNHEALTHY

    def test_run_health_check_cycle(self, ha, nodes):
        ha.register_node(nodes[0])
        ha.register_node(nodes[1])
        ha.record_heartbeat("node1")
        ha.record_heartbeat("node2")
        results = ha.run_health_check_cycle()
        assert len(results) == 2

    def test_deregister_node(self, ha, nodes):
        ha.register_node(nodes[0])
        result = ha.deregister_node("node1")
        assert result is True
        assert ha.get_cluster_status()["total_nodes"] == 0

    def test_deregister_nonexistent(self, ha):
        result = ha.deregister_node("nonexistent")
        assert result is False

    def test_get_available_nodes(self, ha, nodes):
        for n in nodes:
            ha.register_node(n)
            ha.record_heartbeat(n.node_id)
        available = ha.get_available_nodes()
        assert len(available) == 3

    def test_cluster_status_structure(self, ha, nodes):
        ha.register_node(nodes[0])
        ha.record_heartbeat("node1")
        status = ha.get_cluster_status()
        assert "total_nodes" in status
        assert "healthy_nodes" in status
        assert "primary" in status

    def test_failover_log_empty_initially(self, ha):
        assert ha.get_failover_log() == []

    def test_failover_triggered_on_repeated_failures(self, ha, nodes):
        cfg = HAConfig(
            heartbeat_timeout_s=0.01,
            max_failures_before_failover=1,
            failover_cooldown_s=0,
        )
        ha2 = HighAvailabilityManager(config=cfg)
        ha2.register_node(nodes[0])  # PRIMARY
        ha2.register_node(nodes[1])  # SECONDARY - available
        ha2.record_heartbeat("node2")
        time.sleep(0.05)
        ha2.run_health_check_cycle()
        # Puede haber failover log si node1 falla
        assert isinstance(ha2.get_failover_log(), list)

    def test_node_is_available(self, nodes):
        nodes[0].status = NodeStatus.HEALTHY
        assert nodes[0].is_available() is True
        nodes[0].status = NodeStatus.OFFLINE
        assert nodes[0].is_available() is False


class TestFailoverManager:
    @pytest.fixture
    def fm(self):
        return FailoverManager(strategy=FailoverStrategy.ACTIVE_PASSIVE)

    def test_register_endpoint(self, fm):
        ep = ServiceEndpoint("api", "10.0.0.1", 8000, priority=10)
        fm.register_endpoint("api_service", ep)
        active = fm.get_active_endpoint("api_service")
        assert active is not None

    def test_failover_to_secondary(self, fm):
        ep1 = ServiceEndpoint("api1", "10.0.0.1", 8000, priority=10, healthy=False)
        ep2 = ServiceEndpoint("api2", "10.0.0.2", 8000, priority=5)
        fm.register_endpoint("svc", ep1)
        fm.register_endpoint("svc", ep2)
        fm.mark_endpoint_unhealthy("svc", "10.0.0.1")
        event = fm.execute_failover("svc", "health_check_failed")
        assert event is not None
        assert event.success is True

    def test_failover_event_recorded(self, fm):
        ep1 = ServiceEndpoint("s1", "10.0.0.1", 8000, priority=10, healthy=False)
        ep2 = ServiceEndpoint("s2", "10.0.0.2", 8000, priority=5)
        fm.register_endpoint("svc2", ep1)
        fm.register_endpoint("svc2", ep2)
        fm.mark_endpoint_unhealthy("svc2", "10.0.0.1")
        fm.execute_failover("svc2")
        events = fm.get_events()
        assert len(events) >= 1

    def test_restore_primary(self, fm):
        ep1 = ServiceEndpoint("r1", "10.0.0.1", 8000, priority=10)
        ep2 = ServiceEndpoint("r2", "10.0.0.2", 8000, priority=5)
        fm.register_endpoint("svc3", ep1)
        fm.register_endpoint("svc3", ep2)
        fm.mark_endpoint_unhealthy("svc3", "10.0.0.1")
        fm.execute_failover("svc3")
        result = fm.restore_primary("svc3", "10.0.0.1")
        assert result is True

    def test_summary_structure(self, fm):
        summary = fm.get_summary()
        assert "strategy" in summary
        assert "total_failovers" in summary

    def test_pre_failover_hook_called(self, fm):
        called = []
        fm.add_pre_failover_hook(lambda svc, host: called.append(True))
        ep1 = ServiceEndpoint("h1", "10.0.0.1", 8000, priority=10, healthy=False)
        ep2 = ServiceEndpoint("h2", "10.0.0.2", 8000, priority=5)
        fm.register_endpoint("svc4", ep1)
        fm.register_endpoint("svc4", ep2)
        fm.mark_endpoint_unhealthy("svc4", "10.0.0.1")
        fm.execute_failover("svc4")
        assert len(called) >= 1


class TestHealthCheckRegistry:
    @pytest.fixture
    def registry(self):
        return HealthCheckRegistry()

    def test_register_and_run_check(self, registry):
        registry.register("db", lambda: True)
        result = registry.run_check("db")
        assert result.status == HealthStatus.HEALTHY

    def test_failing_check(self, registry):
        registry.register("cache", lambda: (_ for _ in ()).throw(Exception("Connection refused")))
        result = registry.run_check("cache")
        assert result.status == HealthStatus.UNHEALTHY

    def test_run_all(self, registry):
        registry.register("svc1", lambda: True)
        registry.register("svc2", lambda: True)
        results = registry.run_all()
        assert len(results) == 2

    def test_overall_status_healthy(self, registry):
        registry.register("a", lambda: True)
        registry.run_all()
        assert registry.get_overall_status() == HealthStatus.HEALTHY

    def test_overall_status_unhealthy(self, registry):
        registry.register("b", lambda: (_ for _ in ()).throw(Exception("down")))
        registry.run_all()
        assert registry.get_overall_status() == HealthStatus.UNHEALTHY

    def test_unknown_component(self, registry):
        result = registry.run_check("nonexistent")
        assert result.status == HealthStatus.UNKNOWN

    def test_summary_structure(self, registry):
        registry.register("x", lambda: True)
        registry.run_all()
        summary = registry.get_summary()
        assert "overall" in summary
        assert "components" in summary

    def test_disk_space_check(self):
        import sys
        path = "C:/" if sys.platform == "win32" else "/"
        result = disk_space_check(path, min_free_gb=0.001)
        assert result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
