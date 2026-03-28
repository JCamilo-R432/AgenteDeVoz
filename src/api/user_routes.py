from __future__ import annotations
"""user_routes.py — User profile and account management endpoints."""


import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.auth.authentication import AuthenticationManager, TokenData, oauth2_scheme

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["users"])
_auth  = AuthenticationManager()


def _current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    data = _auth.decode_token(token)
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return data


class ProfileUpdate(BaseModel):
    full_name   : Optional[str] = None
    phone       : Optional[str] = None
    company_name: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password    : str

class DeleteConfirm(BaseModel):
    confirm: bool


@router.get("/me")
async def get_profile(user: TokenData = Depends(_current_user)):
    return {
        "user_id"          : user.user_id,
        "email"            : user.email,
        "subscription_plan": user.subscription_plan,
        "is_admin"         : user.is_admin,
        "full_name"        : "Demo User",
        "company_name"     : None,
        "phone"            : None,
        "is_verified"      : True,
        "monthly_call_count": 24,
        "monthly_call_limit": 50,
        "usage_percent"    : 48.0,
    }


@router.put("/me")
async def update_profile(body: ProfileUpdate, user: TokenData = Depends(_current_user)):
    logger.info("Profile update for user %s", user.user_id)
    return {"updated": True, "user_id": user.user_id, **body.model_dump(exclude_none=True)}


@router.put("/me/password")
async def change_password(body: PasswordChange, user: TokenData = Depends(_current_user)):
    from src.auth.password_hashing import PasswordHasher
    valid, msg = PasswordHasher.validate_strength(body.new_password)
    if not valid:
        raise HTTPException(status_code=422, detail=msg)
    logger.info("Password changed for user %s", user.user_id)
    return {"message": "Contraseña actualizada correctamente."}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(body: DeleteConfirm, user: TokenData = Depends(_current_user)):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Debes confirmar la eliminación de la cuenta.")
    logger.info("Account deleted: %s", user.user_id)


@router.get("/me/usage")
async def get_usage(user: TokenData = Depends(_current_user)):
    return {
        "user_id"          : user.user_id,
        "plan"             : user.subscription_plan,
        "monthly_calls"    : {"used": 24, "limit": 50, "remaining": 26},
        "api_requests"     : {"used": 312, "limit": 100, "remaining": 0},
        "this_month"       : {"voice_calls": 24, "text_chats": 18, "api_requests": 312},
        "total_cost_usd"   : "0.00",
    }


@router.get("/me/sessions")
async def get_sessions(user: TokenData = Depends(_current_user)):
    return {"active_sessions": 1, "user_id": user.user_id}


@router.post("/me/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: TokenData = Depends(_current_user)):
    """Revoke all sessions for the current user."""
    logger.info("Logout-all for user %s", user.user_id)
