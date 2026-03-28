"""
Tests for OTP authentication system (Module 2).
Uses SQLite in-memory — no external services required.
Run: pytest tests/test_auth_otp.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio

_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    from database import engine, Base
    import models  # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(db_engine):
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


# ── OTPCode model tests ────────────────────────────────────────────────────────

class TestOTPCodeModel:

    def test_hash_is_not_plaintext(self):
        from models.auth import OTPCode
        code = "123456"
        h = OTPCode.hash(code)
        assert h != code
        assert len(h) == 64  # SHA-256 hex

    def test_matches_correct_code(self):
        from models.auth import OTPCode
        code = "987654"
        otp = OTPCode(id=str(uuid.uuid4()), code_hash=OTPCode.hash(code),
                      channel="sms", expires_at=__import__("datetime").datetime(2099,1,1))
        assert otp.matches(code) is True

    def test_does_not_match_wrong_code(self):
        from models.auth import OTPCode
        otp = OTPCode(id=str(uuid.uuid4()), code_hash=OTPCode.hash("111111"),
                      channel="sms", expires_at=__import__("datetime").datetime(2099,1,1))
        assert otp.matches("999999") is False

    def test_is_blocked_after_5_attempts(self):
        from models.auth import OTPCode
        import datetime
        otp = OTPCode(id=str(uuid.uuid4()), code_hash=OTPCode.hash("111111"),
                      channel="sms", expires_at=datetime.datetime(2099,1,1), attempts=5)
        assert otp.is_blocked() is True

    def test_not_blocked_at_4_attempts(self):
        from models.auth import OTPCode
        import datetime
        otp = OTPCode(id=str(uuid.uuid4()), code_hash=OTPCode.hash("111111"),
                      channel="sms", expires_at=datetime.datetime(2099,1,1), attempts=4)
        assert otp.is_blocked() is False


# ── OTPService tests ───────────────────────────────────────────────────────────

class TestOTPService:

    @pytest.mark.asyncio
    async def test_generate_and_send_sms(self, db_session):
        from services.otp_service import OTPService
        svc = OTPService(db_session)

        with patch("services.sms_service.SMSService.send_otp", return_value=True):
            result = await svc.generate_and_send(phone="+573001111111", channel="sms")

        assert result["sent"] is True
        assert result["expires_in"] == 300

    @pytest.mark.asyncio
    async def test_generate_and_send_email(self, db_session):
        from services.otp_service import OTPService
        svc = OTPService(db_session)

        with patch("services.email_service.EmailService.send_otp", return_value=True):
            result = await svc.generate_and_send(email="test@example.com", channel="email")

        assert result["sent"] is True

    @pytest.mark.asyncio
    async def test_verify_correct_code(self, db_session):
        """Inject a known OTP into DB then verify it."""
        from services.otp_service import OTPService
        from models.auth import OTPCode
        from datetime import datetime, timedelta, timezone

        phone = "+573002222222"
        code  = "424242"

        # Manually insert OTP
        otp = OTPCode(
            id=str(uuid.uuid4()),
            phone=phone,
            code_hash=OTPCode.hash(code),
            channel="sms",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db_session.add(otp)
        await db_session.flush()

        svc = OTPService(db_session)
        result = await svc.verify(phone=phone, code=code)

        assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_verify_wrong_code_increments_attempts(self, db_session):
        from services.otp_service import OTPService
        from models.auth import OTPCode
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import select

        phone = "+573003333333"
        otp = OTPCode(
            id=str(uuid.uuid4()),
            phone=phone,
            code_hash=OTPCode.hash("111111"),
            channel="sms",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db_session.add(otp)
        await db_session.flush()

        svc = OTPService(db_session)
        result = await svc.verify(phone=phone, code="999999")

        assert result["verified"] is False
        assert result["remaining_attempts"] == 4

    @pytest.mark.asyncio
    async def test_verify_expired_otp(self, db_session):
        from services.otp_service import OTPService
        from models.auth import OTPCode
        from datetime import datetime, timedelta, timezone

        phone = "+573004444444"
        otp = OTPCode(
            id=str(uuid.uuid4()),
            phone=phone,
            code_hash=OTPCode.hash("555555"),
            channel="sms",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # already expired
        )
        db_session.add(otp)
        await db_session.flush()

        svc = OTPService(db_session)
        result = await svc.verify(phone=phone, code="555555")

        assert result["verified"] is False
        assert result["reason"] == "expired"

    @pytest.mark.asyncio
    async def test_verify_no_active_otp(self, db_session):
        from services.otp_service import OTPService

        svc = OTPService(db_session)
        result = await svc.verify(phone="+573009999999", code="000000")

        assert result["verified"] is False
        assert result["reason"] == "no_active_otp"

    @pytest.mark.asyncio
    async def test_rate_limit_after_3_sends(self, db_session):
        from services.otp_service import OTPService

        phone = "+573005555555"
        svc = OTPService(db_session)

        with patch("services.sms_service.SMSService.send_otp", return_value=True):
            for _ in range(3):
                await svc.generate_and_send(phone=phone, channel="sms")

            # 4th should be rate-limited
            result = await svc.generate_and_send(phone=phone, channel="sms")

        assert result["sent"] is False
        assert result["reason"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_audit_log_created_on_send(self, db_session):
        from services.otp_service import OTPService
        from models.auth import AuthAuditLog
        from sqlalchemy import select

        phone = "+573006666666"
        svc = OTPService(db_session)

        with patch("services.sms_service.SMSService.send_otp", return_value=True):
            await svc.generate_and_send(phone=phone, channel="sms")

        result = await db_session.execute(
            select(AuthAuditLog).where(AuthAuditLog.phone == phone)
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        assert logs[0].action == "send_otp"

    @pytest.mark.asyncio
    async def test_create_tokens_structure(self, db_session):
        from services.otp_service import OTPService

        svc = OTPService(db_session)
        tokens = svc.create_tokens(
            customer_id=str(uuid.uuid4()),
            phone="+573001234567",
        )
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["expires_in"] == 1800

    @pytest.mark.asyncio
    async def test_decode_valid_token(self, db_session):
        from services.otp_service import OTPService

        svc = OTPService(db_session)
        customer_id = str(uuid.uuid4())
        tokens = svc.create_tokens(customer_id=customer_id, phone="+573001234567")

        payload = svc.decode_token(tokens["access_token"])
        assert payload is not None
        assert payload["sub"] == customer_id
        assert payload["type"] == "customer_access"

    @pytest.mark.asyncio
    async def test_decode_invalid_token_returns_none(self, db_session):
        from services.otp_service import OTPService

        svc = OTPService(db_session)
        result = svc.decode_token("totally.invalid.token")
        assert result is None
