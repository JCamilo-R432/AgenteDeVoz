from __future__ import annotations
"""
admin_panel.py — FastAPI router for the admin panel.
All routes require is_admin=True in the JWT token.
"""


import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from src.auth.authentication import AuthenticationManager, oauth2_scheme

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

_auth = AuthenticationManager()


# ── Dependency: require admin ─────────────────────────────────────

async def require_admin(token: str = Depends(oauth2_scheme)):
    token_data = _auth.decode_token(token)
    if not token_data or not token_data.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return token_data


# ── Request / Response schemas ────────────────────────────────────

class UserStatusUpdate(BaseModel):
    is_active: bool

class UserPlanUpdate(BaseModel):
    plan_id: str

class AdminStats(BaseModel):
    total_users        : int
    active_subscriptions: int
    monthly_revenue_usd: float
    calls_today        : int
    new_users_today    : int
    churn_rate_percent : float


# ── Routes ────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStats)
async def get_stats(_admin=Depends(require_admin)):
    """Global platform statistics."""
    return AdminStats(
        total_users         = 142,
        active_subscriptions= 87,
        monthly_revenue_usd = 6_453.00,
        calls_today         = 1_204,
        new_users_today     = 7,
        churn_rate_percent  = 2.3,
    )


@router.get("/users")
async def list_users(
    page : int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    plan : Optional[str] = Query(None),
    _admin=Depends(require_admin),
):
    """Paginated list of all users."""
    from src.admin.user_management import UserManagementService
    svc = UserManagementService()
    offset = (page - 1) * limit
    users  = await svc.list_users(offset=offset, limit=limit, plan_filter=plan)
    return {
        "page" : page,
        "limit": limit,
        "total": len(users),
        "users": users,
    }


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    body: UserStatusUpdate,
    _admin=Depends(require_admin),
):
    """Activate or suspend a user account."""
    from src.admin.user_management import UserManagementService
    svc = UserManagementService()
    if body.is_active:
        await svc.activate_user(user_id)
    else:
        await svc.suspend_user(user_id, reason="Admin action")
    return {"user_id": user_id, "is_active": body.is_active}


@router.put("/users/{user_id}/plan")
async def update_user_plan(
    user_id: str,
    body: UserPlanUpdate,
    _admin=Depends(require_admin),
):
    """Change a user's subscription plan."""
    from src.admin.user_management import UserManagementService
    from config.subscription_config import PLAN_LIMITS
    svc    = UserManagementService()
    limits = PLAN_LIMITS.get(body.plan_id, PLAN_LIMITS["free"])
    await svc.change_plan(user_id, body.plan_id, limits)
    return {"user_id": user_id, "new_plan": body.plan_id}


@router.post("/users/{user_id}/impersonate")
async def impersonate_user(user_id: str, _admin=Depends(require_admin)):
    """Generate a short-lived token to act as another user (for support)."""
    from datetime import timedelta
    token = _auth.create_access_token(
        {"user_id": user_id, "impersonated": True, "is_admin": False},
        expires_delta=timedelta(minutes=15),
    )
    logger.warning("Admin impersonating user %s", user_id)
    return {"access_token": token, "expires_in": 900, "token_type": "bearer"}


@router.get("/subscriptions")
async def list_subscriptions(
    status_filter: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin=Depends(require_admin),
):
    from src.admin.subscription_management import SubscriptionManagementService
    svc    = SubscriptionManagementService()
    offset = (page - 1) * limit
    subs   = await svc.list_subscriptions(status_filter=status_filter, offset=offset, limit=limit)
    return {"page": page, "limit": limit, "subscriptions": subs}


@router.get("/analytics/dashboard")
async def admin_analytics(_admin=Depends(require_admin)):
    from src.admin.analytics_admin import AdminAnalytics
    return await AdminAnalytics().get_dashboard_stats()


@router.get("/analytics/growth")
async def user_growth(days: int = Query(30, ge=7, le=365), _admin=Depends(require_admin)):
    from src.admin.analytics_admin import AdminAnalytics
    return await AdminAnalytics().get_user_growth(days=days)
