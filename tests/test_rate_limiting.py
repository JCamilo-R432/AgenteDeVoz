"""Tests para Gap #14: Rate Limiting."""
import pytest
import time
from src.infrastructure.rate_limiter import (
    RateLimiter, RateLimitConfig, RateLimitAlgorithm, RateLimitResult,
    TokenBucket, SlidingWindowCounter,
)
from src.infrastructure.ip_rate_limiting import IPRateLimiter, IPRateConfig
from src.infrastructure.user_rate_limiting import (
    UserRateLimiter, ServicePlan,
)
from src.infrastructure.ddos_protection import DDoSProtection, DDoSConfig, MitigationAction


class TestTokenBucket:
    def test_initial_tokens(self):
        bucket = TokenBucket(rate=10.0, burst=10)
        allowed, remaining = bucket.consume(1)
        assert allowed is True
        assert remaining == 9

    def test_burst_consumption(self):
        bucket = TokenBucket(rate=1.0, burst=5)
        for _ in range(5):
            allowed, _ = bucket.consume(1)
            assert allowed is True
        allowed, _ = bucket.consume(1)
        assert allowed is False

    def test_refill_over_time(self):
        bucket = TokenBucket(rate=10.0, burst=10)
        # Consume all
        for _ in range(10):
            bucket.consume(1)
        time.sleep(0.15)  # 10 tokens/s * 0.15s = 1.5 tokens
        allowed, _ = bucket.consume(1)
        assert allowed is True

    def test_time_to_next_token(self):
        bucket = TokenBucket(rate=1.0, burst=1)
        bucket.consume(1)
        wait = bucket.time_to_next_token()
        assert wait > 0


class TestSlidingWindowCounter:
    def test_allows_within_limit(self):
        counter = SlidingWindowCounter(limit=5, window_s=60)
        for _ in range(5):
            allowed, _ = counter.is_allowed()
            assert allowed is True

    def test_blocks_over_limit(self):
        counter = SlidingWindowCounter(limit=3, window_s=60)
        for _ in range(3):
            counter.is_allowed()
        allowed, remaining = counter.is_allowed()
        assert allowed is False
        assert remaining == 0

    def test_resets_after_window(self):
        counter = SlidingWindowCounter(limit=2, window_s=1)
        counter.is_allowed()
        counter.is_allowed()
        time.sleep(1.1)
        allowed, _ = counter.is_allowed()
        assert allowed is True


class TestRateLimiter:
    @pytest.fixture
    def limiter(self):
        config = RateLimitConfig(requests_per_second=5.0, burst_size=5)
        return RateLimiter(default_config=config)

    def test_allows_within_rate(self, limiter):
        for _ in range(5):
            decision = limiter.check("user:test1")
            assert decision.result == RateLimitResult.ALLOWED

    def test_denies_over_rate(self, limiter):
        for _ in range(5):
            limiter.check("user:test2")
        decision = limiter.check("user:test2")
        assert decision.result == RateLimitResult.DENIED

    def test_different_keys_independent(self, limiter):
        for _ in range(5):
            limiter.check("user:a")
        decision = limiter.check("user:b")
        assert decision.result == RateLimitResult.ALLOWED

    def test_custom_limit_for_key_prefix(self, limiter):
        custom = RateLimitConfig(requests_per_second=100.0, burst_size=100)
        limiter.set_custom_limit("vip:", custom)
        for _ in range(50):
            decision = limiter.check("vip:user1")
        assert decision.result == RateLimitResult.ALLOWED

    def test_sliding_window_algorithm(self):
        config = RateLimitConfig(
            requests_per_second=2.0,
            burst_size=2,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            window_seconds=10,
        )
        limiter = RateLimiter(default_config=config)
        decision = limiter.check("test:sw")
        assert decision.result == RateLimitResult.ALLOWED

    def test_reset_clears_state(self, limiter):
        for _ in range(5):
            limiter.check("user:reset_test")
        limiter.reset("user:reset_test")
        decision = limiter.check("user:reset_test")
        assert decision.result == RateLimitResult.ALLOWED

    def test_stats_structure(self, limiter):
        stats = limiter.get_stats()
        assert "total_denied" in stats
        assert "active_token_buckets" in stats

    def test_decision_has_remaining(self, limiter):
        decision = limiter.check("user:remaining")
        assert decision.remaining >= 0

    def test_denied_decision_has_retry_after(self, limiter):
        for _ in range(6):
            decision = limiter.check("user:retry")
        assert decision.retry_after_s >= 0


class TestIPRateLimiter:
    @pytest.fixture
    def ip_limiter(self):
        config = IPRateConfig(requests_per_minute=5, requests_per_hour=20, auto_block_threshold=10)
        return IPRateLimiter(config=config)

    def test_allows_within_limit(self, ip_limiter):
        for _ in range(5):
            result = ip_limiter.is_allowed("192.168.1.1")
            assert result["allowed"] is True

    def test_blocks_over_rpm(self, ip_limiter):
        for _ in range(5):
            ip_limiter.is_allowed("192.168.1.2")
        result = ip_limiter.is_allowed("192.168.1.2")
        assert result["allowed"] is False

    def test_whitelist_always_allowed(self, ip_limiter):
        ip_limiter.whitelist_ip("10.0.0.1")
        for _ in range(100):
            result = ip_limiter.is_allowed("10.0.0.1")
            assert result["allowed"] is True

    def test_permanent_blacklist_blocked(self, ip_limiter):
        ip_limiter.blacklist_ip("1.2.3.4", permanent=True)
        result = ip_limiter.is_allowed("1.2.3.4")
        assert result["allowed"] is False
        assert result.get("retry_after_s") == -1

    def test_manual_block_and_unblock(self, ip_limiter):
        ip_limiter.blacklist_ip("5.6.7.8")
        result = ip_limiter.is_allowed("5.6.7.8")
        assert result["allowed"] is False
        ip_limiter.unblock_ip("5.6.7.8")
        result = ip_limiter.is_allowed("5.6.7.8")
        assert result["allowed"] is True

    def test_stats_structure(self, ip_limiter):
        stats = ip_limiter.get_stats()
        assert "tracked_ips" in stats
        assert "currently_blocked" in stats

    def test_top_ips(self, ip_limiter):
        for _ in range(3):
            ip_limiter.is_allowed("1.1.1.1")
        top = ip_limiter.get_top_ips(n=5)
        assert isinstance(top, list)


class TestUserRateLimiter:
    @pytest.fixture
    def user_limiter(self):
        return UserRateLimiter()

    def test_register_user(self, user_limiter):
        user_limiter.register_user("user1", ServicePlan.PRO)
        usage = user_limiter.get_user_usage("user1")
        assert usage["plan"] == "pro"

    def test_allows_within_plan(self, user_limiter):
        user_limiter.register_user("user2", ServicePlan.PRO)
        result = user_limiter.check_and_record("user2")
        assert result["allowed"] is True

    def test_creates_free_user_if_not_registered(self, user_limiter):
        result = user_limiter.check_and_record("new_user_xyz")
        assert result["allowed"] is True
        assert result["plan"] == "free"

    def test_upgrade_plan(self, user_limiter):
        user_limiter.register_user("user3", ServicePlan.FREE)
        user_limiter.upgrade_plan("user3", ServicePlan.ENTERPRISE)
        usage = user_limiter.get_user_usage("user3")
        assert usage["plan"] == "enterprise"

    def test_concurrent_calls_limit(self, user_limiter):
        user_limiter.register_user("user4", ServicePlan.FREE)
        # FREE plan allows 2 concurrent calls
        assert user_limiter.start_call("user4") is True
        assert user_limiter.start_call("user4") is True
        assert user_limiter.start_call("user4") is False  # 3rd blocked

    def test_end_call_decrements(self, user_limiter):
        user_limiter.register_user("user5", ServicePlan.FREE)
        user_limiter.start_call("user5")
        user_limiter.start_call("user5")
        user_limiter.end_call("user5")
        assert user_limiter.start_call("user5") is True

    def test_internal_plan_no_limit(self, user_limiter):
        user_limiter.register_user("svc_internal", ServicePlan.INTERNAL)
        for _ in range(100):
            result = user_limiter.check_and_record("svc_internal")
        assert result["allowed"] is True

    def test_stats_structure(self, user_limiter):
        stats = user_limiter.get_stats()
        assert "total_users" in stats
        assert "by_plan" in stats


class TestDDoSProtection:
    @pytest.fixture
    def ddos(self):
        config = DDoSConfig(rps_threshold=10, per_ip_rps_threshold=5, auto_mitigation=True)
        return DDoSProtection(config=config)

    def test_allows_normal_traffic(self, ddos):
        action = ddos.record_request("192.168.1.1")
        assert action == MitigationAction.NONE

    def test_blocks_high_rpm_ip(self, ddos):
        for _ in range(5):
            ddos.record_request("10.0.0.1")
        action = ddos.record_request("10.0.0.1")
        assert action == MitigationAction.BLOCK

    def test_attack_event_created(self, ddos):
        for _ in range(6):
            ddos.record_request("attacker_ip")
        events = ddos.get_attack_events()
        assert len(events) >= 1

    def test_unblock_ip(self, ddos):
        for _ in range(6):
            ddos.record_request("ip_to_unblock")
        ddos.unblock_ip("ip_to_unblock")
        action = ddos.record_request("ip_to_unblock")
        assert action != MitigationAction.BLOCK

    def test_status_structure(self, ddos):
        status = ddos.get_status()
        assert "under_attack" in status
        assert "global_rps" in status
        assert "blocked_ips" in status

    def test_resolve_attack(self, ddos):
        for _ in range(6):
            ddos.record_request("bad_ip")
        events = ddos.get_attack_events()
        if events:
            result = ddos.resolve_attack(events[0]["attack_id"])
            assert result is True

    def test_challenge_ip(self, ddos):
        ddos.challenge_ip("suspicious_ip")
        # IP challenged should be tracked
        assert "suspicious_ip" in ddos._challenged_ips
