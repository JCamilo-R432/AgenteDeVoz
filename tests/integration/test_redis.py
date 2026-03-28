"""
Tests de integración para RedisCache.
Corre en modo in-memory si Redis no está disponible.
"""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestRedisCacheIntegration:
    """Tests de integración para RedisCache (con fallback in-memory)."""

    @pytest.fixture
    def cache(self):
        """Cache apuntando a un puerto incorrecto para forzar fallback in-memory."""
        from integrations.redis_cache import RedisCache
        # Puerto 6380 (incorrecto) fuerza el fallback a memoria
        return RedisCache(host="localhost", port=6380)

    @pytest.fixture
    def cache_real(self):
        """Cache intentando conectar a Redis real."""
        from integrations.redis_cache import RedisCache
        return RedisCache(host="localhost", port=6379)

    # ── Operaciones básicas ────────────────────────────────────────────────────

    def test_set_and_get_string(self, cache):
        """set/get de string funciona."""
        key = f"test:str:{time.time()}"
        cache.set(key, "hello world", ttl=60)
        assert cache.get(key) == "hello world"

    def test_set_and_get_dict(self, cache):
        """set/get de diccionario funciona."""
        key = f"test:dict:{time.time()}"
        data = {"session": "abc", "state": "ESCUCHANDO", "turns": 3}
        cache.set(key, data, ttl=60)
        result = cache.get(key)
        assert result is not None
        assert result["session"] == "abc"
        assert result["state"] == "ESCUCHANDO"

    def test_set_and_get_integer(self, cache):
        """set/get de entero funciona."""
        key = f"test:int:{time.time()}"
        cache.set(key, 42, ttl=60)
        result = cache.get(key)
        assert result == 42

    def test_set_and_get_list(self, cache):
        """set/get de lista funciona."""
        key = f"test:list:{time.time()}"
        data = [1, 2, 3, "cuatro"]
        cache.set(key, data, ttl=60)
        result = cache.get(key)
        assert result == data

    def test_get_nonexistent_returns_none(self, cache):
        """get() de clave inexistente retorna None."""
        result = cache.get(f"nonexistent:{time.time()}")
        assert result is None

    def test_delete_removes_key(self, cache):
        """delete() elimina la clave."""
        key = f"test:del:{time.time()}"
        cache.set(key, "value", ttl=60)
        assert cache.get(key) == "value"
        cache.delete(key)
        assert cache.get(key) is None

    def test_exists_true(self, cache):
        """exists() retorna True para clave existente."""
        key = f"test:exists:{time.time()}"
        cache.set(key, "val", ttl=60)
        assert cache.exists(key) is True

    def test_exists_false(self, cache):
        """exists() retorna False para clave inexistente."""
        assert cache.exists(f"no_existe_{time.time()}") is False

    # ── TTL / Expiración ───────────────────────────────────────────────────────

    def test_memory_ttl_expiry(self, cache):
        """Clave con TTL vencido retorna None en modo memoria."""
        key = f"test:expire:{time.time()}"
        cache.set(key, "expiring", ttl=1)
        # Forzar expiración modificando el timestamp
        if key in cache._memory_ttl:
            cache._memory_ttl[key] = time.time() - 1
        result = cache._memory_get(key)
        assert result is None

    # ── Sesiones ───────────────────────────────────────────────────────────────

    def test_set_session_and_get(self, cache):
        """set_session/get_session funcionan correctamente."""
        sid = f"sess_{int(time.time())}"
        data = {"state": "AUTENTICANDO", "phone": "3001234567", "turns": 0}
        cache.set_session(sid, data)
        result = cache.get_session(sid)
        assert result is not None
        assert result["state"] == "AUTENTICANDO"

    def test_delete_session(self, cache):
        """delete_session elimina la sesión."""
        sid = f"sess_del_{int(time.time())}"
        cache.set_session(sid, {"state": "FIN"})
        cache.delete_session(sid)
        assert cache.get_session(sid) is None

    # ── Incrementar ────────────────────────────────────────────────────────────

    def test_increment_from_zero(self, cache):
        """increment() crea la clave con valor 1."""
        key = f"counter:{int(time.time())}"
        cache.delete(key)
        result = cache.increment(key, ttl=60)
        assert result == 1

    def test_increment_accumulates(self, cache):
        """Múltiples increment() acumulan el valor."""
        key = f"counter_acc:{int(time.time())}"
        cache.delete(key)
        cache.increment(key, ttl=60)
        cache.increment(key, ttl=60)
        result = cache.increment(key, ttl=60)
        assert result == 3

    # ── Rate limiting ──────────────────────────────────────────────────────────

    def test_rate_limit_allows_within_limit(self, cache):
        """rate_limit() permite solicitudes dentro del límite."""
        identifier = f"user_{int(time.time())}"
        result = cache.rate_limit(identifier, limit=100, window_seconds=60)
        assert result is True

    def test_rate_limit_blocks_when_exceeded(self, cache):
        """rate_limit() bloquea cuando se excede el límite."""
        identifier = f"spam_{int(time.time())}"
        limit = 3
        results = []
        for _ in range(limit + 2):
            results.append(cache.rate_limit(identifier, limit=limit, window_seconds=60))
        # Las primeras `limit` deben pasar, las demás deben fallar
        assert results[:limit] == [True] * limit
        assert False in results[limit:]

    # ── Estadísticas ──────────────────────────────────────────────────────────

    def test_get_stats_returns_dict(self, cache):
        """get_stats() retorna un diccionario."""
        stats = cache.get_stats()
        assert isinstance(stats, dict)
        assert "backend" in stats

    def test_get_stats_backend_is_memory(self, cache):
        """Con Redis no disponible, el backend es 'memory'."""
        stats = cache.get_stats()
        assert stats["backend"] == "memory"

    # ── Flush pattern ─────────────────────────────────────────────────────────

    def test_flush_pattern_deletes_matching_keys(self, cache):
        """flush_pattern() elimina claves que coinciden con el patrón."""
        ts = int(time.time())
        cache.set(f"patt:{ts}:a", "1", ttl=60)
        cache.set(f"patt:{ts}:b", "2", ttl=60)
        cache.set(f"other:{ts}:c", "3", ttl=60)
        count = cache.flush_pattern(f"patt:{ts}:*")
        assert count >= 2
        assert cache.get(f"other:{ts}:c") == "3"

    # ── Fallback en memoria ───────────────────────────────────────────────────

    def test_fallback_backend_label(self, cache):
        """El cache en modo fallback tiene backend='memory'."""
        assert cache._use_redis is False
        stats = cache.get_stats()
        assert stats["backend"] == "memory"

    def test_memory_operations_are_functional(self, cache):
        """Las operaciones básicas funcionan en modo memoria."""
        key = f"mem_func_{int(time.time())}"
        # set
        assert cache.set(key, {"x": 1}, ttl=60) is True
        # get
        assert cache.get(key) == {"x": 1}
        # exists
        assert cache.exists(key) is True
        # delete
        cache.delete(key)
        assert cache.get(key) is None
