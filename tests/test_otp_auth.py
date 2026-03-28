"""Tests del sistema OTP y verificación de identidad."""
import os
import sys
import time
import pytest

_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


# ── OTP Manager Tests ─────────────────────────────────────────────────────────

def test_generate_otp_returns_6_digits():
    from auth.otp_manager import OTPManager
    mgr = OTPManager()
    code = mgr.generate_otp("+573160438031")
    assert code is not None
    assert len(code) == 6
    assert code.isdigit()


def test_verify_otp_success():
    from auth.otp_manager import OTPManager
    mgr = OTPManager()
    phone = "+573160438001"
    code = mgr.generate_otp(phone)
    assert mgr.verify_otp(phone, code) is True


def test_verify_otp_wrong_code_increments_attempts():
    from auth.otp_manager import OTPManager
    mgr = OTPManager()
    phone = "+573160438002"
    mgr.generate_otp(phone)
    mgr.verify_otp(phone, "000000")
    remaining = mgr.get_remaining_attempts(phone)
    assert remaining == mgr.MAX_ATTEMPTS - 1


def test_verify_otp_unknown_phone_returns_false():
    from auth.otp_manager import OTPManager
    mgr = OTPManager()
    assert mgr.verify_otp("+573160000000", "123456") is False


def test_rate_limiting_blocks_after_3_sends():
    from auth.otp_manager import OTPManager
    mgr = OTPManager()
    phone = "+573160438003"
    for _ in range(mgr.MAX_SENDS_PER_WINDOW):
        mgr.generate_otp(phone)
    # 4to envío debe ser bloqueado
    result = mgr.generate_otp(phone)
    assert result is None


def test_invalidate_removes_otp():
    from auth.otp_manager import OTPManager
    mgr = OTPManager()
    phone = "+573160438004"
    code = mgr.generate_otp(phone)
    mgr.invalidate(phone)
    assert mgr.verify_otp(phone, code) is False


# ── Rate Limiter Tests ────────────────────────────────────────────────────────

def test_rate_limiter_allows_within_limit():
    from middleware.rate_limit_otp import OTPRateLimiter
    limiter = OTPRateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        assert limiter.is_allowed("user1") is True


def test_rate_limiter_blocks_after_limit():
    from middleware.rate_limit_otp import OTPRateLimiter
    limiter = OTPRateLimiter(max_requests=2, window_seconds=60)
    limiter.is_allowed("user2")
    limiter.is_allowed("user2")
    assert limiter.is_allowed("user2") is False


def test_rate_limiter_remaining_decreases():
    from middleware.rate_limit_otp import OTPRateLimiter
    limiter = OTPRateLimiter(max_requests=5, window_seconds=60)
    limiter.is_allowed("user3")
    limiter.is_allowed("user3")
    assert limiter.remaining("user3") == 3


# ── Context Manager Tests ─────────────────────────────────────────────────────

def test_context_manager_preserves_order_across_turns():
    from core.context_manager import ContextManager
    ctx = ContextManager("session-123")
    ctx.set_order_context("ECO-2026-001234")
    assert ctx.ctx.current_order_number == "ECO-2026-001234"


def test_context_manager_resolves_references():
    from core.context_manager import ContextManager
    ctx = ContextManager("session-456")
    ctx.set_order_context("ECO-2026-001234")

    # Usuario dice "ese pedido" sin dar número
    enriched = ctx.resolve_references({}, "¿cuándo llega ese pedido?")
    assert enriched.get("order_number") == "ECO-2026-001234"


def test_context_manager_no_reference_without_context():
    from core.context_manager import ContextManager
    ctx = ContextManager("session-789")
    # Sin pedido activo, no debe inyectar nada
    enriched = ctx.resolve_references({}, "quiero saber de ese pedido")
    assert enriched.get("order_number") is None


def test_context_manager_voice_summary():
    from core.context_manager import ContextManager
    ctx = ContextManager("session-abc")
    ctx.set_customer_verified("cust-1", "María García", "3160438031", "token123")
    ctx.set_order_context("ECO-2026-001234")
    summary = ctx.get_voice_context_summary()
    assert "María García" in summary
    assert "ECO-2026-001234" in summary


def test_context_manager_session_store():
    from core.session_store import SessionStore, ContextManager
    store = SessionStore()
    ctx = ContextManager("session-store-test")
    ctx.set_order_context("ECO-2026-999999")
    store.save("session-store-test", ctx)
    loaded = store.load("session-store-test")
    assert loaded is not None
    assert loaded.ctx.current_order_number == "ECO-2026-999999"


# ── Customer Verifier Tests ───────────────────────────────────────────────────

def test_customer_verifier_mask_email():
    from auth.customer_verifier import CustomerVerifier
    v = CustomerVerifier()
    assert v.mask_email("juan@gmail.com") == "j***@gmail.com"


def test_customer_verifier_name_similarity():
    from auth.customer_verifier import CustomerVerifier
    v = CustomerVerifier()
    score = v._name_similarity("Juan Camilo Rivera", "Juan C. Rivera")
    assert score > 0.5


def test_customer_verifier_validate_token_invalid():
    from auth.customer_verifier import CustomerVerifier
    v = CustomerVerifier()
    result = v.validate_session_token("not.a.valid.token")
    assert result is None
