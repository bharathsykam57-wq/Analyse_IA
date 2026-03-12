"""Pydantic request/response schemas for authentication API endpoints.

This module defines validation schemas for:
- User registration and login requests
- Token refresh and logout operations
- JWT token and user profile responses

Design Principles:
- Request schemas validate input before processing (FastAPI dependency)
- Response schemas control output serialization and API documentation
- Field validators enforce business rules consistently across all routes
- Bilingual error messages for French-first user experience
- Pydantic config enables ORM model to schema conversion (from_attributes)

Integration:
- Used with FastAPI dependency injection for request validation
- Automatically generates OpenAPI/Swagger schema with Examples
- Validates JWT payload structure before storing in database
"""

from pydantic import BaseModel, EmailStr, field_validator, Field
from datetime import datetime
from uuid import UUID
from typing import Optional
import re


class RegisterRequest(BaseModel):
    """User registration request schema.
    
    Validates new user account creation: email uniqueness, password strength,
    optional profile information, and language preference.
    
    Attributes:
        email (EmailStr): RFC 5322 compliant email address (must be unique)
        password (str): Min 8 chars, 1+ uppercase, 1+ digit (validated by password_strength)
        full_name (str, optional): User display name (defaults to None)
        preferred_language (str): 'fr' or 'en' language code (defaults to 'fr' per RGPD)
    
    Validation Rules:
        - email: Must be valid email format (EmailStr)
        - password: Minimum 8 characters, 1 uppercase, 1 digit (strength checker)
        - preferred_language: Only 'fr' or 'en' allowed
    
    API Response (201 Created):
        {
            "user": {
                "id": "uuid",
                "email": "user@example.com",
                "full_name": "John Doe",
                "is_active": true,
                "is_verified": false,
                "preferred_language": "en",
                "created_at": "2026-03-12T10:30:00Z"
            },
            "tokens": {
                "access_token": "eyJ0eXAi...",
                "refresh_token": "eyJ0eXAi...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }
    """
    email: EmailStr = Field(..., description="Valid email address, used as login identifier")
    password: str = Field(..., min_length=8, 
                         description="Min 8 chars, 1+ uppercase, 1+ digit")
    full_name: Optional[str] = Field(None, max_length=255,
                                    description="Optional display name")
    preferred_language: str = Field("fr", pattern="^(fr|en)$",
                                   description="Language preference: 'fr' or 'en'")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password meets minimum security requirements.
        
        Rules:
        - Minimum 8 characters (enforced by Field)
        - At least 1 uppercase letter (A-Z)
        - At least 1 digit (0-9)
        
        Args:
            v: Password string to validate
            
        Returns:
            str: Original password if valid
            
        Raises:
            ValueError: If password fails strength check (localized to French)
        """
        if len(v) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Le mot de passe doit contenir au moins une majuscule")
        if not re.search(r"[0-9]", v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre")
        return v

    @field_validator("preferred_language")
    @classmethod
    def language_valid(cls, v: str) -> str:
        """Validate language code is supported.
        
        Args:
            v: Language code string ('fr' or 'en')
            
        Returns:
            str: Original language code if valid
            
        Raises:
            ValueError: If language not in supported set
        """
        if v not in ("fr", "en"):
            raise ValueError("Langue non supportée. Utiliser 'fr' ou 'en'")
        return v


class LoginRequest(BaseModel):
    """User login request schema.
    
    Validates authentication credentials: email and password.
    Server authenticates against User.hashed_password (bcrypt hash).
    
    Attributes:
        email (EmailStr): Registered email address
        password (str): User's plaintext password (hashed server-side)
    
    Validation:
        - email: Must be valid email format
        - password: No client-side validation (server does hash comparison)
    
    Success Response (200 OK):
        Returns AuthResponse with access_token + refresh_token
        
    Error Response (401 Unauthorized):
        {"detail": "Email ou mot de passe incorrect"}
    """
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password (plaintext, hashed server-side)")


class RefreshRequest(BaseModel):
    """Token refresh request schema.
    
    Client exchanges expiring access_token for new one using refresh_token.
    Refresh tokens are long-lived (30+ days) and stored in database.
    
    Server validation:
    - Token must exist in database (not deleted/revoked)
    - Token must not be expired (expires_at > now)
    - User must be active (is_active=True)
    - User must be verified (is_verified=True)
    
    Attributes:
        refresh_token (str): JWT or opaque token string from previous auth response
    
    Success Response (200 OK):
        {
            "access_token": "new JWT eyJ0eXAi...",
            "refresh_token": "same or new refresh_token",
            "token_type": "bearer",
            "expires_in": 3600
        }
    
    Error Responses:
        401: Token invalid, expired, or revoked
        403: User account suspended or not verified
    """
    refresh_token: str = Field(..., 
                              description="Long-lived refresh token from previous auth")


class LogoutRequest(BaseModel):
    """User logout request schema.
    
    Client sends refresh_token to explicitly invalidate current session.
    Logout marks the token as revoked=True (soft-delete for audit trail).
    
    Design Notes:
    - Token is not deleted (keeps forensic history)
    - revoked=True prevents future refresh operations
    - User can still use access_token until it expires
    - For immediate logout, also clear client-side tokens
    
    Attributes:
        refresh_token (str): Current session's refresh token to revoke
    
    Success Response (204 No Content):
        Empty body with 204 status (logout always succeeds, idempotent)
    
    Note:
        Logout is idempotent: calling twice with same token returns 204 both times.
        This simplifies client-side logic (no error on double-logout).
    """
    refresh_token: str = Field(..., description="Token to revoke/logout")


class TokenResponse(BaseModel):
    """JWT token pair response schema.
    
    Contains both access and refresh tokens returned during login/refresh.
    
    Token Types:
        - access_token: Short-lived JWT (15-60 min), used for API calls
          Includes user_id, exp, iat in payload, signed with JWT_SECRET_KEY
          
        - refresh_token: Long-lived JWT or opaque token (7-30 days), used for rotation
          Stored in database as RefreshToken.token (revocable)
          
    Client Flow:
        1. POST /auth/register → Get access_token + refresh_token
        2. Use access_token for API calls: Authorization: bearer <access_token>
        3. When access_token expires (401): POST /auth/refresh → New pair
        4. On logout: POST /auth/logout → Revoke refresh_token
    
    Attributes:
        access_token (str): JWT bearer token for API authentication
        refresh_token (str): Long-lived token for obtaining new access tokens
        token_type (str): Always "bearer" (RFC 6750 Bearer Token standard)
        expires_in (int): Access token lifetime in seconds (e.g., 3600 = 1 hour)
    
    API Usage:
        All API calls (except auth endpoints) must include:
        Authorization: bearer {access_token}
    """
    access_token: str = Field(..., description="Short-lived JWT for API calls")
    refresh_token: str = Field(..., description="Long-lived token for token refresh")
    token_type: str = Field("bearer", description="RFC 6750 token type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class UserResponse(BaseModel):
    """Authenticated user profile response schema.
    
    Serializes User ORM model to JSON for API responses.
    Includes account status, preferences, and timestamps (excludes password).
    
    ORM Integration:
        model_config = {"from_attributes": True}
        Enables: UserResponse.from_orm(user_orm_instance)
        Automatically maps ORM attributes to schema fields.
    
    Attributes:
        id (UUID): Unique user identifier
        email (str): Email address (UNIQUE in database)
        full_name (str, optional): User display name
        is_active (bool): Account status (False = suspended)
        is_verified (bool): Email verification status (False = unconfirmed)
        preferred_language (str): 'fr' or 'en' language code
        created_at (datetime): Account creation timestamp (UTC)
    
    Example Response:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "alice@example.com",
            "full_name": "Alice Wonderland",
            "is_active": true,
            "is_verified": true,
            "preferred_language": "en",
            "created_at": "2026-03-12T10:30:00Z"
        }
    
    Security Notes:
        - password_hash is NEVER included in response
        - is_active/is_verified inform client of account restrictions
        - preferred_language guides UI language selection
    """
    id: UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="Email address used for login")
    full_name: Optional[str] = Field(None, description="User display name")
    is_active: bool = Field(..., description="Account active status")
    is_verified: bool = Field(..., description="Email verified status")
    preferred_language: str = Field(..., description="Language preference ('fr' or 'en')")
    created_at: datetime = Field(..., description="Account creation timestamp (UTC)")

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Complete authentication response schema (login/register success).
    
    Combines user profile + JWT token pair in single response.
    Returned by POST /auth/register and POST /auth/login endpoints.
    
    Response Structure:
        {
            "user": { UserResponse },
            "tokens": { TokenResponse }
        }
    
    Flow:
        Client receives both:
        1. User profile (for UI: display email, preferred_language, verification status)
        2. JWT tokens (for API authentication going forward)
        
    Example:
        {
            "user": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "alice@example.com",
                "full_name": "Alice",
                "is_active": true,
                "is_verified": false,
                "preferred_language": "en",
                "created_at": "2026-03-12T10:30:00Z"
            },
            "tokens": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }
    """
    user: UserResponse = Field(..., description="Authenticated user profile")
    tokens: TokenResponse = Field(..., description="JWT access and refresh tokens")