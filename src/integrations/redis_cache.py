"""
Cache con Redis y fallback a diccionario en memoria.
Soporta TTL, serialización JSON, y patrones de invalidación.
"""

import json
import time
import hashlib
from typing import Any, Optional
from utils.logger import setup_logger

logger = setup_logger("redis_cache")


class RedisCache:
    """
    Cliente de cache con Redis.
    Fallback automático a in-memory dict si Redis no está disponible.
    """

    DEFAULT_TTL = 300          # 5 minutos
    AUDIO_TTL   = 3600         # 1 hora (TTS cache)
    SESSION_TTL = 1800         # 30 minutos (sesiones activas)

    def __init__(self, host: str = "localhost", port: int = 6379,
                 db: int = 0, password: Optional[str] = None):
        self._memory: dict = {}        # fallback in-memory
        self._memory_ttl: dict = {}    # expiry timestamps
        self._redis = None
        self._use_redis = False

        try:
            import redis
            client = redis.Redis(
                host=host, port=port, db=db,
                password=password,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            client.ping()
            self._redis = client
            self._use_redis = True
            logger.info(f"Redis conectado en {host}:{port} db={db}")
        except Exception as e:
            logger.warning(f"Redis no disponible ({e}). Usando cache en memoria.")

    # ── Operaciones básicas ────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del cache. Retorna None si no existe o expiró."""
        if self._use_redis:
            try:
                raw = self._redis.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            except Exception as e:
                logger.error(f"Redis GET error: {e}")
                return self._memory_get(key)
        return self._memory_get(key)

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        """Guarda un valor en el cache con TTL en segundos."""
        if self._use_redis:
            try:
                serialized = json.dumps(value, ensure_ascii=False, default=str)
                self._redis.setex(key, ttl, serialized)
                return True
            except Exception as e:
                logger.error(f"Redis SET error: {e}")
                return self._memory_set(key, value, ttl)
        return self._memory_set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Elimina una clave del cache."""
        if self._use_redis:
            try:
                self._redis.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis DELETE error: {e}")
        self._memory.pop(key, None)
        self._memory_ttl.pop(key, None)
        return True

    def exists(self, key: str) -> bool:
        """Comprueba si una clave existe y no ha expirado."""
        if self._use_redis:
            try:
                return bool(self._redis.exists(key))
            except Exception:
                pass
        return self._memory_get(key) is not None

    def flush_pattern(self, pattern: str) -> int:
        """Elimina todas las claves que coinciden con el patrón (Redis only)."""
        count = 0
        if self._use_redis:
            try:
                keys = self._redis.keys(pattern)
                if keys:
                    count = self._redis.delete(*keys)
                return count
            except Exception as e:
                logger.error(f"Redis FLUSH PATTERN error: {e}")
        # fallback: recorrer memoria
        to_delete = [k for k in self._memory if self._match_pattern(pattern, k)]
        for k in to_delete:
            self._memory.pop(k, None)
            self._memory_ttl.pop(k, None)
            count += 1
        return count

    def increment(self, key: str, amount: int = 1, ttl: int = DEFAULT_TTL) -> int:
        """Incrementa un contador atómicamente. Crea la clave si no existe."""
        if self._use_redis:
            try:
                pipe = self._redis.pipeline()
                pipe.incrby(key, amount)
                pipe.expire(key, ttl)
                result = pipe.execute()
                return result[0]
            except Exception as e:
                logger.error(f"Redis INCR error: {e}")
        # fallback
        current = self._memory_get(key) or 0
        new_val = current + amount
        self._memory_set(key, new_val, ttl)
        return new_val

    # ── Helpers de dominio ─────────────────────────────────────────────────────

    def cache_audio(self, text: str, audio_bytes: bytes, language: str = "es-CO") -> str:
        """Guarda audio TTS en Redis como bytes raw. Retorna la clave usada."""
        key = f"tts:{language}:{hashlib.md5(text.encode()).hexdigest()}"
        if self._use_redis:
            try:
                self._redis.setex(key, self.AUDIO_TTL, audio_bytes)
                return key
            except Exception as e:
                logger.error(f"Redis audio cache error: {e}")
        # No almacenar bytes en memoria dict (demasiado voluminoso)
        return key

    def get_audio(self, text: str, language: str = "es-CO") -> Optional[bytes]:
        """Recupera audio TTS cacheado. Retorna None si no existe."""
        key = f"tts:{language}:{hashlib.md5(text.encode()).hexdigest()}"
        if self._use_redis:
            try:
                raw = self._redis.get(key)
                # decode_responses=True retorna str; re-encode si aplica
                if isinstance(raw, str):
                    return raw.encode("latin-1")
                return raw
            except Exception as e:
                logger.error(f"Redis audio get error: {e}")
        return None

    def set_session(self, session_id: str, data: dict) -> bool:
        """Guarda el estado de una sesión de conversación."""
        key = f"session:{session_id}"
        return self.set(key, data, ttl=self.SESSION_TTL)

    def get_session(self, session_id: str) -> Optional[dict]:
        """Recupera el estado de una sesión de conversación."""
        key = f"session:{session_id}"
        return self.get(key)

    def delete_session(self, session_id: str) -> bool:
        """Elimina la sesión al finalizar la llamada."""
        return self.delete(f"session:{session_id}")

    def rate_limit(self, identifier: str, limit: int = 10,
                   window_seconds: int = 60) -> bool:
        """
        Verifica rate limit de tipo sliding window.
        Retorna True si la solicitud está dentro del límite.
        """
        key = f"rate:{identifier}:{int(time.time()) // window_seconds}"
        count = self.increment(key, ttl=window_seconds * 2)
        return count <= limit

    def get_stats(self) -> dict:
        """Retorna estadísticas del cache."""
        stats = {"backend": "redis" if self._use_redis else "memory"}
        if self._use_redis:
            try:
                info = self._redis.info("memory")
                stats["used_memory_human"] = info.get("used_memory_human", "N/A")
                stats["connected_clients"] = self._redis.info("clients").get(
                    "connected_clients", 0
                )
                stats["total_keys"] = self._redis.dbsize()
            except Exception:
                stats["error"] = "no se pudo obtener info de Redis"
        else:
            self._evict_expired()
            stats["total_keys"] = len(self._memory)
        return stats

    # ── Fallback in-memory ─────────────────────────────────────────────────────

    def _memory_get(self, key: str) -> Optional[Any]:
        expiry = self._memory_ttl.get(key)
        if expiry and time.time() > expiry:
            self._memory.pop(key, None)
            self._memory_ttl.pop(key, None)
            return None
        return self._memory.get(key)

    def _memory_set(self, key: str, value: Any, ttl: int) -> bool:
        self._memory[key] = value
        self._memory_ttl[key] = time.time() + ttl
        return True

    def _evict_expired(self):
        now = time.time()
        expired = [k for k, t in self._memory_ttl.items() if t < now]
        for k in expired:
            self._memory.pop(k, None)
            self._memory_ttl.pop(k, None)

    @staticmethod
    def _match_pattern(pattern: str, key: str) -> bool:
        """Matching simplificado de patrones Redis (solo sufijo *)."""
        if pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        return key == pattern
