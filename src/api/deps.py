from __future__ import annotations
"""
FastAPI shared dependencies: authentication, DB session, service factories.
"""


import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


# ── Auth ───────────────────────────────────────────────────────────────────────

async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    Validate JWT bearer token and return the decoded payload.
    Raises HTTP 401 if the token is missing or invalid.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        from jose import JWTError, jwt
        from config.settings import settings

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        subject: Optional[str] = payload.get("sub")
        if subject is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing 'sub' claim",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload

    except Exception as exc:
        # Catches JWTError and any other decode issues
        logger.warning(f"JWT validation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Service factories ──────────────────────────────────────────────────────────

def get_tenant_id(request: Request) -> Optional[str]:
    """Extract tenant_id from request state (set by TenantMiddleware)."""
    return getattr(request.state, "tenant_id", None)


async def get_order_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Dependency providing an OrderService scoped to the current tenant."""
    from services.order_service import OrderService

    tenant_id = getattr(request.state, "tenant_id", None)
    return OrderService(db, tenant_id=tenant_id)


async def get_customer_repository(
    db: AsyncSession = Depends(get_db),
):
    """Dependency that provides direct access to the AsyncSession for customer ops."""
    return db
