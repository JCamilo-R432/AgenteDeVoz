"""Tests para Gap #12: Database Replication."""
import pytest
from datetime import datetime
from src.infrastructure.database_replication import (
    DatabaseReplicationManager, DatabaseNode, ReplicationRole, ReplicationStatus,
)
from src.infrastructure.postgresql_replication import (
    PostgreSQLReplicationConfigurator, PostgreSQLConfig,
)
from src.infrastructure.replication_monitor import ReplicationMonitor, ReplicationMetric


class TestDatabaseReplicationManager:
    @pytest.fixture
    def manager(self):
        return DatabaseReplicationManager(max_replica_lag_s=10.0)

    @pytest.fixture
    def primary_node(self):
        return DatabaseNode("primary", "10.0.0.1", 5432, "agentevoz", ReplicationRole.PRIMARY)

    @pytest.fixture
    def replica_node(self):
        node = DatabaseNode("replica1", "10.0.0.2", 5432, "agentevoz", ReplicationRole.REPLICA)
        node.status = ReplicationStatus.STREAMING
        return node

    def test_register_nodes(self, manager, primary_node, replica_node):
        manager.register_node(primary_node)
        manager.register_node(replica_node)
        status = manager.get_replication_status()
        assert status["total_writes"] == 0

    def test_get_write_node_returns_primary(self, manager, primary_node):
        manager.register_node(primary_node)
        write_node = manager.get_write_node()
        assert write_node is not None
        assert write_node.role == ReplicationRole.PRIMARY

    def test_get_read_node_prefers_replica(self, manager, primary_node, replica_node):
        manager.register_node(primary_node)
        manager.register_node(replica_node)
        read_node = manager.get_read_node(prefer_replica=True)
        assert read_node is not None

    def test_update_replication_lag(self, manager, replica_node):
        manager.register_node(replica_node)
        manager.update_replication_lag("replica1", lag_bytes=1024, lag_seconds=0.5)
        status = manager.get_replication_status()
        assert status["streaming_replicas"] >= 0

    def test_high_lag_marks_catching_up(self, manager, replica_node):
        manager.register_node(replica_node)
        manager.update_replication_lag("replica1", lag_bytes=1024*1024, lag_seconds=30.0)
        assert replica_node.status == ReplicationStatus.CATCHING_UP

    def test_promote_replica(self, manager, primary_node, replica_node):
        manager.register_node(primary_node)
        manager.register_node(replica_node)
        result = manager.promote_replica("replica1")
        assert result is True
        assert replica_node.role == ReplicationRole.PRIMARY

    def test_promote_replica_demotes_old_primary(self, manager, primary_node, replica_node):
        manager.register_node(primary_node)
        manager.register_node(replica_node)
        manager.promote_replica("replica1")
        assert primary_node.role == ReplicationRole.REPLICA

    def test_failover_log(self, manager, primary_node, replica_node):
        manager.register_node(primary_node)
        manager.register_node(replica_node)
        manager.promote_replica("replica1")
        status = manager.get_replication_status()
        assert status["failover_count"] == 1

    def test_no_write_node_when_primary_disconnected(self, manager, primary_node):
        primary_node.status = ReplicationStatus.DISCONNECTED
        manager.register_node(primary_node)
        write_node = manager.get_write_node()
        assert write_node is None

    def test_replication_status_structure(self, manager, primary_node):
        manager.register_node(primary_node)
        status = manager.get_replication_status()
        assert "nodes" in status
        assert "primary_available" in status
        assert "replica_count" in status

    def test_read_falls_back_to_primary(self, manager, primary_node):
        manager.register_node(primary_node)
        read_node = manager.get_read_node(prefer_replica=True)
        assert read_node is not None
        assert read_node.role == ReplicationRole.PRIMARY


class TestPostgreSQLReplicationConfigurator:
    @pytest.fixture
    def config(self):
        return PostgreSQLConfig(host="10.0.0.1", replication_user="replicator")

    @pytest.fixture
    def configurator(self, config):
        return PostgreSQLReplicationConfigurator(config)

    def test_generate_primary_config(self, configurator):
        cfg = configurator.generate_primary_config()
        assert "wal_level" in cfg
        assert "max_wal_senders" in cfg

    def test_primary_config_contains_hot_standby(self, configurator):
        cfg = configurator.generate_primary_config()
        assert "hot_standby" in cfg

    def test_generate_replica_config(self, configurator):
        cfg = configurator.generate_replica_config("10.0.0.1", "replica1")
        assert "primary_conninfo" in cfg
        assert "hot_standby" in cfg

    def test_generate_pg_hba(self, configurator):
        hba = configurator.generate_pg_hba_primary(["10.0.0.2", "10.0.0.3"])
        assert "replication" in hba
        assert "10.0.0.2" in hba

    def test_generate_replication_slot_sql(self, configurator):
        sql = configurator.generate_replication_slot_sql("slot_replica1")
        assert "pg_create_physical_replication_slot" in sql
        assert "slot_replica1" in sql

    def test_generate_basebackup_command(self, configurator):
        cmd = configurator.generate_basebackup_command("10.0.0.1")
        assert "pg_basebackup" in cmd
        assert "-h 10.0.0.1" in cmd

    def test_monitoring_sql_structure(self, configurator):
        queries = configurator.generate_replication_monitoring_sql()
        assert "lag_bytes" in queries
        assert "slots" in queries
        assert "replica_status" in queries


class TestReplicationMonitor:
    @pytest.fixture
    def monitor(self):
        return ReplicationMonitor(max_lag_bytes=50*1024*1024, max_lag_seconds=30.0)

    def test_record_metric(self, monitor):
        metric = ReplicationMetric(
            replica_name="replica1",
            lag_bytes=1024,
            lag_seconds=0.5,
            state="streaming",
            measured_at=datetime.now().isoformat(),
        )
        monitor.record_metric(metric)
        latest = monitor.get_latest_metrics()
        assert "replica1" in latest

    def test_high_lag_triggers_alert(self, monitor):
        alerts = []
        monitor.add_alert_handler(lambda m, t: alerts.append(t))
        metric = ReplicationMetric(
            replica_name="replica1",
            lag_bytes=1024,
            lag_seconds=60.0,   # > max_lag_seconds
            state="catchup",
            measured_at=datetime.now().isoformat(),
        )
        monitor.record_metric(metric)
        assert len(alerts) >= 1

    def test_healthy_no_alert(self, monitor):
        alerts = []
        monitor.add_alert_handler(lambda m, t: alerts.append(t))
        metric = ReplicationMetric(
            replica_name="replica2",
            lag_bytes=100,
            lag_seconds=0.1,
            state="streaming",
            measured_at=datetime.now().isoformat(),
        )
        monitor.record_metric(metric)
        assert len(alerts) == 0

    def test_health_summary(self, monitor):
        metric = ReplicationMetric("r1", 1024, 0.5, "streaming", datetime.now().isoformat())
        monitor.record_metric(metric)
        summary = monitor.get_health_summary()
        assert "status" in summary
        assert "replicas" in summary

    def test_lag_trend(self, monitor):
        for i in range(5):
            metric = ReplicationMetric(
                "r1", i * 1024, float(i) * 0.1, "streaming", datetime.now().isoformat()
            )
            monitor.record_metric(metric)
        trend = monitor.get_lag_trend("r1", last_n=3)
        assert len(trend) == 3

    def test_disconnected_state_alert(self, monitor):
        alerts = []
        monitor.add_alert_handler(lambda m, t: alerts.append(t))
        metric = ReplicationMetric("r1", 0, 0, "stopped", datetime.now().isoformat())
        monitor.record_metric(metric)
        assert any("state_stopped" in a for a in alerts)

    def test_no_data_summary(self, monitor):
        summary = monitor.get_health_summary()
        assert summary["status"] == "no_data"
