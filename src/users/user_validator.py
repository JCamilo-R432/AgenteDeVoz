from __future__ import annotations
"""
user_validator.py — Input validation helpers for user operations.
"""


import re
from typing import Optional


class UserValidator:

    EMAIL_RE   = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    PHONE_RE   = re.compile(r"^\+?[1-9]\d{6,14}$")

    @classmethod
    def validate_email(cls, email: str) -> tuple[bool, str]:
        email = email.strip()
        if not email:
            return False, "Email is required"
        if not cls.EMAIL_RE.match(email):
            return False, "Invalid email format"
        if len(email) > 255:
            return False, "Email is too long"
        return True, ""

    @classmethod
    def validate_phone(cls, phone: Optional[str]) -> tuple[bool, str]:
        if not phone:
            return True, ""   # optional
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not cls.PHONE_RE.match(phone):
            return False, "Invalid phone number (include country code, e.g. +573001234567)"
        return True, ""

    @classmethod
    def validate_name(cls, name: str) -> tuple[bool, str]:
        name = name.strip()
        if not name or len(name) < 2:
            return False, "Name must be at least 2 characters"
        if len(name) > 100:
            return False, "Name is too long (max 100 characters)"
        if re.search(r"[<>\"'%;()&+]", name):
            return False, "Name contains invalid characters"
        return True, ""

    @classmethod
    def sanitize_email(cls, email: str) -> str:
        return email.strip().lower()

    @classmethod
    def sanitize_name(cls, name: str) -> str:
        return name.strip()
