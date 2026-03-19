"""Rebuild metrics_summary from analytics_events.

Useful as periodic maintenance or repair command.

Usage:
  python scripts/rebuild_metrics_summary.py --days 30
  python scripts/rebuild_metrics_summary.py --full
"""

from __future__ import annotations

import argparse
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def _conn_str() -> str:
    db_url = os.getenv("DATABASE_URL", "")
    return db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild metrics_summary table")
    parser.add_argument("--days", type=int, default=30, help="Rebuild rolling window (days)")
    parser.add_argument("--full", action="store_true", help="Rebuild full table from all events")
    args = parser.parse_args()

    conn = psycopg2.connect(_conn_str())
    cur = conn.cursor()

    try:
        if args.full:
            cur.execute("DELETE FROM metrics_summary")
            cur.execute(
                """
                INSERT INTO metrics_summary (
                    summary_date, event_type, total_count, success_count,
                    failure_count, avg_duration_ms, last_event_at
                )
                SELECT
                    (created_at AT TIME ZONE 'UTC')::date AS summary_date,
                    event_type,
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN status <> 'success' THEN 1 ELSE 0 END) AS failure_count,
                    AVG(duration_ms) AS avg_duration_ms,
                    MAX(created_at) AS last_event_at
                FROM analytics_events
                GROUP BY (created_at AT TIME ZONE 'UTC')::date, event_type
                """
            )
            print("PASS: rebuilt full metrics_summary table")
        else:
            cur.execute(
                "DELETE FROM metrics_summary WHERE summary_date >= CURRENT_DATE - (%s * INTERVAL '1 day')",
                (args.days,),
            )
            cur.execute(
                """
                INSERT INTO metrics_summary (
                    summary_date, event_type, total_count, success_count,
                    failure_count, avg_duration_ms, last_event_at
                )
                SELECT
                    (created_at AT TIME ZONE 'UTC')::date AS summary_date,
                    event_type,
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN status <> 'success' THEN 1 ELSE 0 END) AS failure_count,
                    AVG(duration_ms) AS avg_duration_ms,
                    MAX(created_at) AS last_event_at
                FROM analytics_events
                WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                GROUP BY (created_at AT TIME ZONE 'UTC')::date, event_type
                """,
                (args.days,),
            )
            print(f"PASS: rebuilt metrics_summary for last {args.days} days")

        conn.commit()
        return 0
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
