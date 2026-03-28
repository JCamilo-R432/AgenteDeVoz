"""Tests para AutoScaler y KubernetesHPA (Gap #25)"""
import pytest
from src.infrastructure.auto_scaler import (
    AutoScaler, ScalingMetrics, ScaleDirection
)
from src.infrastructure.kubernetes_hpa import KubernetesHPA, HPAConfig


def make_metrics(cpu=50.0, mem=50.0, conns=10, latency_ms=200.0, queue=0) -> ScalingMetrics:
    return ScalingMetrics(
        cpu_percent=cpu,
        memory_percent=mem,
        active_connections=conns,
        avg_response_ms=latency_ms,
        queue_depth=queue,
    )


@pytest.fixture
def scaler():
    return AutoScaler(deployment_name="agentevoz", namespace="production", min_replicas=1, max_replicas=10)


@pytest.fixture
def hpa():
    return KubernetesHPA(dry_run=True)


class TestAutoScaler:
    def test_initial_replicas(self, scaler):
        assert scaler.get_current_replicas() == 1

    def test_normal_load_no_scale(self, scaler):
        decision = scaler.evaluate(make_metrics(cpu=50.0))
        assert decision.direction == ScaleDirection.NONE

    def test_high_cpu_scale_up(self, scaler):
        decision = scaler.evaluate(make_metrics(cpu=75.0))
        assert decision.direction == ScaleDirection.UP

    def test_high_memory_scale_up(self, scaler):
        decision = scaler.evaluate(make_metrics(mem=85.0))
        assert decision.direction == ScaleDirection.UP

    def test_high_latency_scale_up(self, scaler):
        decision = scaler.evaluate(make_metrics(latency_ms=3000.0))
        assert decision.direction == ScaleDirection.UP

    def test_target_within_max(self, scaler):
        scaler.set_replicas(9)
        decision = scaler.evaluate(make_metrics(cpu=90.0))
        assert decision.target_replicas <= scaler.max_replicas

    def test_scale_down_low_load(self, scaler):
        scaler.set_replicas(5)
        # Forzar cooldowns a 0 para permitir scale down
        scaler._last_scale_up = 0.0
        scaler._last_scale_down = 0.0
        decision = scaler.evaluate(make_metrics(cpu=20.0, mem=30.0, latency_ms=100.0))
        assert decision.direction in (ScaleDirection.DOWN, ScaleDirection.NONE)

    def test_target_not_below_min(self, scaler):
        scaler.set_replicas(1)
        scaler._last_scale_up = 0.0
        scaler._last_scale_down = 0.0
        decision = scaler.evaluate(make_metrics(cpu=10.0, mem=10.0, latency_ms=50.0))
        assert decision.target_replicas >= scaler.min_replicas

    def test_apply_decision_updates_replicas(self, scaler):
        decision = scaler.evaluate(make_metrics(cpu=80.0))
        scaler.apply_decision(decision)
        assert scaler.get_current_replicas() == decision.target_replicas

    def test_set_replicas_clamps_to_max(self, scaler):
        scaler.set_replicas(999)
        assert scaler.get_current_replicas() == scaler.max_replicas

    def test_set_replicas_clamps_to_min(self, scaler):
        scaler.set_replicas(0)
        assert scaler.get_current_replicas() == scaler.min_replicas

    def test_scaling_history_grows(self, scaler):
        for _ in range(3):
            scaler.evaluate(make_metrics(cpu=80.0))
        history = scaler.get_scaling_history()
        assert len(history) >= 1

    def test_stats_structure(self, scaler):
        stats = scaler.get_stats()
        assert "deployment" in stats
        assert "current_replicas" in stats
        assert "total_scale_ups" in stats


class TestKubernetesHPA:
    def test_generate_manifest_structure(self, hpa):
        config = HPAConfig(
            name="agentevoz-hpa",
            namespace="production",
            deployment="agentevoz",
            min_replicas=2,
            max_replicas=10,
            cpu_target_percent=70,
        )
        manifest = hpa.generate_manifest(config)
        assert manifest["kind"] == "HorizontalPodAutoscaler"
        assert manifest["apiVersion"] == "autoscaling/v2"

    def test_manifest_min_replicas(self, hpa):
        config = HPAConfig("hpa", "default", "app", 2, 8)
        manifest = hpa.generate_manifest(config)
        assert manifest["spec"]["minReplicas"] == 2

    def test_manifest_max_replicas(self, hpa):
        config = HPAConfig("hpa", "default", "app", 2, 8)
        manifest = hpa.generate_manifest(config)
        assert manifest["spec"]["maxReplicas"] == 8

    def test_manifest_has_cpu_metric(self, hpa):
        config = HPAConfig("hpa", "default", "app", 1, 5, cpu_target_percent=60)
        manifest = hpa.generate_manifest(config)
        metrics = manifest["spec"]["metrics"]
        cpu_metrics = [m for m in metrics if m["type"] == "Resource" and m["resource"]["name"] == "cpu"]
        assert len(cpu_metrics) == 1

    def test_manifest_memory_metric_optional(self, hpa):
        config = HPAConfig("hpa", "default", "app", 1, 5, memory_target_percent=80)
        manifest = hpa.generate_manifest(config)
        metrics = manifest["spec"]["metrics"]
        mem_metrics = [m for m in metrics if m["type"] == "Resource" and m["resource"]["name"] == "memory"]
        assert len(mem_metrics) == 1

    def test_apply_hpa_dry_run(self, hpa):
        config = HPAConfig("test-hpa", "default", "app", 1, 5)
        result = hpa.apply_hpa(config)
        assert result is True

    def test_get_hpa_status_no_kubectl(self, hpa):
        status = hpa.get_hpa_status("test-hpa", "default")
        assert status is not None

    def test_scale_deployment_no_kubectl(self, hpa):
        result = hpa.scale_deployment("app", 3)
        assert result is True
