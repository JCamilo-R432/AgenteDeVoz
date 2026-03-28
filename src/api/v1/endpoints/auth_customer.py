from __future__ import annotations
"""
Customer authentication endpoints — OTP flow.

Flow:
  1. POST /auth/send-otp   → Generate + deliver 6-digit OTP (SMS | Email | WhatsApp)
  2. POST /auth/verify-otp → Verify code → issue JWT access + refresh tokens
  3. POST /auth/refresh    → Exchange refresh token for new access token
  4. GET  /auth/me         → Return decoded session info
  5. POST /auth/logout     → Revoke session (client discards token)

Security:
  - OTP codes hashed (SHA-256) in DB — never stored plaintext
  - Rate limit: 3 sends per 10 min per phone/email
  - Lockout: after 5 wrong attempts, OTP is invalidated
  - Audit log: every action recorded in auth_audit_logs
"""


import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from schemas.auth import (
    SendOTPRequest,
    SendOTPResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
    RefreshTokenRequest,
    TokenResponse,
    CustomerMeResponse,
)
from services.otp_service import OTPService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["customer-auth"])


# ── Dependency helpers ─────────────────────────────────────────────────────────

def _svc(db: AsyncSession = Depends(get_db)) -> OTPService:
    return OTPService(db)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _tenant_id(request: Request) -> Optional[str]:
    return getattr(request.state, "tenant_id", None)


def _brand_name(request: Request) -> str:
    tenant = getattr(request.state, "tenant", None)
    if tenant and tenant.settings:
        return tenant.settings.get("brand_name", "Agente de Voz")
    return "Agente de Voz"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/send-otp",
    response_model=SendOTPResponse,
    summary="Send OTP code via SMS, Email, or WhatsApp",
)
async def send_otp(
    payload: SendOTPRequest,
    request: Request,
    svc: OTPService = Depends(_svc),
) -> SendOTPResponse:
    """
    Generate a 6-digit OTP and deliver it via the chosen channel.
    Rate-limited to 3 OTPs per 10-minute window per phone/email.
    """
    if not payload.phone and not payload.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either 'phone' or 'email'.",
        )

    # Use tenant from API key if not explicitly provided in body
    tenant_id = payload.tenant_id or _tenant_id(request)
    brand = _brand_name(request)

    result = await svc.generate_and_send(
        phone=payload.phone,
        email=payload.email,
        tenant_id=tenant_id,
        channel=payload.channel,
        ip_address=_client_ip(request),
        brand_name=brand,
    )

    if not result["sent"]:
        if result.get("reason") == "rate_limited":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos. Espera 10 minutos antes de solicitar otro código.",
                headers={"Retry-After": str(result.get("retry_after", 600))},
            )
        # Delivery failed (Twilio/SendGrid error) — don't reveal whether number exists
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo enviar el código. Intenta de nuevo en unos momentos.",
        )

    recipient = payload.phone or payload.email or ""
    return SendOTPResponse(
        message=f"Código enviado a {_mask(recipient)} vía {payload.channel}.",
        expires_in=result["expires_in"],
        channel=result["channel"],
    )


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
    summary="Verify OTP and receive JWT tokens",
)
async def verify_otp(
    payload: VerifyOTPRequest,
    request: Request,
    svc: OTPService = Depends(_svc),
) -> VerifyOTPResponse:
    """
    Verify the submitted OTP code.
    On success, returns access (30 min) + refresh (7 days) JWT tokens.
    After 5 wrong attempts the OTP is permanently invalidated.
    """
    if not payload.phone and not payload.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either 'phone' or 'email'.",
        )

    tenant_id = payload.tenant_id or _tenant_id(request)

    result = await svc.verify(
        phone=payload.phone,
        email=payload.email,
        tenant_id=tenant_id,
        code=payload.code,
        ip_address=_client_ip(request),
    )

    if not result["verified"]:
        reason = result.get("reason", "invalid")
        remaining = result.get("remaining_attempts", 0)

        if reason == "expired":
            raise HTTPException(status_code=400, detail="El código ha expirado. Solicita uno nuevo.")
        if reason in ("max_attempts_reached", "lockout"):
            raise HTTPException(status_code=400, detail="Máximo de intentos. Solicita un nuevo código.")
        if reason == "no_active_otp":
            raise HTTPException(status_code=400, detail="No hay un código activo. Solicita uno nuevo.")

        raise HTTPException(
            status_code=400,
            detail=f"Código incorrecto. Intentos restantes: {remaining}.",
            headers={"X-Remaining-Attempts": str(remaining)},
        )

    # Resolve customer identity from DB
    customer_id, customer_name = await _resolve_customer(
        payload.phone, payload.email, tenant_id, svc.session
    )

    tokens = svc.create_tokens(
        customer_id=customer_id,
        phone=payload.phone,
        email=payload.email,
        tenant_id=tenant_id,
    )

    return VerifyOTPResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type="bearer",
        expires_in=tokens["expires_in"],
        customer_id=customer_id,
        customer_name=customer_name,
        verified=True,
    )


@router.post(
    "/verify-phone",
    response_model=SendOTPResponse,
    summary="Alias for /send-otp (backward compat)",
    include_in_schema=False,
)
async def verify_phone(payload: SendOTPRequest, request: Request, svc: OTPService = Depends(_svc)):
    """Backward-compatible alias — delegates to send_otp."""
    return await send_otp(payload, request, svc)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange refresh token for new access token",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    svc: OTPService = Depends(_svc),
) -> TokenResponse:
    """Issue a new access token using a valid refresh token."""
    decoded = svc.decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "customer_refresh":
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado.")

    tokens = svc.create_tokens(
        customer_id=decoded["sub"],
        phone=decoded.get("phone"),
        email=decoded.get("email"),
        tenant_id=decoded.get("tenant_id"),
    )
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=payload.refresh_token,  # keep same refresh token
        token_type="bearer",
        expires_in=tokens["expires_in"],
    )


@router.get(
    "/me",
    response_model=CustomerMeResponse,
    summary="Return authenticated customer info",
)
async def me(request: Request, svc: OTPService = Depends(_svc)) -> CustomerMeResponse:
    """Return info from the current access token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido.")

    payload = svc.decode_token(auth[7:])
    if not payload or payload.get("type") != "customer_access":
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")

    return CustomerMeResponse(
        customer_id=payload["sub"],
        phone=payload.get("phone"),
        email=payload.get("email"),
        tenant_id=payload.get("tenant_id"),
        verified=True,
    )


@router.post("/logout", summary="Revoke customer session")
async def logout():
    """
    Client should discard both tokens.
    Full server-side revocation requires Redis (not yet enabled).
    """
    return {"message": "Sesión cerrada. Descarta los tokens del cliente."}


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _resolve_customer(
    phone: Optional[str],
    email: Optional[str],
    tenant_id: Optional[str],
    session,
) -> tuple[str, str]:
    """Return (customer_id, full_name) from DB, or use phone/email as fallback ID."""
    try:
        from sqlalchemy import select, and_
        from models.customer import Customer

        filters = []
        if phone:
            filters.append(Customer.phone == phone)
        elif email:
            filters.append(Customer.email == email.lower())
        if tenant_id:
            filters.append(Customer.tenant_id == tenant_id)

        result = await session.execute(
            select(Customer).where(and_(*filters)).limit(1)
        )
        customer = result.scalar_one_or_none()
        if customer:
            return str(customer.id), customer.full_name
    except Exception as exc:
        logger.warning(f"Customer lookup failed: {exc}")

    return phone or email or "unknown", ""


def _mask(value: str) -> str:
    """Mask phone or email for display: +57***1234 / g***@gmail.com"""
    if "@" in value:
        parts = value.split("@")
        return f"{parts[0][0]}***@{parts[1]}"
    if len(value) >= 4:
        return f"***{value[-4:]}"
    return "****"
