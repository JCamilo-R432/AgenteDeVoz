"""
Configuración compartida de pytest para todos los tests.
Fixtures globales, path setup, y variables de entorno de testing.
"""

import pytest
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

# ── Path setup ────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ── Variables de entorno para testing ────────────────────────────────────────

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/agentevoz_test")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-32ch")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("APP_SECRET_KEY", "test-app-secret-key-for-testing-32chars")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("STT_ENGINE", "pyttsx3")
os.environ.setdefault("TTS_ENGINE", "pyttsx3")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-for-testing")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "testtoken")
os.environ.setdefault("TWILIO_PHONE_NUMBER", "+15550000000")
os.environ.setdefault("SENDGRID_API_KEY", "SG.testkey")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "test_wa_token")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "test_phone_id")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_verify_token")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("CRM_API_KEY", "test_crm_key")
os.environ.setdefault("CRM_BASE_URL", "https://api.hubapi.com")

# ── Fixtures globales ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_session_id():
    """Genera ID de sesión único para la sesión de tests."""
    return f"test-session-{datetime.now().strftime('%Y%m%d%H%M%S')}"

@pytest.fixture(scope="function")
def sample_ticket_data():
    """Datos de ejemplo para tickets."""
    return {
        "description": "Problema de prueba con la factura",
        "phone": "3001234567",
        "email": "test@example.com",
        "priority": "MEDIA",
    }

@pytest.fixture(scope="function")
def sample_user_data():
    """Datos de ejemplo para usuario."""
    return {
        "name": "Usuario Test",
        "phone": "3001234567",
        "email": "test@example.com",
    }

@pytest.fixture(scope="function")
def sample_conversation_data():
    """Datos de ejemplo para conversación."""
    return {
        "session_id": f"test-conv-{datetime.now().strftime('%H%M%S%f')}",
        "transcript": "Hola, tengo un problema con mi factura",
        "duration": 120,
    }

@pytest.fixture
def mock_db():
    """Mock de la base de datos para tests que no requieren PostgreSQL real."""
    db = MagicMock()
    db.insert.return_value = "test-id-001"
    db.find_one.return_value = {
        "id": "test-id-001",
        "ticket_number": "TKT-2026-000001",
        "status": "ABIERTO",
        "priority": "MEDIA",
        "description": "Test ticket",
    }
    db.find_all.return_value = []
    db.update.return_value = True
    db.connection = MagicMock()
    db.connection.closed = 0
    return db

@pytest.fixture
def mock_redis():
    """Mock de Redis para tests que no requieren Redis real."""
    _store = {}
    cache = MagicMock()
    cache.get.side_effect = lambda key, default=None: _store.get(key, default)
    cache.set.side_effect = lambda key, val, **kw: _store.update({key: val}) or True
    cache.delete.side_effect = lambda key: _store.pop(key, None) is not None or True
    cache.exists.side_effect = lambda key: key in _store
    cache.get_stats.return_value = {"backend": "mock"}
    return cache

@pytest.fixture
def agent_fixture():
    """Agente de voz listo para tests (sin dependencias externas)."""
    from core.agent import CustomerServiceAgent
    agent = CustomerServiceAgent(session_id="test-agent-001")
    return agent

@pytest.fixture
def started_agent(agent_fixture):
    """Agente ya iniciado con start_call()."""
    agent_fixture.start_call()
    return agent_fixture

@pytest.fixture(autouse=False)
def no_llm(monkeypatch):
    """Desactiva las llamadas a LLM para que los tests sean deterministicos."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
