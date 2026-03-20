from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from typing import Generator
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")

# --- MANUAL FIX: Lazy Engine Initialization ---
if not DATABASE_URL:
    logger.warning("DATABASE_URL not set. Engine initialized as None for CI/CD compatibility.")
    engine = None
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
        connect_args={
            "connect_timeout": 10,
            "application_name": "analyse_ia_api",
        }
    )

# bind=engine will be None if DATABASE_URL is missing, preventing early crashes
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db() -> Generator[Session, None, None]:
    """Provides a database session with a safety check for initialization."""
    # --- MANUAL FIX: Raise error ONLY when the database is actually requested ---
    if engine is None:
        raise ImportError(
            "Database engine is not initialized. Please set the DATABASE_URL environment variable."
        )
        
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.exception(f"Database error in request: {e}")
        db.rollback()
        raise
    finally:
        db.close()