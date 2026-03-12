"""SQLAlchemy ORM models for authentication and user management in Analyse_IA.

This module defines the database schema for user accounts, authentication credentials,
and JWT refresh token management. All models inherit from DeclarativeBase, which
provides SQLAlchemy ORM functionality and metadata tracking for Alembic migrations.

Models Defined:
- User: Core user account with credentials, preferences, and verification status
- RefreshToken: JWT refresh tokens for session persistence and renewal

Key Design Decisions:
- UUID primary keys for security and scalability across microservices
- PostgreSQL UUID type for native database support
- timezone-aware datetime for all timestamps (UTC)
- French-first language preference ("fr" default, RGPD/CNIL compliance)
- Cascade delete for refresh tokens when user is deleted
- Indexed unique fields (email, tokens) for fast lookups and duplicate prevention

Integration with Alembic:
- Base.metadata contains all table definitions
- Alembic autogenerate detects schema changes: alembic revision --autogenerate -m "message"
- All migrations use this declarative schema as source of truth
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, timezone
import uuid


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models.
    
    All database models inherit from this Base class, which automatically tracks
    model definitions and provides metadata to Alembic for schema migration
    autogeneration.
    
    Alembic Integration:
        target_metadata = Base.metadata
        # Alembic now detects all model changes and generates migration scripts
    """
    pass


class User(Base):
    """User account model for Analyse_IA authentication system.
    
    Stores core user information, credentials, and preferences. Each user can have
    multiple active refresh tokens for managing concurrent sessions across devices.
    
    Attributes:
        id (UUID): Primary key, auto-generated unique identifier for user
        email (str): Unique email address, used as login identifier (indexed for fast lookup)
        hashed_password (str): bcrypt-hashed password (NEVER store plaintext)
        full_name (str, optional): User's display name for personalization
        is_active (bool): Account status - False when user account is disabled/suspended
        is_verified (bool): Email verification status - False until email confirmation
        preferred_language (str): Language code ('fr' or 'en') - defaults to 'fr' per RGPD policy
        created_at (datetime): Account creation timestamp, UTC timezone-aware
        updated_at (datetime): Last profile modification timestamp, auto-updated
        
        refresh_tokens (list[RefreshToken]): Relationship to user's active refresh tokens
    
    Relationships:
        refresh_tokens: One-to-many relationship with RefreshToken
            - cascade="all, delete-orphan": Deleting user removes all their tokens
            - back_populates="user": Bidirectional relationship access
    
    Database Constraints:
        - email: UNIQUE (prevents duplicate accounts)
        - email: INDEXED (fast user lookup by email)
        - is_active: NOT NULL (enforce account status)
        - is_verified: NOT NULL (enforce email verification requirement)
        - preferred_language: NOT NULL (always have language preference)
    
    Usage Example:
        user = User(
            email="alice@example.com",
            hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()),
            full_name="Alice Wonderland",
            preferred_language="en"  # English user (non-default)
        )
        db.session.add(user)
        db.session.commit()
    """
    __tablename__ = "users"

    # Primary key: PostgreSQL UUID (native support for security)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Authentication: Unique email indexed for O(log n) login lookup
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Security: Password hashed with bcrypt (never store plaintext)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile: Optional display name for UI personalization
    full_name = Column(String(255), nullable=True)
    
    # Account status: False disables account without deleting data
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Email verification: False until user confirms email address
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Bilingual support: Default 'fr' for French-first policy (RGPD/CNIL)
    # Can override to 'en' when user changes preference
    preferred_language = Column(String(10), default="fr", nullable=False)
    
    # Timestamps: UTC timezone-aware for consistency across regions
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationship: User can have multiple active refresh tokens (for multi-device sessions)
    # cascade="all, delete-orphan": Removing user removes all their tokens automatically
    refresh_tokens = relationship("RefreshToken", back_populates="user",
                                  cascade="all, delete-orphan")


class RefreshToken(Base):
    """JWT Refresh Token model for session persistence and token renewal.
    
    Implements secure token-based authentication with automatic expiration.
    Users receive short-lived access tokens + long-lived refresh tokens.
    When access token expires, client exchanges refresh token for a new one.
    
    Security Design:
    - Each session gets unique refresh token (can't reuse across sessions)
    - Tokens are cryptographically random strings (indexed for lookup)
    - Expiration enforced at database level (server truth)
    - Revocation support for logout and suspicious activity
    - Foreign key cascade ensures token deletion when user deleted
    
    Attributes:
        id (UUID): Unique token identifier (auto-generated)
        token (str): The actual refresh token (hashed at API layer, indexed for lookup)
        user_id (UUID): Foreign key reference to User (with cascade delete)
        expires_at (datetime): Token expiration timestamp, UTC timezone-aware
        revoked (bool): Revocation flag - True when user logs out or suspects compromise
        created_at (datetime): Issue timestamp for audit/forensics
        
        user (User): Bidirectional relationship to parent User account
    
    Relationships:
        user: Many-to-one relationship with User
            - back_populates="refresh_tokens": Access tokens from user object
            - ForeignKey cascade: Deleting user cascades to tokens
    
    Database Constraints:
        - token: UNIQUE (prevent duplicate token instantiation)
        - token: INDEXED (fast token lookup during refresh request)
        - user_id: FOREIGN KEY with ON DELETE CASCADE
        - expires_at: NOT NULL (enforce expiration time)
        - revoked: NOT NULL (enforce revocation status)
    
    Workflow:
        1. User login: Create RefreshToken with expiration (e.g., 30 days)
        2. Access token expires: POST /auth/refresh {refresh_token}
        3. Server validates: Check token, expiration, user active, not revoked
        4. Create new access token + optionally new refresh token
        5. Logout: Mark token revoked=True (don't delete, keep audit trail)
    
    Usage Example:
        # After successful login authentication
        token = RefreshToken(
            token=secrets.token_urlsafe(32),  # Cryptographically secure
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        db.session.add(token)
        db.session.commit()
    """
    __tablename__ = "refresh_tokens"

    # Primary key: Unique identifier per token instantiation
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Token string: Cryptographically random, indexed for O(log n) validation lookup
    # API layer should hash with bcrypt before storage (optional, depends on security policy)
    token = Column(Text, unique=True, nullable=False, index=True)
    
    # User reference: Which user owns this token
    # CASCADE delete: When user deleted, all their tokens are automatically removed
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False)
    
    # Expiration: Server enforces token lifetime
    # API routes should check: datetime.now(timezone.utc) < token.expires_at
    # Expired tokens are invalid even if not revoked
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Revocation: Soft-delete flag for logout/security events
    # False: Token is valid (if not expired); True: Token is explicitly invalidated
    # Keep revoked tokens for audit trail (don't delete to maintain forensics)
    revoked = Column(Boolean, default=False, nullable=False)
    
    # Timestamp: When token was created (useful for token rotation audit)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationship: Access parent User from token object
    # Allows: token.user.email, token.user.is_active checks during validation
    user = relationship("User", back_populates="refresh_tokens")