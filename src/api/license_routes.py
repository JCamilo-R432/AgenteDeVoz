from __future__ import annotations
"""license_routes.py — License activation, validation, and management."""


import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.auth.authentication import AuthenticationManager, TokenData, oauth2_scheme

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/licenses", tags=["licenses"])
_auth  = AuthenticationManager()


def _current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    data = _auth.decode_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid token")
    return data

def _require_admin(user: TokenData = Depends(_current_user)) -> TokenData:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user


class ActivateRequest(BaseModel):
    key: str

class ValidateRequest(BaseModel):
    key: str


@router.get("/")
async def list_licenses(user: TokenData = Depends(_current_user)):
    from src.licenses.license_manager import LicenseManager
    mgr = LicenseManager()
    licenses = await mgr.list_for_user(user.user_id)
    return {"licenses": licenses}


@router.post("/activate")
async def activate_license(body: ActivateRequest, user: TokenData = Depends(_current_user)):
    from src.licenses.license_validator import LicenseValidator
    validator = LicenseValidator()
    result    = await validator.activate(body.key, user.user_id)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.reason)
    return {
        "activated"      : True,
        "key"            : body.key,
        "plan_id"        : result.plan_id,
        "seats_remaining": result.seats_remaining,
    }


@router.post("/validate")
async def validate_license(body: ValidateRequest, _user: TokenData = Depends(_current_user)):
    from src.licenses.license_validator import LicenseValidator
    validator = LicenseValidator()
    result    = await validator.validate(body.key)
    return {
        "key"            : body.key,
        "is_valid"       : result.valid,
        "plan_id"        : result.plan_id,
        "reason"         : result.reason,
        "seats_remaining": result.seats_remaining,
    }


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_license(key: str, admin: TokenData = Depends(_require_admin)):
    from src.licenses.license_manager import LicenseManager
    mgr     = LicenseManager()
    revoked = await mgr.revoke(key, reason=f"Revoked by admin {admin.user_id}")
    if not revoked:
        raise HTTPException(status_code=404, detail="License not found")
