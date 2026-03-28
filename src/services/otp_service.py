from __future__ import annotations
"""
OTP Service — database-backed OTP generation, verification, and audit logging.
Replaces the in-memory OTPManager for production use.

Key differences from in-memory version:
  - OTPs survive server restarts
  - Full audit trail in DB
  - 5-minute expiry (spec requirement)
  - Lockout after 5 failed attempts
  - Multi-channel: sms | email | whatsapp
"""


import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.auth import OTPCode, AuthAuditLog

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 5
OTP_MAX_ATTEMPTS   = 5


class OTPService:
    """Async database-backed OTP service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Generate & Send ────────────────────────────────────────────────────────

    async def generate_and_send(
        self,
        *,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        tenant_id: Optional[str] = None,
        channel: str = "sms",
        ip_address: Optional[str] = None,
        brand_name: str = "Agente de Voz",
    ) -> dict:
        """
        Generate a 6-digit OTP, persist it (hashed), and send via the chosen channel.
        Returns: {"sent": bool, "expires_in": int, "retry_after": int|None}
        """
        if not phone and not email:
            raise ValueError("phone or email is required")

        # Check rate limit (max 3 pending/active OTPs per identifier in last 10 min)
        identifier = phone or email
        recent_count = await self._count_recent_otps(phone=phone, email=email, tenant_id=tenant_id)
        if recent_count >= 3:
            await self._audit(phone=phone, email=email, tenant_id=tenant_id,
                              action="send_otp", status="rate_limited", ip=ip_address)
            return {"sent": False, "reason": "rate_limited", "retry_after": 600}

        # Invalidate any existing active OTPs for this recipient
        await self._invalidate_existing(phone=phone, email=email, tenant_id=tenant_id)

        # Generate
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)

        otp = OTPCode(
            id=str(uuid.uuid4()),
            phone=phone,
            email=email,
            tenant_id=tenant_id,
            code_hash=OTPCode.hash(code),
            channel=channel,
            expires_at=expires_at,
        )
        self.session.add(otp)
        await self.session.flush()

        # Send
        sent = await self._deliver(phone=phone, email=email, code=code,
                                   channel=channel, brand_name=brand_name)

        await self._audit(phone=phone, email=email, tenant_id=tenant_id,
                          action="send_otp", status="success" if sent else "failed",
                          ip=ip_address, detail=f"channel={channel}")

        return {
            "sent": sent,
            "expires_in": OTP_EXPIRY_MINUTES * 60,
            "channel": channel,
        }

    # ── Verify ─────────────────────────────────────────────────────────────────

    async def verify(
        self,
        *,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        tenant_id: Optional[str] = None,
        code: str,
        ip_address: Optional[str] = None,
    ) -> dict:
        """
        Verify a submitted OTP code.
        Returns: {"verified": bool, "reason": str, "remaining_attempts": int}
        """
        otp = await self._get_active_otp(phone=phone, email=email, tenant_id=tenant_id)

        if otp is None:
            await self._audit(phone=phone, email=email, tenant_id=tenant_id,
                              action="verify_otp", status="failed", ip=ip_address,
                              detail="no_active_otp")
            return {"verified": False, "reason": "no_active_otp", "remaining_attempts": 0}

        if otp.is_expired():
            otp.used = True
            await self.session.flush()
            await self._audit(phone=phone, email=email, tenant_id=tenant_id,
                              action="verify_otp", status="expired", ip=ip_address)
            return {"verified": False, "reason": "expired", "remaining_attempts": 0}

        if otp.is_blocked():
            await self._audit(phone=phone, email=email, tenant_id=tenant_id,
                              action="verify_otp", status="blocked", ip=ip_address)
            return {"verified": False, "reason": "max_attempts_reached", "remaining_attempts": 0}

        if not otp.matches(code):
            otp.attempts += 1
            remaining = max(0, OTP_MAX_ATTEMPTS - otp.attempts)
            await self.session.flush()

            status = "lockout" if remaining == 0 else "failed"
            await self._audit(phone=phone, email=email, tenant_id=tenant_id,
                              action="verify_otp", status=status, ip=ip_address,
                              detail=f"remaining={remaining}")
            return {"verified": False, "reason": "invalid_code", "remaining_attempts": remaining}

        # SUCCESS
        otp.used = True
        await self.session.flush()
        await self._audit(phone=phone, email=email, tenant_id=tenant_id,
                          action="verify_success", status="success", ip=ip_address)
        return {"verified": True, "reason": "ok", "remaining_attempts": OTP_MAX_ATTEMPTS}

    # ── JWT token creation ─────────────────────────────────────────────────────

    def create_tokens(
        self, customer_id: str, phone: Optional[str] = None, email: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> dict:
        """
        Issue JWT access token (30 min) + refresh token (7 days).
        """
        from jose import jwt
        from config.settings import settings

        now = datetime.now(timezone.utc)
        jti = str(uuid.uuid4())

        access_payload = {
            "sub":       customer_id,
            "phone":     phone,
            "email":     email,
            "tenant_id": tenant_id,
            "type":      "customer_access",
            "jti":       jti,
            "exp":       now + timedelta(minutes=30),
            "iat":       now,
        }
        refresh_payload = {
            "sub":       customer_id,
            "tenant_id": tenant_id,
            "type":      "customer_refresh",
            "jti":       str(uuid.uuid4()),
            "exp":       now + timedelta(days=7),
            "iat":       now,
        }

        algo = settings.JWT_ALGORITHM
        secret = settings.JWT_SECRET_KEY
        return {
            "access_token":  jwt.encode(access_payload,  secret, algorithm=algo),
            "refresh_token": jwt.encode(refresh_payload, secret, algorithm=algo),
            "token_type":    "bearer",
            "expires_in":    1800,
        }

    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate a JWT. Returns payload or None."""
        try:
            from jose import jwt, JWTError
            from config.settings import settings
            return jwt.decode(token, settings.JWT_SECRET_KEY,
                              algorithms=[settings.JWT_ALGORITHM])
        except Exception:
            return None

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _get_active_otp(
        self, phone: Optional[str], email: Optional[str], tenant_id: Optional[str]
    ) -> Optional[OTPCode]:
        filters = [OTPCode.used.is_(False)]
        if phone:
            filters.append(OTPCode.phone == phone)
        if email:
            filters.append(OTPCode.email == email)
        if tenant_id:
            filters.append(OTPCode.tenant_id == tenant_id)

        result = await self.session.execute(
            select(OTPCode)
            .where(and_(*filters))
            .order_by(OTPCode.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _count_recent_otps(
        self, phone: Optional[str], email: Optional[str], tenant_id: Optional[str]
    ) -> int:
        """Count ALL OTPs (used or not) in the last 10 min — rate-limit window."""
        from sqlalchemy import func as sqlfunc
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        # Note: include used OTPs so prior sends count against the limit
        filters = [OTPCode.created_at >= cutoff]
        if phone:
            filters.append(OTPCode.phone == phone)
        if email:
            filters.append(OTPCode.email == email)

        result = await self.session.execute(
            select(sqlfunc.count(OTPCode.id)).where(and_(*filters))
        )
        return result.scalar_one()

    async def _invalidate_existing(
        self, phone: Optional[str], email: Optional[str], tenant_id: Optional[str]
    ) -> None:
        """Mark all previous unused OTPs for this recipient as used."""
        from sqlalchemy import update
        filters = [OTPCode.used.is_(False)]
        if phone:
            filters.append(OTPCode.phone == phone)
        if email:
            filters.append(OTPCode.email == email)

        await self.session.execute(
            update(OTPCode).where(and_(*filters)).values(used=True)
        )

    async def _audit(
        self,
        *,
        phone: Optional[str],
        email: Optional[str],
        tenant_id: Optional[str],
        action: str,
        status: str,
        ip: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        log = AuthAuditLog(
            id=str(uuid.uuid4()),
            phone=phone,
            email=email,
            tenant_id=tenant_id,
            action=action,
            status=status,
            ip_address=ip,
            detail=detail,
        )
        self.session.add(log)
        await self.session.flush()  # make visible within this transaction

    async def _deliver(
        self,
        *,
        phone: Optional[str],
        email: Optional[str],
        code: str,
        channel: str,
        brand_name: str,
    ) -> bool:
        """Route OTP delivery to the correct channel."""
        try:
            if channel in ("sms", "whatsapp") and phone:
                from services.sms_service import SMSService
                svc = SMSService()
                if channel == "whatsapp":
                    return svc.send_whatsapp_otp(phone, code)
                return svc.send_otp(phone, code)

            if channel == "email" and email:
                from services.email_service import EmailService
                svc = EmailService()
                return svc.send_otp(email, code, brand_name=brand_name)

            logger.warning(f"No delivery method for channel={channel} phone={phone} email={email}")
            return False
        except Exception as exc:
            logger.error(f"OTP delivery error: {exc}")
            return False
