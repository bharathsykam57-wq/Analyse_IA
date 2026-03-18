"""optimize refresh token indexes

Revision ID: c4b7e2d1a9f0
Revises: a7c1d2e9f4b3
Create Date: 2026-03-18 23:12:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4b7e2d1a9f0"
down_revision: Union[str, Sequence[str], None] = "a7c1d2e9f4b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Supports fast cleanup scans and admin/session queries.
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires_at ON refresh_tokens (expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_revoked_expires_at ON refresh_tokens (revoked, expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id_revoked ON refresh_tokens (user_id, revoked)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_user_id_revoked")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_revoked_expires_at")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_expires_at")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_user_id")
