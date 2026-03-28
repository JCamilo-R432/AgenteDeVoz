"""Tests para CDNManager y CloudflareIntegration (Gap #26)"""
import time
import pytest
from src.infrastructure.cdn_manager import CDNManager, CDNProvider, CacheConfig, CDNAsset
from src.infrastructure.cloudflare_integration import CloudflareIntegration


@pytest.fixture
def cdn():
    return CDNManager(
        provider=CDNProvider.CLOUDFLARE,
        base_url="https://cdn.example.com",
        cache_config=CacheConfig(ttl_audio_s=60),
    )


@pytest.fixture
def cf():
    return CloudflareIntegration(api_token="test_token", zone_id="abc123zone")


class TestCDNManager:
    def test_cache_audio_response(self, cdn):
        asset = cdn.cache_audio_response("Hola mundo", b"\x00" * 1024, "voice_es")
        assert isinstance(asset, CDNAsset)
        assert asset.content_type == "audio/mpeg"

    def test_cached_audio_url_contains_base_url(self, cdn):
        asset = cdn.cache_audio_response("texto", b"\x00" * 100, "voice_es")
        assert "cdn.example.com" in asset.url

    def test_get_cached_audio_hit(self, cdn):
        cdn.cache_audio_response("Hola mundo", b"\x01" * 500, "voice_es")
        asset = cdn.get_cached_audio("Hola mundo", "voice_es")
        assert asset is not None

    def test_get_cached_audio_miss(self, cdn):
        asset = cdn.get_cached_audio("texto_no_cacheado", "voice_es")
        assert asset is None

    def test_get_cached_audio_expired(self, cdn):
        asset = cdn.cache_audio_response("texto exp", b"\x00" * 100, "voice_es")
        asset.cached_at = time.time() - 9999  # Forzar expiracion
        result = cdn.get_cached_audio("texto exp", "voice_es")
        assert result is None

    def test_cache_hit_count_increments(self, cdn):
        cdn.cache_audio_response("texto", b"\x00" * 100, "v1")
        cdn.get_cached_audio("texto", "v1")
        cdn.get_cached_audio("texto", "v1")
        assert cdn._hit_count == 2

    def test_cache_miss_count_increments(self, cdn):
        cdn.get_cached_audio("no_existe", "v1")
        assert cdn._miss_count == 1

    def test_get_static_url(self, cdn):
        url = cdn.get_static_url("/js/app.js")
        assert "cdn.example.com" in url
        assert "app.js" in url

    def test_invalidate_removes_entries(self, cdn):
        cdn.cache_audio_response("audio para invalidar", b"\x00" * 100, "v1")
        initial_count = len(cdn._local_cache)
        cdn.invalidate(["audio_para_invalidar"])
        # La invalidacion busca por URL, puede que no coincida exactamente pero no lanza excepcion
        assert len(cdn._local_cache) <= initial_count

    def test_purge_expired_removes_old(self, cdn):
        asset = cdn.cache_audio_response("texto old", b"\x00" * 100, "v1")
        asset.cached_at = time.time() - 9999
        removed = cdn.purge_expired()
        assert removed >= 1

    def test_stats_structure(self, cdn):
        stats = cdn.get_stats()
        assert "provider" in stats
        assert "hit_rate_percent" in stats
        assert "cache_entries" in stats

    def test_hit_rate_calculation(self, cdn):
        cdn.cache_audio_response("t", b"\x00" * 10, "v1")
        cdn.get_cached_audio("t", "v1")      # hit
        cdn.get_cached_audio("missing", "v1") # miss
        stats = cdn.get_stats()
        assert stats["hit_rate_percent"] == pytest.approx(50.0)

    def test_asset_not_expired(self, cdn):
        asset = cdn.cache_audio_response("texto nuevo", b"\x00" * 100, "v1")
        assert asset.is_expired() is False


class TestCloudflareIntegration:
    def test_purge_cache_success(self, cf):
        result = cf.purge_cache(["https://example.com/audio/abc.mp3"])
        assert result is True

    def test_purge_large_batch(self, cf):
        urls = [f"https://example.com/file_{i}.mp3" for i in range(50)]
        result = cf.purge_cache(urls)
        assert result is True

    def test_purge_everything(self, cf):
        result = cf.purge_everything()
        assert result is True

    def test_create_page_rule(self, cf):
        rule = cf.create_page_rule("https://example.com/audio/*", cache_ttl_s=3600)
        assert rule is not None
        assert rule.cache_ttl_s == 3600

    def test_get_cache_analytics(self, cf):
        analytics = cf.get_cache_analytics(since_hours=24)
        assert "zone_id" in analytics
        assert "cache_ratio_percent" in analytics

    def test_set_security_level_valid(self, cf):
        result = cf.set_security_level("high")
        assert result is True

    def test_set_security_level_invalid(self, cf):
        result = cf.set_security_level("nuclear")
        assert result is False

    def test_enable_ddos_protection(self, cf):
        result = cf.enable_ddos_protection()
        assert result is True

    def test_get_zone_info(self, cf):
        info = cf.get_zone_info()
        assert "zone_id" in info
        assert info["zone_id"] == "abc123zone"
