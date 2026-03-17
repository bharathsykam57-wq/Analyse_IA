# Production Database Migration and Setup Script
# Usage: python scripts/production_setup.py --env .env.production

import os
import sys
import argparse
import subprocess
import psycopg2
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

def load_environment(env_file: str):
    """Load environment variables from .env file"""
    if not os.path.exists(env_file):
        logger.error(f"Environment file not found: {env_file}")
        sys.exit(1)
    
    load_dotenv(env_file)
    logger.info(f"✓ Loaded environment from {env_file}")

def verify_secrets() -> bool:
    """Verify all required secrets are set"""
    required = [
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "ENVIRONMENT",
    ]
    
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        return False
    
    if os.getenv("ENVIRONMENT") != "production":
        logger.warning(f"ENVIRONMENT is '{os.getenv('ENVIRONMENT')}' (expected 'production')")
    
    if len(os.getenv("JWT_SECRET_KEY", "")) < 32:
        logger.error("JWT_SECRET_KEY must be at least 32 characters")
        return False
    
    logger.info("✓ All required secrets verified")
    return True

def test_database_connection() -> bool:
    """Test PostgreSQL connection"""
    try:
        db_url = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"✓ Database connected: {version.split(',')[0]}")
        
        # Check pgvector extension
        cursor.execute("SELECT extname FROM pg_extension WHERE extname='vector'")
        if cursor.fetchone():
            logger.info("✓ pgvector extension installed")
        else:
            logger.warning("⚠ pgvector extension not installed (required for RAG)")
            logger.info("  → Run: CREATE EXTENSION vector;")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False

def test_redis_connection() -> bool:
    """Test Redis connection"""
    try:
        import redis
        redis_url = os.getenv("REDIS_URL")
        r = redis.from_url(redis_url)
        r.ping()
        logger.info(f"✓ Redis connected: {r.connection_pool}")
        return True
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        return False

def run_migrations() -> bool:
    """Run Alembic migrations"""
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        if result.returncode != 0:
            logger.error(f"✗ Migration failed: {result.stderr}")
            return False
        
        logger.info("✓ Database migrations completed")
        
        # Show migration status
        status_result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        if status_result.returncode == 0:
            logger.info(f"  → Current head: {status_result.stdout.strip()}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Migration error: {e}")
        return False

def verify_cors_configuration() -> bool:
    """Verify CORS configuration"""
    cors_origins = os.getenv("CORS_ORIGINS", "")
    
    if not cors_origins:
        logger.warning("⚠ CORS_ORIGINS not set (will default to http://localhost:3000)")
        return False
    
    origins = [o.strip() for o in cors_origins.split(",")]
    
    # Check for localhost in production
    if os.getenv("ENVIRONMENT") == "production":
        localhost_origins = [o for o in origins if "localhost" in o or "127.0.0.1" in o]
        if localhost_origins:
            logger.error(f"✗ Localhost URLs in CORS_ORIGINS (production): {localhost_origins}")
            return False
    
    logger.info(f"✓ CORS configured for: {', '.join(origins)}")
    return True

def create_upload_directory() -> bool:
    """Create upload directory if needed"""
    try:
        upload_dir = os.getenv("UPLOAD_DIR", "uploads")
        
        # Skip if cloud storage path
        if upload_dir.startswith("s3://") or upload_dir.startswith("gs://"):
            logger.info(f"✓ Cloud storage configured: {upload_dir}")
            return True
        
        os.makedirs(upload_dir, exist_ok=True)
        logger.info(f"✓ Upload directory ready: {upload_dir}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create upload directory: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Production setup and verification")
    parser.add_argument("--env", default=".env.production", help="Environment file path")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip database migrations")
    parser.add_argument("--verify-only", action="store_true", help="Only verify, don't migrate")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("PRODUCTION ENVIRONMENT SETUP")
    logger.info("=" * 60)
    
    # 1. Load environment
    load_environment(args.env)
    
    # 2. Verify secrets
    if not verify_secrets():
        sys.exit(1)
    
    # 3. Test connections
    logger.info("\n[CONNECTIONS]")
    db_ok = test_database_connection()
    redis_ok = test_redis_connection()
    
    if not db_ok or not redis_ok:
        logger.error("Fix connection issues before proceeding")
        sys.exit(1)
    
    # 4. Verify CORS
    logger.info("\n[SECURITY]")
    verify_cors_configuration()
    
    # 5. Setup uploads
    logger.info("\n[FILE STORAGE]")
    create_upload_directory()
    
    # 6. Run migrations
    if not args.verify_only:
        logger.info("\n[DATABASE]")
        if not args.skip_migrations:
            if not run_migrations():
                logger.error("Migration failed. Fix issues and retry.")
                sys.exit(1)
        else:
            logger.info("⊘ Migrations skipped (use --skip-migrations to force)")
    
    logger.info("\n" + "=" * 60)
    logger.info("✓ Production environment ready!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Deploy backend to Railway")
    logger.info("2. Deploy frontend with NEXT_PUBLIC_API_URL set")
    logger.info("3. Run tests/test_production_auth.py")
    logger.info("4. Monitor Railway logs")

if __name__ == "__main__":
    main()
