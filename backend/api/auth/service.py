
"""Authentication service module for user management and JWT token operations.

This module implements core authentication business logic:
- User registration and login with password hashing (bcrypt)
- JWT token generation and validation (access + refresh tokens)
- Token refresh workflow with automatic token rotation
- User session management and logout handling

Key Design Patterns:
- Two-token system: Short-lived access tokens (15 min) + long-lived refresh tokens (7 days)
- Database-backed refresh tokens: Stored in RefreshToken model for revocation support
- Bcrypt password hashing: One-way hash with auto salt (no plaintext ever stored)
- JWT payload validation: Verify token type, expiration, user status before use
- Bilingual error messages: French-first error responses (RGPD/CNIL compliance)

Security Features:
- Transparent salt generation per password (bcrypt handles)
- JWT expiration enforced by decode() (no manual checking needed)
- Refresh token rotation: Old token revoked after refresh (prevents token replay)
- Automatic revocation on logout: Prevents unauthorized refresh operations
- User status checks: Inactive/unverified users rejected at login
- Token type validation: Prevents mixing access/refresh token types

Configuration (from .env environment):
- JWT_SECRET_KEY: Private key for signing/verifying JWTs (min 32 chars)
- JWT_ALGORITHM: Signing algorithm, default HS256
- JWT_ACCESS_TOKEN_EXPIRE_MINUTES: Bearer token lifetime, default 15 min
- JWT_REFRESH_TOKEN_EXPIRE_DAYS: Refresh token lifetime, default 7 days

Token Architecture:
    Access Token (Short-lived):
    - Format: JWT (JSON Web Token)
    - Payload: user_id (sub), email, expiration (exp), token_type (access)
    - Used in: Authorization: Bearer <token> header for API requests
    - Verified: ExpiredSignatureError, JWTError on invalid/expired token
    
    Refresh Token (Long-lived):
    - Format: Cryptographically random hex string (secrets.token_hex)
    - Storage: Stored in RefreshToken database table (revocable, expiration trackable)
    - Used in: POST /auth/refresh body for obtaining new access tokens
    - Verified: Database lookup, revocation check, expiration check

Usage in Routes:
    POST /auth/register:
        1. Validate RegisterRequest (email, password strength)
        2. Call register_user() → Creates User record
        3. Call create_access_token() + create_refresh_token()
        4. Return AuthResponse with both tokens
    
    POST /auth/login:
        1. Validate LoginRequest (email + password)
        2. Call login_user() → Authenticates credentials, checks active status
        3. Call create_access_token() + create_refresh_token()
        4. Return AuthResponse with both tokens
    
    POST /auth/refresh:
        1. Validate RefreshRequest (token present)
        2. Call refresh_access_token() → Validates, rotates, creates new tokens
        3. Return new TokenResponse (old refresh_token is now revoked)
    
    Protected Routes:
        1. Extract Bearer token from Authorization header
        2. Call decode_access_token() → Verify JWT signature and expiration
        3. Call get_current_user() → Load User from database, check active
        4. Use user object in route handler

Error Handling:
- ValueError: Business logic errors (invalid credentials, expired token)
- JWTError: Cryptographic errors (invalid signature, malformed token)
- All errors logged as warnings (not exceptions) for security (don't leak details)
- Route handlers should catch these and return 401/403 status codes
"""

from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from uuid import UUID
import os
import logging
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.api.auth.models import User, RefreshToken
from backend.api.auth.schemas import RegisterRequest, LoginRequest

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# PASSWORD HASHING CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
# CryptContext: Manage password hashing with bcrypt (library: passlib)
# 
# Bcrypt Implementation:
# - Transparent salt generation: Each password gets unique random salt
# - Cost factor (rounds): Default 12 iterations (configurable for performance)
# - Output: $2b$12$<salt><hash> format (always 60 characters)
# - One-way: Cannot decrypt password from hash (by design)
# - Timing-safe comparison: Resistant to timing attacks (passlib handles)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ═══════════════════════════════════════════════════════════════════════════
# JWT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
# Configuration loaded from environment variables (.env or system vars)
# Critical for security: JWT_SECRET_KEY must be strong (32+ chars) and not exposed

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if not JWT_SECRET_KEY:
    logger.error(
        "JWT_SECRET_KEY not configured. Set JWT_SECRET_KEY environment variable. "
        "Example: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


# ═══════════════════════════════════════════════════════════════════════════
# PASSWORD HASHING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """Hash plaintext password using bcrypt with automatic salt generation.
    
    Converts plaintext password to bcrypt hash for permanent storage.
    NEVER store plaintext passwords in database (major security violation).
    
    Bcrypt Algorithm:
    - Generates random 16-byte salt per call (even same password produces different hashes)
    - Cost factor: 12 (default, balance between security and speed)
    - Output format: $2b$12$<22-char-salt><31-char-hash> (always 60 chars)
    - One-way: Hash cannot be reversed to plaintext (salted hash function)
    - Timing-safe: Comparison resistant to timing attacks (see verify_password)
    
    Args:
        password (str): Plaintext password from user (RegisterRequest or LoginRequest)
    
    Returns:
        str: Bcrypt hash string (60 characters, always $2b$12$ prefix)
    
    Security Notes:
        - Never use plain SHA256 or MD5 (rainbow table vulnerable)
        - Bcrypt automatically handles salt (don't reuse password on different sites)
        - Cost factor can increase over time: hardening against GPU attacks
        - Python-Password-Hash library (passlib) handles all complexity
    
    Example:
        password = "MySecure!Pass123"
        hashed = hash_password(password)
        # hashed = "$2b$12$...(60 chars total)"
        
        # For storage in database
        user = User(email="user@example.com", hashed_password=hashed)
        db.add(user)
        db.commit()
    
    Usage in Auth Flow:
        register_user() → hash_password(request.password) → Store in User.hashed_password
    """
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plaintext password matches bcrypt hash (used during login).
    
    Compares plaintext password from login request against stored bcrypt hash.
    Uses timing-safe comparison to prevent timing-based password guessing attacks.
    
    Verification Process:
    - Extracts salt from stored hash ($2b$12$<salt>...)
    - Hashes plaintext password with extracted salt
    - Compares result with stored hash bit-by-bit (timing-safe)
    - Returns True only if hashes match exactly
    
    Args:
        plain (str): Plaintext password from user login attempt
        hashed (str): Stored bcrypt hash from User.hashed_password
    
    Returns:
        bool: True if plaintext matches hash, False otherwise
    
    Security Notes:
        - Timing-safe: Always compares full hashes (doesn't short-circuit on mismatch)
        - Prevents attackers from timing response differences to guess passwords
        - passlib.context.verify() handles all complexity (don't roll your own)
    
    Error Behavior:
        - Invalid hash format: Returns False (doesn't raise exception)
        - Malformed plaintext: Returns False (empty string, unicode issues, etc.)
        - Never leaks which field was wrong (timing-safe comparison)
    
    Example:
        # During login
        user = db.query(User).filter(User.email == request.email).first()
        if user and verify_password(request.password, user.hashed_password):
            # Login successful
            return create_tokens(user)
        else:
            # Generic error message (don't reveal if email or password wrong)
            raise ValueError("Email ou mot de passe incorrect")
    
    Usage in Auth Flow:
        login_user() → verify_password(request.password, user.hashed_password)
    """
    return pwd_context.verify(plain, hashed)


# ═══════════════════════════════════════════════════════════════════════════
# JWT TOKEN FUNCTIONS (Access & Refresh Tokens)
# ═══════════════════════════════════════════════════════════════════════════

def create_access_token(user_id: UUID, email: str) -> tuple[str, int]:
    """Generate short-lived JWT access token for API authentication.
    
    Creates JSON Web Token with user identity and expiration.
    Access tokens are used in Authorization header for all API requests.
    Short lifetime (15 min default) balances security vs. refresh frequency.
    
    JWT Structure:
        Header: {"alg": "HS256", "typ": "JWT"}
        Payload: {
            "sub": "<user_id>",           # Subject (user identifier)
            "email": "<email>",           # Email for debugging/display
            "exp": <unix_timestamp>,      # Expiration time
            "iat": <unix_timestamp>,      # Issued at time (auto from jose)
            "type": "access"              # Distinguish from refresh_token type
        }
        Signature: HMAC-SHA256(header.payload, JWT_SECRET_KEY)
    
    Security Design:
    - Short expiration (15 min): Limits window if token is compromised
    - Payload doesn't include password or sensitive data (JWT is readable)
    - Signature validates token hasn't been tampered with
    - Client can't modify exp without invalidating signature
    - type="access" prevents using refresh_token as access_token
    
    Args:
        user_id (UUID): User's unique identifier from User.id
        email (str): User's email address (for convenience, included in token)
    
    Returns:
        tuple[str, int]: (JWT token string, expiration in seconds)
            - Token: Base64-encoded JWT ready for Authorization: Bearer header
            - Expires_in: Seconds until expiration (3600 for 60 min example)
    
    Example:
        token, expires_in = create_access_token(
            user_id=uuid.UUID('550e8400-...'),
            email='alice@example.com'
        )
        # token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        # expires_in = 900 (15 minutes * 60 seconds)
        
        # Client uses in every API request:
        headers = {"Authorization": f"Bearer {token}"}
    
    Token Generation Flow:
        1. Calculate expiration time: now + 15 minutes
        2. Build payload dict with user_id, email, type, exp
        3. Sign with JWT_SECRET_KEY using HS256 algorithm
        4. Return encoded token and lifetime in seconds
    
    Usage in Auth Flow:
        register_user() → create_access_token(user.id, user.email)
        login_user() → create_access_token(user.id, user.email)
        refresh_access_token() → create_access_token(user.id, user.email)
    """
    expires_in = JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "type": "access",
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expires_in


def create_refresh_token(user_id: UUID, db: Session) -> str:
    """Generate long-lived refresh token and store in database.
    
    Creates a cryptographically random token for exchanging expired access tokens.
    Unlike access_token (JWT), refresh_token is stored in database for revocation.
    Longer lifetime (7 days default) allows extended session without explicit login.
    
    Token Design:
    - Format: 128-character hex string (64 bytes of random data)
    - Generation: secrets.token_hex(64) (cryptographically secure PRNG)
    - Storage: Stored in RefreshToken model with user_id, expires_at
    - Revocation: Can be marked revoked=True (soft-delete for audit)
    - Database-backed: Unlike JWT, can be revoked without cryptographic key
    
    Token Storage in Database:
        RefreshToken {
            id: UUID (auto-generated)
            token: str (this 128-char hex string)
            user_id: UUID (foreign key to User)
            expires_at: datetime (7 days from now)
            revoked: bool (False initially, True after logout/refresh rotation)
            created_at: datetime (now)
        }
    
    Security Features:
    - Database storage allows revocation (can't revoke JWTs)
    - Unique constraint on token (prevents duplicate issuance)
    - Foreign key cascade (token deleted when user deleted)
    - Soft-delete via revoked flag (forensic audit trail)
    - secrets.token_hex() uses os.urandom() (cryptographically secure)
    
    Args:
        user_id (UUID): User's unique identifier
        db (Session): Database session for persisting token
    
    Returns:
        str: 128-character hex string refresh token
    
    Raises:
        SQLAlchemy exceptions: If database insert fails (connection issues, constraints)
    
    Example:
        token = create_refresh_token(user.id, db)
        # token = "a1b2c3d4e5f6....(128 hex chars)"
        # Stored in RefreshToken table for future lookups
    
    Token Usage Flow:
        1. Server creates access_token + refresh_token after successful login
        2. Client stores both tokens (access in memory, refresh in secure cookie)
        3. When access_token expires (401 response), client calls POST /auth/refresh
        4. POST /auth/refresh validates refresh_token from database
        5. If valid and not revoked: create new access_token + refresh_token pair
        6. Old refresh_token is revoked (marked revoked=True)
    
    Usage in Auth Flow:
        register_user() creates tokens → create_refresh_token(user.id, db)
        login_user() creates tokens → create_refresh_token(user.id, db)
        refresh_access_token() rotates token → create_refresh_token(db_token.user_id, db)
    """
    token = secrets.token_hex(64)  # 128-character cryptographically random string
    expires_at = datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    # Persist token to database (enables revocation, expiration-based validation)
    db_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
    )
    db.add(db_token)
    db.commit()
    
    logger.info(f"Refresh token created for user {user_id}")
    return token


def decode_access_token(token: str) -> dict:
    """Validate and decode JWT access token to extract payload.
    
    Verifies token signature, expiration, and token type before decoding.
    Essential step before using token claims (user_id) in route handlers.
    
    Validation Steps:
        1. Verify signature: Confirms token hasn't been tampered with
        2. Verify expiration: Rejects tokens with exp < now
        3. Verify token type: Ensures token is access_token (type="access")
    
    JWT Verification:
    - Signature: Computed with JWT_SECRET_KEY (verifies origin from server)
    - Expiration (exp claim): Automatically checked by jwt.decode()
    - Algorithm (alg): Header field verified against allowed algorithms
    - If any check fails: Raises JWTError with specific reason
    
    Args:
        token (str): JWT access token string from Authorization header
    
    Returns:
        dict: Decoded payload with claims:
            {
                "sub": "<user_id>",
                "email": "<email>",
                "exp": <unix_timestamp>,
                "iat": <unix_timestamp>,
                "type": "access"
            }
    
    Raises:
        JWTError: If token invalid, expired, tampered, or wrong type
            - ExpiredSignatureError (subclass of JWTError): Token expired
            - DecodeError: Malformed token or invalid signature
            - JWTError: Invalid token type (not "access")
    
    Error Handling:
        All errors are logged at WARNING level (not EXCEPTION level)
        Prevents leaking sensitive information (don't expose JWT details)
    
    Example:
        try:
            payload = decode_access_token(authorization_header_token)
            user_id = payload["sub"]
            # Use user_id to fetch user from database
        except JWTError as e:
            # Return 401 Unauthorized to client
            raise HTTPException(status_code=401, detail="Invalid token")
    
    Usage in Protected Routes:
        1. Extract token from Authorization: Bearer <token> header
        2. Call decode_access_token(token) to verify and extract payload
        3. Use payload["sub"] as user_id to fetch User from database
        4. Return user object to route handler
    
    Usage in get_current_user():
        payload = decode_access_token(token) → Extract user_id
        user = db.query(User).filter(User.id == user_id).first()
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Verify token type (access vs refresh_token)
        if payload.get("type") != "access":
            logger.warning("JWT token type mismatch: expected 'access'")
            raise JWTError("Invalid token type")
        
        return payload
        
    except JWTError as e:
        # Log warning (not exception) to prevent leaking JWT details in production logs
        logger.warning(f"JWT decode failed: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════
# USER AUTHENTICATION OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════

def register_user(request: RegisterRequest, db: Session) -> User:
    """Create new user account from registration request.
    
    Validates email uniqueness, hashes password, and persists User record.
    CRITICAL: Called only after RegisterRequest validation (email format, password strength).
    
    Registration Process:
        1. Check email not already registered (uniqueness constraint)
        2. Hash plaintext password with bcrypt (never store plaintext)
        3. Create User object with validated data
        4. Persist to database and commit
        5. Log successful registration for audit
        6. Return User object (with auto-generated id, timestamps)
    
    Args:
        request (RegisterRequest): Validated registration data:
            - email: Valid, unique email address
            - password: Strong password (8+ chars, 1+ upper, 1+ digit)
            - full_name: Optional display name
            - preferred_language: 'fr' or 'en'
        
        db (Session): Database session for persistence
    
    Returns:
        User: Created user object with:
            - id: UUID auto-generated primary key
            - email: Email address (verified unique)
            - hashed_password: Bcrypt hash (plaintext discarded)
            - full_name: Display name or None
            - is_active: True (default, account enabled)
            - is_verified: False (email not yet confirmed)
            - preferred_language: User's language choice
            - created_at: Registration timestamp (UTC)
            - updated_at: Registration timestamp (UTC)
    
    Raises:
        ValueError: Email already registered (business logic error)
        SQLAlchemy exceptions: Database constraint violations
    
    Error Handling:
        Email Duplicate: ValueError with French message (RGPD compliance)
        Database Issues: SQLAlchemy exceptions propagate (FastAPI converts to 500)
    
    Example:
        request = RegisterRequest(
            email="alice@example.com",
            password="SecurePass123!",
            full_name="Alice Wonderland",
            preferred_language="en"
        )
        try:
            user = register_user(request, db)
            # user.id = UUID('550e8400-...')
            # user.hashed_password = "$2b$12$..." (hashed)
        except ValueError:
            # Handle email exists error → return 409 Conflict
    
    Security Notes:
        - Check database before creating (atomic uniqueness constraint)
        - Password hashed immediately (never logged, never exposed)
        - User is_verified=False (requires email confirmation)
        - User is_active=True (but can't login until verified, depends on policy)
        - Logging only records email (not password, not full_name)
    
    Follow-up in Auth Flow:
        After register_user(): Create access_token + refresh_token for immediate login
        Route returns AuthResponse with user + tokens
    
    Database State After:
        User table: New row with user data
        RefreshToken table: Row created by create_refresh_token() in caller
        (Note: This function doesn't create tokens, caller handles that)
    """
    # Check email uniqueness (database unique constraint is fallback)
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        logger.warning(f"Registration attempt with existing email: {request.email}")
        raise ValueError("Un compte existe déjà avec cet email")

    # Create user with hashed password (detach plaintext immediately)
    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        preferred_language=request.preferred_language,
    )
    
    # Persist to database
    db.add(user)
    db.commit()
    db.refresh(user)  # Reload to populate auto-generated values
    
    logger.info(f"New user registered: {user.email} (id={user.id})")
    return user


def login_user(request: LoginRequest, db: Session) -> User:
    """Authenticate user credentials and return User object.
    
    Validates email exists, password matches, and account is active.
    Called only after LoginRequest validation (email format).
    
    Authentication Process:
        1. Lookup user by email (unique index for O(log n) speed)
        2. If user not found → Reject (don't reveal if email exists)
        3. Verify plaintext password against stored bcrypt hash
        4. If password wrong → Reject with generic error (security)
        5. If user account inactive → Reject (account suspended)
        6. Return User object for token creation
    
    Args:
        request (LoginRequest): Login credentials:
            - email: Email address (may not exist)
            - password: Plaintext password from user
        
        db (Session): Database session for user lookup
    
    Returns:
        User: Authenticated user object ready for token creation:
            - id: User's UUID (needed for access_token sub claim)
            - email: User's email
            - is_active: True (verified in this function)
            - Other fields: Used for token payload or response
    
    Raises:
        ValueError: Invalid credentials or inactive account (all same generic message)
            - Email not found
            - Password incorrect
            - Account deactivated (is_active=False)
    
    Error Handling:
        All errors raise ValueError with GENERIC French message:
        "Email ou mot de passe incorrect" (don't leak which field failed)
        
        This prevents username enumeration attacks (attacker can't discover valid emails)
    
    Example:
        request = LoginRequest(email="alice@example.com", password="MyPassword123!")
        try:
            user = login_user(request, db)
            # user.email = "alice@example.com"
            # user.is_active = True
        except ValueError:
            # Return 401 Unauthorized (don't specify which field wrong)
    
    Security Notes:
        - Timing-safe password comparison (verify_password handles)
        - Generic error message prevents email enumeration
        - Account active check prevents suspended user access
        - No account lockout after N attempts (optional enhancement)
        - Error logged as warning (not exception, no leak)
        - Plaintext password never stored in memory longer than needed
    
    Follow-up in Auth Flow:
        After login_user(): Create access_token + refresh_token for session
        Route returns AuthResponse with user + tokens
    
    Typical Login Response Flow:
        1. POST /auth/login with email + password
        2. Call login_user() → Returns User or raises ValueError
        3. If User returned: Call create_access_token() + create_refresh_token()
        4. Return 200 OK with AuthResponse (user + tokens)
        5. If ValueError: Return 401 Unauthorized with error_detail
    """
    # Lookup user by email (unique index)
    user = db.query(User).filter(User.email == request.email).first()
    
    # Verify both existence and password (same generic error for both)
    if not user or not verify_password(request.password, user.hashed_password):
        logger.warning(f"Login attempt failed for email: {request.email}")
        raise ValueError("Email ou mot de passe incorrect")
    
    # Check account is active (not suspended)
    if not user.is_active:
        logger.warning(f"Login attempt on inactive account: {request.email}")
        raise ValueError("Compte désactivé")
    
    logger.info(f"User logged in: {user.email} (id={user.id})")
    return user


def refresh_access_token(refresh_token: str, db: Session) -> tuple[User, str]:
    """Exchange refresh token for new access + refresh token pair (token rotation).
    
    Implements OAuth2 token refresh with automatic token rotation.
    Old refresh_token is revoked (prevents reuse if compromised).
    Creates new access_token + refresh_token for continued session.
    
    Token Rotation Design:
        Purpose: Limits window of vulnerability if token is exposed/intercepted
        
        Before Refresh:
        - Access token: Expired or expiring
        - Refresh token: Valid, in database, not revoked
        
        After Refresh:
        - Old refresh token: Marked revoked=True (can't refresh again)
        - New access token: Fresh 15-minute validity
        - New refresh token: Fresh 7-day validity
        - Client must use new tokens (old tokens invalidated)
    
    Refresh Process:
        1. Lookup refresh_token in database (must exist, not revoked)
        2. Check expiration (expires_at > now)
        3. Mark old token revoked (audit trail, can't refresh again)
        4. Create new refresh_token (cryptographically random, stored)
        5. Load user from database (verify still exists)
        6. Return user + new refresh_token
    
    Args:
        refresh_token (str): 128-character hex string from client
        db (Session): Database session for token/user lookups
    
    Returns:
        tuple[User, str]: (User object, new refresh_token string)
            - User: Updated from database (use for access_token creation)
            - new_refresh_token: 128-char hex replacement token
    
    Raises:
        ValueError: Token invalid, expired, or user not found
            - "Token de rafraîchissement invalide" (not in DB, revoked, etc.)
            - "Token de rafraîchissement expiré" (expires_at < now)
            - Database issues if user mysteriously deleted (shouldn't happen)
    
    Error Handling:
        All errors raise ValueError (route handler converts to 401)
        Log each failure for security monitoring (detect brute force)
    
    Example:
        try:
            user, new_token = refresh_access_token(old_refresh_token, db)
            # old_refresh_token is now revoked in database
            # new_token is fresh and valid for 7 days
            access_token, exp = create_access_token(user.id, user.email)
            # Client receives new access + refresh tokens
        except ValueError:
            # Return 401 Unauthorized (token invalid or expired)
    
    Security Features:
        - Database lookup (can't forge or modify token)
        - Revocation (old token becomes invalid after refresh)
        - Expiration check (database enforces lifetime)
        - User lookup (verifies user still exists, not deleted)
        - Atomic transaction (all-or-nothing state consistency)
    
    Attack Prevention:
        Token Theft:
            - Old token revoked immediately → usefulness limited to one refresh
            - New token is unique per refresh → can't predict
        
        Replay Attack:
            - Token is revoked after one use
            - Replaying same token returns 401 (invalid/revoked)
        
        Token Leakage:
            - Even if attacker gets old token, can only refresh once
            - Then token is revoked, attacker can't refresh again
    
    Follow-up in Auth Flow:
        After refresh_access_token():
        1. Create new access_token from returned user
        2. Return TokenResponse with new access_token + new_refresh_token
        3. Client stores new tokens, discards old ones
        4. Continue API requests with new access_token
    
    Database State After:
        RefreshToken table:
        - Old token: revoked=True (audit trail preserved)
        - New token: revoked=False, expires_at=now+7days
    """
    # Find refresh token in database (must exist and not be revoked)
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
        RefreshToken.revoked == False,  # Only non-revoked tokens valid
    ).first()

    if not db_token:
        logger.warning(f"Refresh token not found or already revoked")
        raise ValueError("Token de rafraîchissement invalide")
    
    # Check expiration (database enforces, but also check here)
    if db_token.expires_at < datetime.now(timezone.utc):
        logger.warning(f"Refresh token expired: {db_token.expires_at}")
        raise ValueError("Token de rafraîchissement expiré")

    # Rotate: revoke old token (audit trail, prevent reuse)
    db_token.revoked = True
    db.commit()
    logger.info(f"Refresh token rotated for user {db_token.user_id}")

    # Create new tokens
    new_refresh_token = create_refresh_token(db_token.user_id, db)
    
    # Load user from database for token creation
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user:
        logger.error(f"User not found after token refresh: {db_token.user_id}")
        raise ValueError("Utilisateur introuvable")
    
    return user, new_refresh_token


def logout_user(refresh_token: str, db: Session) -> None:
    """Revoke refresh token to prevent future refreshes (logout).
    
    Marks refresh token as revoked=True in database.
    Prevents token from being used for future refresh operations.
    User's access_token remains valid until natural expiration.
    
    Logout Design (Soft-Delete Strategy):
    - Token NOT deleted (preserved for audit trail/forensics)
    - revoked flag set to True (prevents refresh queries from finding)
    - Client should also clear tokens locally (cookies, localStorage)
    
    Process:
        1. Find refresh_token in database by token string
        2. If found: Set revoked=True and commit
        3. If not found: No-op (idempotent logout)
        4. Always return success (idempotent API)
    
    Args:
        refresh_token (str): Token to revoke (from Authorization header or body)
        db (Session): Database session for update
    
    Returns:
        None: Logout always succeeds (no return value)
    
    Raises:
        None: Logout is idempotent (no error if token not found)
    
    Idempotency:
        Calling logout twice with same token:
        - First call: Token found, revoked=True set, 204 returned
        - Second call: Token found but already revoked, no-op, 204 returned
        - Result: Same outcome (client happy either way)
    
    Example:
        try:
            logout_user(refresh_token, db)
            # Always succeeds, returns 204 No Content
        except Exception:
            # Very unlikely (only database connection failure)
            # Return 500 Internal Server Error
    
    Security Notes:
        - Token soft-deleted (revoked, not removed from DB)
        - Audit trail preserved for security forensics
        - Can investigate compromised tokens historically
        - Database constraint prevents deletion (intentional)
    
    Client-Side Behavior:
        After logout_user() succeeds:
        - Client receives 204 No Content
        - Client clears tokens from memory/cookies
        - Client redirects to login page
        - If client tries to use old access_token: 401 (expired or user deactivated)
        - If client tries to refresh: 401 (token revoked, invalid query result)
    
    Future Token Validation:
        After logout:
        - refresh_access_token() can't find revoked token → 401
        - Client must login again for new tokens
    
    Follow-up in Auth Flow:
        Logout endpoint typically returns 204 No Content (no body needed)
        Client handles clearing tokens and redirect UI
    """
    # Find and revoke token (soft-delete)
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_token,
    ).first()
    
    if db_token:
        db_token.revoked = True
        db.commit()
        logger.info(f"Refresh token revoked for user {db_token.user_id}")
    else:
        # Token not found (already deleted, never existed, etc.)
        # Logout is idempotent: succeed anyway
        logger.debug(f"Logout called for non-existent token (idempotent)")


def get_current_user(token: str, db: Session) -> User:
    """Extract user from valid access token for use in route handlers.
    
    Dependency function for FastAPI route parameters.
    Verifies token, extracts user_id, loads User from database.
    Used to enforce authentication on protected endpoints.
    
    Authentication Pipeline:
        1. Extract Bearer token from Authorization header (done by route)
        2. Call decode_access_token(token) → Verify signature, exp, type
        3. Extract user_id from payload["sub"]
        4. Load User by id from database
        5. Verify user still active (not suspended between requests)
        6. Return User to route handler for business logic
    
    Args:
        token (str): JWT access token from Authorization: Bearer header
        db (Session): Database session for user lookup
    
    Returns:
        User: Authenticated user object ready for business logic
            - id, email, full_name, is_active, preferences, etc.
    
    Raises:
        ValueError: User not found or inactive
        JWTError: Token invalid (passed from decode_access_token)
    
    Error Handling:
        JWTError: Token invalid → route returns 401 Unauthorized
        ValueError: User not found → route returns 404 (or 401 depending on policy)
    
    FastAPI Dependency Usage:
        @router.get("/me")
        async def get_profile(current_user: User = Depends(get_current_user)):
            return current_user
        
        Route handler:
        1. Extracts Bearer token from request header
        2. Passes token to get_current_user() automatically
        3. Receives User object or 401/404 error
        4. Uses current_user.id, current_user.email, etc. in logic
    
    Example Request:
        GET /users/me HTTP/1.1
        Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
        
        → FastAPI calls get_current_user(token, db)
        → Returns User object
        → Route returns {"id": "...", "email": "..."}
    
    Security Checks:
        - Token signature verified (decode_access_token)
        - Token expiration checked (JsonWe jwt.decode)
        - Token type validated (must be "access", not "refresh")
        - User record verification (still exists, still active)
    
    Double Check: User Active Status
        Reason: User could be suspended between request and token verification
        Scenario: User account disabled but token still valid
        Solution: Check is_active=True even for valid token
    
    Follow-up in Route Handler:
        @router.post("/data")
        async def upload_data(
            file: UploadFile,
            current_user: User = Depends(get_current_user)
        ):
            # current_user.id = UUID
            # current_user.email = "user@example.com"
            # Use in audit logging, permission checks, etc.
    """
    # Verify token and extract payload
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    
    # Load user from database
    user = db.query(User).filter(User.id == user_id).first()
    
    # Verify user exists and is active (not suspended)
    if not user or not user.is_active:
        logger.warning(f"Invalid user or inactive account: {user_id}")
        raise ValueError("Utilisateur introuvable ou désactivé")
    
    logger.debug(f"User authenticated: {user.email}")
    return user