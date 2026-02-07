"""
Comprehensive Unit Tests for User Manager Module
Tests authentication, JWT, password hashing, permissions, and RBAC
"""
import pytest
import jwt
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.user_manager import (
    UserRole, UserStatus, Permission, ROLE_PERMISSIONS,
    User, Session, APIKey, Invitation,
    PasswordHasher, TokenGenerator, JWTManager
)


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def jwt_secret():
    """JWT secret key for testing"""
    return "test-jwt-secret-minimum-32-characters-long-for-testing-purposes"


@pytest.fixture
def jwt_manager(jwt_secret):
    """JWT manager instance"""
    return JWTManager(secret_key=jwt_secret)


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    return User(
        user_id="user_123",
        email="test@example.com",
        name="Test User",
        company="Test Corp",
        role=UserRole.ANALYST,
        status=UserStatus.ACTIVE,
        created_at=datetime.utcnow().isoformat(),
        subscription_tier="pro",
        api_calls_limit=10000
    )


@pytest.fixture
def sample_session():
    """Sample session for testing"""
    return Session(
        session_id="session_123",
        user_id="user_123",
        token="test_token_abc123",
        created_at=datetime.utcnow().isoformat(),
        expires_at=(datetime.utcnow() + timedelta(hours=24)).isoformat(),
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
        is_active=True
    )


# ═══════════════════════════════════════════════════════════════
# PASSWORD HASHER TESTS
# ═══════════════════════════════════════════════════════════════

class TestPasswordHasher:
    """Test password hashing and verification"""

    def test_hash_password_returns_string(self):
        """Hash should return a string"""
        hashed = PasswordHasher.hash_password("MyPassword123!")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_different_each_time(self):
        """Same password should produce different hashes (salt)"""
        password = "MyPassword123!"
        hash1 = PasswordHasher.hash_password(password)
        hash2 = PasswordHasher.hash_password(password)
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Correct password should verify"""
        password = "MyPassword123!"
        hashed = PasswordHasher.hash_password(password)
        assert PasswordHasher.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Incorrect password should not verify"""
        password = "MyPassword123!"
        wrong_password = "WrongPassword456!"
        hashed = PasswordHasher.hash_password(password)
        assert PasswordHasher.verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_string(self):
        """Empty password should not verify"""
        password = "MyPassword123!"
        hashed = PasswordHasher.hash_password(password)
        assert PasswordHasher.verify_password("", hashed) is False

    def test_is_strong_password_valid(self):
        """Valid strong password should pass"""
        is_valid, errors = PasswordHasher.is_strong_password("MyPassword123!")
        assert is_valid is True
        assert len(errors) == 0

    def test_is_strong_password_too_short(self):
        """Password too short should fail"""
        is_valid, errors = PasswordHasher.is_strong_password("Pass1!")
        assert is_valid is False
        assert "at least 8 characters" in errors[0]

    def test_is_strong_password_no_uppercase(self):
        """Password without uppercase should fail"""
        is_valid, errors = PasswordHasher.is_strong_password("mypassword123!")
        assert is_valid is False
        assert any("uppercase" in e for e in errors)

    def test_is_strong_password_no_lowercase(self):
        """Password without lowercase should fail"""
        is_valid, errors = PasswordHasher.is_strong_password("MYPASSWORD123!")
        assert is_valid is False
        assert any("lowercase" in e for e in errors)

    def test_is_strong_password_no_digit(self):
        """Password without digit should fail"""
        is_valid, errors = PasswordHasher.is_strong_password("MyPassword!")
        assert is_valid is False
        assert any("digit" in e for e in errors)

    def test_is_strong_password_no_special(self):
        """Password without special character should fail"""
        is_valid, errors = PasswordHasher.is_strong_password("MyPassword123")
        assert is_valid is False
        assert any("special character" in e for e in errors)

    def test_is_strong_password_multiple_errors(self):
        """Weak password should return multiple errors"""
        is_valid, errors = PasswordHasher.is_strong_password("weak")
        assert is_valid is False
        assert len(errors) >= 3  # Multiple requirements failed


# ═══════════════════════════════════════════════════════════════
# TOKEN GENERATOR TESTS
# ═══════════════════════════════════════════════════════════════

class TestTokenGenerator:
    """Test token generation"""

    def test_generate_token_returns_string(self):
        """Token should be a string"""
        token = TokenGenerator.generate_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_custom_length(self):
        """Token should respect custom length"""
        token = TokenGenerator.generate_token(length=64)
        assert len(token) > 60  # URL-safe encoding affects length

    def test_generate_token_unique(self):
        """Generated tokens should be unique"""
        token1 = TokenGenerator.generate_token()
        token2 = TokenGenerator.generate_token()
        assert token1 != token2

    def test_generate_api_key_has_prefix(self):
        """API key should have 'rs_' prefix"""
        api_key = TokenGenerator.generate_api_key()
        assert api_key.startswith("rs_")

    def test_generate_api_key_unique(self):
        """Generated API keys should be unique"""
        key1 = TokenGenerator.generate_api_key()
        key2 = TokenGenerator.generate_api_key()
        assert key1 != key2

    def test_hash_token_deterministic(self):
        """Same token should produce same hash"""
        token = "test_token_123"
        hash1 = TokenGenerator.hash_token(token)
        hash2 = TokenGenerator.hash_token(token)
        assert hash1 == hash2

    def test_hash_token_different_for_different_tokens(self):
        """Different tokens should produce different hashes"""
        hash1 = TokenGenerator.hash_token("token1")
        hash2 = TokenGenerator.hash_token("token2")
        assert hash1 != hash2

    def test_hash_token_returns_hex(self):
        """Token hash should be hexadecimal string"""
        token_hash = TokenGenerator.hash_token("test")
        assert all(c in "0123456789abcdef" for c in token_hash)


# ═══════════════════════════════════════════════════════════════
# JWT MANAGER TESTS
# ═══════════════════════════════════════════════════════════════

class TestJWTManager:
    """Test JWT token creation and verification"""

    def test_create_token_returns_string(self, jwt_manager):
        """JWT token should be a string"""
        token = jwt_manager.create_token(user_id="user_123", role="analyst")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_token_contains_claims(self, jwt_manager, jwt_secret):
        """JWT token should contain correct claims"""
        user_id = "user_123"
        role = "analyst"
        token = jwt_manager.create_token(user_id=user_id, role=role)

        # Decode without verification for testing
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        assert payload["user_id"] == user_id
        assert payload["role"] == role
        assert "iat" in payload
        assert "exp" in payload

    def test_create_token_custom_expiry(self, jwt_manager):
        """JWT token should respect custom expiry"""
        token = jwt_manager.create_token(
            user_id="user_123",
            role="analyst",
            expires_hours=48
        )
        payload = jwt_manager.verify_token(token)
        assert payload is not None

        # Check expiry is approximately 48 hours from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        diff = (exp_time - now).total_seconds() / 3600
        assert 47 < diff < 49  # Allow small margin

    def test_verify_token_valid(self, jwt_manager):
        """Valid token should verify successfully"""
        token = jwt_manager.create_token(user_id="user_123", role="analyst")
        payload = jwt_manager.verify_token(token)

        assert payload is not None
        assert payload["user_id"] == "user_123"
        assert payload["role"] == "analyst"

    def test_verify_token_invalid(self, jwt_manager):
        """Invalid token should return None"""
        invalid_token = "invalid.jwt.token"
        payload = jwt_manager.verify_token(invalid_token)
        assert payload is None

    def test_verify_token_wrong_secret(self, jwt_manager):
        """Token signed with different secret should fail"""
        token = jwt_manager.create_token(user_id="user_123", role="analyst")

        # Create manager with different secret
        wrong_manager = JWTManager(secret_key="wrong_secret_key_at_least_32_chars_long")
        payload = wrong_manager.verify_token(token)
        assert payload is None

    def test_verify_token_expired(self, jwt_manager):
        """Expired token should return None"""
        # Create token that expires immediately
        token = jwt_manager.create_token(
            user_id="user_123",
            role="analyst",
            expires_hours=0
        )

        # Wait a moment to ensure expiration
        time.sleep(1)

        payload = jwt_manager.verify_token(token)
        assert payload is None

    def test_refresh_token_valid(self, jwt_manager):
        """Valid token should be refreshable"""
        original_token = jwt_manager.create_token(user_id="user_123", role="analyst")

        # Add small delay to ensure different timestamp
        import time
        time.sleep(1.1)

        new_token = jwt_manager.refresh_token(original_token)

        assert new_token is not None
        # Tokens should be different after delay
        assert new_token != original_token

        # New token should be valid
        payload = jwt_manager.verify_token(new_token)
        assert payload is not None
        assert payload["user_id"] == "user_123"

    def test_refresh_token_invalid(self, jwt_manager):
        """Invalid token should not refresh"""
        new_token = jwt_manager.refresh_token("invalid.token")
        assert new_token is None

    def test_refresh_token_expired(self, jwt_manager):
        """Expired token should not refresh"""
        expired_token = jwt_manager.create_token(
            user_id="user_123",
            role="analyst",
            expires_hours=0
        )
        time.sleep(1)

        new_token = jwt_manager.refresh_token(expired_token)
        assert new_token is None


# ═══════════════════════════════════════════════════════════════
# USER MODEL TESTS
# ═══════════════════════════════════════════════════════════════

class TestUser:
    """Test User dataclass"""

    def test_user_creation(self, sample_user):
        """User should be created with all fields"""
        assert sample_user.user_id == "user_123"
        assert sample_user.email == "test@example.com"
        assert sample_user.role == UserRole.ANALYST
        assert sample_user.status == UserStatus.ACTIVE

    def test_user_to_dict(self, sample_user):
        """User should convert to dict"""
        data = sample_user.to_dict()
        assert isinstance(data, dict)
        assert data["user_id"] == "user_123"
        assert data["email"] == "test@example.com"
        assert data["role"] == "analyst"  # Enum converted to string
        assert data["status"] == "active"

    def test_user_to_public_dict(self, sample_user):
        """Public dict should not include sensitive data"""
        data = sample_user.to_public_dict()

        # Should include
        assert "user_id" in data
        assert "email" in data
        assert "role" in data

        # Should NOT include sensitive fields
        assert "api_calls_used" not in data
        assert "stripe_customer_id" not in data
        assert "metadata" not in data

    def test_user_default_values(self):
        """User should have sensible defaults"""
        user = User(
            user_id="user_456",
            email="user@example.com",
            name="User",
            company="Company",
            role=UserRole.VIEWER,
            status=UserStatus.ACTIVE,
            created_at=datetime.utcnow().isoformat()
        )

        assert user.api_calls_used == 0
        assert user.api_calls_limit == 100
        assert user.subscription_tier == "trial"
        assert user.stripe_customer_id == ""


# ═══════════════════════════════════════════════════════════════
# SESSION MODEL TESTS
# ═══════════════════════════════════════════════════════════════

class TestSession:
    """Test Session dataclass"""

    def test_session_creation(self, sample_session):
        """Session should be created with all fields"""
        assert sample_session.session_id == "session_123"
        assert sample_session.user_id == "user_123"
        assert sample_session.is_active is True

    def test_session_to_dict(self, sample_session):
        """Session should convert to dict"""
        data = sample_session.to_dict()
        assert isinstance(data, dict)
        assert data["session_id"] == "session_123"
        assert data["is_active"] is True

    def test_session_is_expired_false(self, sample_session):
        """Valid session should not be expired"""
        assert sample_session.is_expired is False

    def test_session_is_expired_true(self):
        """Expired session should be detected"""
        session = Session(
            session_id="session_456",
            user_id="user_456",
            token="token",
            created_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() - timedelta(hours=1)).isoformat(),
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )
        assert session.is_expired is True


# ═══════════════════════════════════════════════════════════════
# ROLE PERMISSIONS TESTS
# ═══════════════════════════════════════════════════════════════

class TestRolePermissions:
    """Test role-based access control"""

    def test_viewer_permissions(self):
        """Viewer should have minimal permissions"""
        permissions = ROLE_PERMISSIONS[UserRole.VIEWER]
        assert Permission.VIEW_REPORTS in permissions
        assert Permission.GENERATE_REPORTS not in permissions
        assert Permission.MANAGE_TEAM not in permissions

    def test_analyst_permissions(self):
        """Analyst should have read and report permissions"""
        permissions = ROLE_PERMISSIONS[UserRole.ANALYST]
        assert Permission.VIEW_REPORTS in permissions
        assert Permission.GENERATE_REPORTS in permissions
        assert Permission.EXPORT_DATA in permissions
        assert Permission.API_READ in permissions
        assert Permission.MANAGE_TEAM not in permissions

    def test_manager_permissions(self):
        """Manager should have team management permissions"""
        permissions = ROLE_PERMISSIONS[UserRole.MANAGER]
        assert Permission.MANAGE_TEAM in permissions
        assert Permission.INVITE_USERS in permissions
        assert Permission.API_WRITE in permissions
        assert Permission.MANAGE_BILLING not in permissions

    def test_admin_permissions(self):
        """Admin should have billing and analytics permissions"""
        permissions = ROLE_PERMISSIONS[UserRole.ADMIN]
        assert Permission.MANAGE_BILLING in permissions
        assert Permission.VIEW_ANALYTICS in permissions
        assert Permission.MANAGE_TEAM in permissions

    def test_superadmin_permissions(self):
        """Superadmin should have all permissions"""
        permissions = ROLE_PERMISSIONS[UserRole.SUPERADMIN]
        all_permissions = list(Permission)

        for perm in all_permissions:
            assert perm in permissions

    def test_permission_hierarchy(self):
        """Higher roles should have more permissions"""
        viewer_perms = len(ROLE_PERMISSIONS[UserRole.VIEWER])
        analyst_perms = len(ROLE_PERMISSIONS[UserRole.ANALYST])
        manager_perms = len(ROLE_PERMISSIONS[UserRole.MANAGER])
        admin_perms = len(ROLE_PERMISSIONS[UserRole.ADMIN])

        assert analyst_perms > viewer_perms
        assert manager_perms > analyst_perms
        assert admin_perms > manager_perms


# ═══════════════════════════════════════════════════════════════
# API KEY TESTS
# ═══════════════════════════════════════════════════════════════

class TestAPIKey:
    """Test APIKey dataclass"""

    def test_api_key_creation(self):
        """API key should be created with all fields"""
        api_key = APIKey(
            key_id="key_123",
            user_id="user_123",
            key_hash="hash_abc",
            name="Production Key",
            permissions=[Permission.API_READ, Permission.API_WRITE],
            created_at=datetime.utcnow().isoformat(),
            expires_at=None,
            is_active=True
        )

        assert api_key.key_id == "key_123"
        assert api_key.is_active is True
        assert len(api_key.permissions) == 2

    def test_api_key_to_dict(self):
        """API key should convert to dict with permission values"""
        api_key = APIKey(
            key_id="key_123",
            user_id="user_123",
            key_hash="hash_abc",
            name="Test Key",
            permissions=[Permission.API_READ],
            created_at=datetime.utcnow().isoformat(),
            expires_at=None
        )

        data = api_key.to_dict()
        assert isinstance(data, dict)
        assert data["permissions"] == ["api_read"]  # Enum converted to string


# ═══════════════════════════════════════════════════════════════
# INVITATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestInvitation:
    """Test Invitation dataclass"""

    def test_invitation_creation(self):
        """Invitation should be created with all fields"""
        invitation = Invitation(
            invitation_id="inv_123",
            email="newuser@example.com",
            inviter_id="user_123",
            company="Test Corp",
            role=UserRole.ANALYST,
            token="invite_token_123",
            created_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
            accepted=False
        )

        assert invitation.invitation_id == "inv_123"
        assert invitation.email == "newuser@example.com"
        assert invitation.accepted is False

    def test_invitation_to_dict(self):
        """Invitation should convert to dict with role value"""
        invitation = Invitation(
            invitation_id="inv_123",
            email="user@example.com",
            inviter_id="user_456",
            company="Company",
            role=UserRole.MANAGER,
            token="token",
            created_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat()
        )

        data = invitation.to_dict()
        assert data["role"] == "manager"  # Enum converted to string


# ═══════════════════════════════════════════════════════════════
# EDGE CASES & SECURITY TESTS
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Test edge cases and security scenarios"""

    def test_password_hash_unicode_characters(self):
        """Password with unicode should hash correctly"""
        password = "Пароль123!émojis🔐"
        hashed = PasswordHasher.hash_password(password)
        assert PasswordHasher.verify_password(password, hashed) is True

    def test_jwt_token_tampering(self, jwt_manager, jwt_secret):
        """Tampered JWT should be rejected"""
        token = jwt_manager.create_token(user_id="user_123", role="viewer")

        # Tamper with token (change role to admin)
        parts = token.split('.')
        # Try to decode and change role (this will break signature)

        # Even if we can't easily tamper, wrong signature should fail
        tampered = token[:-5] + "XXXXX"
        payload = jwt_manager.verify_token(tampered)
        assert payload is None

    def test_empty_user_id(self, jwt_manager):
        """Empty user_id should still create token (validation is external)"""
        token = jwt_manager.create_token(user_id="", role="analyst")
        payload = jwt_manager.verify_token(token)
        assert payload is not None
        assert payload["user_id"] == ""

    def test_special_characters_in_role(self, jwt_manager):
        """Special characters in role should work"""
        token = jwt_manager.create_token(
            user_id="user_123",
            role="analyst<script>alert('xss')</script>"
        )
        payload = jwt_manager.verify_token(token)
        assert payload is not None


# ═══════════════════════════════════════════════════════════════
# USER MANAGER TESTS - CREATE USER
# ═══════════════════════════════════════════════════════════════

class TestUserManagerCreateUser:
    """Test UserManager create_user method"""

    @pytest.fixture
    def user_manager(self, jwt_secret):
        """User manager instance"""
        from modules.user_manager import UserManager
        return UserManager(jwt_secret=jwt_secret)

    def test_create_user_success(self, user_manager):
        """Should create user successfully"""
        user, errors = user_manager.create_user(
            email="newuser@example.com",
            password="StrongPassword123!",
            name="New User",
            company="Test Company"
        )

        assert user is not None
        assert len(errors) == 0
        assert user.email == "newuser@example.com"
        assert user.status == UserStatus.PENDING
        assert user.role == UserRole.ANALYST  # Default role

    def test_create_user_with_custom_role(self, user_manager):
        """Should create user with custom role"""
        user, errors = user_manager.create_user(
            email="manager@example.com",
            password="SecurePass456!",
            name="Manager User",
            company="Test Co",
            role=UserRole.MANAGER
        )

        assert user is not None
        assert user.role == UserRole.MANAGER

    def test_create_user_invalid_email(self, user_manager):
        """Should reject invalid email"""
        user, errors = user_manager.create_user(
            email="invalid-email",
            password="Password123!",
            name="Test",
            company="Test"
        )

        assert user is None
        assert "Invalid email format" in errors

    def test_create_user_weak_password(self, user_manager):
        """Should reject weak password"""
        user, errors = user_manager.create_user(
            email="test@example.com",
            password="weak",
            name="Test",
            company="Test"
        )

        assert user is None
        assert len(errors) > 0

    def test_create_user_duplicate_email(self, user_manager):
        """Should reject duplicate email"""
        # Create first user
        user1, _ = user_manager.create_user(
            email="duplicate@example.com",
            password="Password123!",
            name="First User",
            company="Test"
        )

        # Try to create second user with same email
        user2, errors = user_manager.create_user(
            email="duplicate@example.com",
            password="DifferentPass456!",
            name="Second User",
            company="Test"
        )

        assert user1 is not None
        assert user2 is None
        assert "Email already registered" in errors

    def test_create_user_email_case_insensitive(self, user_manager):
        """Should treat emails as case-insensitive"""
        user, _ = user_manager.create_user(
            email="Test@Example.COM",
            password="Password123!",
            name="Test",
            company="Test"
        )

        assert user.email == "test@example.com"  # Lowercased

    def test_create_user_generates_id(self, user_manager):
        """Should generate unique user ID"""
        user1, _ = user_manager.create_user(
            email="user1@example.com",
            password="Password123!",
            name="User 1",
            company="Test"
        )

        user2, _ = user_manager.create_user(
            email="user2@example.com",
            password="Password123!",
            name="User 2",
            company="Test"
        )

        assert user1.user_id != user2.user_id


# ═══════════════════════════════════════════════════════════════
# USER MANAGER TESTS - AUTHENTICATION
# ═══════════════════════════════════════════════════════════════

class TestUserManagerAuth:
    """Test UserManager authentication methods"""

    @pytest.fixture
    def user_manager(self, jwt_secret):
        """User manager with a test user"""
        from modules.user_manager import UserManager
        manager = UserManager(jwt_secret=jwt_secret)

        # Create test user
        user, _ = manager.create_user(
            email="testauth@example.com",
            password="TestPassword123!",
            name="Auth Test User",
            company="Test Corp"
        )

        # Activate user (change from PENDING to ACTIVE)
        user.status = UserStatus.ACTIVE

        return manager

    def test_login_success(self, user_manager):
        """Should login successfully with correct credentials"""
        session, token, error = user_manager.login(
            email="testauth@example.com",
            password="TestPassword123!",
            ip_address="127.0.0.1",
            user_agent="TestAgent/1.0"
        )

        assert session is not None
        assert token is not None
        assert error == ""
        assert session.is_active is True

    def test_login_wrong_password(self, user_manager):
        """Should reject wrong password"""
        session, token, error = user_manager.login(
            email="testauth@example.com",
            password="WrongPassword",
            ip_address="127.0.0.1"
        )

        assert session is None
        assert token is None
        assert "Invalid credentials" in error

    def test_login_user_not_found(self, user_manager):
        """Should reject non-existent user"""
        session, token, error = user_manager.login(
            email="nonexistent@example.com",
            password="Password123!",
            ip_address="127.0.0.1"
        )

        assert session is None
        assert token is None
        assert "Invalid credentials" in error

    def test_login_banned_user(self, user_manager):
        """Should reject banned user"""
        # Ban the user
        user = user_manager.get_user_by_email("testauth@example.com")
        user.status = UserStatus.BANNED

        session, token, error = user_manager.login(
            email="testauth@example.com",
            password="TestPassword123!",
            ip_address="127.0.0.1"
        )

        assert session is None
        assert "banned" in error.lower()

    def test_login_suspended_user(self, user_manager):
        """Should reject suspended user"""
        user = user_manager.get_user_by_email("testauth@example.com")
        user.status = UserStatus.SUSPENDED

        session, token, error = user_manager.login(
            email="testauth@example.com",
            password="TestPassword123!",
            ip_address="127.0.0.1"
        )

        assert session is None
        assert "suspended" in error.lower()

    def test_login_updates_last_login(self, user_manager):
        """Should update last login timestamp"""
        user_before = user_manager.get_user_by_email("testauth@example.com")
        last_login_before = user_before.last_login

        user_manager.login(
            email="testauth@example.com",
            password="TestPassword123!",
            ip_address="127.0.0.1"
        )

        user_after = user_manager.get_user_by_email("testauth@example.com")
        assert user_after.last_login != last_login_before

    def test_logout_success(self, user_manager):
        """Should logout successfully"""
        # Login first
        session, _, _ = user_manager.login(
            email="testauth@example.com",
            password="TestPassword123!",
            ip_address="127.0.0.1"
        )

        # Logout
        result = user_manager.logout(session.session_id)

        assert result is True
        assert session.is_active is False

    def test_logout_invalid_session(self, user_manager):
        """Should handle invalid session ID"""
        result = user_manager.logout("invalid_session_id")

        assert result is False

    def test_verify_token_success(self, user_manager):
        """Should verify valid token"""
        # Login to get token
        _, token, _ = user_manager.login(
            email="testauth@example.com",
            password="TestPassword123!",
            ip_address="127.0.0.1"
        )

        # Verify token
        user = user_manager.verify_token(token)

        assert user is not None
        assert user.email == "testauth@example.com"

    def test_verify_token_invalid(self, user_manager):
        """Should reject invalid token"""
        user = user_manager.verify_token("invalid.token.here")

        assert user is None


# ═══════════════════════════════════════════════════════════════
# USER MANAGER TESTS - USER CRUD
# ═══════════════════════════════════════════════════════════════

class TestUserManagerCRUD:
    """Test UserManager CRUD operations"""

    @pytest.fixture
    def user_manager_with_users(self, jwt_secret):
        """User manager with multiple test users"""
        from modules.user_manager import UserManager
        manager = UserManager(jwt_secret=jwt_secret)

        # Create multiple users
        for i in range(3):
            manager.create_user(
                email=f"user{i}@example.com",
                password="Password123!",
                name=f"User {i}",
                company="Test Corp"
            )

        return manager

    def test_get_user_by_id(self, user_manager_with_users):
        """Should get user by ID"""
        # Get first user
        user = user_manager_with_users.get_user_by_email("user0@example.com")
        user_id = user.user_id

        # Get by ID
        retrieved = user_manager_with_users.get_user(user_id)

        assert retrieved is not None
        assert retrieved.user_id == user_id

    def test_get_user_by_email(self, user_manager_with_users):
        """Should get user by email"""
        user = user_manager_with_users.get_user_by_email("user1@example.com")

        assert user is not None
        assert user.email == "user1@example.com"

    def test_update_user(self, user_manager_with_users):
        """Should update user fields"""
        user = user_manager_with_users.get_user_by_email("user0@example.com")

        updated = user_manager_with_users.update_user(
            user.user_id,
            name="Updated Name",
            company="Updated Company"
        )

        assert updated.name == "Updated Name"
        assert updated.company == "Updated Company"

    def test_delete_user(self, user_manager_with_users):
        """Should soft delete user"""
        user = user_manager_with_users.get_user_by_email("user2@example.com")

        result = user_manager_with_users.delete_user(user.user_id)

        assert result is True
        assert user.status == UserStatus.DELETED

    def test_get_multiple_users(self, user_manager_with_users):
        """Should be able to get multiple users"""
        user0 = user_manager_with_users.get_user_by_email("user0@example.com")
        user1 = user_manager_with_users.get_user_by_email("user1@example.com")
        user2 = user_manager_with_users.get_user_by_email("user2@example.com")

        assert all([user0, user1, user2])
        assert len(set([user0.user_id, user1.user_id, user2.user_id])) == 3


# ═══════════════════════════════════════════════════════════════
# USER MANAGER TESTS - SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════

class TestSessionManagement:
    """Test session management"""

    @pytest.fixture
    def user_manager(self, jwt_secret):
        """User manager with test user"""
        from modules.user_manager import UserManager
        manager = UserManager(jwt_secret=jwt_secret)

        user, _ = manager.create_user(
            email="session@example.com",
            password="Password123!",
            name="Session User",
            company="Test"
        )
        user.status = UserStatus.ACTIVE

        return manager

    def test_create_session_on_login(self, user_manager):
        """Should create session on login"""
        session, _, _ = user_manager.login(
            email="session@example.com",
            password="Password123!",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        assert session.session_id is not None
        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "Mozilla/5.0"
        assert session.is_active is True

    def test_multiple_sessions_per_user(self, user_manager):
        """Should allow multiple sessions per user"""
        session1, token1, _ = user_manager.login(
            email="session@example.com",
            password="Password123!",
            ip_address="192.168.1.1"
        )

        session2, token2, _ = user_manager.login(
            email="session@example.com",
            password="Password123!",
            ip_address="192.168.1.2"
        )

        assert session1.session_id != session2.session_id
        assert token1 != token2

    def test_revoke_session(self, user_manager):
        """Should revoke specific session"""
        session, _, _ = user_manager.login(
            email="session@example.com",
            password="Password123!",
            ip_address="127.0.0.1"
        )

        # Revoke
        result = user_manager.logout(session.session_id)

        assert result is True
        assert session.is_active is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
