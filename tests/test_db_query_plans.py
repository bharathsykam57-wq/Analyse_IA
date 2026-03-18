"""Database query-plan smoke checks for refresh token performance paths.

Purpose:
- Verify planner uses indexes for critical refresh token queries
- Surface regressions early after schema/migration changes

Usage:
  python tests/test_db_query_plans.py
  python tests/test_db_query_plans.py --database-url postgresql://...
  python tests/test_db_query_plans.py --env-file .env.local
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import psycopg2
from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check DB query plans for refresh token paths")
    parser.add_argument("--database-url", default="", help="PostgreSQL URL (defaults to DATABASE_URL env)")
    parser.add_argument("--env-file", default=".env.local", help="Optional env file to load first")
    return parser.parse_args()


def explain_lines(cur, sql: str) -> list[str]:
    cur.execute(f"EXPLAIN (COSTS OFF) {sql}")
    return [row[0] for row in cur.fetchall()]


def explain_lines_seqscan_off(cur, sql: str) -> list[str]:
    cur.execute("BEGIN")
    try:
        cur.execute("SET LOCAL enable_seqscan = off")
        cur.execute(f"EXPLAIN (COSTS OFF) {sql}")
        return [row[0] for row in cur.fetchall()]
    finally:
        cur.execute("ROLLBACK")


def plan_uses_index(plan_lines: list[str], index_name: str) -> bool:
    joined = "\n".join(plan_lines)
    pattern = rf"(Index Scan|Index Only Scan|Bitmap Index Scan).*{re.escape(index_name)}"
    return bool(re.search(pattern, joined, re.IGNORECASE))


def print_plan(title: str, lines: list[str]):
    print(f"\n[{title}]")
    for line in lines:
        print(f"  {line}")


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
            checks: list[tuple[str, list[str], str, bool, list[str] | None]] = []

            # 1) Token refresh lookup path
            q1 = (
                "SELECT * FROM refresh_tokens "
                "WHERE token = 'plan_probe_token' AND revoked = FALSE AND expires_at > NOW()"
            )
            p1 = explain_lines(cur, q1)
            p1_forced = explain_lines_seqscan_off(cur, q1)
            p1_ok = plan_uses_index(p1, "ix_refresh_tokens_token") or plan_uses_index(
                p1_forced, "ix_refresh_tokens_token"
            )
            checks.append((
                "refresh lookup by token",
                p1,
                "ix_refresh_tokens_token",
                p1_ok,
                p1_forced,
            ))

            # 2) Cleanup expired tokens candidate scan
            q2 = "SELECT id FROM refresh_tokens WHERE expires_at < NOW() - INTERVAL '7 days'"
            p2 = explain_lines(cur, q2)
            checks.append((
                "cleanup expired tokens",
                p2,
                "ix_refresh_tokens_expires_at",
                plan_uses_index(p2, "ix_refresh_tokens_expires_at"),
                None,
            ))

            # 3) Cleanup revoked token retention scan
            q3 = (
                "SELECT id FROM refresh_tokens "
                "WHERE revoked = TRUE AND created_at < NOW() - INTERVAL '30 days'"
            )
            p3 = explain_lines(cur, q3)
            # Index can be either (user-added) revoked_created_at or generic index that planner prefers.
            uses_revoked_created = plan_uses_index(p3, "ix_refresh_tokens_revoked_created_at")
            uses_revoked_expires = plan_uses_index(p3, "ix_refresh_tokens_revoked_expires_at")
            checks.append((
                "cleanup revoked retention",
                p3,
                "ix_refresh_tokens_revoked_created_at",
                uses_revoked_created,
                None,
            ))

        hard_fail = False
        for label, plan, expected_index, ok, forced_plan in checks:
            print_plan(label, plan)
            if forced_plan is not None:
                print_plan(f"{label} (seqscan off)", forced_plan)
            print(f"  expected index: {expected_index}")
            print(f"  index used: {'YES' if ok else 'NO'}")

            # Hard requirement for token lookup; warnings for cleanup paths.
            if label == "refresh lookup by token" and not ok:
                hard_fail = True

        if hard_fail:
            print("\nFAIL: critical token lookup path is not using expected index")
            return 1

        print("\nPASS: query plan smoke checks completed")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
