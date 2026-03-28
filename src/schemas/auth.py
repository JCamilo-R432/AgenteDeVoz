from __future__ import annotations
"""Pydantic v2 schemas for OTP authentication endpoints."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SendOTPRequest(BaseModel):
    phone:     Optional[str] = Field(None, description="Phone with country code: +573001234567")
    email:     Optional[str] = Field(None, description="Email address")
    channel:   Literal["sms", "email", "whatsapp"] = "sms"
    tenant_id: Optional[str] = None

    @field_validator("phone", "email", mode="before")
    @classmethod
    def strip_spaces(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    model_config = ConfigDict(from_attributes=True)


class VerifyOTPRequest(BaseModel):
    phone:     Optional[str] = None
    email:     Optional[str] = None
    code:      str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    tenant_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RefreshTokenRequest(BaseModel):
    refresh_token: str

    model_config = ConfigDict(from_attributes=True)


class SendOTPResponse(BaseModel):
    message:    str
    expires_in: int
    channel:    str

    model_config = ConfigDict(from_attributes=True)


class VerifyOTPResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int
    customer_id:   str
    customer_name: str = ""
    verified:      bool = True

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: Optional[str] = None
    token_type:    str = "bearer"
    expires_in:    int

    model_config = ConfigDict(from_attributes=True)


class CustomerMeResponse(BaseModel):
    customer_id: str
    phone:       Optional[str] = None
    email:       Optional[str] = None
    tenant_id:   Optional[str] = None
    verified:    bool = True

    model_config = ConfigDict(from_attributes=True)
