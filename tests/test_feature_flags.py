"""
Tests para Feature Flags Manager (Gap #40)
"""
import pytest
from src.compliance.feature_flags import FeatureFlagManager, FeatureFlag, FlagStatus


class TestFeatureFlagManager:
    def setup_method(self):
        self.manager = FeatureFlagManager()

    def test_default_flags_loaded(self):
        flags = self.manager.list_flags()
        names = [f["name"] for f in flags]
        assert "use_llm_intent_classifier" in names
        assert "google_stt_primary" in names

    def test_create_flag(self):
        flag = self.manager.create_flag(
            name="test_feature_new",
            description="Feature de prueba",
            enabled=False,
        )
        assert isinstance(flag, FeatureFlag)
        assert flag.name == "test_feature_new"
        assert flag.enabled is False

    def test_create_duplicate_flag_raises(self):
        self.manager.create_flag("unique_flag_test", "Desc")
        with pytest.raises(ValueError, match="ya existe"):
            self.manager.create_flag("unique_flag_test", "Otra desc")

    def test_create_flag_invalid_rollout_raises(self):
        with pytest.raises(ValueError):
            self.manager.create_flag("bad_rollout", rollout_percentage=150.0)

    def test_is_enabled_true(self):
        self.manager.create_flag("flag_enabled", enabled=True, rollout_percentage=100.0)
        assert self.manager.is_enabled("flag_enabled") is True

    def test_is_enabled_false_when_disabled(self):
        self.manager.create_flag("flag_disabled", enabled=False)
        assert self.manager.is_enabled("flag_disabled") is False

    def test_is_enabled_nonexistent_returns_false(self):
        assert self.manager.is_enabled("nonexistent_flag_xyz") is False

    def test_rollout_deterministic(self):
        """El mismo usuario siempre recibe la misma decision."""
        self.manager.create_flag("rollout_test", enabled=True, rollout_percentage=50.0)
        result1 = self.manager.is_enabled("rollout_test", user_id="user_abc")
        result2 = self.manager.is_enabled("rollout_test", user_id="user_abc")
        assert result1 == result2

    def test_rollout_zero_percent_always_false(self):
        """0% de rollout -> nunca activo para ningun usuario."""
        self.manager.create_flag("rollout_zero", enabled=True, rollout_percentage=0.0)
        for i in range(20):
            assert self.manager.is_enabled("rollout_zero", user_id=f"user_{i}") is False

    def test_rollout_100_percent_always_true(self):
        """100% de rollout -> siempre activo."""
        self.manager.create_flag("rollout_full", enabled=True, rollout_percentage=100.0)
        for i in range(20):
            assert self.manager.is_enabled("rollout_full", user_id=f"user_{i}") is True

    def test_rollout_50_percent_distributes(self):
        """50% de rollout debe activar aproximadamente la mitad de usuarios."""
        self.manager.create_flag("rollout_half", enabled=True, rollout_percentage=50.0)
        results = [
            self.manager.is_enabled("rollout_half", user_id=f"user_{i}")
            for i in range(100)
        ]
        active_count = sum(results)
        # Con 100 usuarios, deberia estar entre 30-70 (margen amplio para test)
        assert 20 <= active_count <= 80

    def test_allowed_user_always_active(self):
        """Usuario en whitelist -> siempre activo, sin importar rollout."""
        self.manager.create_flag("flag_whitelist", enabled=True, rollout_percentage=0.0)
        self.manager.add_allowed_user("flag_whitelist", "vip_user")
        assert self.manager.is_enabled("flag_whitelist", user_id="vip_user") is True

    def test_blocked_user_always_inactive(self):
        """Usuario en blacklist -> siempre inactivo."""
        self.manager.create_flag("flag_blacklist", enabled=True, rollout_percentage=100.0)
        self.manager.block_user("flag_blacklist", "blocked_user")
        assert self.manager.is_enabled("flag_blacklist", user_id="blocked_user") is False

    def test_update_flag_enabled(self):
        self.manager.create_flag("flag_to_update", enabled=False)
        self.manager.update_flag("flag_to_update", enabled=True)
        assert self.manager.is_enabled("flag_to_update") is True

    def test_update_flag_invalid_rollout_raises(self):
        self.manager.create_flag("flag_update_bad", enabled=True)
        with pytest.raises(ValueError):
            self.manager.update_flag("flag_update_bad", rollout_percentage=-5.0)

    def test_set_rollout(self):
        self.manager.create_flag("flag_rollout_change", enabled=True, rollout_percentage=0.0)
        self.manager.set_rollout("flag_rollout_change", 75.0, updated_by="devops")
        flag = self.manager.get_flag("flag_rollout_change")
        assert flag.rollout_percentage == 75.0

    def test_flag_status_disabled(self):
        self.manager.create_flag("flag_status_dis", enabled=False)
        flag = self.manager.get_flag("flag_status_dis")
        assert flag.status() == FlagStatus.DISABLED.value

    def test_flag_status_rollout(self):
        self.manager.create_flag("flag_status_roll", enabled=True, rollout_percentage=50.0)
        flag = self.manager.get_flag("flag_status_roll")
        assert flag.status() == FlagStatus.ROLLOUT.value

    def test_flag_status_enabled(self):
        self.manager.create_flag("flag_status_en", enabled=True, rollout_percentage=100.0)
        flag = self.manager.get_flag("flag_status_en")
        assert flag.status() == FlagStatus.ENABLED.value

    def test_audit_log_on_create(self):
        self.manager.create_flag("flag_audit", enabled=True)
        log = self.manager.get_audit_log("flag_audit")
        assert len(log) >= 1
        assert log[0]["action"] == "created"

    def test_audit_log_on_update(self):
        self.manager.create_flag("flag_audit2", enabled=False)
        self.manager.update_flag("flag_audit2", updated_by="admin", enabled=True)
        log = self.manager.get_audit_log("flag_audit2")
        actions = [e["action"] for e in log]
        assert "created" in actions
        assert "updated" in actions

    def test_audit_log_filter_by_flag(self):
        self.manager.create_flag("flag_audit_filter", enabled=True)
        log = self.manager.get_audit_log("flag_audit_filter")
        for entry in log:
            assert entry["flag"] == "flag_audit_filter"

    def test_list_flags_by_tag(self):
        self.manager.create_flag("flag_tagged", tags=["experimental"])
        experimental_flags = self.manager.list_flags(tag="experimental")
        names = [f["name"] for f in experimental_flags]
        assert "flag_tagged" in names

    def test_get_nonexistent_flag(self):
        result = self.manager.get_flag("nonexistent_xyz")
        assert result is None

    def test_flag_to_dict(self):
        self.manager.create_flag("flag_dict", description="Para dict", enabled=True)
        flag = self.manager.get_flag("flag_dict")
        d = flag.to_dict()
        assert "name" in d
        assert "enabled" in d
        assert "rollout_percentage" in d
        assert "status" in d
        assert "allowed_users_count" in d
