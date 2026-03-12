"""FastAPI dependency injection for database session management.

This module provides reusable dependency functions for FastAPI route handlers.
Dependencies inject common resources (database sessions, current user, etc.) 
automatically without explicit function parameter passing.

Database Session Management:
- Provides SQLAlchemy Session instances to route handlers
- Handles connection pooling and resource cleanup
- Uses context manager pattern for guaranteed cleanup

Connection Pool Configuration:
- pool_pre_ping=True: Verify connections before use (prevents stale connections)
- Connections automatically closed after route completion
- NullPool used in migrations to prevent Alembic conflicts

FastAPI Integration:
- Dependencies are injected via Depends() in route parameters
- Sessions are tied to request lifecycle (created → used → closed)
- Automatic rollback on exceptions without explicit handling

Usage in Routes:
    from fastapi import Depends
    from sqlalchemy.orm import Session
    
    @router.get("/users/{user_id}")
    async def get_user(user_id: int, db: Session = Depends(get_db)):
        return db.query(User).filter(User.id == user_id).first()
    
    # FastAPI automatically:
    # 1. Calls get_db() for each request
    # 2. Injects session into db parameter
    # 3. Calls finally block to close session

Example Dependency Chain:
    @router.post("/auth/register")
    async def register(
        request: RegisterRequest,
        db: Session = Depends(get_db),  # Database session
        current_user: User = Depends(get_current_user)  # Current authenticated user
    ):
        # Route receives both injected dependencies
        pass
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from typing import Generator
from dotenv import load_dotenv
import os
import logging

# Load environment variables from .env BEFORE any os.getenv() calls
# This must happen at module import time, not deferred to main.py
load_dotenv()

logger = logging.getLogger(__name__)

# Load database URL from environment variable (.env or system env)
# Must be in format: postgresql://user:password@host:port/database
DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    logger.warning(
        "DATABASE_URL not set. Please set DATABASE_URL environment variable. "
        "Example: postgresql://user:password@localhost:5432/analyse_ia"
    )

# SQLAlchemy Engine Configuration
# ============================================================================
# Purpose: Manages database connection pool and SQL execution
#
# Configuration Details:
# - pool_pre_ping=True: Execute "SELECT 1" before using connection
#   Detects stale connections that were closed by database server
#   Prevents "lost connection" errors during request processing
#
# - echo=False: Disable SQL logging in production
#   Set to True in development for debugging (logs all SQL statements)
#
# Connection Pool:
# - QueuePool (default): Thread-safe queue of reusable connections
# - pool_size=5: Maintain 5 idle connections ready
# - max_overflow=10: Allow up to 10 additional connections under load
# - pool_recycle=3600: Recycle connections after 1 hour (MySQL/PostgreSQL timeout)
# - pool_pre_ping=True: Verify connection alive before use

engine = create_engine(
    DATABASE_URL,
    # Connection pooling and validation
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    # Disable SQL echo in production (enable in development for debugging)
    echo=False,
    # PostgreSQL-specific
    connect_args={
        "connect_timeout": 10,  # Fail fast if database unreachable
        "application_name": "analyse_ia_api",  # Track connections in pg_stat_activity
    }
)

# Session Factory: Creates new Session instances bound to engine
# ============================================================================
# autocommit=False: Manual transaction control (preferred for most apps)
# autoflush=False: Explicit flush() calls (prevents unexpected database writes)
# bind=engine: Connect session to engine for SQL execution
#
# Each new SessionLocal() call creates a new database session
# Perfect for dependency injection in FastAPI (one session per request)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# ============================================================================
# Dependency Functions
# ============================================================================



def get_db() -> Generator[Session, None, None]:
    """Provide SQLAlchemy Session for database operations in route handlers.
    
    FastAPI Dependency: Automatically called for routes that request db parameter.
    Handles connection pooling, transaction management, and cleanup.
    
    Lifecycle (per HTTP request):
        1. FastAPI calls get_db() to create Session instance
        2. Session is yielded to route handler for database operations
        3. Route handler executes and modifies database (uncommitted)
        4. After route returns, finally block is executed
        5. Session is closed (uncommitted changes are rolled back)
        
    Transaction Behavior:
        - autocommit=False: Each query is NOT auto-committed
        - Manual db.commit() required to persist changes
        - If exception occurs before commit(), changes are rolled back
        - Finally block ensures connection returns to pool
    
    Usage in Routes:
        from fastapi import APIRouter, Depends
        from sqlalchemy.orm import Session
        
        router = APIRouter()
        
        @router.get("/users/{user_id}")
        async def get_user(user_id: int, db: Session = Depends(get_db)):
            # db is automatically injected from get_db()
            user = db.query(User).filter(User.id == user_id).first()
            return user  # Automatic serialization to JSON
        
        @router.post("/users")
        async def create_user(
            req: CreateUserRequest,
            db: Session = Depends(get_db)
        ):
            # Create user object
            user = User(email=req.email, full_name=req.full_name)
            db.add(user)  # Stage for insert
            db.commit()   # Execute INSERT
            db.refresh(user)  # Reload from DB (populate id, created_at)
            return user
    
    Error Handling:
        If exception occurs:
        - Uncommitted changes are rolled back
        - Connection closed and returned to pool
        - Exception propagates to FastAPI error handlers
        - Client receives error response (400, 500, etc.)
    
    Performance Notes:
        - Connection reused from pool (not reconnected per request)
        - pool_pre_ping prevents "lost connection" errors
        - pool_recycle=3600 handles database timeout settings
        - Multiple requests can use different connections concurrently
    
    Yields:
        Session: SQLAlchemy session bound to engine, ready for queries
        
    Example Transaction Flow:
        Request 1:
        - get_db() → Session A
        - INSERT user → db.add(), db.commit() → COMMITTED
        - Finally → Session A closed to pool
        
        Request 2:
        - get_db() → Session A (or B, reused from pool)
        - SELECT * FROM users → Returns data including Request 1 insert
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # Log unexpected errors (optional, FastAPI logs by default)
        logger.exception(f"Database error in request: {e}")
        # Rollback any pending transactions to avoid connection corruption
        db.rollback()
        raise
    finally:
        # Always close: return connection to pool, release locks
        db.close()