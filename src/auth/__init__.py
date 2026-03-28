"""
src/auth — Authentication & authorization layer.
Exports the public API for the rest of the application.
"""

try:
    from src.auth.authentication import (
        AuthenticationManager,
        Token,
        TokenData,
        UserInDB,
        oauth2_scheme,
    )
    from src.auth.password_hashing import PasswordHasher
    from src.auth.token_manager import TokenManager
    from src.auth.session_manager import SessionManager

    __all__ = [
        "AuthenticationManager",
        "Token",
        "TokenData",
        "UserInDB",
        "oauth2_scheme",
        "PasswordHasher",
        "TokenManager",
        "SessionManager",
    ]
except ImportError:
    __all__ = []
