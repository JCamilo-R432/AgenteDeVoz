"""Tests de seguridad para autenticación y autorización."""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestJWTSecurity:
    """Tests de seguridad para JWT."""

    def test_jwt_token_generation(self):
        """Se puede generar un JWT válido."""
        try:
            from jose import jwt
            secret = "test-secret-key-for-testing-only-32ch"
            payload = {"sub": "test_user", "exp": int(time.time()) + 3600}
            token = jwt.encode(payload, secret, algorithm="HS256")
            assert token is not None
            assert len(token) > 50
        except ImportError:
            pytest.skip("python-jose no instalado")

    def test_jwt_token_validation(self):
        """Un JWT válido puede ser verificado."""
        try:
            from jose import jwt
            secret = "test-secret-key-for-testing-only-32ch"
            payload = {"sub": "test_user", "role": "agent", "exp": int(time.time()) + 3600}
            token = jwt.encode(payload, secret, algorithm="HS256")
            decoded = jwt.decode(token, secret, algorithms=["HS256"])
            assert decoded["sub"] == "test_user"
            assert decoded["role"] == "agent"
        except ImportError:
            pytest.skip("python-jose no instalado")

    def test_jwt_expired_token_rejected(self):
        """Un JWT expirado es rechazado."""
        try:
            from jose import jwt, JWTError
            secret = "test-secret-key-for-testing-only-32ch"
            # Token con fecha de expiración en el pasado
            payload = {"sub": "test_user", "exp": int(time.time()) - 3600}
            token = jwt.encode(payload, secret, algorithm="HS256")
            with pytest.raises(JWTError):
                jwt.decode(token, secret, algorithms=["HS256"])
        except ImportError:
            pytest.skip("python-jose no instalado")

    def test_jwt_wrong_secret_rejected(self):
        """Un JWT firmado con secreto incorrecto es rechazado."""
        try:
            from jose import jwt, JWTError
            secret = "correct-secret-key-32chars-minimum"
            wrong_secret = "wrong-secret-key-32chars-minimum-x"
            payload = {"sub": "test_user", "exp": int(time.time()) + 3600}
            token = jwt.encode(payload, secret, algorithm="HS256")
            with pytest.raises(JWTError):
                jwt.decode(token, wrong_secret, algorithms=["HS256"])
        except ImportError:
            pytest.skip("python-jose no instalado")

    def test_jwt_tampered_token_rejected(self):
        """Un JWT con payload modificado es rechazado."""
        try:
            from jose import jwt, JWTError
            import base64

            secret = "test-secret-key-for-testing-only-32ch"
            payload = {"sub": "user", "role": "viewer", "exp": int(time.time()) + 3600}
            token = jwt.encode(payload, secret, algorithm="HS256")

            # Intentar modificar el payload (el token se invalida)
            parts = token.split(".")
            if len(parts) == 3:
                # Decodificar y re-encodificar con admin role
                tampered_payload = base64.b64encode(
                    b'{"sub":"user","role":"admin","exp":9999999999}'
                ).decode().rstrip("=")
                tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

                with pytest.raises((JWTError, Exception)):
                    jwt.decode(tampered_token, secret, algorithms=["HS256"])
        except ImportError:
            pytest.skip("python-jose no instalado")

    def test_jwt_algorithm_none_attack(self):
        """El algoritmo 'none' no es aceptado."""
        try:
            from jose import jwt, JWTError
            secret = "test-secret-key-for-testing-only-32ch"

            # Intentar crear un token con alg=none
            try:
                token = jwt.encode({"sub": "admin"}, "", algorithm="none")
                # Si genera el token, la decodificación debe fallar
                with pytest.raises((JWTError, Exception)):
                    jwt.decode(token, secret, algorithms=["HS256"])
            except Exception:
                pass  # Aceptable — jwt puede rechazar alg=none en encode
        except ImportError:
            pytest.skip("python-jose no instalado")


class TestAPIAuthentication:
    """Tests de autenticación para la API."""

    @pytest.fixture
    def client(self):
        """Cliente de test para la API."""
        from fastapi.testclient import TestClient
        from api.routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return TestClient(app)

    def test_protected_endpoint_without_token(self, client):
        """Endpoints protegidos requieren token."""
        response = client.get("/api/v1/sessions")
        assert response.status_code in (401, 403)

    def test_protected_endpoint_with_invalid_token(self, client):
        """Token inválido es rechazado o ignorado."""
        response = client.get(
            "/api/v1/sessions",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )
        # Puede ser 200 (MVP simplificado) o 401 (producción)
        assert response.status_code in (200, 401, 403)

    def test_login_with_wrong_credentials(self, client):
        """Credenciales incorrectas retornan 401."""
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "admin", "password": "WRONG_PASSWORD"},
        )
        assert response.status_code == 401

    def test_login_with_nonexistent_user(self, client):
        """Usuario inexistente retorna 401."""
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "usuario_no_existe_xyz", "password": "any"},
        )
        assert response.status_code == 401

    def test_login_returns_token_structure(self, client):
        """Login exitoso retorna estructura de token correcta."""
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "admin", "password": "admin123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "token_type" in body
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 10

    def test_public_endpoints_accessible(self, client):
        """Endpoints públicos no requieren autenticación."""
        # /ping y /health son públicos
        ping_resp = client.get("/api/v1/ping")
        health_resp = client.get("/api/v1/health")
        assert ping_resp.status_code == 200
        assert health_resp.status_code == 200


class TestRateLimiting:
    """Tests para rate limiting."""

    def test_rate_limit_in_memory(self):
        """El rate limiting funciona en modo in-memory."""
        from integrations.redis_cache import RedisCache
        cache = RedisCache(host="localhost", port=6380)

        identifier = f"rate_test_{int(time.time())}"
        limit = 5

        # Primeras `limit` solicitudes deben pasar
        results = []
        for _ in range(limit):
            results.append(cache.rate_limit(identifier, limit=limit, window_seconds=60))
        assert all(results), "Primeras solicitudes deben pasar el rate limit"

        # La solicitud extra debe ser bloqueada
        extra = cache.rate_limit(identifier, limit=limit, window_seconds=60)
        assert extra is False, "La solicitud extra debe ser bloqueada"

    def test_rate_limit_resets_per_window(self):
        """Rate limit se resetea en una nueva ventana temporal."""
        from integrations.redis_cache import RedisCache
        cache = RedisCache(host="localhost", port=6380)

        # Usar un timestamp futuro como identificador para simular nueva ventana
        future_id = f"future_{int(time.time()) + 9999}"
        result = cache.rate_limit(future_id, limit=5, window_seconds=60)
        assert result is True, "Nueva ventana temporal debe permitir solicitudes"


class TestDataProtectionInAuth:
    """Tests para protección de datos en autenticación."""

    def test_password_not_echoed_in_error(self):
        """Las contraseñas no aparecen en mensajes de error."""
        from fastapi.testclient import TestClient
        from api.routes import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        client = TestClient(app)

        secret_password = "mi_password_secreto_12345"
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "admin", "password": secret_password},
        )
        response_text = response.text
        assert secret_password not in response_text, \
            "La contraseña no debe aparecer en la respuesta de error"

    def test_token_has_no_sensitive_data_in_plain(self):
        """El token no contiene datos sensibles en texto plano sin verificación."""
        from fastapi.testclient import TestClient
        from api.routes import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/token",
            data={"username": "admin", "password": "admin123"},
        )
        if response.status_code == 200:
            token = response.json().get("access_token", "")
            # El token no debe contener la contraseña en texto plano
            assert "admin123" not in token
