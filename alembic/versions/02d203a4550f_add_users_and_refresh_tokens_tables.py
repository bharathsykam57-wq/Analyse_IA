"""Add users and refresh_tokens tables

Revision ID: 02d203a4550f
Revises: 
Create Date: 2026-03-12 12:27:32.526585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '02d203a4550f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.Column('preferred_language', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table('refresh_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('token', sa.Text(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_token'), 'refresh_tokens', ['token'], unique=True)

    # Drop legacy documents table only if it exists (safe for fresh databases)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'documents' in inspector.get_table_names():
        # Drop the vector index first if it exists
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('documents')]
        if 'documents_embedding_idx' in existing_indexes:
            op.drop_index(
                'documents_embedding_idx',
                table_name='documents',
                postgresql_ops={'embedding': 'vector_cosine_ops'},
                postgresql_using='hnsw'
            )
        op.drop_table('documents')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('documents',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('source', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('page', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('chunk_index', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('content', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('embedding', sa.NullType(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('documents_pkey')),
    sa.UniqueConstraint('source', 'page', 'chunk_index', name=op.f('documents_source_page_chunk_unique'), postgresql_include=[], postgresql_nulls_not_distinct=False)
    )
    op.create_index(op.f('documents_embedding_idx'), 'documents', ['embedding'], unique=False, postgresql_ops={'embedding': 'vector_cosine_ops'}, postgresql_using='hnsw')
    op.drop_index(op.f('ix_refresh_tokens_token'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')