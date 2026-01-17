#!/usr/bin/env python3
"""
USER MANAGER - Authentication & User Management
System 5.0.5 - Handles users, sessions, permissions, API keys

Author: ReviewSignal Team
Version: 5.0.5
Date: January 2026
"""

import hashlib
import secrets
import bcrypt
import jwt
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime, timedelta
import structlog
import re

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════

class UserRole(Enum):
    """User role levels"""
    VIEWER = "viewer"       # Read-only access
    ANALYST = "analyst"     # Generate reports
    MANAGER = "manager"     # Manage team
    ADMIN = "admin"         # Full access
    SUPERADMIN = "superadmin"  # System admin


class UserStatus(Enum):
    """User account status"""
    PENDING = "pending"     # Email not verified
    ACTIVE = "active"       # Active account
    SUSPENDED = "suspended"  # Temporarily suspended
    BANNED = "banned"       # Permanently banned
    DELETED = "deleted"     # Soft deleted


class Permission(Enum):
    """System permissions"""
    # Data access
    VIEW_REPORTS = "view_reports"
    GENERATE_REPORTS = "generate_reports"
    EXPORT_DATA = "export_data"
    
    # API access
    API_READ = "api_read"
    API_WRITE = "api_write"
    
    # Lead management
    VIEW_LEADS = "view_leads"
    EXPORT_LEADS = "export_leads"
    
    # Team management
    MANAGE_TEAM = "manage_team"
    INVITE_USERS = "invite_users"
    
    # Admin
    MANAGE_BILLING = "manage_billing"
    SYSTEM_SETTINGS = "system_settings"
    VIEW_ANALYTICS = "view_analytics"


# Role -> Permissions mapping
ROLE_PERMISSIONS = {
    UserRole.VIEWER: [
        Permission.VIEW_REPORTS,
    ],
    UserRole.ANALYST: [
        Permission.VIEW_REPORTS,
        Permission.GENERATE_REPORTS,
        Permission.EXPORT_DATA,
        Permission.API_READ,
        Permission.VIEW_LEADS,
    ],
    UserRole.MANAGER: [
        Permission.VIEW_REPORTS,
        Permission.GENERATE_REPORTS,
        Permission.EXPORT_DATA,
        Permission.API_READ,
        Permission.API_WRITE,
        Permission.VIEW_LEADS,
        Permission.EXPORT_LEADS,
        Permission.MANAGE_TEAM,
        Permission.INVITE_USERS,
    ],
    UserRole.ADMIN: [
        Permission.VIEW_REPORTS,
        Permission.GENERATE_REPORTS,
        Permission.EXPORT_DATA,
        Permission.API_READ,
        Permission.API_WRITE,
        Permission.VIEW_LEADS,
        Permission.EXPORT_LEADS,
        Permission.MANAGE_TEAM,
        Permission.INVITE_USERS,
        Permission.MANAGE_BILLING,
        Permission.VIEW_ANALYTICS,
    ],
    UserRole.SUPERADMIN: [
        p for p in Permission
    ]
}


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class User:
    """User model"""
    user_id: str
    email: str
    name: str
    company: str
    role: UserRole
    status: UserStatus
    created_at: str
    last_login: Optional[str] = None
    stripe_customer_id: str = ""
    subscription_tier: str = "trial"
    api_calls_used: int = 0
    api_calls_limit: int = 100
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['role'] = self.role.value
        data['status'] = self.status.value
        return data
    
    def to_public_dict(self) -> Dict:
        """Return public-safe user data"""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "company": self.company,
            "role": self.role.value,
            "subscription_tier": self.subscription_tier
        }


@dataclass
class Session:
    """User session"""
    session_id: str
    user_id: str
    token: str
    created_at: str
    expires_at: str
    ip_address: str
    user_agent: str
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > datetime.fromisoformat(self.expires_at)


@dataclass
class APIKey:
    """API key for programmatic access"""
    key_id: str
    user_id: str
    key_hash: str
    name: str
    permissions: List[Permission]
    created_at: str
    expires_at: Optional[str]
    last_used: Optional[str] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['permissions'] = [p.value for p in self.permissions]
        return data


@dataclass
class Invitation:
    """Team invitation"""
    invitation_id: str
    email: str
    inviter_id: str
    company: str
    role: UserRole
    token: str
    created_at: str
    expires_at: str
    accepted: bool = False
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['role'] = self.role.value
        return data


# ═══════════════════════════════════════════════════════════════════
# HELPER CLASSES
# ═══════════════════════════════════════════════════════════════════

class PasswordHasher:
    """Secure password hashing using bcrypt"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    @staticmethod
    def is_strong_password(password: str) -> Tuple[bool, List[str]]:
        """
        Check if password meets strength requirements.
        
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors


class TokenGenerator:
    """Generate secure tokens"""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a random token."""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate an API key with prefix."""
        return f"rs_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()


class JWTManager:
    """JWT token management"""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_token(
        self,
        user_id: str,
        role: str,
        expires_hours: int = 24
    ) -> str:
        """
        Create a JWT token.
        
        Args:
            user_id: User ID
            role: User role
            expires_hours: Token expiry in hours
        
        Returns:
            JWT token string
        """
        payload = {
            "user_id": user_id,
            "role": role,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=expires_hours)
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify and decode a JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload or None if invalid
        """
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            logger.warning("jwt_expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("jwt_invalid", error=str(e))
            return None
    
    def refresh_token(
        self,
        token: str,
        extends_hours: int = 24
    ) -> Optional[str]:
        """
        Refresh an existing token.
        
        Args:
            token: Current JWT token
            extends_hours: New expiry period
        
        Returns:
            New JWT token or None
        """
        payload = self.verify_token(token)
        if not payload:
            return None
        
        return self.create_token(
            user_id=payload["user_id"],
            role=payload["role"],
            expires_hours=extends_hours
        )


# ═══════════════════════════════════════════════════════════════════
# MAIN CLASS
# ═══════════════════════════════════════════════════════════════════

class UserManager:
    """
    User Manager for ReviewSignal.
    Handles authentication, sessions, permissions, and API keys.
    """
    
    def __init__(self, jwt_secret: str, db_connection=None):
        """
        Initialize User Manager.
        
        Args:
            jwt_secret: Secret key for JWT tokens
            db_connection: Database connection (optional)
        """
        self.jwt_manager = JWTManager(jwt_secret)
        self.password_hasher = PasswordHasher()
        self.token_generator = TokenGenerator()
        self.db = db_connection
        
        # In-memory stores (replace with DB in production)
        self._users: Dict[str, Dict] = {}
        self._sessions: Dict[str, Session] = {}
        self._api_keys: Dict[str, APIKey] = {}
        self._invitations: Dict[str, Invitation] = {}
        
        logger.info("user_manager_initialized")
    
    # ───────────────────────────────────────────────────────────────
    # USER CRUD
    # ───────────────────────────────────────────────────────────────
    
    def create_user(
        self,
        email: str,
        password: str,
        name: str,
        company: str,
        role: UserRole = UserRole.ANALYST
    ) -> Tuple[Optional[User], List[str]]:
        """
        Create a new user.
        
        Args:
            email: User email
            password: Plain text password
            name: User name
            company: Company name
            role: User role (default: ANALYST)
        
        Returns:
            Tuple of (User, errors)
        """
        errors = []
        
        # Validate email
        if not self._validate_email(email):
            errors.append("Invalid email format")
        
        # Check if email exists
        if self._email_exists(email):
            errors.append("Email already registered")
        
        # Validate password
        is_strong, pwd_errors = self.password_hasher.is_strong_password(password)
        if not is_strong:
            errors.extend(pwd_errors)
        
        if errors:
            return None, errors
        
        # Create user
        user_id = self.token_generator.generate_token(16)
        password_hash = self.password_hasher.hash_password(password)
        
        user = User(
            user_id=user_id,
            email=email.lower(),
            name=name,
            company=company,
            role=role,
            status=UserStatus.PENDING,
            created_at=datetime.utcnow().isoformat()
        )
        
        # Store user with password hash
        self._users[user_id] = {
            "user": user,
            "password_hash": password_hash,
            "verification_token": self.token_generator.generate_token()
        }
        
        logger.info(
            "user_created",
            user_id=user_id,
            email=email,
            role=role.value
        )
        
        return user, []
    
    def get_user(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
        
        Returns:
            User or None
        """
        user_data = self._users.get(user_id)
        return user_data["user"] if user_data else None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.
        
        Args:
            email: User email
        
        Returns:
            User or None
        """
        email_lower = email.lower()
        for user_data in self._users.values():
            if user_data["user"].email == email_lower:
                return user_data["user"]
        return None
    
    def update_user(
        self,
        user_id: str,
        **kwargs
    ) -> Optional[User]:
        """
        Update user fields.
        
        Args:
            user_id: User ID
            **kwargs: Fields to update
        
        Returns:
            Updated User or None
        """
        user_data = self._users.get(user_id)
        if not user_data:
            return None
        
        user = user_data["user"]
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        logger.info("user_updated", user_id=user_id, fields=list(kwargs.keys()))
        
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """
        Soft delete a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Success boolean
        """
        user = self.get_user(user_id)
        if not user:
            return False
        
        user.status = UserStatus.DELETED
        
        # Invalidate all sessions
        self._invalidate_user_sessions(user_id)
        
        logger.info("user_deleted", user_id=user_id)
        
        return True
    
    # ───────────────────────────────────────────────────────────────
    # AUTHENTICATION
    # ───────────────────────────────────────────────────────────────
    
    def login(
        self,
        email: str,
        password: str,
        ip_address: str = "",
        user_agent: str = ""
    ) -> Tuple[Optional[Session], Optional[str], str]:
        """
        Authenticate user and create session.
        
        Args:
            email: User email
            password: Plain text password
            ip_address: Client IP
            user_agent: Client user agent
        
        Returns:
            Tuple of (Session, JWT token, error message)
        """
        user = self.get_user_by_email(email)
        
        if not user:
            logger.warning("login_failed_user_not_found", email=email)
            return None, None, "Invalid credentials"
        
        # Check user status
        if user.status == UserStatus.BANNED:
            return None, None, "Account has been banned"
        if user.status == UserStatus.SUSPENDED:
            return None, None, "Account is suspended"
        if user.status == UserStatus.DELETED:
            return None, None, "Account not found"
        
        # Verify password
        user_data = self._users.get(user.user_id)
        if not self.password_hasher.verify_password(password, user_data["password_hash"]):
            logger.warning("login_failed_wrong_password", user_id=user.user_id)
            return None, None, "Invalid credentials"
        
        # Create session
        session = self._create_session(user.user_id, ip_address, user_agent)
        
        # Create JWT token
        token = self.jwt_manager.create_token(user.user_id, user.role.value)
        
        # Update last login
        user.last_login = datetime.utcnow().isoformat()
        
        logger.info("login_success", user_id=user.user_id, email=email)
        
        return session, token, ""
    
    def logout(self, session_id: str) -> bool:
        """
        End a user session.
        
        Args:
            session_id: Session ID
        
        Returns:
            Success boolean
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        session.is_active = False
        
        logger.info("logout", session_id=session_id)
        
        return True
    
    def verify_token(self, token: str) -> Optional[User]:
        """
        Verify JWT token and return user.
        
        Args:
            token: JWT token
        
        Returns:
            User or None
        """
        payload = self.jwt_manager.verify_token(token)
        if not payload:
            return None
        
        return self.get_user(payload["user_id"])
    
    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> Tuple[bool, str]:
        """
        Change user password.
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
        
        Returns:
            Tuple of (success, error message)
        """
        user_data = self._users.get(user_id)
        if not user_data:
            return False, "User not found"
        
        # Verify old password
        if not self.password_hasher.verify_password(old_password, user_data["password_hash"]):
            return False, "Current password is incorrect"
        
        # Validate new password
        is_strong, errors = self.password_hasher.is_strong_password(new_password)
        if not is_strong:
            return False, errors[0]
        
        # Update password
        user_data["password_hash"] = self.password_hasher.hash_password(new_password)
        
        # Invalidate all sessions except current
        self._invalidate_user_sessions(user_id)
        
        logger.info("password_changed", user_id=user_id)
        
        return True, ""
    
    # ───────────────────────────────────────────────────────────────
    # PERMISSIONS
    # ───────────────────────────────────────────────────────────────
    
    def has_permission(
        self,
        user_id: str,
        permission: Permission
    ) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            user_id: User ID
            permission: Permission to check
        
        Returns:
            Boolean indicating if user has permission
        """
        user = self.get_user(user_id)
        if not user or user.status != UserStatus.ACTIVE:
            return False
        
        user_permissions = ROLE_PERMISSIONS.get(user.role, [])
        return permission in user_permissions
    
    def get_user_permissions(self, user_id: str) -> List[Permission]:
        """
        Get all permissions for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            List of permissions
        """
        user = self.get_user(user_id)
        if not user:
            return []
        
        return ROLE_PERMISSIONS.get(user.role, [])
    
    def require_permission(
        self,
        user_id: str,
        permission: Permission
    ) -> None:
        """
        Require a permission or raise exception.
        
        Args:
            user_id: User ID
            permission: Required permission
        
        Raises:
            PermissionError if user lacks permission
        """
        if not self.has_permission(user_id, permission):
            raise PermissionError(f"User lacks permission: {permission.value}")
    
    # ───────────────────────────────────────────────────────────────
    # API KEYS
    # ───────────────────────────────────────────────────────────────
    
    def create_api_key(
        self,
        user_id: str,
        name: str,
        permissions: List[Permission] = None,
        expires_days: int = None
    ) -> Tuple[Optional[str], Optional[APIKey]]:
        """
        Create an API key for a user.
        
        Args:
            user_id: User ID
            name: Key name/description
            permissions: Key permissions (defaults to user's permissions)
            expires_days: Days until expiry (None = no expiry)
        
        Returns:
            Tuple of (raw key, APIKey object) - raw key shown only once!
        """
        user = self.get_user(user_id)
        if not user:
            return None, None
        
        # Default to user's permissions
        if permissions is None:
            permissions = self.get_user_permissions(user_id)
        
        # Generate key
        raw_key = self.token_generator.generate_api_key()
        key_hash = self.token_generator.hash_token(raw_key)
        key_id = self.token_generator.generate_token(16)
        
        expires_at = None
        if expires_days:
            expires_at = (datetime.utcnow() + timedelta(days=expires_days)).isoformat()
        
        api_key = APIKey(
            key_id=key_id,
            user_id=user_id,
            key_hash=key_hash,
            name=name,
            permissions=permissions,
            created_at=datetime.utcnow().isoformat(),
            expires_at=expires_at
        )
        
        self._api_keys[key_id] = api_key
        
        logger.info(
            "api_key_created",
            user_id=user_id,
            key_id=key_id,
            name=name
        )
        
        return raw_key, api_key
    
    def verify_api_key(self, raw_key: str) -> Optional[Tuple[User, APIKey]]:
        """
        Verify an API key.
        
        Args:
            raw_key: Raw API key
        
        Returns:
            Tuple of (User, APIKey) or None
        """
        key_hash = self.token_generator.hash_token(raw_key)
        
        for api_key in self._api_keys.values():
            if api_key.key_hash == key_hash and api_key.is_active:
                # Check expiry
                if api_key.expires_at:
                    if datetime.utcnow() > datetime.fromisoformat(api_key.expires_at):
                        return None
                
                user = self.get_user(api_key.user_id)
                if user and user.status == UserStatus.ACTIVE:
                    # Update last used
                    api_key.last_used = datetime.utcnow().isoformat()
                    return user, api_key
        
        return None
    
    def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: API key ID
            user_id: User ID (for authorization)
        
        Returns:
            Success boolean
        """
        api_key = self._api_keys.get(key_id)
        if not api_key or api_key.user_id != user_id:
            return False
        
        api_key.is_active = False
        
        logger.info("api_key_revoked", key_id=key_id, user_id=user_id)
        
        return True
    
    def list_api_keys(self, user_id: str) -> List[APIKey]:
        """
        List all API keys for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            List of APIKey objects (without hashes)
        """
        return [
            k for k in self._api_keys.values()
            if k.user_id == user_id and k.is_active
        ]
    
    # ───────────────────────────────────────────────────────────────
    # INVITATIONS
    # ───────────────────────────────────────────────────────────────
    
    def create_invitation(
        self,
        inviter_id: str,
        email: str,
        role: UserRole = UserRole.ANALYST
    ) -> Optional[Invitation]:
        """
        Create a team invitation.
        
        Args:
            inviter_id: ID of user sending invitation
            email: Email to invite
            role: Role for new user
        
        Returns:
            Invitation object or None
        """
        inviter = self.get_user(inviter_id)
        if not inviter:
            return None
        
        # Check permission
        if not self.has_permission(inviter_id, Permission.INVITE_USERS):
            return None
        
        invitation_id = self.token_generator.generate_token(16)
        token = self.token_generator.generate_token()
        
        invitation = Invitation(
            invitation_id=invitation_id,
            email=email.lower(),
            inviter_id=inviter_id,
            company=inviter.company,
            role=role,
            token=token,
            created_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat()
        )
        
        self._invitations[invitation_id] = invitation
        
        logger.info(
            "invitation_created",
            invitation_id=invitation_id,
            email=email,
            inviter_id=inviter_id
        )
        
        return invitation
    
    def accept_invitation(
        self,
        token: str,
        name: str,
        password: str
    ) -> Tuple[Optional[User], str]:
        """
        Accept an invitation and create user.
        
        Args:
            token: Invitation token
            name: New user's name
            password: New user's password
        
        Returns:
            Tuple of (User, error message)
        """
        # Find invitation
        invitation = None
        for inv in self._invitations.values():
            if inv.token == token and not inv.accepted:
                invitation = inv
                break
        
        if not invitation:
            return None, "Invalid or expired invitation"
        
        # Check expiry
        if datetime.utcnow() > datetime.fromisoformat(invitation.expires_at):
            return None, "Invitation has expired"
        
        # Create user
        user, errors = self.create_user(
            email=invitation.email,
            password=password,
            name=name,
            company=invitation.company,
            role=invitation.role
        )
        
        if errors:
            return None, errors[0]
        
        # Mark invitation as accepted
        invitation.accepted = True
        
        # Activate user immediately
        user.status = UserStatus.ACTIVE
        
        logger.info(
            "invitation_accepted",
            invitation_id=invitation.invitation_id,
            user_id=user.user_id
        )
        
        return user, ""
    
    # ───────────────────────────────────────────────────────────────
    # PRIVATE METHODS
    # ───────────────────────────────────────────────────────────────
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _email_exists(self, email: str) -> bool:
        """Check if email already exists."""
        return self.get_user_by_email(email) is not None
    
    def _create_session(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str
    ) -> Session:
        """Create a new session."""
        session_id = self.token_generator.generate_token()
        token = self.token_generator.generate_token()
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            token=token,
            created_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self._sessions[session_id] = session
        return session
    
    def _invalidate_user_sessions(self, user_id: str) -> None:
        """Invalidate all sessions for a user."""
        for session in self._sessions.values():
            if session.user_id == user_id:
                session.is_active = False


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*60)
    print("👤 USER MANAGER - TEST RUN")
    print("="*60)
    
    # Initialize manager
    manager = UserManager(jwt_secret="test-secret-key-123")
    
    # Create user
    print("\n👤 Creating test user...")
    user, errors = manager.create_user(
        email="test@example.com",
        password="SecurePass123!",
        name="Test User",
        company="Test Corp",
        role=UserRole.ANALYST
    )
    
    if user:
        print(f"   User created: {user.user_id}")
        print(f"   Email: {user.email}")
        print(f"   Role: {user.role.value}")
        
        # Activate user
        user.status = UserStatus.ACTIVE
        
        # Test login
        print("\n🔐 Testing login...")
        session, token, error = manager.login(
            email="test@example.com",
            password="SecurePass123!"
        )
        
        if session:
            print(f"   Session ID: {session.session_id[:20]}...")
            print(f"   JWT Token: {token[:50]}...")
            
            # Verify token
            verified_user = manager.verify_token(token)
            print(f"   Token verified: {verified_user.email}")
        
        # Check permissions
        print("\n🔑 Checking permissions...")
        for perm in [Permission.VIEW_REPORTS, Permission.GENERATE_REPORTS, Permission.SYSTEM_SETTINGS]:
            has = manager.has_permission(user.user_id, perm)
            print(f"   {perm.value}: {'✅' if has else '❌'}")
        
        # Create API key
        print("\n🔑 Creating API key...")
        raw_key, api_key = manager.create_api_key(
            user_id=user.user_id,
            name="Test API Key",
            expires_days=30
        )
        
        if raw_key:
            print(f"   Key ID: {api_key.key_id}")
            print(f"   Raw Key: {raw_key[:20]}... (store securely!)")
    else:
        print(f"   Errors: {errors}")
    
    print("\n" + "="*60)
    print("✅ User Manager test complete!")
    print("="*60)
