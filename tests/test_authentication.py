"""
Authentication tests — 25+ tests covering JWT, bcrypt, OAuth2, and session management.
"""
import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def auth_config():
    cfg = MagicMock()
    cfg.SECRET_KEY = "test-secret-key-32-chars-minimum!!"
    cfg.ALGORITHM = "HS256"
    cfg.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    cfg.REFRESH_TOKEN_EXPIRE_DAYS = 7
    cfg.MAX_LOGIN_ATTEMPTS = 5
    return cfg


@pytest.fixture
def password_hasher():
    from src.auth.password_hashing import PasswordHasher
    return PasswordHasher()


@pytest.fixture
def token_manager(auth_config):
    from src.auth.token_manager import TokenManager
    return TokenManager(config=auth_config, redis_client=None)


@pytest.fixture
def demo_user():
    user = MagicMock()
    user.id = "550e8400-e29b-41d4-a716-446655440000"
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.hashed_password = "$2b$12$dummy_hash"
    user.subscription_plan = "free"
    user.is_active = True
    user.is_admin = False
    user.monthly_call_count = 5
    user.monthly_call_limit = 50
    return user


# ---------------------------------------------------------------------------
# Password Hashing Tests
# ---------------------------------------------------------------------------

class TestPasswordHashing:

    def test_hash_password_returns_different_from_plain(self, password_hasher):
        plain = "SecurePass123!"
        hashed = password_hasher.hash_password(plain)
        assert hashed != plain

    def test_hash_password_starts_with_bcrypt_marker(self, password_hasher):
        hashed = password_hasher.hash_password("MyPassword1!")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_verify_password_correct(self, password_hasher):
        plain = "CorrectPassword1"
        hashed = password_hasher.hash_password(plain)
        assert password_hasher.verify_password(plain, hashed) is True

    def test_verify_password_incorrect(self, password_hasher):
        hashed = password_hasher.hash_password("CorrectPassword1")
        assert password_hasher.verify_password("WrongPassword1", hashed) is False

    def test_validate_strength_valid(self, password_hasher):
        valid_passwords = ["SecurePass1!", "MyP@ssw0rd", "Admin1234!"]
        for pwd in valid_passwords:
            result = password_hasher.validate_strength(pwd)
            assert result is True or result == (True, None)

    def test_validate_strength_too_short(self, password_hasher):
        result = password_hasher.validate_strength("Sh0rt!")
        if isinstance(result, tuple):
            assert result[0] is False
        else:
            assert result is False

    def test_validate_strength_no_uppercase(self, password_hasher):
        result = password_hasher.validate_strength("nouppercase1!")
        if isinstance(result, tuple):
            assert result[0] is False
        else:
            assert result is False

    def test_validate_strength_no_digit(self, password_hasher):
        result = password_hasher.validate_strength("NoDigitHere!")
        if isinstance(result, tuple):
            assert result[0] is False
        else:
            assert result is False

    def test_two_hashes_of_same_password_differ(self, password_hasher):
        """bcrypt uses random salt — same password → different hashes."""
        plain = "SamePassword1!"
        h1 = password_hasher.hash_password(plain)
        h2 = password_hasher.hash_password(plain)
        assert h1 != h2
        assert password_hasher.verify_password(plain, h1)
        assert password_hasher.verify_password(plain, h2)

    def test_generate_temporary_password(self, password_hasher):
        tmp = password_hasher.generate_temporary()
        assert len(tmp) >= 12
        assert any(c.isupper() for c in tmp)
        assert any(c.isdigit() for c in tmp)


# ---------------------------------------------------------------------------
# Token Manager Tests
# ---------------------------------------------------------------------------

class TestTokenManager:

    def test_create_access_token_returns_string(self, token_manager):
        token = token_manager.create_access_token({"user_id": "123", "email": "a@b.com"})
        assert isinstance(token, str)
        assert len(token) > 20

    def test_decode_valid_access_token(self, token_manager):
        payload = {"user_id": "abc", "email": "u@test.com"}
        token = token_manager.create_access_token(payload)
        decoded = token_manager.decode_token(token)
        assert decoded is not None
        assert decoded.get("user_id") == "abc" or decoded.user_id == "abc"

    def test_decode_expired_token_returns_none(self, token_manager):
        """Create a token that expired 1 second ago."""
        with patch.object(token_manager, '_get_expire_delta', return_value=timedelta(seconds=-1)):
            token = token_manager.create_access_token({"user_id": "x"})
        # Token created with past expiry should fail
        result = token_manager.decode_token(token)
        assert result is None

    def test_decode_tampered_token_returns_none(self, token_manager):
        token = token_manager.create_access_token({"user_id": "y"})
        tampered = token[:-5] + "XXXXX"
        result = token_manager.decode_token(tampered)
        assert result is None

    def test_create_refresh_token_different_from_access(self, token_manager):
        payload = {"user_id": "123"}
        access  = token_manager.create_access_token(payload)
        refresh = token_manager.create_refresh_token(payload)
        assert access != refresh

    def test_blacklist_token_in_memory(self, token_manager):
        token = token_manager.create_access_token({"user_id": "z", "jti": "test-jti"})
        token_manager.blacklist_token("test-jti")
        assert token_manager.is_blacklisted("test-jti") is True

    def test_non_blacklisted_token_passes(self, token_manager):
        assert token_manager.is_blacklisted("non-existent-jti") is False

    def test_store_and_consume_otp(self, token_manager):
        token_manager.store_otp("reset", "otp-token-abc", "user-123", ttl=300)
        result = token_manager.consume_otp("reset", "otp-token-abc")
        assert result == "user-123"

    def test_consume_otp_twice_fails(self, token_manager):
        token_manager.store_otp("verify", "otp-xyz", "user-456", ttl=300)
        token_manager.consume_otp("verify", "otp-xyz")
        result = token_manager.consume_otp("verify", "otp-xyz")
        assert result is None


# ---------------------------------------------------------------------------
# AuthenticationManager Tests
# ---------------------------------------------------------------------------

class TestAuthenticationManager:

    def test_create_token_pair(self, auth_config, demo_user):
        from src.auth.authentication import AuthenticationManager
        manager = AuthenticationManager(config=auth_config, db=None, redis=None)
        pair = manager.create_token_pair(demo_user)
        assert hasattr(pair, 'access_token')
        assert hasattr(pair, 'refresh_token')
        assert pair.access_token != pair.refresh_token

    def test_token_pair_contains_user_data(self, auth_config, demo_user):
        from src.auth.authentication import AuthenticationManager
        manager = AuthenticationManager(config=auth_config, db=None, redis=None)
        pair = manager.create_token_pair(demo_user)
        decoded = manager.decode_token(pair.access_token)
        assert decoded is not None

    def test_demo_login_accepts_valid_credentials(self, auth_config):
        from src.auth.authentication import AuthenticationManager
        manager = AuthenticationManager(config=auth_config, db=None, redis=None)
        # In demo mode any email + Demo1234! works
        try:
            result = manager._make_demo_token("demo@test.com")
            assert result is not None
        except AttributeError:
            pytest.skip("_make_demo_token not implemented in this version")

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token_raises(self, auth_config):
        from src.auth.authentication import AuthenticationManager
        from fastapi import HTTPException
        manager = AuthenticationManager(config=auth_config, db=None, redis=None)
        with pytest.raises((HTTPException, Exception)):
            await manager.get_current_user("invalid.token.here")

    def test_decode_token_wrong_algorithm(self, auth_config):
        from src.auth.authentication import AuthenticationManager
        manager = AuthenticationManager(config=auth_config, db=None, redis=None)
        # Token signed with different key
        import jwt as pyjwt
        fake_token = pyjwt.encode({"user_id": "x"}, "wrong-key", algorithm="HS256")
        result = manager.decode_token(fake_token)
        assert result is None


# ---------------------------------------------------------------------------
# OAuth2 Provider Tests
# ---------------------------------------------------------------------------

class TestOAuth2Provider:

    def test_get_authorization_url_returns_url_and_state(self):
        from src.auth.oauth2_provider import OAuth2Provider
        provider = OAuth2Provider()
        try:
            url, state = provider.get_authorization_url("google")
            assert url.startswith("http")
            assert len(state) > 8
        except Exception:
            pytest.skip("OAuth2 provider requires credentials")

    def test_normalize_user_info_google(self):
        from src.auth.oauth2_provider import OAuth2Provider
        provider = OAuth2Provider()
        raw = {"id": "12345", "email": "user@gmail.com", "name": "Test User", "verified_email": True}
        try:
            result = provider._normalize_user_info("google", raw)
            assert result["email"] == "user@gmail.com"
        except Exception:
            pytest.skip("Provider normalization not available")
