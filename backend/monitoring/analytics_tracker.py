"""Analytics event tracking utilities.

Best-effort, non-blocking style: all functions swallow errors and log warnings.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any

import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _conn_str() -> str:
    db_url = os.getenv("DATABASE_URL", "")
    return db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")


def log_analytics_event_sync(
    *,
    event_type: str,
    status: str = "success",
    user_id: str | None = None,
    session_id: str | None = None,
    task_id: str | None = None,
    duration_ms: float | None = None,
    file_type: str | None = None,
    file_size_bytes: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        conn = psycopg2.connect(_conn_str())
        cur = conn.cursor()

        now = datetime.now(timezone.utc)
        today = date.today()

        cur.execute(
            """
            INSERT INTO analytics_events (
                event_type, status, user_id, session_id, task_id,
                duration_ms, file_type, file_size_bytes, metadata, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_type,
                status,
                user_id,
                session_id,
                task_id,
                duration_ms,
                file_type,
                file_size_bytes,
                Json(metadata) if metadata is not None else None,
                now,
            ),
        )

        cur.execute(
            """
            INSERT INTO metrics_summary (
                summary_date, event_type, total_count, success_count, failure_count,
                avg_duration_ms, last_event_at
            ) VALUES (
                %s, %s, 1, %s, %s, %s, %s
            )
            ON CONFLICT (summary_date, event_type)
            DO UPDATE SET
                total_count = metrics_summary.total_count + 1,
                success_count = metrics_summary.success_count + EXCLUDED.success_count,
                failure_count = metrics_summary.failure_count + EXCLUDED.failure_count,
                avg_duration_ms = CASE
                    WHEN EXCLUDED.avg_duration_ms IS NULL THEN metrics_summary.avg_duration_ms
                    WHEN metrics_summary.avg_duration_ms IS NULL THEN EXCLUDED.avg_duration_ms
                    ELSE ((metrics_summary.avg_duration_ms * metrics_summary.total_count) + EXCLUDED.avg_duration_ms)
                         / (metrics_summary.total_count + 1)
                END,
                last_event_at = EXCLUDED.last_event_at
            """,
            (
                today,
                event_type,
                1 if status == "success" else 0,
                1 if status != "success" else 0,
                duration_ms,
                now,
            ),
        )

        conn.commit()
        cur.close()
        conn.close()
    except Exception as err:
        logger.warning(f"Analytics event logging failed (non-blocking): {err}")


def get_analytics_summary_sync(days: int = 7) -> dict[str, Any]:
    try:
        conn = psycopg2.connect(_conn_str())
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                event_type,
                SUM(total_count) AS total_count,
                SUM(success_count) AS success_count,
                SUM(failure_count) AS failure_count,
                AVG(avg_duration_ms) AS avg_duration_ms
            FROM metrics_summary
            WHERE summary_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
            GROUP BY event_type
            ORDER BY total_count DESC
            """,
            (days,),
        )
        by_event = [
            {
                "event_type": row[0],
                "total_count": int(row[1] or 0),
                "success_count": int(row[2] or 0),
                "failure_count": int(row[3] or 0),
                "avg_duration_ms": float(row[4]) if row[4] is not None else None,
            }
            for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT
                COALESCE(SUM(total_count), 0),
                COALESCE(SUM(success_count), 0),
                COALESCE(SUM(failure_count), 0)
            FROM metrics_summary
            WHERE summary_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
            """,
            (days,),
        )
        totals = cur.fetchone() or (0, 0, 0)

        cur.close()
        conn.close()

        total_count = int(totals[0] or 0)
        success_count = int(totals[1] or 0)
        failure_count = int(totals[2] or 0)

        return {
            "window_days": days,
            "total_events": total_count,
            "success_events": success_count,
            "failure_events": failure_count,
            "success_rate": (success_count / total_count) if total_count else 0.0,
            "events_by_type": by_event,
        }
    except Exception as err:
        logger.warning(f"Analytics summary fetch failed (non-blocking): {err}")
        return {
            "window_days": days,
            "total_events": 0,
            "success_events": 0,
            "failure_events": 0,
            "success_rate": 0.0,
            "events_by_type": [],
            "error": str(err),
        }


def get_analytics_dashboard_cards_sync(days: int = 7) -> dict[str, Any]:
    summary = get_analytics_summary_sync(days=days)
    event_map = {item["event_type"]: item for item in summary.get("events_by_type", [])}

    def _count(event_type: str) -> int:
        return int(event_map.get(event_type, {}).get("total_count", 0))

    analysis_event = event_map.get("analysis_requested", {})
    execution_event = event_map.get("task_execution", {})

    return {
        "window_days": days,
        "cards": {
            "signups": _count("user_signup"),
            "logins": _count("user_login"),
            "uploads": _count("file_upload"),
            "analysis_requests": _count("analysis_requested"),
            "task_success_rate": (
                execution_event.get("success_count", 0) / execution_event.get("total_count", 1)
                if execution_event.get("total_count", 0)
                else 0.0
            ),
            "analysis_avg_duration_ms": analysis_event.get("avg_duration_ms"),
        },
    }


def get_upload_distribution_sync(days: int = 7) -> dict[str, Any]:
    try:
        conn = psycopg2.connect(_conn_str())
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                COALESCE(file_type, 'unknown') AS file_type,
                COUNT(*) AS upload_count,
                COALESCE(SUM(file_size_bytes), 0) AS total_bytes,
                AVG(file_size_bytes) AS avg_size_bytes,
                MAX(file_size_bytes) AS max_size_bytes
            FROM analytics_events
            WHERE event_type = 'file_upload'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY COALESCE(file_type, 'unknown')
            ORDER BY upload_count DESC
            """,
            (days,),
        )

        rows = cur.fetchall()
        items = [
            {
                "file_type": row[0],
                "upload_count": int(row[1] or 0),
                "total_bytes": int(row[2] or 0),
                "avg_size_bytes": float(row[3]) if row[3] is not None else None,
                "max_size_bytes": int(row[4]) if row[4] is not None else None,
            }
            for row in rows
        ]

        cur.close()
        conn.close()

        return {
            "window_days": days,
            "total_uploads": sum(item["upload_count"] for item in items),
            "by_file_type": items,
        }
    except Exception as err:
        logger.warning(f"Upload distribution fetch failed (non-blocking): {err}")
        return {
            "window_days": days,
            "total_uploads": 0,
            "by_file_type": [],
            "error": str(err),
        }


def get_user_activity_overview_sync(user_id: str, days: int = 7) -> dict[str, Any]:
    try:
        conn = psycopg2.connect(_conn_str())
        cur = conn.cursor()

        cur.execute(
            """
            SELECT event_type, COUNT(*)
            FROM analytics_events
            WHERE user_id = %s
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            GROUP BY event_type
            """,
            (user_id, days),
        )
        event_counts = {row[0]: int(row[1] or 0) for row in cur.fetchall()}

        cur.execute(
            """
            SELECT COALESCE(SUM(file_size_bytes), 0)
            FROM analytics_events
            WHERE user_id = %s
              AND event_type = 'file_upload'
              AND created_at >= NOW() - (%s * INTERVAL '1 day')
            """,
            (user_id, days),
        )
        total_upload_bytes = int((cur.fetchone() or [0])[0] or 0)

        cur.close()
        conn.close()

        return {
            "window_days": days,
            "user_id": user_id,
            "cards": {
                "logins": event_counts.get("user_login", 0),
                "uploads": event_counts.get("file_upload", 0),
                "analysis_requests": event_counts.get("analysis_requested", 0),
                "cancellations": event_counts.get("task_canceled", 0),
                "total_upload_bytes": total_upload_bytes,
            },
            "events_by_type": [
                {"event_type": key, "count": value}
                for key, value in sorted(event_counts.items())
            ],
        }
    except Exception as err:
        logger.warning(f"User activity overview fetch failed (non-blocking): {err}")
        return {
            "window_days": days,
            "user_id": user_id,
            "cards": {
                "logins": 0,
                "uploads": 0,
                "analysis_requests": 0,
                "cancellations": 0,
                "total_upload_bytes": 0,
            },
            "events_by_type": [],
            "error": str(err),
        }


def get_analysis_performance_timeseries_sync(days: int = 7) -> dict[str, Any]:
    try:
        conn = psycopg2.connect(_conn_str())
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                summary_date,
                event_type,
                total_count,
                success_count,
                failure_count,
                avg_duration_ms
            FROM metrics_summary
            WHERE summary_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
              AND event_type IN ('analysis_requested', 'task_execution')
            ORDER BY summary_date ASC
            """,
            (days,),
        )

        rows = cur.fetchall()
        cur.close()
        conn.close()

        daily: dict[str, dict[str, Any]] = {}
        for summary_date, event_type, total_count, success_count, failure_count, avg_duration_ms in rows:
            key = summary_date.isoformat()
            if key not in daily:
                daily[key] = {
                    "date": key,
                    "analysis_requests": 0,
                    "analysis_avg_duration_ms": None,
                    "task_executions": 0,
                    "task_success_rate": None,
                }

            if event_type == "analysis_requested":
                daily[key]["analysis_requests"] = int(total_count or 0)
                daily[key]["analysis_avg_duration_ms"] = float(avg_duration_ms) if avg_duration_ms is not None else None
            elif event_type == "task_execution":
                total = int(total_count or 0)
                success = int(success_count or 0)
                daily[key]["task_executions"] = total
                daily[key]["task_success_rate"] = (success / total) if total else None

        return {
            "window_days": days,
            "series": [daily[k] for k in sorted(daily.keys())],
        }
    except Exception as err:
        logger.warning(f"Analysis performance series fetch failed (non-blocking): {err}")
        return {
            "window_days": days,
            "series": [],
            "error": str(err),
        }
