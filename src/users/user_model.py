from __future__ import annotations
"""
user_model.py — Pydantic schemas for user API (request / response).
"""


from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserRegister(BaseModel):
    email       : EmailStr
    password    : str = Field(..., min_length=8)
    full_name   : str = Field(..., min_length=2, max_length=100)
    company_name: Optional[str] = None
    phone       : Optional[str] = None

    @validator("password")
    def _strong_password(cls, v):
        import re
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    email   : EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name   : Optional[str] = Field(None, min_length=2, max_length=100)
    phone       : Optional[str] = None
    company_name: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password    : str = Field(..., min_length=8)


class PasswordReset(BaseModel):
    token       : str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id               : str
    email            : str
    full_name        : Optional[str]
    company_name     : Optional[str]
    subscription_plan: str
    is_verified      : bool
    created_at       : datetime
    monthly_call_count: int
    monthly_call_limit: int
    usage_percent    : float

    class Config:
        from_attributes = True


class UserPublicProfile(BaseModel):
    id        : str
    full_name : Optional[str]
    company_name: Optional[str]
    created_at: datetime
