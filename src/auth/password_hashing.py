from __future__ import annotations
"""
password_hashing.py — Password hashing utilities (bcrypt).
Provides both standalone functions and a class wrapper.
"""


import re
import secrets
import string
from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Password strength requirements
MIN_LENGTH    = 8
REQUIRE_UPPER = True
REQUIRE_DIGIT = True
REQUIRE_SPECIAL = False   # opt-in — tighten for enterprise


class PasswordHasher:
    """Thin wrapper around passlib for testability."""

    @staticmethod
    def hash(password: str) -> str:
        return _ctx.hash(password)

    @staticmethod
    def verify(plain: str, hashed: str) -> bool:
        return _ctx.verify(plain, hashed)

    @staticmethod
    def needs_update(hashed: str) -> bool:
        """Returns True if the hash scheme is outdated and should be re-hashed."""
        return _ctx.needs_update(hashed)

    @staticmethod
    def validate_strength(password: str) -> tuple[bool, str]:
        """
        Validates password against strength rules.
        Returns (is_valid, error_message).
        """
        if len(password) < MIN_LENGTH:
            return False, f"La contraseña debe tener al menos {MIN_LENGTH} caracteres."

        if REQUIRE_UPPER and not re.search(r"[A-Z]", password):
            return False, "La contraseña debe contener al menos una letra mayúscula."

        if REQUIRE_DIGIT and not re.search(r"\d", password):
            return False, "La contraseña debe contener al menos un número."

        if REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "La contraseña debe contener al menos un carácter especial."

        return True, ""

    @staticmethod
    def generate_temporary(length: int = 16) -> str:
        """Generate a secure temporary password."""
        alphabet = string.ascii_letters + string.digits + "!@#$"
        while True:
            pwd = "".join(secrets.choice(alphabet) for _ in range(length))
            # Ensure it meets all requirements
            if (
                re.search(r"[A-Z]", pwd)
                and re.search(r"\d", pwd)
            ):
                return pwd
