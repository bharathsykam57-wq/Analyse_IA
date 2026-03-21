"""merge_heads

Revision ID: 10b8c05ee221
Revises: b2a6d9e4c1f7, d3f8a1c2e9b5
Create Date: 2026-03-21 19:21:08.606490

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10b8c05ee221'
down_revision: Union[str, Sequence[str], None] = ('b2a6d9e4c1f7', 'd3f8a1c2e9b5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
