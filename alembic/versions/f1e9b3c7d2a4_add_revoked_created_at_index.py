"""add revoked_created_at index for refresh token cleanup

Revision ID: f1e9b3c7d2a4
Revises: c4b7e2d1a9f0
Create Date: 2026-03-18 23:28:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f1e9b3c7d2a4"
down_revision: Union[str, Sequence[str], None] = "c4b7e2d1a9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_refresh_tokens_revoked_created_at",
        "refresh_tokens",
        ["revoked", "created_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_revoked_created_at", table_name="refresh_tokens")
