"""Production database index verification for Task 10.

Checks that refresh_tokens optimization indexes exist.

Usage:
  python tests/test_production_db_indexes.py
  python tests/test_production_db_indexes.py --database-url postgresql://...
  python tests/test_production_db_indexes.py --env-file .env.production
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv


EXPECTED_INDEXES = {
    "ix_refresh_tokens_token",
    "ix_refresh_tokens_user_id",
    "ix_refresh_tokens_expires_at",
    "ix_refresh_tokens_revoked_expires_at",
    "ix_refresh_tokens_revoked_created_at",
    "ix_refresh_tokens_user_id_revoked",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify production DB indexes")
    parser.add_argument(
        "--database-url",
        default="",
        help="PostgreSQL URL (defaults to DATABASE_URL env)",
    )
    parser.add_argument(
        "--env-file",
        default=".env.local",
        help="Optional env file to load first (default: .env.local)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.env_file and os.path.exists(args.env_file):
        load_dotenv(args.env_file)

    db_url = args.database_url or os.getenv("DATABASE_URL", "")
    if not db_url:
        print("FAIL: DATABASE_URL not set (use --database-url or --env-file)")
        return 1

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'refresh_tokens'
                """
            )
            found = {row[0] for row in cur.fetchall()}

        missing = sorted(EXPECTED_INDEXES - found)

        print("refresh_tokens index verification")
        print(f"  expected: {len(EXPECTED_INDEXES)}")
        print(f"  found:    {len(found)}")

        if missing:
            print("FAIL: missing indexes:")
            for name in missing:
                print(f"  - {name}")
            return 1

        print("PASS: all expected refresh_tokens indexes present")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
