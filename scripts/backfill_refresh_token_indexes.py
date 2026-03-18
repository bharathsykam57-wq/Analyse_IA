"""Idempotent backfill utility for refresh_tokens indexes.

Use this when a migration was marked as applied but indexes are missing.
Safe to run multiple times.

Usage:
  python scripts/backfill_refresh_token_indexes.py
  python scripts/backfill_refresh_token_indexes.py --env-file .env.production
"""

from __future__ import annotations

import argparse
import os

import psycopg2
from dotenv import load_dotenv


DDL_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON public.refresh_tokens (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires_at ON public.refresh_tokens (expires_at)",
    "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_revoked_expires_at ON public.refresh_tokens (revoked, expires_at)",
    "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_revoked_created_at ON public.refresh_tokens (revoked, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id_revoked ON public.refresh_tokens (user_id, revoked)",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill refresh token indexes")
    parser.add_argument("--database-url", default="", help="PostgreSQL URL (defaults to DATABASE_URL env)")
    parser.add_argument("--env-file", default=".env.local", help="Optional env file to load first")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.env_file and os.path.exists(args.env_file):
        load_dotenv(args.env_file)

    db_url = args.database_url or os.getenv("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL missing")
        return 1

    conn = psycopg2.connect(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                for ddl in DDL_STATEMENTS:
                    cur.execute(ddl)
        print("PASS: refresh_tokens indexes backfilled")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
