from typing import Dict, List, Optional, Any, Union
"""
SQLAlchemy models for OTP verification and auth audit logging.
Persists OTP codes and every auth attempt to the database.
"""

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Boolean, Integer, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str) -> str:
    """Store OTP as SHA-256 hash, never plaintext."""
    return hashlib.sha256(code.encode()).hexdigest()


class OTPCode(Base):
    """
    One OTP record per (phone OR email) per request.
    Code is stored as SHA-256 hash for security.
    """

    __tablename__ = "otp_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    # Recipient — at least one must be set
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="sms")  # sms | email | whatsapp
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, server_default=func.now(), nullable=False
    )

    @staticmethod
    def hash(code: str) -> str:
        return _hash_code(code)

    def matches(self, code: str) -> bool:
        return self.code_hash == _hash_code(code)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def is_blocked(self) -> bool:
        return self.attempts >= 5

    def __repr__(self) -> str:
        return f"<OTPCode phone={self.phone} used={self.used} attempts={self.attempts}>"


class AuthAuditLog(Base):
    """
    Immutable audit record for every authentication action.
    Used for security monitoring and incident investigation.
    """

    __tablename__ = "auth_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # Actions: send_otp | verify_otp | verify_success | verify_fail | lockout | refresh | logout
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Statuses: success | failed | rate_limited | expired | blocked
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuthAuditLog action={self.action} status={self.status} phone={self.phone}>"
