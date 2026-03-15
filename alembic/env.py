"""Alembic migration environment configuration for Analyse_IA.

Configures SQLAlchemy and Alembic for both online (normal) and offline
(SQL script generation) migration modes. Supports autogenerate for detecting
model changes and generating migration scripts automatically.

Environment Setup:
- Loads .env configuration for database credentials
- Injects project root into sys.path for backend module imports
- Configures logging from alembic.ini
- Links SQLAlchemy Base metadata for autogenerate support

Migration Modes:
- Offline: Emit SQL to stdout without connecting to database (CI/CD preview)
- Online: Connect to database and apply migrations in transaction

Usage:
    alembic revision --autogenerate -m "Add user table"
    alembic upgrade head
    alembic downgrade -1
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from alembic.config import Config

import os
import sys
from dotenv import load_dotenv

load_dotenv()  # Load DATABASE_URL and other config from .env
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # Add project root for backend imports

# Import SQLAlchemy Base containing all model metadata (required for autogenerate)
from backend.api.auth.models import Base

# Get Alembic configuration from alembic.ini
config = context.config

# Override database URL from environment variable (.env)
# Allows migrations to use DATABASE_URL from environment instead of hardcoded alembic.ini
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", ""))

# Configure logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy metadata for autogenerate support
# Alembic compares current model definitions against database schema
# and generates migration scripts for schema changes (add table, add column, etc.)
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Execute migrations in offline mode: generate SQL without database connection.
    
    Offline mode creates SQL migration scripts without connecting to database.
    Useful for:
    - Code review of generated SQL before applying
    - CI/CD pipelines that need to preview migrations
    - Environments without direct database access
    
    Output: SQL statements printed to stdout that can be manually reviewed/executed
    """
    url = config.get_main_option("sqlalchemy.url")
    # Configure offline context: use URL only, no Engine needed
    # literal_binds=True: Convert SQL parameters to literal values (no placeholders)
    # dialect_opts: PostgreSQL-specific options for paramstyle
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    # Execute migrations within transaction context
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Execute migrations in online mode: connect to database and apply directly.
    
    Online mode is the standard migration mode:
    - Connects to database via SQLAlchemy Engine
    - Applies migration scripts within database transaction
    - Rolls back automatically if any migration fails
    
    Configuration: Uses DATABASE_URL for Supabase Transaction Pooler (port 6543)
    Connection Pool: NullPool (no pooling) for migration safety
    SSL: Required for Supabase cloud connections
    Timeout: Optimized for Transaction Pooler's idle timeout (~15 seconds)
    """
    from sqlalchemy import create_engine
    
    url = config.get_main_option("sqlalchemy.url")
    
    # Create engine with explicit configuration for Supabase Transaction Pooler
    # Transaction Pooler (port 6543) characteristics:
    # - Idle timeout ~15 seconds (set keepalives_idle lower to maintain connection)
    # - Better for short-lived connections
    # - NullPool: no pooling - essential for Alembic compatibility
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args={
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 5,  # Reduced to avoid pooler baseline timeout
        }
    )

    try:
        # Execute migrations within transaction: all-or-nothing atomicity
        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        # Ensure proper cleanup to avoid hanging on Transaction Pooler
        connectable.dispose(close=True)


# Route to appropriate migration mode based on context
if context.is_offline_mode():
    run_migrations_offline()  # Generate SQL script (no database connection)
else:
    run_migrations_online()  # Apply migrations to database (requires connection)
