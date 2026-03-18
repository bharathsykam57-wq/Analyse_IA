"""Cleanup expired/revoked refresh tokens.

Purpose:
- Reduce refresh_tokens table growth over time
- Keep lookup/query performance stable
- Preserve short forensic retention windows before deletion

Usage:
  python scripts/cleanup_refresh_tokens.py --dry-run
  python scripts/cleanup_refresh_tokens.py
  python scripts/cleanup_refresh_tokens.py --expired-retention-days 14 --revoked-retention-days 45

Recommended scheduling:
- Run daily via cron or Railway scheduled job.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup stale refresh tokens")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="PostgreSQL connection URL (defaults to DATABASE_URL env)",
    )
    parser.add_argument(
        "--expired-retention-days",
        type=int,
        default=7,
        help="Delete expired tokens older than this many days (default: 7)",
    )
    parser.add_argument(
        "--revoked-retention-days",
        type=int,
        default=30,
        help="Delete revoked tokens older than this many days (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show counts only without deleting",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.database_url:
        print("ERROR: DATABASE_URL is required (env or --database-url)")
        return 1

    now = datetime.now(timezone.utc)
    expired_before = now - timedelta(days=args.expired_retention_days)
    revoked_before = now - timedelta(days=args.revoked_retention_days)

    engine = create_engine(args.database_url, pool_pre_ping=True)

    count_sql = text(
        """
        SELECT COUNT(*)
        FROM refresh_tokens
        WHERE expires_at < :expired_before
           OR (revoked = TRUE AND created_at < :revoked_before)
        """
    )

    delete_sql = text(
        """
        DELETE FROM refresh_tokens
        WHERE expires_at < :expired_before
           OR (revoked = TRUE AND created_at < :revoked_before)
        """
    )

    params = {
        "expired_before": expired_before,
        "revoked_before": revoked_before,
    }

    with engine.begin() as conn:
        to_delete = int(conn.execute(count_sql, params).scalar() or 0)

        print("Refresh token cleanup")
        print(f"  now: {now.isoformat()}")
        print(f"  expired_before: {expired_before.isoformat()}")
        print(f"  revoked_before: {revoked_before.isoformat()}")
        print(f"  candidates: {to_delete}")

        if args.dry_run:
            print("  mode: dry-run (no deletion)")
            return 0

        result = conn.execute(delete_sql, params)
        deleted = int(result.rowcount or 0)
        print(f"  deleted: {deleted}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
