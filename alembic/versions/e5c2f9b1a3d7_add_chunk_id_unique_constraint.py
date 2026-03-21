"""add chunk_id column with UNIQUE constraint for deduplication

Fixes the broken ON CONFLICT DO NOTHING in store_chunks() which had no
unique constraint to conflict on. Adds chunk_id (MD5[:16] of content)
as a stable, content-addressed deduplication key.

Existing data is truncated: it contains duplicate chunks from every
re-upload because the previous constraint was missing.

Revision ID: e5c2f9b1a3d7
Revises: d3f8a1c2e9b5
Create Date: 2026-03-21 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e5c2f9b1a3d7"
down_revision: Union[str, Sequence[str], None] = "d3f8a1c2e9b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Truncate first: existing rows are duplicates because the UNIQUE constraint
    # was never in place, so ON CONFLICT DO NOTHING never fired.
    op.execute("TRUNCATE TABLE documents")

    # Add chunk_id: MD5(content)[:16], used as the deduplication key.
    # NOT NULL because every chunk must have a deterministic ID.
    op.add_column(
        "documents",
        sa.Column("chunk_id", sa.String(16), nullable=False, server_default=""),
    )

    # Remove the transient server_default now that the column exists
    op.alter_column("documents", "chunk_id", server_default=None)

    # Unique constraint: ON CONFLICT (chunk_id) DO NOTHING now works correctly
    op.create_unique_constraint("uq_documents_chunk_id", "documents", ["chunk_id"])


def downgrade() -> None:
    op.drop_constraint("uq_documents_chunk_id", "documents", type_="unique")
    op.drop_column("documents", "chunk_id")
