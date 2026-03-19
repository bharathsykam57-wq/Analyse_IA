"""add analytics_events and metrics_summary tables

Revision ID: b2a6d9e4c1f7
Revises: f1e9b3c7d2a4
Create Date: 2026-03-19 09:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2a6d9e4c1f7"
down_revision: Union[str, Sequence[str], None] = "f1e9b3c7d2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("file_type", sa.String(length=32), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"], unique=False)
    op.create_index("ix_analytics_events_status", "analytics_events", ["status"], unique=False)
    op.create_index("ix_analytics_events_user_id", "analytics_events", ["user_id"], unique=False)
    op.create_index("ix_analytics_events_created_at", "analytics_events", ["created_at"], unique=False)

    op.create_table(
        "metrics_summary",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_duration_ms", sa.Float(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_unique_constraint(
        "uq_metrics_summary_date_event",
        "metrics_summary",
        ["summary_date", "event_type"],
    )
    op.create_index("ix_metrics_summary_date", "metrics_summary", ["summary_date"], unique=False)
    op.create_index("ix_metrics_summary_event_type", "metrics_summary", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_metrics_summary_event_type", table_name="metrics_summary")
    op.drop_index("ix_metrics_summary_date", table_name="metrics_summary")
    op.drop_constraint("uq_metrics_summary_date_event", "metrics_summary", type_="unique")
    op.drop_table("metrics_summary")

    op.drop_index("ix_analytics_events_created_at", table_name="analytics_events")
    op.drop_index("ix_analytics_events_user_id", table_name="analytics_events")
    op.drop_index("ix_analytics_events_status", table_name="analytics_events")
    op.drop_index("ix_analytics_events_event_type", table_name="analytics_events")
    op.drop_table("analytics_events")
